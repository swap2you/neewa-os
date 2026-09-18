"""Persistent mission supervisor for unattended NEEWA recovery.

Wraps existing parent jobs. Does not reopen historical terminals, invent
Council providers, or spend unauthorized credits. Cursor remains the
implementation executor; this module owns persistence, recovery bounds,
and the final report.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "11_CONFIG"
PROVIDERS = CONFIG / "providers.json"
MODELS = CONFIG / "models.json"
BUDGETS = CONFIG / "budgets.json"
RUNTIME = CONFIG / "runtime.json"

MISSION_STATES = (
    "CREATED",
    "PREFLIGHT",
    "PLANNING",
    "EXECUTING",
    "VALIDATING",
    "RECOVERING",
    "WAITING",
    "OWNER_REVIEW",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
)
ALLOWED_TRANSITIONS = {
    "CREATED": {"PREFLIGHT", "BLOCKED", "CANCELLED"},
    "PREFLIGHT": {"PLANNING", "BLOCKED", "CANCELLED"},
    "PLANNING": {"EXECUTING", "WAITING", "BLOCKED", "CANCELLED"},
    "EXECUTING": {"VALIDATING", "RECOVERING", "WAITING", "BLOCKED", "FAILED", "CANCELLED"},
    "VALIDATING": {"OWNER_REVIEW", "RECOVERING", "WAITING", "BLOCKED", "FAILED", "CANCELLED"},
    "RECOVERING": {"PLANNING", "EXECUTING", "VALIDATING", "OWNER_REVIEW", "WAITING", "BLOCKED", "FAILED", "CANCELLED"},
    "WAITING": {"PLANNING", "EXECUTING", "RECOVERING", "BLOCKED", "CANCELLED", "FAILED"},
    "OWNER_REVIEW": set(),
    "BLOCKED": set(),
    "FAILED": set(),
    "CANCELLED": set(),
}
TERMINAL = {"OWNER_REVIEW", "BLOCKED", "FAILED", "CANCELLED"}
JOB_SUCCESS = {"OWNER_REVIEW", "DONE", "RELEASE_CANDIDATE"}
JOB_FAILED = {"FAILED", "CANCELLED"}
JOB_BLOCKED = {"BLOCKED"}
JOB_WAITING = {"WAITING"}


def job_meets_mission_success(job: dict | None) -> bool:
    """Mission success requires a success-state job with real independent_validation PASS.

    IMPLEMENTER_CLAIMED is never enough. Does not rewrite historical job records.
    """
    if not job or job.get("state") not in JOB_SUCCESS:
        return False
    return (job.get("validation") or {}).get("independent_rerun") == "PASS"
JOB_TERMINAL = {"DONE", "BLOCKED", "FAILED", "CANCELLED"}
RECOVERABLE = {
    "CHILD_TIMEOUT",
    "VALIDATION",
    "CLI_EXIT",
    "INDEPENDENT_TEST_FAIL",
    "CONFIG_DEFECT",
    "MISSING_IMPLEMENTATION_ARTIFACTS",
    "STALE_CHILD",
    "WORKER_ERROR",
}
NON_RECOVERABLE = {
    "POLICY",
    "DENIED_REPO",
    "UNAPPROVED_PATH",
    "BLOCKED_INTENT",
    "UNAUTHORIZED_REPO",
    "PATH_TRAVERSAL",
    "PATH_ESCAPE",
    "A2_GATE",
    "A3_GATE",
}
WORKER_UNAVAILABLE = {"WORKER_UNAVAILABLE", "NO_CODING_WORKER", "MISSING_WORKER"}
BUDGET_STOP = {"BUDGET_EXHAUSTED", "COST_UNKNOWN"}
PREFERRED_ADVISORS = (
    {
        "role": "gpt-5.6-sol",
        "match_ids": ("neewa-premium", "openai-api-sol"),
        "match_models": ("openai/gpt-5.6-sol", "gpt-5.6-sol"),
    },
    {
        "role": "claude-opus",
        "match_ids": ("claude-opus", "anthropic-opus"),
        "match_models": ("claude-opus", "claude-opus-4", "claude-4-opus", "claude-3-opus"),
    },
)
MAX_REPAIR_CYCLES = 3
DEFAULT_KIND = "sdlc"
HEARTBEAT_STALE_SEC = 120
WORKER_PENDING_STALE_SEC = 900
STATUS_DIR = Path(os.environ.get("NEEWA_STATUS_DIR", "/opt/neewa/status"))
HOST_SNAPSHOT = STATUS_DIR / "autonomy.json"


class DuplicateMission(Exception):
    def __init__(self, existing: dict):
        self.existing = existing
        super().__init__(f"active mission already exists: {existing.get('mission_id')}")


class HostPathUnmounted(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, indent=2) + "\n"
    tmp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(body, encoding="utf-8")
    os.replace(tmp, path)


def _auto_mod():
    return SourceFileLoader("neewa_autonomy_mission", str(ROOT / "12_SCRIPTS" / "neewa_autonomy.py")).load_module()


def autonomy_root(explicit: Path | None, auto=None) -> Path:
    inbox_mod = SourceFileLoader(
        "windows_job_inbox_mission", str(ROOT / "12_SCRIPTS" / "windows_job_inbox.py")
    ).load_module()
    if explicit:
        path = explicit
        if inbox_mod.is_unmounted_host_inbox(path):
            raise HostPathUnmounted(
                "HOST_PATH_UNMOUNTED: Conversation must use /workspace/windows-jobs/autonomy"
            )
        path.mkdir(parents=True, exist_ok=True)
        (path / "work").mkdir(exist_ok=True)
        return path
    auto = auto or _auto_mod()
    return auto.autonomy_root(None)


def new_mission_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"MISSION-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def mission_path(mission_id: str, root: Path) -> Path:
    return root / f"{mission_id}.json"


def mission_workdir(mission: dict, root: Path) -> Path:
    path = root / "work" / mission["mission_id"]
    path.mkdir(parents=True, exist_ok=True)
    return path


def max_repair_cycles() -> int:
    if RUNTIME.is_file():
        configured = load_json(RUNTIME).get("max_mission_repair_cycles")
        if configured is not None:
            return int(configured)
    return MAX_REPAIR_CYCLES


def load_mission(mission_id: str, root: Path) -> dict | None:
    path = mission_path(mission_id, root)
    if not path.is_file():
        return None
    row = load_json(path)
    row["_path"] = str(path)
    return row


def list_missions(root: Path) -> list[dict]:
    rows = []
    for path in sorted(root.glob("MISSION-*.json")):
        # Windows glob is case-insensitive; ignore heartbeat/report sidecars.
        if not path.name.startswith("MISSION-") or not path.name.endswith(".json"):
            continue
        row = load_json(path)
        if not row.get("mission_id") or not row.get("state"):
            continue
        row["_path"] = str(path)
        rows.append(row)
    return rows


def save_mission(mission: dict, root: Path | None = None) -> Path:
    path = Path(mission.get("_path") or "")
    if not path.name:
        if root is None:
            raise ValueError("save_mission requires root or _path")
        path = mission_path(mission["mission_id"], root)
    payload = {k: v for k, v in mission.items() if k != "_path"}
    payload["updated_at"] = utc_now()
    payload["progress_at"] = payload["updated_at"]
    save_json(path, payload)
    mission.update(payload)
    mission["_path"] = str(path)
    return path


def objective_key(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def find_active_duplicate(root: Path, objective: str, *, exclude_id: str | None = None) -> dict | None:
    key = objective_key(objective)
    if not key:
        return None
    for mission in list_missions(root):
        if mission.get("state") in TERMINAL:
            continue
        if exclude_id and mission.get("mission_id") == exclude_id:
            continue
        if objective_key(mission.get("owner_objective")) == key:
            return mission
    return None


def _parse_utc(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _age_sec(stamp: str | None, now: datetime | None = None) -> int | None:
    parsed = _parse_utc(stamp)
    if not parsed:
        return None
    now = now or datetime.now(timezone.utc)
    return max(0, int((now - parsed).total_seconds()))


def _read_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def _host_systemd_state(unit: str = "neewa-autonomy-runner.service") -> str | None:
    if shutil.which("systemctl") is None:
        return None
    try:
        completed = subprocess.run(
            ["systemctl", "--user", "is-active", unit],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        return (completed.stdout or completed.stderr or "unknown").strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return None


def _read_git_head(root: Path = ROOT) -> tuple[str | None, str | None]:
    git_dir = root / ".git"
    head = git_dir / "HEAD"
    if not head.is_file():
        return None, None
    try:
        text = head.read_text(encoding="utf-8").strip()
    except OSError:
        return None, None
    if text.startswith("ref:"):
        ref_name = text.split(" ", 1)[1].strip()
        ref = git_dir / ref_name
        branch = ref_name.rsplit("/", 1)[-1]
        if ref.is_file():
            try:
                return ref.read_text(encoding="utf-8").strip(), branch
            except OSError:
                return None, branch
        return None, branch
    return text, None


def _deployed_versions() -> dict:
    host = _read_json(STATUS_DIR / "latest.json") or {}
    repo = (host.get("repository") or {}) if host else {}
    sha = None
    source = None
    branch = repo.get("branch")
    try:
        sha = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
            text=True,
            timeout=5,
        ).strip()
        source = "git"
    except (OSError, subprocess.SubprocessError):
        file_sha, file_branch = _read_git_head(ROOT)
        if file_sha:
            sha = file_sha
            source = "git-files"
            branch = file_branch or branch
        else:
            sha = repo.get("head") or "UNKNOWN"
            source = "host-snapshot" if repo.get("head") else "unavailable"
    return {
        "repo": str(ROOT),
        "sha": sha,
        "branch": branch,
        "source": source,
        "host_snapshot_at": host.get("generated_at"),
        "host_snapshot_sha": repo.get("head"),
    }


def _provider_credits() -> dict:
    return {
        "remaining": "UNKNOWN",
        "source": "none",
        "reason": (
            "No configured provider exposes an authoritative remaining-credit "
            "or hard quota API. Nous subscription quota is unknown. "
            "openai-api is credential_pending. Do not invent a balance."
        ),
        "authoritative_balance": False,
        "authoritative_hard_limit": False,
    }


def _worker_status(inbox_root: Path) -> dict:
    if not inbox_root.is_dir():
        return {
            "accessible": False,
            "status": "unavailable",
            "reason": "inbox root is not a directory",
            "last_receipt_at": None,
            "last_receipt_id": None,
            "last_receipt_age_sec": None,
            "pending_inbox": 0,
            "pending_processing": 0,
        }
    latest = None
    latest_mtime = -1.0
    for folder in ("inbox", "processing", "done", "failed", "records"):
        directory = inbox_root / folder
        if not directory.is_dir():
            continue
        for path in directory.glob("*.json"):
            try:
                mtime = path.stat().st_mtime
            except OSError:
                continue
            if mtime > latest_mtime:
                latest_mtime = mtime
                latest = path
    pending_inbox = len(list((inbox_root / "inbox").glob("*.json"))) if (inbox_root / "inbox").is_dir() else 0
    pending_processing = (
        len(list((inbox_root / "processing").glob("*.json"))) if (inbox_root / "processing").is_dir() else 0
    )
    last_at = None
    last_id = None
    age = None
    if latest is not None:
        last_id = latest.stem
        last_at = datetime.fromtimestamp(latest_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        age = _age_sec(last_at)
    if pending_inbox or pending_processing:
        status = "stale_pending" if (age is None or age > WORKER_PENDING_STALE_SEC) else "active"
    elif latest is None:
        status = "unknown"
    else:
        status = "idle"
    return {
        "accessible": True,
        "status": status,
        "inbox": str(inbox_root),
        "last_receipt_at": last_at,
        "last_receipt_id": last_id,
        "last_receipt_age_sec": age,
        "pending_inbox": pending_inbox,
        "pending_processing": pending_processing,
    }


def _budget_status(*, auto=None) -> dict:
    auto = auto or _auto_mod()
    budgets = load_json(BUDGETS) if BUDGETS.is_file() else {}
    defaults = budgets.get("job_defaults") or {}
    ceiling = defaults.get("max_cost")
    estimate = (budgets.get("conservative_estimates_usd") or {}).get("cursor_call")
    probe = {"budget": {"ceiling": ceiling, "consumed_usd": 0.0, "reserved_usd": 0.0, "invocations": []}}
    decision = auto.budget_decision(probe, "cursor-agent-cli")
    credits = _provider_credits()
    hard_limit = ceiling is not None and estimate is not None
    return {
        "mission_ceiling_usd": ceiling,
        "conservative_cursor_estimate_usd": estimate,
        "remaining_ceiling_usd": decision.get("remaining"),
        "enforcement": "NEEWA_CEILING_CONSERVATIVE" if hard_limit else "NONE",
        "provider_credits_remaining": credits["remaining"],
        "provider_credits": credits,
        "block_when_cost_unknown": bool(budgets.get("block_when_cost_unknown")),
        "decision_reason": decision.get("reason"),
        "allows_next_cursor_call": bool(decision.get("allows")) and hard_limit,
    }


def mission_preflight(
    *,
    root: Path | None = None,
    inbox_root: Path | None = None,
    auto=None,
    now: datetime | None = None,
    systemd_state: str | None = None,
    publish: bool = False,
) -> dict:
    """Conversation-visible status. Uses bind-mount evidence, not systemctl inside Docker."""
    inbox_mod = SourceFileLoader(
        "windows_job_inbox_preflight", str(ROOT / "12_SCRIPTS" / "windows_job_inbox.py")
    ).load_module()
    mapping = inbox_mod.path_mapping()
    blockers = []
    warnings = []
    now = now or datetime.now(timezone.utc)
    try:
        jobs_root = autonomy_root(root, auto=auto)
        storage = {
            "accessible": True,
            "path": str(jobs_root),
            "canonical": True,
        }
    except HostPathUnmounted as exc:
        jobs_root = None
        storage = {"accessible": False, "path": str(root), "canonical": False, "reason": str(exc)}
        blockers.append("HOST_PATH_UNMOUNTED")
    except OSError as exc:
        jobs_root = None
        storage = {"accessible": False, "path": str(root) if root else None, "reason": str(exc)}
        blockers.append("AUTONOMY_STORAGE_INACCESSIBLE")

    explicit_inbox = inbox_root
    if explicit_inbox is None:
        inbox_root = Path(mapping["canonical_inbox"]) if not root else (Path(root).parent if root else Path(mapping["canonical_inbox"]))
        if jobs_root is not None:
            inbox_root = jobs_root.parent
    else:
        inbox_root = explicit_inbox
    worker = _worker_status(inbox_root)
    if not worker.get("accessible"):
        blockers.append("WINDOWS_WORKER_INBOX_UNAVAILABLE")
    elif worker.get("status") == "stale_pending":
        warnings.append("WINDOWS_WORKER_STALE_PENDING")

    heartbeat = _read_json(jobs_root / "runner-heartbeat.json") if jobs_root else None
    heartbeat_at = (heartbeat or {}).get("at")
    heartbeat_age = _age_sec(heartbeat_at, now)
    host_snapshot = _read_json(HOST_SNAPSHOT)
    snapshot_age = _age_sec((host_snapshot or {}).get("generated_at"), now)
    if systemd_state is None:
        systemd_state = _host_systemd_state()
    if systemd_state is None and host_snapshot:
        systemd_state = (host_snapshot.get("runner") or {}).get("systemd")
    runner_fresh = heartbeat_age is not None and heartbeat_age <= HEARTBEAT_STALE_SEC
    if heartbeat is None:
        blockers.append("RUNNER_HEARTBEAT_MISSING")
        runner_state = "missing-heartbeat"
    elif not runner_fresh:
        blockers.append("RUNNER_HEARTBEAT_STALE")
        runner_state = "stale-heartbeat"
    elif systemd_state == "active" or systemd_state is None:
        runner_state = "active"
    else:
        runner_state = systemd_state
        warnings.append(f"SYSTEMD_{systemd_state.upper()}")

    missions = list_missions(jobs_root) if jobs_root else []
    active_missions = [
        {
            "mission_id": m["mission_id"],
            "state": m.get("state"),
            "active_job_id": m.get("active_job_id"),
            "kind": m.get("kind"),
        }
        for m in missions
        if m.get("state") not in TERMINAL
    ]
    active_jobs = []
    if jobs_root and auto:
        for job in auto.list_parent_jobs(jobs_root):
            if job.get("state") not in {"DONE", "BLOCKED", "FAILED", "CANCELLED", "OWNER_REVIEW"}:
                active_jobs.append({"job_id": job["job_id"], "state": job.get("state"), "mission_id": job.get("mission_id")})
    elif jobs_root:
        try:
            auto_mod = _auto_mod()
            for job in auto_mod.list_parent_jobs(jobs_root):
                if job.get("state") not in {"DONE", "BLOCKED", "FAILED", "CANCELLED", "OWNER_REVIEW"}:
                    active_jobs.append(
                        {"job_id": job["job_id"], "state": job.get("state"), "mission_id": job.get("mission_id")}
                    )
        except Exception:
            pass

    budget = _budget_status(auto=auto)
    if not budget.get("allows_next_cursor_call"):
        blockers.append(budget.get("decision_reason") or "BUDGET_NOT_ENFORCEABLE")
    if not budget["provider_credits"].get("authoritative_balance"):
        warnings.append("PROVIDER_CREDITS_UNKNOWN")

    versions = _deployed_versions()
    submission_safe = not blockers
    report = {
        "schema_version": 1,
        "generated_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "submission_safe": submission_safe,
        "blockers": blockers,
        "warnings": warnings,
        "runner": {
            "state": runner_state,
            "systemd": systemd_state or "unavailable-in-sandbox",
            "heartbeat_at": heartbeat_at,
            "heartbeat_age_sec": heartbeat_age,
            "heartbeat_stale": bool(heartbeat is None or not runner_fresh),
            "pid": (heartbeat or {}).get("pid"),
            "evidence": str(jobs_root / "runner-heartbeat.json") if jobs_root else None,
        },
        "autonomy_storage": storage,
        "path_mapping": mapping,
        "windows_worker": worker,
        "active_missions": active_missions,
        "active_jobs": active_jobs,
        "versions": versions,
        "budget": budget,
        "host_snapshot": {
            "path": str(HOST_SNAPSHOT),
            "present": host_snapshot is not None,
            "generated_at": (host_snapshot or {}).get("generated_at"),
            "age_sec": snapshot_age,
        },
        "note": (
            "Use /workspace/windows-jobs from Conversation. Do not use the unmounted "
            "host path and do not require systemctl inside the sandbox."
        ),
    }
    if publish and jobs_root:
        publish_status_snapshot(report, jobs_root=jobs_root)
    return report


def publish_status_snapshot(
    report: dict | None = None,
    *,
    root: Path | None = None,
    jobs_root: Path | None = None,
    inbox_root: Path | None = None,
    auto=None,
    **kwargs,
) -> dict:
    jobs_root = jobs_root or root
    report = report or mission_preflight(
        root=jobs_root, inbox_root=inbox_root, auto=auto, publish=False, **kwargs
    )
    if jobs_root is None:
        try:
            jobs_root = autonomy_root(None, auto=auto)
        except (HostPathUnmounted, OSError):
            jobs_root = None
    if jobs_root:
        save_json(jobs_root / "conversation-status.json", report)
    if STATUS_DIR.is_dir() and os.access(STATUS_DIR, os.W_OK):
        try:
            save_json(HOST_SNAPSHOT, report)
            os.chmod(HOST_SNAPSHOT, 0o644)
        except OSError:
            pass
    return report


def transition(mission: dict, state: str, note: str = "", root: Path | None = None) -> dict:
    current = mission.get("state")
    allowed = ALLOWED_TRANSITIONS.get(current) or set()
    if state != current and state not in allowed:
        raise ValueError(f"illegal mission transition {current} -> {state}")
    if state != current:
        mission["state"] = state
        mission.setdefault("history", []).append({"state": state, "at": utc_now(), "note": note})
        mission["stage"] = state
    elif note:
        mission.setdefault("history", []).append({"state": state, "at": utc_now(), "note": note})
    if state in TERMINAL:
        mission["terminal_result"] = state
        if note and not mission.get("failure_reason") and state != "OWNER_REVIEW":
            mission["failure_reason"] = note
    root_path = root or (Path(mission["_path"]).parent if mission.get("_path") else None)
    if root_path:
        save_mission(mission, root_path)
    return mission


def create_mission(
    objective: str,
    *,
    workspace: str | None = None,
    project_id: str | None = None,
    root: Path | None = None,
    budget_ceiling: float | None = None,
    origin: str = "conversation",
    kind: str = DEFAULT_KIND,
    auto=None,
) -> dict:
    auto = auto or _auto_mod()
    jobs_root = autonomy_root(root, auto=auto)
    duplicate = find_active_duplicate(jobs_root, objective)
    if duplicate:
        raise DuplicateMission(duplicate)
    if budget_ceiling is None:
        budget_ceiling = float(load_json(BUDGETS)["job_defaults"]["max_cost"])
    mission = {
        "schema_version": 1,
        "mission_id": new_mission_id(),
        "coordinator": "neewa-mission-supervisor",
        "origin": origin,
        "kind": kind or DEFAULT_KIND,
        "owner_objective": objective,
        "workspace": workspace,
        "project_id": project_id,
        "state": "CREATED",
        "stage": "CREATED",
        "active_job_id": None,
        "active_attempt_id": 0,
        "job_ids": [],
        "retry_count": 0,
        "repair_cycles": 0,
        "max_repair_cycles": max_repair_cycles(),
        "budget": {
            "ceiling": float(budget_ceiling),
            "consumed_usd": 0.0,
            "reserved_usd": 0.0,
            "estimated_usd": 0.0,
            "actual_usd": None,
            "actual_status": "unavailable-until-measured",
        },
        "consultation_history": [],
        "failure_history": [],
        "last_failure_signature": None,
        "last_evidence_hash": None,
        "evidence_locations": [],
        "terminal_result": None,
        "failure_reason": None,
        "report_path": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "progress_at": utc_now(),
        "history": [{"state": "CREATED", "at": utc_now(), "note": "persisted before dispatch"}],
    }
    save_mission(mission, jobs_root)
    return mission


def public_mission(mission: dict) -> dict:
    return {k: v for k, v in mission.items() if k != "_path"}


def evidence_hash(parts: list[str]) -> str:
    blob = "\n".join(str(p or "") for p in parts)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


def classify_failure(job: dict | None, *, worker_available: bool = True) -> dict:
    if not worker_available:
        return {
            "class": "WORKER_UNAVAILABLE",
            "recoverable": False,
            "waiting": True,
            "reason": "coding worker unavailable",
        }
    if not job:
        return {"class": "NO_JOB", "recoverable": False, "waiting": False, "reason": "no active job"}
    state = job.get("state")
    reason = str(job.get("failure_reason") or "")
    cls = str(job.get("failure_class") or "")
    if state in JOB_WAITING or cls in WORKER_UNAVAILABLE:
        return {
            "class": "WORKER_UNAVAILABLE",
            "recoverable": False,
            "waiting": True,
            "reason": reason or "worker unavailable",
        }
    if cls in BUDGET_STOP or reason in BUDGET_STOP or "BUDGET" in reason or reason == "COST_UNKNOWN":
        return {
            "class": reason if reason in BUDGET_STOP else (cls or "BUDGET_EXHAUSTED"),
            "recoverable": False,
            "waiting": False,
            "budget_stop": True,
            "reason": reason or cls or "budget stop",
        }
    if cls in NON_RECOVERABLE or any(token in reason for token in ("POLICY", "DENIED_REPO", "A2/A3", "A2 owner", "A3")):
        return {
            "class": cls or "POLICY",
            "recoverable": False,
            "waiting": False,
            "reason": reason or cls,
        }
    if state in JOB_BLOCKED:
        if "BUDGET" in reason or reason == "COST_UNKNOWN":
            return {"class": reason or "BUDGET_EXHAUSTED", "recoverable": False, "budget_stop": True, "reason": reason}
        if "MISSING_WORKSPACE" in reason or "NO_EXECUTABLE" in reason:
            return {"class": "CONFIG_DEFECT", "recoverable": False, "reason": reason}
        return {"class": cls or "BLOCKED", "recoverable": False, "reason": reason or "blocked"}
    if cls in RECOVERABLE or state in JOB_FAILED:
        return {
            "class": cls or "JOB_FAILED",
            "recoverable": cls in RECOVERABLE or not cls,
            "waiting": False,
            "reason": reason or cls or state,
        }
    return {"class": cls or state or "UNKNOWN", "recoverable": False, "reason": reason or state}


def discover_advisors(*, models: list | None = None, providers: list | None = None) -> list[dict]:
    model_rows = models if models is not None else (load_json(MODELS).get("models") if MODELS.is_file() else [])
    provider_rows = providers if providers is not None else (
        load_json(PROVIDERS).get("providers") if PROVIDERS.is_file() else []
    )
    providers_by_id = {p.get("id"): p for p in provider_rows}
    discovered = []
    for preferred in PREFERRED_ADVISORS:
        match = None
        for row in model_rows:
            model_name = str(row.get("model") or "")
            if row.get("id") in preferred["match_ids"] or model_name in preferred["match_models"]:
                match = row
                break
        if not match:
            discovered.append(
                {
                    "role": preferred["role"],
                    "id": None,
                    "model": None,
                    "provider": None,
                    "availability": "not_configured",
                    "status": "UNAVAILABLE",
                    "reason": f"{preferred['role']} is not listed in 11_CONFIG/models.json",
                    "invoked": False,
                }
            )
            continue
        provider = providers_by_id.get(match.get("provider")) or {}
        availability = str(match.get("availability") or provider.get("availability") or "unknown")
        cost_class = str(match.get("cost_class") or provider.get("cost_class") or "unknown")
        verified = availability in {"verified", "configured"} and str(provider.get("status") or "") in {
            "configured",
            "configured-and-tested",
            "",
        }
        pending = availability in {
            "credential-pending",
            "credential_pending",
            "not-authenticated",
            "pending_owner_oauth",
            "pending_secure_credential",
        } or str(provider.get("status") or "") in {
            "not_configured",
            "not_installed",
            "not_authenticated",
            "credential_pending",
        }
        paid_unauthorized = cost_class in {"paid"} and pending
        if pending or not verified:
            status = "UNAVAILABLE"
            reason = (
                f"{match.get('id')} availability={availability} "
                f"provider={match.get('provider')} status={provider.get('status') or 'missing'}"
            )
        elif paid_unauthorized:
            status = "UNAVAILABLE"
            reason = "paid provider is not authorized"
        else:
            status = "AVAILABLE"
            reason = f"configured via {match.get('provider')} ({cost_class})"
        discovered.append(
            {
                "role": preferred["role"],
                "id": match.get("id"),
                "model": match.get("model"),
                "provider": match.get("provider"),
                "availability": availability,
                "cost_class": cost_class,
                "status": status,
                "reason": reason,
                "invoked": False,
                "authorization": "existing-subscription" if cost_class in {"subscription", "existing-subscription", "free-local"} else cost_class,
            }
        )
    return discovered


def consult_advisors(
    evidence: dict,
    *,
    invoke: bool = False,
    invoke_fn: Callable[..., dict] | None = None,
    budget_ok: bool = True,
    models: list | None = None,
    providers: list | None = None,
) -> dict:
    """One-pass independent advisory consultation. Never invents a reply."""
    advisors = discover_advisors(models=models, providers=providers)
    responses = []
    disagreement = []
    for advisor in advisors:
        receipt = dict(advisor)
        receipt["at"] = utc_now()
        if advisor["status"] != "AVAILABLE":
            receipt["response"] = None
            responses.append(receipt)
            continue
        if not budget_ok:
            receipt["status"] = "UNAVAILABLE"
            receipt["reason"] = "BUDGET_EXHAUSTED"
            receipt["response"] = None
            responses.append(receipt)
            continue
        if not invoke:
            receipt["status"] = "CONFIGURED_NOT_INVOKED"
            receipt["reason"] = (
                advisor["reason"] + "; consult invoke disabled (no silent spend)"
            )
            receipt["response"] = None
            responses.append(receipt)
            continue
        if invoke_fn is None:
            receipt["status"] = "UNAVAILABLE"
            receipt["reason"] = "no authorized invoke function; refusing to fake a consultation"
            receipt["response"] = None
            responses.append(receipt)
            continue
        try:
            result = invoke_fn(advisor, evidence)
        except Exception as exc:  # noqa: BLE001 — receipt must record the failure
            result = {"status": "UNAVAILABLE", "reason": str(exc)[:300], "response": None}
        receipt["invoked"] = True
        receipt["status"] = result.get("status") or "UNAVAILABLE"
        receipt["reason"] = result.get("reason") or receipt["reason"]
        receipt["response"] = result.get("response")
        responses.append(receipt)
    recommendations = [r.get("response") for r in responses if r.get("response")]
    available = [r for r in responses if r.get("status") in {"AVAILABLE", "CONFIGURED_NOT_INVOKED", "CONSULTED"}]
    consulted = [r for r in responses if r.get("invoked") and r.get("response")]
    if len({json.dumps(item, sort_keys=True) for item in recommendations}) > 1:
        disagreement.append("advisor responses differ; NEEWA retains the technical plan")
    return {
        "at": utc_now(),
        "evidence_hash": evidence.get("hash"),
        "advisors": responses,
        "recommendations": recommendations,
        "disagreement": disagreement,
        "available_count": len(available),
        "consulted_count": len(consulted),
        "unavailable": [r for r in responses if r.get("status") == "UNAVAILABLE"],
        "neewa_owns_plan": True,
        "fake_consultation": False,
    }


def write_report(mission: dict, root: Path) -> dict:
    work = mission_workdir(mission, root)
    report = {
        "mission_id": mission["mission_id"],
        "owner_objective": mission.get("owner_objective"),
        "state": mission.get("state"),
        "terminal_result": mission.get("terminal_result") or mission.get("state"),
        "active_job_id": mission.get("active_job_id"),
        "job_ids": list(mission.get("job_ids") or []),
        "repair_cycles": mission.get("repair_cycles"),
        "retry_count": mission.get("retry_count"),
        "budget": mission.get("budget"),
        "consultation_history": mission.get("consultation_history") or [],
        "failure_history": mission.get("failure_history") or [],
        "evidence_locations": mission.get("evidence_locations") or [],
        "failure_reason": mission.get("failure_reason"),
        "generated_at": utc_now(),
        "history": mission.get("history") or [],
    }
    json_path = work / "final-report.json"
    md_path = work / "final-report.md"
    save_json(json_path, report)
    lines = [
        f"# Mission {mission['mission_id']}",
        "",
        f"- Objective: {mission.get('owner_objective')}",
        f"- Result: {report['terminal_result']}",
        f"- Jobs: {', '.join(report['job_ids']) or 'none'}",
        f"- Repair cycles: {report['repair_cycles']}/{mission.get('max_repair_cycles')}",
        f"- Budget ceiling: {((mission.get('budget') or {}).get('ceiling'))}",
        f"- Estimated consumed: {((mission.get('budget') or {}).get('estimated_usd'))}",
        f"- Actual billed: {((mission.get('budget') or {}).get('actual_usd'))}",
        f"- Failure: {mission.get('failure_reason') or 'none'}",
        "",
        "## Consultations",
    ]
    if not report["consultation_history"]:
        lines.append("None.")
    for row in report["consultation_history"]:
        lines.append(f"- {row.get('at')}: consulted={row.get('consulted_count')} unavailable={len(row.get('unavailable') or [])}")
        for advisor in row.get("advisors") or []:
            lines.append(
                f"  - {advisor.get('role')} id={advisor.get('id')} status={advisor.get('status')} ({advisor.get('reason')})"
            )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mission["report_path"] = str(md_path)
    for loc in (str(json_path), str(md_path)):
        if loc not in mission["evidence_locations"]:
            mission["evidence_locations"].append(loc)
    save_mission(mission, root)
    return report


def sync_budget_from_job(mission: dict, job: dict | None) -> None:
    if not job:
        return
    src = job.get("budget") or {}
    dst = mission.setdefault("budget", {})
    dst["consumed_usd"] = float(src.get("consumed_usd") or 0.0)
    dst["reserved_usd"] = float(src.get("reserved_usd") or 0.0)
    dst["estimated_usd"] = float(src.get("estimated_usd") or dst["consumed_usd"])
    dst["actual_usd"] = src.get("actual_usd")
    dst["actual_status"] = src.get("actual_status") or dst.get("actual_status")
    dst["consumed_basis"] = src.get("consumed_basis")


def _resume_owned_job(mission: dict, auto, root: Path) -> dict | None:
    job_id = mission.get("active_job_id")
    if not job_id:
        return None
    job = auto.resume_job(job_id, root)
    if not job:
        return None
    if job.get("mission_id") and job.get("mission_id") != mission["mission_id"]:
        return None
    if job_id not in (mission.get("job_ids") or []):
        # Never adopt a historical terminal job that this mission did not create.
        return None
    return job


def _attach_job(mission: dict, job: dict) -> None:
    job_id = job["job_id"]
    job["mission_id"] = mission["mission_id"]
    mission["active_job_id"] = job_id
    if job_id not in mission["job_ids"]:
        mission["job_ids"].append(job_id)
    mission["active_attempt_id"] = len(mission["job_ids"])


def _budget_probe(mission: dict, auto, next_worker: str = "cursor-agent-cli") -> dict:
    probe = {
        "budget": dict(mission.get("budget") or {}),
    }
    return auto.budget_decision(probe, next_worker)


def step_mission(
    mission: dict,
    *,
    root: Path,
    inbox_root: Path | None = None,
    auto=None,
    worker_registry: dict | None = None,
    consult_invoke: bool = False,
    invoke_fn: Callable[..., dict] | None = None,
    worker_available: bool | None = None,
    **advance_kwargs,
) -> dict:
    auto = auto or _auto_mod()
    if mission.get("state") in TERMINAL:
        return mission
    kind = mission.get("kind") or DEFAULT_KIND

    if mission["state"] == "CREATED":
        return transition(mission, "PREFLIGHT", "supervisor loaded persisted mission", root)

    if mission["state"] == "PREFLIGHT":
        gate = auto.authorize_execution(
            approval_level="A1",
            owner_decision=None,
            prompt=mission.get("owner_objective") or "",
            repo=mission.get("workspace") or "",
            write=kind == "sdlc",
        )
        if not gate.get("allowed"):
            mission["failure_reason"] = gate.get("reason") or "PREFLIGHT_DENIED"
            transition(mission, "BLOCKED", mission["failure_reason"], root)
            write_report(mission, root)
            return mission
        decision = _budget_probe(mission, auto)
        if not decision.get("allows"):
            mission["failure_reason"] = decision.get("reason") or "BUDGET_EXHAUSTED"
            transition(mission, "BLOCKED", mission["failure_reason"], root)
            write_report(mission, root)
            return mission
        return transition(mission, "PLANNING", "preflight passed", root)

    if mission["state"] == "PLANNING":
        if kind == "diagnostic":
            return transition(mission, "EXECUTING", "diagnostic has no child job", root)
        if mission.get("active_job_id"):
            job = _resume_owned_job(mission, auto, root)
            if job and job.get("state") not in JOB_TERMINAL | JOB_SUCCESS:
                return transition(mission, "EXECUTING", "resume existing child; no duplicate dispatch", root)
            if job and job_meets_mission_success(job):
                mission["active_job_id"] = job["job_id"]
                return transition(mission, "VALIDATING", "existing job already succeeded", root)
            if job and job.get("state") in JOB_SUCCESS:
                return transition(
                    mission,
                    "RECOVERING",
                    "existing job lacks independent_validation PASS",
                    root,
                )
            if job and job.get("state") in JOB_FAILED | JOB_BLOCKED:
                return transition(mission, "RECOVERING", "existing owned job ended; recover without reopen", root)
        for existing in auto.list_parent_jobs(root):
            if existing.get("mission_id") != mission["mission_id"]:
                continue
            if existing.get("job_id") in (mission.get("job_ids") or []) and existing.get("state") in JOB_TERMINAL | JOB_SUCCESS:
                continue
            if existing.get("state") in JOB_TERMINAL and existing.get("job_id") not in (mission.get("job_ids") or []):
                continue
            if existing.get("state") not in JOB_TERMINAL | JOB_SUCCESS:
                _attach_job(mission, existing)
                save_mission(mission, root)
                return transition(mission, "EXECUTING", "adopted persisted child; no duplicate dispatch", root)
        decision = _budget_probe(mission, auto)
        if not decision.get("allows"):
            mission["failure_reason"] = decision.get("reason") or "BUDGET_EXHAUSTED"
            return transition(mission, "BLOCKED", mission["failure_reason"], root)
        save_mission(mission, root)
        job = auto.create_parent_job(
            mission["owner_objective"] if mission.get("repair_cycles", 0) == 0 else (
                mission.get("repair_objective") or mission["owner_objective"]
            ),
            project_id=mission.get("project_id"),
            workspace=mission.get("workspace"),
            root=root,
            budget_ceiling=float((mission.get("budget") or {}).get("ceiling") or 0),
            origin="mission-supervisor",
            mission_id=mission["mission_id"],
        )
        _attach_job(mission, job)
        auto.save_job(job)
        save_mission(mission, root)
        return transition(mission, "EXECUTING", f"dispatched {job['job_id']}", root)

    if mission["state"] == "EXECUTING":
        if kind == "diagnostic":
            heartbeat = root / "runner-heartbeat.json"
            if heartbeat.is_file():
                loc = str(heartbeat)
                if loc not in mission["evidence_locations"]:
                    mission["evidence_locations"].append(loc)
            return transition(mission, "VALIDATING", "diagnostic execution observed runner heartbeat", root)
        job = _resume_owned_job(mission, auto, root)
        if not job:
            mission["failure_reason"] = "ACTIVE_JOB_MISSING"
            return transition(mission, "FAILED", mission["failure_reason"], root)
        if job.get("state") in JOB_TERMINAL | JOB_SUCCESS and job.get("state") != "WAITING":
            sync_budget_from_job(mission, job)
            if job_meets_mission_success(job):
                return transition(mission, "VALIDATING", f"job {job['job_id']} {job['state']}", root)
            if job.get("state") in JOB_SUCCESS:
                return transition(
                    mission,
                    "RECOVERING",
                    f"job {job['job_id']} reached {job['state']} without independent_validation PASS",
                    root,
                )
            return transition(mission, "RECOVERING", f"job {job['job_id']} {job['state']}", root)
        available = worker_available
        if available is None:
            choice = auto.select_coding_worker(worker_registry)
            available = bool(choice.get("available"))
        if not available and job.get("state") in {"CLASSIFIED", "COUNCIL", "PLANNED", "WAITING"}:
            return transition(mission, "WAITING", "coding worker unavailable", root)
        updated = auto.advance_job(
            job,
            root=root,
            inbox_root=inbox_root,
            worker_registry=worker_registry,
            **advance_kwargs,
        )
        sync_budget_from_job(mission, updated)
        save_mission(mission, root)
        if updated.get("state") in JOB_SUCCESS:
            if job_meets_mission_success(updated):
                return transition(mission, "VALIDATING", f"job reached {updated['state']}", root)
            return transition(
                mission,
                "RECOVERING",
                f"job reached {updated['state']} without independent_validation PASS",
                root,
            )
        if updated.get("state") in JOB_FAILED:
            return transition(mission, "RECOVERING", f"job {updated['state']}", root)
        if updated.get("state") in JOB_BLOCKED:
            classified = classify_failure(updated, worker_available=True)
            if classified.get("budget_stop"):
                mission["failure_reason"] = classified["reason"]
                return transition(mission, "BLOCKED", classified["reason"], root)
            if classified.get("waiting"):
                return transition(mission, "WAITING", classified["reason"], root)
            return transition(mission, "RECOVERING", classified["reason"], root)
        if updated.get("state") in JOB_WAITING:
            return transition(mission, "WAITING", updated.get("failure_reason") or "waiting", root)
        save_mission(mission, root)
        return mission

    if mission["state"] == "WAITING":
        available = worker_available
        if available is None:
            choice = auto.select_coding_worker(worker_registry)
            available = bool(choice.get("available"))
        if not available:
            save_mission(mission, root)
            return mission
        job = _resume_owned_job(mission, auto, root)
        if job and job.get("state") not in JOB_TERMINAL | JOB_SUCCESS:
            return transition(mission, "EXECUTING", "worker restored; resume without new dispatch", root)
        return transition(mission, "PLANNING", "worker restored", root)

    if mission["state"] == "VALIDATING":
        if kind == "diagnostic":
            transition(mission, "OWNER_REVIEW", "diagnostic report written", root)
            write_report(mission, root)
            return mission
        job = _resume_owned_job(mission, auto, root)
        if job:
            job = auto.reconcile_parent_job(
                job, inbox_root=inbox_root, orch_harvest=advance_kwargs.get("orch_harvest")
            )
            sync_budget_from_job(mission, job)
        if job and job_meets_mission_success(job):
            transition(mission, "OWNER_REVIEW", "validation reconciled", root)
            write_report(mission, root)
            return mission
        if job and job.get("state") in JOB_SUCCESS:
            return transition(
                mission,
                "RECOVERING",
                "OWNER_REVIEW without independent_validation PASS is not mission success",
                root,
            )
        return transition(mission, "RECOVERING", "validation did not hold", root)

    if mission["state"] == "RECOVERING":
        job = _resume_owned_job(mission, auto, root)
        if job:
            job = auto.reconcile_parent_job(
                job, inbox_root=inbox_root, orch_harvest=advance_kwargs.get("orch_harvest")
            )
            sync_budget_from_job(mission, job)
            if job_meets_mission_success(job):
                return transition(mission, "VALIDATING", "reconcile showed success; do not recover", root)
            if job.get("state") not in JOB_TERMINAL | JOB_SUCCESS | JOB_WAITING | JOB_BLOCKED:
                return transition(mission, "EXECUTING", "child still active; do not recover yet", root)
        available = worker_available
        if available is None:
            choice = auto.select_coding_worker(worker_registry)
            available = bool(choice.get("available"))
        classified = classify_failure(job, worker_available=bool(available))
        signature = f"{classified.get('class')}|{classified.get('reason')}"
        hash_parts = [
            signature,
            (job or {}).get("state"),
            (job or {}).get("active_child_id"),
            json.dumps((job or {}).get("validation") or {}, sort_keys=True)[:2000],
        ]
        hashed = evidence_hash(hash_parts)
        evidence = {
            "hash": hashed,
            "classification": classified,
            "job_id": (job or {}).get("job_id"),
            "job_state": (job or {}).get("state"),
            "failure_reason": (job or {}).get("failure_reason"),
            "mission_id": mission["mission_id"],
        }
        consult = consult_advisors(
            evidence,
            invoke=consult_invoke,
            invoke_fn=invoke_fn,
            budget_ok=bool(_budget_probe(mission, auto).get("allows")),
        )
        mission.setdefault("consultation_history", []).append(consult)
        mission.setdefault("failure_history", []).append(
            {"at": utc_now(), "signature": signature, "evidence_hash": hashed, "classification": classified}
        )
        if classified.get("waiting"):
            save_mission(mission, root)
            return transition(mission, "WAITING", classified["reason"], root)
        if classified.get("budget_stop"):
            mission["failure_reason"] = classified["reason"]
            transition(mission, "BLOCKED", classified["reason"], root)
            write_report(mission, root)
            return mission
        if not classified.get("recoverable"):
            mission["failure_reason"] = classified["reason"]
            transition(mission, "FAILED", classified["reason"], root)
            write_report(mission, root)
            return mission
        if (
            mission.get("last_failure_signature") == signature
            and mission.get("last_evidence_hash") == hashed
        ):
            mission["failure_reason"] = "IDENTICAL_FAILURE_NO_NEW_EVIDENCE"
            transition(mission, "FAILED", mission["failure_reason"], root)
            write_report(mission, root)
            return mission
        cycles = int(mission.get("repair_cycles") or 0)
        if cycles >= int(mission.get("max_repair_cycles") or MAX_REPAIR_CYCLES):
            mission["failure_reason"] = "MAX_REPAIR_CYCLES"
            transition(mission, "FAILED", mission["failure_reason"], root)
            write_report(mission, root)
            return mission
        mission["last_failure_signature"] = signature
        mission["last_evidence_hash"] = hashed
        mission["repair_cycles"] = cycles + 1
        mission["retry_count"] = int(mission.get("retry_count") or 0) + 1
        mission["active_job_id"] = None
        mission["repair_objective"] = (
            f"{mission.get('owner_objective')}\n\n"
            f"REPAIR CYCLE {mission['repair_cycles']}/{mission.get('max_repair_cycles')}. "
            f"Previous job {(job or {}).get('job_id')} failed: {classified.get('reason')}. "
            "Do not reopen the failed job. Do not weaken tests, security policy, or acceptance. "
            "Implement a genuine repair and leave independent validation intact."
        )
        save_mission(mission, root)
        return transition(mission, "PLANNING", f"repair cycle {mission['repair_cycles']}", root)

    save_mission(mission, root)
    return mission


def supervisor_once(
    *,
    root: Path | None = None,
    inbox_root: Path | None = None,
    auto=None,
    **kwargs,
) -> list[dict]:
    auto = auto or _auto_mod()
    jobs_root = autonomy_root(root, auto=auto)
    heartbeat = {
        "at": utc_now(),
        "pid": os.getpid(),
        "supervisor": "neewa_mission",
    }
    save_json(jobs_root / "mission-heartbeat.json", heartbeat)
    results = []
    for mission in list_missions(jobs_root):
        if mission.get("state") in TERMINAL:
            results.append({"mission_id": mission["mission_id"], "state": mission["state"], "skipped": "terminal"})
            continue
        updated = step_mission(
            mission,
            root=jobs_root,
            inbox_root=inbox_root,
            auto=auto,
            **kwargs,
        )
        results.append(
            {
                "mission_id": updated["mission_id"],
                "state": updated["state"],
                "active_job_id": updated.get("active_job_id"),
            }
        )
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA persistent mission supervisor")
    sub = parser.add_subparsers(dest="command", required=True)
    subp = sub.add_parser("submit")
    subp.add_argument("--objective", required=True)
    subp.add_argument("--workspace")
    subp.add_argument("--project-id")
    subp.add_argument("--root")
    subp.add_argument("--budget-ceiling", type=float)
    subp.add_argument("--origin", default="conversation")
    subp.add_argument("--kind", default=DEFAULT_KIND, choices=("sdlc", "research", "diagnostic"))
    getp = sub.add_parser("get")
    getp.add_argument("--mission-id", required=True)
    getp.add_argument("--root")
    listp = sub.add_parser("list")
    listp.add_argument("--root")
    stepp = sub.add_parser("step")
    stepp.add_argument("--mission-id", required=True)
    stepp.add_argument("--root")
    stepp.add_argument("--inbox-root")
    adv = sub.add_parser("advisors")
    prep = sub.add_parser("preflight")
    prep.add_argument("--root")
    prep.add_argument("--inbox-root")
    args = parser.parse_args()
    if args.command == "advisors":
        print(json.dumps(discover_advisors(), indent=2))
        return 0
    if args.command == "preflight":
        report = mission_preflight(
            root=Path(args.root) if args.root else None,
            inbox_root=Path(args.inbox_root) if args.inbox_root else None,
        )
        print(json.dumps(report, indent=2))
        return 0 if report.get("submission_safe") else 2
    root = Path(args.root) if getattr(args, "root", None) else None
    jobs_root = autonomy_root(root)
    if args.command == "submit":
        mission = create_mission(
            args.objective,
            workspace=args.workspace,
            project_id=getattr(args, "project_id", None),
            root=jobs_root,
            budget_ceiling=args.budget_ceiling,
            origin=args.origin,
            kind=args.kind,
        )
        print(json.dumps(public_mission(mission), indent=2))
        return 0
    if args.command == "list":
        rows = [
            {
                "mission_id": m["mission_id"],
                "state": m.get("state"),
                "active_job_id": m.get("active_job_id"),
                "objective": m.get("owner_objective"),
            }
            for m in list_missions(jobs_root)
        ]
        print(json.dumps(rows, indent=2))
        return 0
    mission = load_mission(args.mission_id, jobs_root)
    if not mission:
        raise SystemExit(f"unknown mission {args.mission_id}")
    if args.command == "get":
        print(json.dumps(public_mission(mission), indent=2))
        return 0
    inbox = Path(args.inbox_root) if args.inbox_root else None
    mission = step_mission(mission, root=jobs_root, inbox_root=inbox)
    print(json.dumps(public_mission(mission), indent=2))
    return 0 if mission["state"] not in {"FAILED", "BLOCKED"} else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
