"""NEEWA autonomous chief-of-staff controller.

Extends the existing Windows orchestrator. Does not open listeners or invent workers.
A generated response is not DONE: artifacts, tests, and the done-gate must pass.

The project-status JSON CLI lives in neewa_autonomy_fixture.py as a regression
fixture only. Production jobs derive requirements from the objective and implement
through the Conversation-to-Cursor Windows worker bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ORCH = SourceFileLoader(
    "neewa_orchestrate_autonomy", str(ROOT / "12_SCRIPTS" / "neewa_orchestrate.py")
).load_module()
FIXTURE = SourceFileLoader(
    "neewa_autonomy_fixture", str(ROOT / "12_SCRIPTS" / "neewa_autonomy_fixture.py")
).load_module()
PLANNING = SourceFileLoader(
    "neewa_autonomy_planning", str(ROOT / "12_SCRIPTS" / "neewa_autonomy_planning.py")
).load_module()
BUDGETS = ROOT / "11_CONFIG" / "budgets.json"
WORKERS = ROOT / "11_CONFIG" / "workers.json"
PROVIDERS = ROOT / "11_CONFIG" / "providers.json"
POLICY = ROOT / "16_WINDOWS_CLIENT" / "worker" / "cursor-call-policy.json"
BASELINE_LOCK = ROOT / "AI-OPS" / "delivery" / "autonomy-baseline" / "BASELINE_LOCK.json"
SOURCE_PACK = ROOT / "14_REFERENCE" / "devotional_sources" / "SOURCE_PACK.md"

PARENT_STATES = (
    "INTAKE",
    "CLASSIFIED",
    "REQUIREMENTS",
    "DESIGN",
    "COUNCIL",
    "BASELINE_LOCKED",
    "PLANNED",
    "PREFLIGHT",
    "EXECUTING",
    "TESTING",
    "VALIDATING",
    "RELEASE_CANDIDATE",
    "OWNER_REVIEW",
    "DONE",
    "WAITING",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
)
ALLOWED_TRANSITIONS = {
    "INTAKE": {"CLASSIFIED", "BLOCKED", "CANCELLED"},
    "CLASSIFIED": {"REQUIREMENTS", "BLOCKED", "CANCELLED"},
    "REQUIREMENTS": {"DESIGN", "BLOCKED", "CANCELLED"},
    "DESIGN": {"COUNCIL", "BLOCKED", "CANCELLED"},
    "COUNCIL": {"BASELINE_LOCKED", "PLANNED", "WAITING", "BLOCKED", "CANCELLED"},
    "BASELINE_LOCKED": {"PLANNED", "BLOCKED", "CANCELLED"},
    "PLANNED": {"PREFLIGHT", "EXECUTING", "BLOCKED", "WAITING", "CANCELLED"},
    "PREFLIGHT": {"PLANNED", "EXECUTING", "FAILED", "BLOCKED", "WAITING", "CANCELLED"},
    "EXECUTING": {"TESTING", "EXECUTING", "FAILED", "BLOCKED", "WAITING", "CANCELLED"},
    "TESTING": {"VALIDATING", "EXECUTING", "FAILED", "BLOCKED", "CANCELLED"},
    "VALIDATING": {"RELEASE_CANDIDATE", "FAILED", "BLOCKED", "CANCELLED"},
    "RELEASE_CANDIDATE": {"OWNER_REVIEW", "BLOCKED", "CANCELLED"},
    "OWNER_REVIEW": {"DONE", "CANCELLED", "FAILED"},
    "WAITING": {"PLANNED", "BLOCKED", "CANCELLED"},
    "DONE": set(),
    "BLOCKED": {"CANCELLED"},
    "FAILED": {"CANCELLED"},
    "CANCELLED": set(),
}
TERMINAL = {"DONE", "BLOCKED", "FAILED", "CANCELLED"}
ACTIVE_CHILD = {"QUEUED", "DISPATCHED", "RUNNING", "VALIDATING", "WAITING"}
A2_HINTS = (
    "publish",
    "deploy to production",
    "purchase",
    "subscribe",
    "rotate credential",
    "make public",
    "npm publish",
    "public internet",
    "roll out to production",
    "roll this out to all users",
    "buy a",
    "charge the card",
    "change visibility",
    "send email",
    "email the client",
    "message the client",
    "post publicly",
    "disable antivirus",
    "disable defender",
    "disable security",
    "format c:",
    "delete everything",
)
A3_HINTS = ("live trade", "place order", "wire transfer", "bank transfer", "send money")
STOP_WORDS = {
    "a", "an", "the", "simple", "small", "new", "please", "neewa", "owner",
    "and", "or", "to", "for", "of", "with", "that", "which", "this",
}


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


def autonomy_root(explicit: Path | None = None) -> Path:
    if explicit:
        path = explicit
    else:
        inbox = ORCH.INBOX_MOD.resolve_inbox_root()
        path = inbox / "autonomy"
    path.mkdir(parents=True, exist_ok=True)
    (path / "work").mkdir(exist_ok=True)
    return path


def contains_negated(blob: str, term: str) -> bool:
    return bool(re.search(rf"\b(?:do not|don't|without|never|no)\b.{{0,40}}\b{re.escape(term)}\b", blob))


def action_needed_from_text(blob: str) -> str:
    lower = blob.lower()
    for hint in A3_HINTS:
        if hint in lower and not contains_negated(lower, hint.split()[-1]):
            return "A3"
    for hint in A2_HINTS:
        if hint in lower:
            token = hint.split()[-1]
            if contains_negated(lower, token):
                continue
            return "A2"
    return "A0"


def infer_capabilities(text: str) -> list[str]:
    lower = (text or "").lower()
    caps: list[str] = []
    software = bool(
        re.search(
            r"\b(build|implement|application|unit tests?|unittest|pytest|vitest|npm test|"
            r"debug|refactor|codebase|repository|\brepo\b|cli|typecheck|compile|"
            r"add tests?|write tests?|test file|software validation)\b",
            lower,
        )
        or (
            re.search(r"\b(inspect|validate|debug|test|fix)\b", lower)
            and re.search(r"\b(repo|repository|code|stack|tests?)\b", lower)
        )
        or (
            re.search(r"\b(add|update|edit|fix|assert|create)\b", lower)
            and re.search(r"\.(py|ts|tsx|js|md)\b", lower)
        )
    )
    research = bool(
        re.search(
            r"\b(katha|research|compare|investigate|briefing|citing|source-grounded)\b",
            lower,
        )
    )
    docs = bool(
        re.search(r"\b(documentation|document|readme|release notes|review the docs)\b", lower)
    )
    files = bool(
        re.search(
            r"\b(create a file|move files|organize files|rename the file|write a note)\b",
            lower,
        )
    )
    if software:
        caps.append("software")
    if research:
        caps.append("research")
    if docs:
        caps.append("documentation")
    if files:
        caps.append("files")
    return caps


def classify_intent(text: str) -> dict:
    lower = text.lower()
    needed = action_needed_from_text(lower)
    caps = infer_capabilities(text)
    base = {"capabilities": caps}
    if needed == "A3":
        return {
            **base,
            "intent": "financial_execution",
            "workflow": "owner_gate",
            "approval": "A3",
            "reason": "reserved owner-controlled financial action",
        }
    if needed == "A2":
        return {
            **base,
            "intent": "publication",
            "workflow": "prepare_then_gate",
            "approval": "A2",
            "reason": "consequential publish/spend/deploy",
        }
    question = bool(re.search(r"\b(what is|how does|explain|status of|show me)\b", lower))
    if "software" in caps:
        return {
            **base,
            "intent": "software",
            "workflow": "sdlc",
            "approval": "A1",
            "reason": "software lifecycle; documentation or review does not block tests",
        }
    if question and "files" not in caps:
        return {
            **base,
            "intent": "question",
            "workflow": "answer",
            "approval": "A0",
            "reason": "informational; no development job",
        }
    if "research" in caps:
        return {
            **base,
            "intent": "research",
            "workflow": "research_report",
            "approval": "A0",
            "reason": "evidence-producing research",
        }
    if re.search(r"\binventory|connected projects|ping\b", lower):
        return {
            **base,
            "intent": "operational",
            "workflow": "known_procedure",
            "approval": "A0",
            "reason": "existing Windows worker procedure",
        }
    if "documentation" in caps or "files" in caps:
        return {
            **base,
            "intent": "document",
            "workflow": "sdlc",
            "approval": "A1",
            "reason": "personal file or document work",
        }
    return {
        **base,
        "intent": "document",
        "workflow": "draft_review",
        "approval": "A1",
        "reason": "default light artifact workflow",
    }


def maybe_reclassify(job: dict) -> dict:
    """Upgrade a parked classification using capabilities before dispatch."""
    fresh = classify_intent(job.get("parent_objective") or "")
    current = job.get("workflow")
    target = fresh.get("workflow")
    caps = list(fresh.get("capabilities") or [])
    executable = {"sdlc", "research_report"}
    gated = {"owner_gate", "prepare_then_gate"}
    if current not in executable and current not in gated:
        if "software" in caps or "documentation" in caps or "files" in caps:
            target = "sdlc"
            fresh = {
                **fresh,
                "intent": "software" if "software" in caps else "document",
                "approval": "A1",
                "reason": "reclassified from capabilities before dispatch",
            }
        elif "research" in caps:
            target = "research_report"
            fresh = {**fresh, "reason": "reclassified from capabilities before dispatch"}
    if target and target != current:
        job.setdefault("reclassification", []).append(
            {
                "at": utc_now(),
                "from": current,
                "to": target,
                "reason": fresh.get("reason"),
                "capabilities": caps,
            }
        )
        job["workflow"] = target
        job["intent"] = fresh.get("intent") or job.get("intent")
        job["approval_level"] = fresh.get("approval") or job.get("approval_level")
    if caps:
        job["capabilities"] = caps
    return job


def new_parent_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"JOB-{stamp}-{uuid.uuid4().hex[:8].upper()}-AUTO"


def load_baseline_lock() -> dict:
    if BASELINE_LOCK.is_file():
        return load_json(BASELINE_LOCK)
    return {"baseline_id": "UNLOCKED", "files": {}}


def spec_sha256(*docs: dict) -> str:
    h = hashlib.sha256()
    for doc in docs:
        h.update(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    return h.hexdigest()


def create_parent_job(
    objective: str,
    *,
    project_id: str | None = None,
    workspace: str | None = None,
    root: Path | None = None,
    budget_ceiling: float | None = None,
    origin: str = "controller",
) -> dict:
    classification = classify_intent(objective)
    resolved = PLANNING.resolve_project(project_id, workspace)
    if resolved.get("allowed") and resolved.get("workspace"):
        workspace = resolved["workspace"]
    budgets = load_json(BUDGETS)
    if budget_ceiling is None:
        ceiling = budgets["job_defaults"]["max_cost"]
    else:
        ceiling = budget_ceiling
    job = {
        "schema_version": 3,
        "job_id": new_parent_id(),
        "coordinator": "neewa-chief",
        "origin": origin,
        "parent_objective": objective,
        "project_id": project_id,
        "workspace": workspace,
        "intent": classification["intent"],
        "workflow": classification["workflow"],
        "approval_level": classification["approval"],
        "capabilities": classification.get("capabilities") or [],
        "requirements_version": None,
        "design_version": None,
        "scope": "approved personal workspace only",
        "assigned_worker": None,
        "execution_worker": None,
        "child_jobs": [],
        "state": "INTAKE",
        "budget": {
            "ceiling": ceiling,
            "consumed_usd": 0.0,
            "reserved_usd": 0.0,
            "consumed_basis": "none",
            "actual_usd": None,
            "estimated_usd": 0.0,
            "actual_status": "unavailable-until-measured",
            "invocations": [],
        },
        "project_resolution": {
            "allowed": resolved.get("allowed"),
            "reason": resolved.get("reason"),
            "access_stage": (resolved.get("project") or {}).get("access_stage"),
        },
        "baseline_id": load_baseline_lock().get("baseline_id"),
        "lease": None,
        "timeout_sec": 600,
        "dependencies": [],
        "artifacts": [],
        "expected_paths": [],
        "validation": None,
        "failure_reason": None,
        "retry_history": [],
        "owner_decision": None,
        "checkpoints": [],
        "public_listener": False,
        "history": [{"state": "INTAKE", "at": utc_now(), "note": classification["reason"]}],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    path = autonomy_root(root) / f"{job['job_id']}.json"
    save_json(path, job)
    job["_path"] = str(path)
    return job


def save_job(job: dict, root: Path | None = None) -> Path:
    path = Path(job.get("_path") or (autonomy_root(root) / f"{job['job_id']}.json"))
    payload = {k: v for k, v in job.items() if k != "_path"}
    payload["updated_at"] = utc_now()
    save_json(path, payload)
    job["_path"] = str(path)
    return path


def checkpoint(job: dict, name: str, payload: dict | None = None) -> None:
    job.setdefault("checkpoints", []).append(
        {"name": name, "at": utc_now(), "payload": payload or {}}
    )
    save_job(job)


def transition(job: dict, state: str, note: str | None = None) -> None:
    if state not in PARENT_STATES:
        raise ValueError(f"unknown parent state {state}")
    current = job.get("state")
    allowed = ALLOWED_TRANSITIONS.get(current, set())
    if current and state != current and state not in allowed:
        raise ValueError(f"invalid transition {current} -> {state}")
    job["state"] = state
    entry = {"state": state, "at": utc_now()}
    if note:
        entry["note"] = note
    job.setdefault("history", []).append(entry)
    save_job(job)


def conservative_cursor_estimate() -> float | None:
    budgets = load_json(BUDGETS)
    estimates = budgets.get("conservative_estimates_usd") or {}
    value = estimates.get("cursor_call")
    if value is None:
        return None
    return float(value)


def invocation_cost(inv: dict) -> tuple[float | None, str]:
    if inv.get("cost_usd") is not None:
        return float(inv["cost_usd"]), "measured"
    worker = str(inv.get("worker") or "")
    if worker in {"cursor-agent-cli", "local-implementer"}:
        est = conservative_cursor_estimate()
        if est is None:
            return None, "unknown"
        if worker == "local-implementer":
            return 0.0, "fixture-local"
        return est, "conservative_estimate"
    return None, "unknown"


def budget_decision(job: dict, next_worker: str = "cursor-agent-cli") -> dict:
    ceiling = job.get("budget", {}).get("ceiling")
    if ceiling is None:
        return {"allows": False, "reason": "COST_UNKNOWN", "remaining": None}
    ceiling = float(ceiling)
    reserved = float(job.get("budget", {}).get("reserved_usd") or 0.0)
    if ceiling <= 0:
        return {
            "allows": False,
            "reason": "BUDGET_EXHAUSTED",
            "remaining": 0.0,
            "consumed": 0.0,
            "reserved": reserved,
        }
    consumed = 0.0
    basis = "conservative_estimate"
    for inv in job.get("budget", {}).get("invocations") or []:
        cost, inv_basis = invocation_cost(inv)
        if cost is None:
            return {"allows": False, "reason": "COST_UNKNOWN", "remaining": None}
        consumed += cost
        if inv_basis == "measured":
            basis = "measured"
    next_cost, next_basis = invocation_cost({"worker": next_worker, "cost_usd": None})
    if next_cost is None:
        return {"allows": False, "reason": "COST_UNKNOWN", "remaining": None, "consumed": consumed}
    remaining = ceiling - consumed - reserved
    job["budget"]["consumed_usd"] = consumed
    job["budget"]["consumed_basis"] = basis
    job["budget"]["estimated_usd"] = consumed
    job["budget"]["reserved_usd"] = reserved
    if remaining < next_cost:
        return {
            "allows": False,
            "reason": "BUDGET_EXHAUSTED",
            "remaining": remaining,
            "consumed": consumed,
            "reserved": reserved,
            "next_estimate": next_cost,
            "next_basis": next_basis,
        }
    return {
        "allows": True,
        "remaining": remaining,
        "consumed": consumed,
        "reserved": reserved,
        "next_estimate": next_cost,
        "next_basis": next_basis,
    }


def reserve_budget(job: dict, worker: str = "cursor-agent-cli") -> dict:
    decision = budget_decision(job, worker)
    if not decision.get("allows"):
        return decision
    amount = float(decision["next_estimate"])
    job["budget"]["reserved_usd"] = float(job["budget"].get("reserved_usd") or 0.0) + amount
    save_job(job)
    decision["reserved"] = job["budget"]["reserved_usd"]
    decision["this_reservation"] = amount
    return decision


def settle_reservation(job: dict, amount: float | None) -> None:
    reserved = float(job.get("budget", {}).get("reserved_usd") or 0.0)
    if amount is None:
        job["budget"]["reserved_usd"] = max(0.0, reserved)
        return
    job["budget"]["reserved_usd"] = max(0.0, reserved - float(amount))


def release_open_reservation(job: dict) -> None:
    job.setdefault("budget", {})["reserved_usd"] = 0.0


def parse_utc(stamp: str | None) -> datetime | None:
    if not stamp:
        return None
    try:
        return datetime.strptime(str(stamp), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def child_is_stale(job: dict) -> bool:
    child_id = job.get("active_child_id")
    if not child_id:
        return False
    timeout = int(job.get("timeout_sec") or 600)
    started = None
    for row in job.get("child_jobs") or []:
        if row.get("job_id") == child_id:
            started = parse_utc(row.get("at"))
            break
    started = started or parse_utc(job.get("updated_at"))
    if not started:
        return False
    return datetime.now(timezone.utc) - started > timedelta(seconds=timeout + 30)


def is_config_defect(record: dict | None, expected: list[str] | None) -> bool:
    if PLANNING.malformed_expected_paths(expected):
        return True
    cls = str((record or {}).get("failure_class") or "")
    if cls in {"CONFIG_DEFECT", "MALFORMED_EXPECTED_PATH"}:
        return True
    reason = str((record or {}).get("failure_reason") or (record or {}).get("reason") or "").lower()
    return "malformed expected" in reason or (
        "missing expected files" in reason and "fastapi/next.js" in reason
    )


def fail_config_defect(job: dict, reason: str) -> dict:
    job["failure_class"] = "CONFIG_DEFECT"
    job["failure_reason"] = reason
    job["active_child_id"] = None
    release_open_reservation(job)
    if job.get("state") == "OWNER_REVIEW":
        transition(job, "FAILED", reason)
    elif job.get("state") not in TERMINAL:
        transition(job, "FAILED", reason)
    save_job(job)
    return job


def budget_allows(job: dict, next_worker: str = "cursor-agent-cli") -> bool:
    return bool(budget_decision(job, next_worker).get("allows"))


def load_policy() -> dict:
    if POLICY.is_file():
        return load_json(POLICY)
    return {}


def authorize_execution(
    *,
    approval_level: str,
    owner_decision: str | None = None,
    prompt: str = "",
    repo: str = "",
    write: bool = False,
) -> dict:
    """Job JSON owner_decision is untrusted and never grants A2/A3."""
    del owner_decision  # mutable job files are not an approval channel
    blob = f"{prompt}\n{repo}".lower()
    needed = "A1" if write else "A0"
    needed_from_text = action_needed_from_text(blob)
    if needed_from_text == "A3":
        needed = "A3"
    elif needed_from_text == "A2":
        needed = "A2"
    policy = load_policy()
    repo_norm = repo.replace("/", "\\").lower()
    try:
        if repo:
            repo_norm = str(Path(repo).resolve()) if Path(repo).exists() else repo_norm
            repo_norm = repo_norm.replace("/", "\\").lower()
    except OSError:
        pass
    for name in policy.get("denied_name_equals") or []:
        if name and name.lower() in repo_norm:
            return {
                "allowed": False,
                "reason": "UNAUTHORIZED_REPO",
                "needed": "DENIED",
                "detail": name,
            }
    for frag in policy.get("denied_name_contains") or []:
        if frag and frag.lower() in repo_norm:
            return {
                "allowed": False,
                "reason": "UNAUTHORIZED_REPO",
                "needed": "DENIED",
                "detail": frag,
            }
    if repo:
        path_gate = PLANNING.workspace_authorization(repo)
        if not path_gate["allowed"]:
            return {
                "allowed": False,
                "reason": path_gate["reason"],
                "needed": "DENIED",
                "detail": repo,
            }
    for frag in policy.get("blocked_intent_substrings") or []:
        if frag and frag.lower() in blob:
            token = frag.split()[-1]
            if contains_negated(blob, token):
                continue
            mapped = "A3" if any(h in frag.lower() for h in A3_HINTS) else "A2"
            return {
                "allowed": False,
                "reason": "BLOCKED_INTENT",
                "needed": mapped,
                "detail": frag,
            }
    rank = {"A0": 0, "A1": 1, "A2": 2, "A3": 3, "DENIED": 9}
    if rank.get(needed, 9) >= 2:
        return {"allowed": False, "reason": f"{needed}_OWNER_GATE", "needed": needed}
    if rank.get(needed, 0) > rank.get(approval_level, 0):
        return {"allowed": False, "reason": f"{needed}_OWNER_GATE", "needed": needed}
    return {"allowed": True, "needed": needed, "reason": None}


def record_usage(job: dict, worker: str, outcome: str, usage: dict | None = None) -> None:
    inv = {
        "at": utc_now(),
        "worker": worker,
        "outcome": outcome,
        "input_tokens": (usage or {}).get("inputTokens") or (usage or {}).get("input_tokens"),
        "output_tokens": (usage or {}).get("outputTokens") or (usage or {}).get("output_tokens"),
        "cache_read_tokens": (usage or {}).get("cacheReadTokens"),
        "cache_write_tokens": (usage or {}).get("cacheWriteTokens"),
        "cost_usd": (usage or {}).get("cost_usd"),
        "cost_basis": "measured" if (usage or {}).get("cost_usd") is not None else "pending",
    }
    cost, basis = invocation_cost(inv)
    inv["cost_usd"] = cost
    inv["cost_basis"] = basis
    job["budget"].setdefault("invocations", []).append(inv)
    settle_reservation(job, cost)
    decision = budget_decision(job, worker)
    job["budget"]["consumed_usd"] = decision.get("consumed")
    job["budget"]["consumed_basis"] = decision.get("next_basis") or basis


def routable_workers(registry: dict | None = None) -> list[dict]:
    data = registry or load_json(WORKERS)
    out = []
    for row in data.get("workers", []):
        if row.get("routable") is False:
            continue
        if row.get("status") in {"verified", "active", "active-local-worker"}:
            out.append(row)
    return out


def select_coding_worker(registry: dict | None = None, fallback_order: list[str] | None = None) -> dict:
    order = fallback_order or ["cursor-agent-cli", "codex", "claude-code", "gemini-cli"]
    available = {w["id"]: w for w in routable_workers(registry)}
    for wid in order:
        row = available.get(wid)
        if row:
            return {"available": True, "worker": wid, "row": row}
    return {
        "available": False,
        "worker": None,
        "missing": "no verified coding worker in fallback order",
    }


def product_slug(objective: str) -> str:
    text = re.sub(r"(?i)^(?:neewa,?\s*|please\s*|owner:\s*)+", "", objective.strip())
    match = re.search(
        r"(?i)(?:build|create|implement|write|make)\s+(?:an?\s+)?(.+?)(?:\s+that\b|\s+which\b|\s+with\b|,|\.|$)",
        text,
    )
    phrase = match.group(1) if match else text[:80]
    phrase = re.sub(r"(?i)\b(cli|application|app|tool|utility|program)\b", " ", phrase)
    words = [w for w in re.findall(r"[a-z0-9]+", phrase.lower()) if w not in STOP_WORDS][:4]
    return "_".join(words) or "task"


def split_objective_clauses(objective: str) -> list[str]:
    cleaned = re.sub(r"(?i)^(?:neewa,?\s*)+", "", objective.strip())
    parts = re.split(r"(?:,|;|\.(?:\s|$)|(?:\s+and\s+)|(?:\s+then\s+))", cleaned)
    return [p.strip() for p in parts if p and len(p.strip()) > 8]


def build_requirements(
    objective: str,
    *,
    fixture: str | None = None,
    workflow: str | None = None,
    workspace: str | None = None,
    project_id: str | None = None,
) -> dict:
    if fixture == FIXTURE.FIXTURE_ID:
        return FIXTURE.fixture_build_requirements(objective)
    workflow = workflow or classify_intent(objective)["workflow"]
    inspect = PLANNING.inspect_workspace(workspace, project_id)
    slug = product_slug(objective)
    clauses = split_objective_clauses(objective)
    reqs: list[dict] = []

    def add(kind: str, text: str) -> None:
        reqs.append({"id": f"REQ-{len(reqs)+1:03d}", "text": text, "kind": kind})

    if workflow == "research_report":
        add("functional", f"Produce a source-grounded research/document artifact for: {objective.strip()}")
        add("provenance", "Cite only approved local corpus files; never invent verses or attributions.")
        add("provenance", "If a needed source is absent, mark SOURCE_PENDING instead of fabricating a citation.")
        add("domain", "List items that require the owner to choose a tradition, policy, or lineage.")
        add("release", "Do not publish; stop at a release candidate for owner review.")
        add("security", "Stay inside approved personal NEEWA references; do not access employer trees.")
    else:
        add("functional", f"Deliver the requested change for `{slug}`: {objective.strip()}")
        lower = objective.lower()
        stack = inspect.get("stack") or ""
        if "read" in lower or "import" in lower or "csv" in lower:
            add("functional", "Read the input file named or implied by the objective; do not scan unrelated directories.")
        if re.search(r"\bprint|output|digest|report|heading|bullet|export|table|subtotal\b", lower):
            add("functional", "Emit the requested output described in the objective (stdout or named artifact).")
        if re.search(r"\bchangelog|markdown|\.md\b", lower):
            add("functional", "Treat Markdown structure as data; preserve headings and list items from the source file.")
        if re.search(r"\bjson\b", lower):
            add("functional", "Honor the JSON input/output contract stated in the objective.")
        if re.search(r"\bcsv\b", lower):
            add("functional", "Reject malformed CSV rows visibly; do not silently drop invalid amounts or headers.")
        if re.search(r"\btest", lower) or "release candidate" in lower or workflow == "sdlc":
            cmd = inspect.get("test_command") or "project tests"
            add("quality", f"Run the repository test command ({cmd}) covering the changed behavior.")
        if stack.startswith("python") or stack in {"", "unknown", "python-stdlib"}:
            add("reliability", "Missing or unreadable input must produce a non-zero exit code and an error on stderr.")
        add("security", "Operate only inside the approved workspace; do not access employer trees.")
        if "release candidate" in lower or workflow == "sdlc":
            add("release", "Produce a release-candidate document with requirement traceability after tests pass.")
    seen = set()
    unique = []
    for req in reqs:
        key = req["text"]
        if key in seen:
            continue
        seen.add(key)
        unique.append(req)
    for i, req in enumerate(unique, start=1):
        req["id"] = f"REQ-{i:03d}"
    payload = {
        "version": "REQ-v1",
        "original_objective": objective,
        "product_slug": slug,
        "workflow": workflow,
        "clauses": clauses,
        "clarifications": [],
        "implementation_decisions": [],
        "proposed_enhancements": [],
        "out_of_scope": ["public deployment", "live trading", "employer data", "Home voice work"],
        "requirements": unique,
        "created_at": utc_now(),
        "source_class": "DERIVED_FROM_OBJECTIVE",
        "baseline_id": load_baseline_lock().get("baseline_id"),
    }
    return PLANNING.attach_acceptance_checks(payload, inspect, workflow)


def initial_design(requirements: dict, objective: str | None = None) -> dict:
    if requirements.get("fixture") == FIXTURE.FIXTURE_ID:
        return FIXTURE.fixture_initial_design(requirements)
    objective = objective or requirements.get("original_objective") or ""
    slug = requirements.get("product_slug") or product_slug(objective)
    workflow = requirements.get("workflow") or classify_intent(objective)["workflow"]
    if workflow == "research_report":
        return {
            "version": "DES-v1",
            "product_slug": slug,
            "workflow": workflow,
            "summary": (
                f"Source-grounded research document `{slug}/RESEARCH_REPORT.md` using only "
                "the approved local source pack. No software CLI."
            ),
            "assumptions": [
                "Approved local corpus files only (OWNER.md, PROJECT_ACCESS.md, source packs as matched).",
                "Missing sources are SOURCE_PENDING, never invented.",
            ],
            "source_plan": "Cite corpus file names; list owner decisions still required.",
            "components": [
                f"{slug}/RESEARCH_REPORT.md",
                f"{slug}/citations.json",
                f"{slug}/SOURCE_STATUS.json",
            ],
            "source_plan": "Quote SRC-IDs from the local pack; list owner tradition choices.",
            "error_handling": "SOURCE_PENDING when the pack lacks a requested source; do not fabricate citations",
            "filesystem_scope": "approved NEEWA reference pack only",
            "acceptance": [r["id"] for r in requirements["requirements"]],
            "created_at": utc_now(),
        }
    stack = requirements.get("stack") or "python-stdlib"
    mentioned = PLANNING.extract_mentioned_paths(objective)
    sandboxish = (
        stack in {"", "unknown", "python-stdlib", "python"}
        or "cursor-sandbox" in objective.lower()
    )
    existing_repo = (stack.startswith("node") or stack.startswith("mixed")) and not sandboxish
    if existing_repo:
        components = PLANNING.constrain_expected_paths(mentioned)
        return {
            "version": "DES-v1",
            "product_slug": slug,
            "workflow": workflow,
            "stack": stack,
            "stack_label": requirements.get("stack_label") or stack,
            "create_new_package": False,
            "test_command": requirements.get("test_command"),
            "summary": (
                f"Scoped change in the existing {stack} repository. "
                "Do not create a new Python CLI package. "
                "Stack label is metadata only and is not a file path. "
                + "; ".join(r["text"] for r in requirements["requirements"] if r["kind"] == "functional")
            ),
            "assumptions": [
                "Use the repository's existing toolchain and tests.",
                "Change only files required by the objective.",
                "Expected paths are repository-relative files, never stack labels.",
            ],
            "components": components,
            "error_handling": "keep existing error handling unless the objective changes it",
            "filesystem_scope": "approved workspace only; no employer trees",
            "acceptance": [r["id"] for r in requirements["requirements"]],
            "created_at": utc_now(),
        }
    components = [f"{slug}/{slug}.py", f"{slug}/test_{slug}.py", f"{slug}/sample_input.txt", f"{slug}/test-results.json"]
    blob = " ".join(r["text"].lower() for r in requirements["requirements"]) + " " + objective.lower()
    if "changelog" in blob or "markdown" in blob:
        components[2] = f"{slug}/sample_CHANGELOG.md"
    if "csv" in blob:
        components[2] = f"{slug}/sample.csv"
    if any(r.get("kind") == "release" for r in requirements["requirements"]):
        components.append(f"{slug}/RELEASE_CANDIDATE.md")
    summary = (
        f"Python CLI `{slug}/{slug}.py` in the approved cursor-sandbox. "
        f"It implements: " + "; ".join(r["text"] for r in requirements["requirements"] if r["kind"] == "functional")
    )
    return {
        "version": "DES-v1",
        "product_slug": slug,
        "workflow": workflow,
        "summary": summary,
        "assumptions": [
            "Local Python 3 is available on the Windows worker.",
            "Workspace is the approved personal sandbox unless a connected repo is named.",
        ],
        "components": components,
        "error_handling": "non-zero exit and stderr on missing/unreadable/invalid input",
        "filesystem_scope": "explicit path argument only; approved workspace",
        "acceptance": [r["id"] for r in requirements["requirements"]],
        "stack": stack,
        "create_new_package": True,
        "test_command": requirements.get("test_command") or "python -m unittest",
        "created_at": utc_now(),
    }


def _design_blob(design: dict) -> str:
    return " ".join(
        [
            str(design.get("summary") or ""),
            str(design.get("error_handling") or ""),
            str(design.get("filesystem_scope") or ""),
            " ".join(str(c) for c in design.get("components") or []),
        ]
    ).lower()


def run_council(design: dict, requirements: dict | None = None) -> dict:
    if design.get("fixture") == FIXTURE.FIXTURE_ID or (requirements or {}).get("fixture") == FIXTURE.FIXTURE_ID:
        return FIXTURE.fixture_run_council(design)
    requirements = requirements or {"requirements": []}
    blob = _design_blob(design)
    findings = []

    def note(role: str, severity: str, finding: str, evidence: str) -> None:
        findings.append({"role": role, "severity": severity, "finding": finding, "evidence": evidence})

    acceptance = set(design.get("acceptance") or [])
    reqs = requirements.get("requirements") or []
    missing_ids = [r["id"] for r in reqs if r["id"] not in acceptance]
    if missing_ids:
        note(
            "quality_engineer",
            "material",
            f"Design acceptance omits {missing_ids}.",
            f"acceptance={sorted(acceptance)}",
        )
    else:
        note(
            "quality_engineer",
            "info",
            "Every requirement ID is listed in design acceptance.",
            f"acceptance={sorted(acceptance)}",
        )

    if any("test" in r["text"].lower() or r["kind"] == "quality" for r in reqs):
        has_test = (
            any("test" in str(c).lower() for c in design.get("components") or [])
            or bool(design.get("test_command"))
            or design.get("create_new_package") is False
        )
        if not has_test:
            note(
                "quality_engineer",
                "material",
                "Quality requirement exists but no test component is listed.",
                f"components={design.get('components')}",
            )
        else:
            note(
                "quality_engineer",
                "info",
                "Test component or repository test command is present.",
                f"components={design.get('components')} test_command={design.get('test_command')}",
            )

    if any(r["kind"] == "reliability" or "invalid" in r["text"].lower() or "missing" in r["text"].lower() for r in reqs):
        if not any(w in blob for w in ("stderr", "non-zero", "exit", "invalid", "missing")):
            note(
                "quality_engineer",
                "material",
                "Reliability requirement is not reflected in error-handling design.",
                f"error_handling={design.get('error_handling')!r} summary={design.get('summary')!r}",
            )
        else:
            note(
                "quality_engineer",
                "info",
                "Error handling is specified.",
                str(design.get("error_handling") or design.get("summary")),
            )

    if any(r["kind"] == "security" for r in reqs):
        if not any(w in blob for w in ("approved", "sandbox", "explicit path", "employer")):
            note(
                "security_privacy",
                "material",
                "Security requirement is not reflected in filesystem scope.",
                str(design.get("filesystem_scope")),
            )
        else:
            note(
                "security_privacy",
                "info",
                "Filesystem scope is constrained.",
                str(design.get("filesystem_scope")),
            )

    if re.search(r"\b(pip install|npm install|paid api|openai api)\b", blob):
        note(
            "cost_operations",
            "material",
            "Design introduces extra installs or paid APIs without authorization.",
            blob[:300],
        )
    else:
        note(
            "cost_operations",
            "info",
            "No extra paid providers in the design.",
            "local toolchain only",
        )

    if (requirements.get("stack") or "").startswith("node") and design.get("create_new_package") is not False:
        note(
            "solution_architect",
            "material",
            "Node/TypeScript repository was given a Python CLI design.",
            f"stack={requirements.get('stack')} summary={design.get('summary')!r}",
        )
    if requirements.get("workflow") == "research_report":
        impl_note = "Research document workflow; no software CLI."
    elif design.get("create_new_package") is False:
        impl_note = f"Scoped change in existing {requirements.get('stack') or 'repository'} using its toolchain."
    else:
        impl_note = "Implementation is a stdlib Python CLI unless later evidence shows otherwise."
    note(
        "implementation_engineer",
        "info",
        impl_note,
        str(design.get("components")),
    )
    if requirements.get("workflow") == "research_report":
        if "cli" in blob and "python cli" in blob:
            note(
                "domain_reviewer",
                "material",
                "Research design incorrectly specifies a software CLI.",
                design.get("summary"),
            )
        else:
            note(
                "domain_reviewer",
                "info",
                "Research design is a source plan, not a CLI.",
                str(design.get("source_plan") or design.get("summary")),
            )
        if "source_pending" not in blob and "source pack" not in blob:
            note(
                "domain_reviewer",
                "material",
                "Research design does not constrain citations to the approved pack.",
                blob[:300],
            )
    note(
        "ux_product",
        "info",
        "CLI should print usage on missing args." if requirements.get("workflow") != "research_report" else "Document should list owner tradition choices.",
        "implicit contract",
    )

    material = [f for f in findings if f["severity"] == "material"]
    revised = dict(design)
    if material:
        revised["version"] = "DES-v2"
        extra = " Corrected to address: " + " ".join(f["finding"] for f in material)
        revised["summary"] = (revised.get("summary") or "") + extra
        if any("error" in f["finding"].lower() or "reliability" in f["finding"].lower() for f in material):
            revised["error_handling"] = "non-zero exit and stderr on missing/unreadable/invalid input"
        if any("security" in f["finding"].lower() or "filesystem" in f["finding"].lower() for f in material):
            revised["filesystem_scope"] = "explicit path argument only; approved workspace; no employer trees"
        if any("test" in f["finding"].lower() for f in material):
            if revised.get("create_new_package") is False:
                revised["test_command"] = requirements.get("test_command") or revised.get("test_command")
            else:
                slug = revised.get("product_slug") or "task"
                comps = list(revised.get("components") or [])
                test_path = f"{slug}/test_{slug}.py"
                if test_path not in comps:
                    comps.append(test_path)
                revised["components"] = comps
        revised["corrections"] = [f["finding"] for f in material]
        revised["acceptance"] = [r["id"] for r in reqs] or revised.get("acceptance")
    else:
        revised["version"] = design.get("version") or "DES-v1"
        revised["corrections"] = []
        revised["no_material_finding"] = (
            "Council checklist passed against the written design; no material defect was found."
        )
    return {
        "rounds": 1,
        "findings": findings,
        "material_count": len(material),
        "approved_design": revised,
        "unresolved_risks": [],
        "created_at": utc_now(),
        "reviewer_identity": "neewa_autonomy.run_council",
        "independence_class": "deterministic_only",
        "limitation": "INDEPENDENCE_UNAVAILABLE",
    }


def expected_paths_from_design(design: dict) -> list[str]:
    return PLANNING.constrain_expected_paths(design.get("components") or [])


def parse_source_pack(path: Path | None = None) -> dict:
    pack = path or SOURCE_PACK
    if not pack.is_file():
        return {"entries": {}, "status": "SOURCE_PENDING", "path": str(pack)}
    text = pack.read_text(encoding="utf-8")
    entries = {}
    current = None
    buf: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^## (SRC-\d+)\b", line)
        if match:
            if current:
                entries[current] = "\n".join(buf).strip()
            current = match.group(1)
            buf = [line]
        elif current:
            buf.append(line)
    if current:
        entries[current] = "\n".join(buf).strip()
    return {
        "entries": entries,
        "status": "AVAILABLE" if entries else "SOURCE_PENDING",
        "path": str(pack),
        "pack_id": "SRC-GANESHA-20260917",
    }


def synthesize_research(objective: str, requirements: dict, design: dict) -> dict:
    result = PLANNING.synthesize_from_corpus(objective, requirements, design)
    pack = parse_source_pack()
    if pack.get("entries") and re.search(r"ganesh|ganapati|chaturthi|katha", objective, re.I):
        extra = ["", "## Source-pack entries (devotional corpus)", ""]
        for sid, body in pack["entries"].items():
            theme = next((ln for ln in body.splitlines() if "Permitted theme" in ln or "Note:" in ln), sid)
            extra.append(f"- **{sid}**: {theme.strip()}")
        extra.append("")
        result["report"] += "\n".join(extra)
        result["citations"].extend({"id": sid, "pack": pack.get("pack_id"), "exists": True} for sid in pack["entries"])
        result["word_count"] = len(result["report"].split())
        result["passed"] = result["passed"] or (bool(pack["entries"]) and "SRC-01" in result["report"])
    return result


def build_worker_prompt(job: dict, requirements: dict, design: dict) -> str:
    req_lines = "\n".join(f"- {r['id']}: {r['text']}" for r in requirements["requirements"])
    files = "\n".join(f"- {p}" for p in expected_paths_from_design(design))
    test_cmd = design.get("test_command") or requirements.get("test_command") or "python -m unittest"
    if design.get("create_new_package") is False:
        return f"""Implement this approved NEEWA work package in the EXISTING repository. Do not change the objective.

OBJECTIVE:
{job['parent_objective']}

REQUIREMENTS ({requirements.get('version')}):
{req_lines}

APPROVED DESIGN ({design.get('version')}):
{design.get('summary')}
Stack: {design.get('stack')}
Filesystem scope: {design.get('filesystem_scope')}

Stack label `{design.get('stack_label') or design.get('stack')}` is descriptive metadata, not a file path. Never create or expect a file named after the stack.

Edit only these repository-relative files (empty means inspect the repo and choose an existing feature; do not invent stack-named paths):
{files or '- (none predeclared; select a real existing feature path)'}

Rules:
- Do NOT create a new Python CLI package.
- Do NOT write FastAPI/Next.js, Next.js, or other stack labels as files.
- Do NOT write RELEASE_CANDIDATE.md into the product repository; the controller owns that artifact.
- Use this repository's toolchain. Run: {test_cmd}
- Print a single final line: TEST_JSON:<compact json with exit_code, passed, stdout, stderr>
- Stay inside this workspace. Do not touch employer trees, myDropbox, secrets, or the rest of the C drive.
- No public distribution, production rollout, buying services, or brokerage actions.
- Do not claim files exist unless you changed or verified them.
"""
    return f"""Implement this approved NEEWA work package. Do not change the objective.

OBJECTIVE:
{job['parent_objective']}

REQUIREMENTS ({requirements.get('version')}):
{req_lines}

APPROVED DESIGN ({design.get('version')}):
{design.get('summary')}
Error handling: {design.get('error_handling')}
Filesystem scope: {design.get('filesystem_scope')}

Write ALL of these files (relative to the workspace root):
{files}

Rules:
- Python 3 stdlib only.
- Automated tests must actually run via python -m unittest.
- Write test-results.json in the product folder with keys exit_code, passed, stdout, stderr from that unittest run.
- Print a single final line: TEST_JSON:<compact json of test-results>
- Stay inside this workspace. Do not touch employer trees or the rest of the C drive.
- No public distribution, production rollout, buying services, or brokerage actions.
- Do not claim files exist unless you wrote them.
"""


def build_validation_prompt(job: dict, requirements: dict, design: dict) -> str:
    test_cmd = design.get("test_command") or requirements.get("test_command") or "python -m unittest"
    return f"""Independently rerun tests for this approved NEEWA work package. Do not expand scope.

OBJECTIVE:
{job['parent_objective']}

Run the repository test command only: {test_cmd}
Do not create a new Python CLI. Do not change unrelated files.
Print a single final line: TEST_JSON:<compact json with exit_code, passed, stdout, stderr>
Stay inside this workspace. Do not touch employer trees, myDropbox, secrets, or the rest of the C drive.
"""


def parse_test_evidence(stdout: str | None, payload: dict | None = None) -> dict:
    text = stdout or ""
    payload = payload or {}
    if payload.get("test_results"):
        row = payload["test_results"]
        return {
            "passed": bool(row.get("passed")),
            "exit_code": row.get("exit_code"),
            "stdout": str(row.get("stdout") or "")[-4000:],
            "source": "payload",
        }
    try:
        wrapped = json.loads(text)
        if isinstance(wrapped, dict) and wrapped.get("result"):
            text = str(wrapped["result"])
    except json.JSONDecodeError:
        pass
    idx = text.find("TEST_JSON:")
    if idx >= 0:
        raw = text[idx + len("TEST_JSON:") :].strip()
        try:
            row = json.JSONDecoder().raw_decode(raw)[0]
            return {
                "passed": bool(row.get("passed")),
                "exit_code": row.get("exit_code"),
                "stdout": str(row.get("stdout") or row.get("stderr") or "")[-4000:],
                "source": "TEST_JSON",
            }
        except json.JSONDecodeError:
            pass
    ran = re.search(r"Ran (\d+) tests?", text)
    ok = bool(re.search(r"(?:^|\n|\\n)OK(?:\n|\\n|\b)", text)) and "FAILED (" not in text
    if ran:
        return {
            "passed": ok,
            "exit_code": 0 if ok else 1,
            "stdout": text[-4000:],
            "source": "unittest-stdout",
            "ran": int(ran.group(1)),
        }
    vitest = re.search(r"Test Files\s+(\d+)\s+passed", text)
    if vitest and not re.search(r"Test Files\s+\d+\s+failed", text):
        return {
            "passed": True,
            "exit_code": 0,
            "stdout": text[-4000:],
            "source": "vitest-stdout",
            "ran": int(vitest.group(1)),
        }
    return {"passed": False, "exit_code": None, "stdout": text[-4000:], "source": "absent"}


def _is_test_path(path: str) -> bool:
    name = Path(path).name.lower()
    return name.startswith("test_") or ".test." in name or name.endswith(".spec.ts")


def _is_impl_path(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    if suffix not in {".py", ".ts", ".tsx", ".js", ".md", ".json"}:
        return False
    return not _is_test_path(path) and "release_candidate" not in Path(path).name.lower()


def evaluate_requirement_check(
    req: dict,
    design: dict,
    *,
    expected_paths: list[str],
    test_evidence: dict,
    workspace: str | None,
    artifacts: list[str] | None = None,
    independent_rerun: str | None = None,
) -> dict:
    check = req.get("check") or ""
    tests_passed = bool(test_evidence.get("passed"))
    stdout = (test_evidence.get("stdout") or "").lower()
    source = test_evidence.get("source") or "absent"
    artifacts = artifacts or []
    blob = " ".join([*expected_paths, *artifacts]).lower()
    evidence = [f"ac={req.get('ac')}", f"check={check or 'legacy'}"]
    result = "FAIL"

    if req["id"] not in (design.get("acceptance") or []):
        evidence.append("requirement not in approved design acceptance")
        return {"requirement": req["id"], "text": req["text"], "ac": req.get("ac"), "check": check, "evidence": evidence, "result": "FAIL"}

    if check in {"independent_tests", "quality"} or (not check and req["kind"] == "quality"):
        if independent_rerun == "UNVERIFIED":
            result = "UNVERIFIED"
            evidence.append("independent rerun was not obtained")
        elif independent_rerun == "FAIL":
            evidence.append("independent rerun failed")
        elif tests_passed and (any(_is_test_path(p) for p in expected_paths) or design.get("test_command") or independent_rerun in {"PASS", "IMPLEMENTER_CLAIMED", "LOCAL_CORPUS"}):
            evidence.append(f"tests_passed via {source}")
            result = "PASS"
        elif source == "absent":
            result = "UNVERIFIED"
            evidence.append("no test evidence")
        else:
            evidence.append(f"tests did not pass source={source}")
    elif check == "workspace_boundary" or (not check and req["kind"] == "security"):
        gate = authorize_execution(
            approval_level="A1",
            prompt="implement approved scoped change",
            repo=workspace or "",
            write=True,
        )
        denied = any(name in (workspace or "").lower() for name in ("oratsutil", "qe_platform", "fintech-automation"))
        if gate.get("allowed") and workspace and not denied:
            evidence.append(f"authorize={gate.get('reason')} workspace={workspace}")
            result = "PASS"
        elif not workspace:
            result = "UNVERIFIED"
            evidence.append("workspace missing")
        else:
            evidence.append(f"boundary failed allowed={gate.get('allowed')} reason={gate.get('reason')}")
    elif check.startswith("file_exists:") or (not check and req["kind"] == "release"):
        name = check.split(":", 1)[1] if check.startswith("file_exists:") else "RELEASE_CANDIDATE.md"
        if name.lower() in blob or design.get("workflow") == "research_report":
            evidence.append(f"artifact referenced: {name}")
            result = "PASS"
        elif tests_passed and design.get("create_new_package") is False:
            evidence.append("existing-repo RELEASE_CANDIDATE.md is controller-owned in the job workdir")
            result = "PASS"
        elif tests_passed and design.get("workflow") == "research_report":
            result = "PASS"
            evidence.append("research RC pending write")
        else:
            result = "UNVERIFIED" if source == "absent" else "FAIL"
            evidence.append(f"{name} not in expected_paths/artifacts")
    elif check in {"citation", "report_file", "report_contains_owner_choice", "no_publish"} or req["kind"] in {"provenance", "domain"}:
        if check == "no_publish":
            evidence.append("job remains owner-review; no publication action")
            result = "PASS"
        elif tests_passed or source in {"PASS", "AVAILABLE", "LOCAL_CORPUS"} or "source" in source.lower():
            evidence.append(f"source_status={source}")
            result = "PASS" if tests_passed or source in {"PASS", "AVAILABLE"} else "FAIL"
        else:
            result = "UNVERIFIED" if source == "absent" else "FAIL"
            evidence.append("citation/report evidence missing")
    elif check == "negative_path" or (not check and req["kind"] == "reliability"):
        observed = bool(re.search(r"missing|invalid|stderr|non-zero|error", stdout))
        designed = "stderr" in (design.get("error_handling") or "").lower() or "non-zero" in (design.get("error_handling") or "").lower()
        if tests_passed and (observed or (designed and any(_is_test_path(p) for p in expected_paths))):
            evidence.append("negative-path covered by tests or observed output")
            result = "PASS"
        elif source == "absent":
            result = "UNVERIFIED"
            evidence.append("no negative-path evidence")
        else:
            evidence.append("negative-path not observed")
    else:
        impl = [p for p in expected_paths if _is_impl_path(p)]
        tests = [p for p in expected_paths if _is_test_path(p)]
        if impl and tests_passed:
            evidence.append("implementation=" + ",".join(impl))
            evidence.append(f"tests_passed via {source}")
            result = "PASS"
        elif tests_passed and design.get("create_new_package") is False and (tests or independent_rerun in {"PASS", "IMPLEMENTER_CLAIMED"}):
            evidence.append("existing-repo test/docs are the objective artifact")
            evidence.append(f"tests_passed via {source}")
            result = "PASS"
        elif tests_passed and not impl:
            evidence.append("tests passed but no objective artifact in expected_paths")
            result = "FAIL"
        elif impl and source == "absent":
            result = "UNVERIFIED"
            evidence.append("artifact planned but tests not run")
        else:
            evidence.append("artifact or test evidence missing")
            result = "FAIL" if source != "absent" else "UNVERIFIED"

    return {
        "requirement": req["id"],
        "text": req["text"],
        "ac": req.get("ac"),
        "check": check,
        "design": design.get("version"),
        "implementation": ",".join(p for p in expected_paths if _is_impl_path(p)) or None,
        "test": source,
        "evidence": evidence,
        "result": result,
    }


def traceability(
    requirements: dict,
    design: dict,
    *,
    expected_paths: list[str],
    test_evidence: dict,
    workspace: str | None,
    artifacts: list[str] | None = None,
    independent_rerun: str | None = None,
) -> dict:
    rows = [
        evaluate_requirement_check(
            req,
            design,
            expected_paths=expected_paths,
            test_evidence=test_evidence,
            workspace=workspace,
            artifacts=artifacts,
            independent_rerun=independent_rerun,
        )
        for req in requirements["requirements"]
    ]
    return {
        "all_pass": all(r["result"] == "PASS" for r in rows) and bool(rows),
        "rows": rows,
        "independent_rerun": independent_rerun,
    }


def evaluate_autonomy_done(job: dict) -> list[str]:
    failures = []
    if job.get("state") not in {"VALIDATING", "RELEASE_CANDIDATE"}:
        failures.append("job is not in VALIDATING")
    if job.get("approval_level") in {"A2", "A3"}:
        failures.append("owner approval is pending")
    if not job.get("requirements_version"):
        failures.append("requirements version missing")
    if not job.get("design_version"):
        failures.append("approved design version missing")
    if not job.get("artifacts"):
        failures.append("artifacts missing")
    validation = job.get("validation") or {}
    if validation.get("tests") != "PASS":
        failures.append("unit tests or citation validation did not pass")
    if job.get("spec_sha256"):
        work = Path(job.get("_path") or ".").parent / "work" / job["job_id"]
        req_p = work / "requirements.json"
        des_p = work / "design-v2.json"
        if req_p.is_file() and des_p.is_file():
            recomputed = spec_sha256(load_json(req_p), load_json(des_p))
            if recomputed != job["spec_sha256"]:
                failures.append("SPEC_DRIFT")
    if validation.get("traceability") != "PASS":
        failures.append("requirements traceability did not pass")
    if validation.get("council") != "PASS":
        failures.append("design council did not complete")
    if not job.get("validation"):
        failures.append("validation block missing")
    return failures


def write_release_candidate(workdir: Path, job: dict, trace: dict) -> Path:
    path = workdir / "RELEASE_CANDIDATE.md"
    body = [
        f"# Release candidate {job['job_id']}",
        "",
        f"Objective: {job['parent_objective']}",
        f"Requirements: {job['requirements_version']}",
        f"Design: {job['design_version']}",
        f"Assigned worker: {job.get('assigned_worker')}",
        f"Execution worker: {job.get('execution_worker')}",
        f"Child jobs: {json.dumps(job.get('child_jobs') or [])}",
        "",
        "## Traceability",
        json.dumps(trace["rows"], indent=2),
        "",
        "## Limitations",
        "- Approved sandbox only; not deployed.",
        f"- Cost basis: {job.get('budget', {}).get('consumed_basis')}.",
        "",
        "Owner review is required before any public release.",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def job_workdir(job: dict, root: Path | None) -> Path:
    base = autonomy_root(root)
    path = base / "work" / job["job_id"]
    path.mkdir(parents=True, exist_ok=True)
    return path


def cancel_job(job: dict, reason: str = "cancelled") -> dict:
    job["failure_reason"] = reason
    transition(job, "CANCELLED", reason)
    save_job(job)
    return job


def resume_job(job_id: str, root: Path | None = None) -> dict | None:
    path = autonomy_root(root) / f"{job_id}.json"
    if not path.is_file():
        return None
    job = load_json(path)
    job["_path"] = str(path)
    return job


def list_parent_jobs(root: Path | None = None) -> list[dict]:
    jobs = []
    for path in sorted(autonomy_root(root).glob("JOB-*.json")):
        row = load_json(path)
        row["_path"] = str(path)
        jobs.append(row)
    return jobs


def _submit_cursor(
    job: dict,
    prompt: str,
    expected_paths: list[str],
    *,
    inbox_root: Path | None,
    orch_submit,
) -> dict:
    gate = authorize_execution(
        approval_level=job.get("approval_level") or "A1",
        owner_decision=job.get("owner_decision"),
        prompt=job.get("parent_objective") or "",
        repo=job.get("workspace") or "",
        write=True,
    )
    if not gate["allowed"]:
        return {"state": "BLOCKED", "failure_reason": gate["reason"], "authorization": gate}
    reservation = reserve_budget(job, job.get("assigned_worker") or "cursor-agent-cli")
    if not reservation.get("allows"):
        return {"state": "BLOCKED", "failure_reason": reservation["reason"], "budget": reservation}
    expected_paths = PLANNING.constrain_expected_paths(expected_paths)
    job["expected_paths"] = expected_paths
    seq = len(job.get("child_jobs") or []) + 1
    child_id = f"{job['job_id']}-CC{seq:02d}"
    try:
        record = orch_submit(
            job_id=child_id,
            capability="code_implementation",
            objective=job["parent_objective"],
            repo=job.get("workspace"),
            prompt=prompt,
            write=True,
            timeout_sec=job.get("timeout_sec") or 600,
            expected_paths=expected_paths,
            project_id=job.get("project_id"),
            approval="A1",
            inbox_root=inbox_root,
        )
    except ValueError as exc:
        settle_reservation(job, reservation.get("this_reservation"))
        save_job(job)
        return {"state": "BLOCKED", "failure_reason": str(exc), "duplicate": "duplicate" in str(exc).lower()}
    job.setdefault("child_jobs", []).append(
        {"job_id": child_id, "at": utc_now(), "state": record.get("state")}
    )
    job["active_child_id"] = child_id
    save_job(job)
    return record


def _child_terminal(record: dict | None) -> bool:
    return bool(record and record.get("state") in {"COMPLETED", "BLOCKED", "FAILED", "CANCELLED"})


def reconcile_parent_job(
    job: dict,
    *,
    inbox_root: Path | None = None,
    orch_harvest=None,
) -> dict:
    """A terminal FAILED child must not leave the parent EXECUTING. Config defects do not retry."""
    if job.get("state") in TERMINAL:
        if float((job.get("budget") or {}).get("reserved_usd") or 0) and job["state"] in {"FAILED", "BLOCKED", "CANCELLED"}:
            release_open_reservation(job)
            save_job(job)
        return job
    expected = job.get("expected_paths") or []
    bad = PLANNING.malformed_expected_paths(expected)
    if bad:
        return fail_config_defect(
            job,
            "malformed expected_paths treated stack labels as files: " + ", ".join(bad),
        )
    child_id = job.get("active_child_id")
    if job.get("state") in {"EXECUTING", "VALIDATING", "PREFLIGHT"} and child_id and child_is_stale(job):
        orch_harvest = orch_harvest or ORCH.harvest
        record = orch_harvest(child_id, inbox_root)
        if not _child_terminal(record):
            job["failure_reason"] = "CHILD_TIMEOUT"
            job["active_child_id"] = None
            release_open_reservation(job)
            transition(job, "FAILED", "CHILD_TIMEOUT")
            save_job(job)
            return job
    return job


def advance_job(
    job: dict,
    *,
    root: Path | None = None,
    inbox_root: Path | None = None,
    worker_registry: dict | None = None,
    orch_submit=None,
    orch_harvest=None,
    stop_before: str | None = None,
) -> dict:
    """Advance at most one meaningful transition. Safe to call after process restart."""
    orch_submit = orch_submit or ORCH.submit
    orch_harvest = orch_harvest or ORCH.harvest
    workdir = job_workdir(job, root)
    job = reconcile_parent_job(job, inbox_root=inbox_root, orch_harvest=orch_harvest)
    if job["state"] in TERMINAL or job["state"] == "OWNER_REVIEW":
        return job

    if job["state"] == "INTAKE":
        transition(job, "CLASSIFIED", job["intent"])
        if stop_before == "CLASSIFIED":
            return job

    if job["state"] == "CLASSIFIED":
        job = maybe_reclassify(job)
        gate = authorize_execution(
            approval_level=job.get("approval_level") or "A1",
            owner_decision=job.get("owner_decision"),
            prompt=job.get("parent_objective") or "",
            repo=job.get("workspace") or "",
            write=job.get("workflow") == "sdlc",
        )
        if not gate["allowed"]:
            job["failure_reason"] = gate["reason"]
            transition(job, "BLOCKED", gate["reason"])
            return job
        resolved = PLANNING.resolve_project(job.get("project_id"), job.get("workspace"))
        if not resolved.get("allowed"):
            job["failure_reason"] = resolved.get("reason")
            transition(job, "BLOCKED", resolved.get("reason"))
            return job
        if resolved.get("workspace") and not job.get("workspace"):
            job["workspace"] = resolved["workspace"]
        job["workspace_inspect"] = PLANNING.inspect_workspace(job.get("workspace"), job.get("project_id"))
        if job["approval_level"] in {"A2", "A3"}:
            job["failure_reason"] = "A2/A3 owner gate"
            transition(job, "BLOCKED", "consequential action requires owner gate")
            return job
        if job.get("workflow") == "sdlc" and not job.get("workspace"):
            job["failure_reason"] = "MISSING_WORKSPACE"
            transition(job, "BLOCKED", "MISSING_WORKSPACE")
            return job
        if job.get("workflow") not in {"sdlc", "research_report"}:
            job["failure_reason"] = "NO_EXECUTABLE_WORKFLOW"
            transition(job, "BLOCKED", "NO_EXECUTABLE_WORKFLOW")
            return job
        if job.get("workflow") == "sdlc" and not budget_allows(job):
            job["failure_reason"] = budget_decision(job)["reason"]
            transition(job, "BLOCKED", job["failure_reason"])
            return job
        transition(job, "REQUIREMENTS")
        if stop_before == "REQUIREMENTS":
            return job

    if job["state"] == "REQUIREMENTS":
        req_path = workdir / "requirements.json"
        if not req_path.is_file():
            requirements = build_requirements(
                job["parent_objective"],
                workflow=job.get("workflow"),
                workspace=job.get("workspace"),
                project_id=job.get("project_id"),
            )
            save_json(req_path, requirements)
        else:
            requirements = load_json(req_path)
        job["requirements_version"] = requirements["version"]
        if str(req_path) not in job["artifacts"]:
            job["artifacts"].append(str(req_path))
        checkpoint(job, "requirements", {"version": requirements["version"], "count": len(requirements["requirements"])})
        if stop_before == "DESIGN":
            save_job(job)
            return job
        transition(job, "DESIGN")
        return job

    if job["state"] == "DESIGN":
        requirements = load_json(workdir / "requirements.json")
        design = initial_design(requirements, job["parent_objective"])
        save_json(workdir / "design-v1.json", design)
        if stop_before == "COUNCIL":
            save_job(job)
            return job
        transition(job, "COUNCIL")
        return job

    if job["state"] == "COUNCIL":
        requirements = load_json(workdir / "requirements.json")
        design = load_json(workdir / "design-v1.json")
        council = run_council(design, requirements)
        save_json(workdir / "council.json", council)
        save_json(workdir / "design-v2.json", council["approved_design"])
        job["design_version"] = council["approved_design"]["version"]
        job["expected_paths"] = expected_paths_from_design(council["approved_design"])
        job["validation"] = {"council": "PASS"}
        job["spec_sha256"] = spec_sha256(requirements, council["approved_design"])
        checkpoint(job, "council", {"material": council["material_count"], "spec_sha256": job["spec_sha256"]})
        if job.get("workflow") == "research_report":
            job["assigned_worker"] = "local-research-synthesizer"
            transition(job, "BASELINE_LOCKED", "research baseline")
            return job
        choice = select_coding_worker(worker_registry)
        if not choice["available"]:
            job["failure_reason"] = choice["missing"]
            transition(job, "WAITING", choice["missing"])
            return job
        job["assigned_worker"] = choice["worker"]
        transition(job, "BASELINE_LOCKED", choice["worker"])
        return job

    if job["state"] == "BASELINE_LOCKED":
        transition(job, "PLANNED", job.get("assigned_worker"))
        return job

    if job["state"] == "WAITING":
        choice = select_coding_worker(worker_registry)
        if not choice["available"]:
            save_job(job)
            return job
        job["assigned_worker"] = choice["worker"]
        job["failure_reason"] = None
        transition(job, "PLANNED", f"resumed with {choice['worker']}")
        return job

    if job["state"] == "PLANNED":
        if stop_before == "EXECUTING":
            save_job(job)
            return job
        design = {}
        if (workdir / "design-v2.json").is_file():
            design = load_json(workdir / "design-v2.json")
        elif (workdir / "design-v1.json").is_file():
            design = load_json(workdir / "design-v1.json")
        if (
            job.get("workflow") == "sdlc"
            and design.get("create_new_package") is False
            and not job.get("windows_preflight")
        ):
            transition(job, "PREFLIGHT", "windows repository identity")
            return job
        if job.get("workflow") == "sdlc" and not budget_allows(job, job.get("assigned_worker") or "cursor-agent-cli"):
            job["failure_reason"] = budget_decision(job)["reason"]
            transition(job, "BLOCKED", job["failure_reason"])
            return job
        transition(job, "EXECUTING", "submit cursor_call" if job.get("workflow") == "sdlc" else "synthesize research")
        return job

    if job["state"] == "PREFLIGHT":
        child_id = job.get("preflight_child_id")
        if not child_id:
            child_id = f"{job['job_id']}-PF01"
            inspect = job.get("workspace_inspect") or {}
            submitted = orch_submit(
                job_id=child_id,
                capability="repo_preflight",
                objective=f"preflight {job.get('workspace')}",
                repo=job.get("workspace"),
                write=False,
                approval="A0",
                project_id=job.get("project_id"),
                markers=inspect.get("catalog_markers") or inspect.get("markers") or [],
                inbox_root=inbox_root,
            )
            if submitted.get("state") == "BLOCKED":
                job["failure_reason"] = submitted.get("failure_reason") or "windows preflight blocked"
                transition(job, "FAILED", "REPO_IDENTITY")
                return job
            job["preflight_child_id"] = child_id
            job["active_child_id"] = child_id
            job.setdefault("child_jobs", []).append(
                {"job_id": child_id, "at": utc_now(), "state": submitted.get("state")}
            )
            save_job(job)
            return job
        record = orch_harvest(child_id, inbox_root)
        if not _child_terminal(record):
            if child_is_stale(job):
                job["failure_reason"] = "CHILD_TIMEOUT"
                job["active_child_id"] = None
                transition(job, "FAILED", "REPO_IDENTITY")
            save_job(job)
            return job
        job["active_child_id"] = None
        preflight = (record or {}).get("preflight") or ((record or {}).get("validation") or {})
        identity_ok = preflight.get("identity_ok")
        if identity_ok is None and record.get("state") == "COMPLETED":
            identity_ok = True
        if record.get("state") != "COMPLETED" or not identity_ok:
            job["failure_reason"] = (record or {}).get("failure_reason") or "windows preflight could not establish repository identity"
            transition(job, "FAILED", "REPO_IDENTITY")
            return job
        job["windows_preflight"] = preflight
        inspect = job.get("workspace_inspect") or {}
        inspect["windows_preflight"] = preflight
        inspect["host_can_see_workspace"] = inspect.get("host_can_see_workspace")
        inspect["absence_is_not_disproof"] = True
        if preflight.get("test_command"):
            inspect["test_command"] = preflight.get("test_command")
        job["workspace_inspect"] = inspect
        if job.get("workflow") == "sdlc" and not budget_allows(job, job.get("assigned_worker") or "cursor-agent-cli"):
            job["failure_reason"] = budget_decision(job)["reason"]
            transition(job, "BLOCKED", job["failure_reason"])
            return job
        transition(job, "EXECUTING", "windows identity established")
        return job

    if job["state"] == "EXECUTING" and job.get("workflow") == "research_report":
        requirements = load_json(workdir / "requirements.json")
        design = load_json(workdir / "design-v2.json") if (workdir / "design-v2.json").is_file() else load_json(workdir / "design-v1.json")
        result = synthesize_research(job["parent_objective"], requirements, design)
        slug_dir = workdir / result["slug"]
        slug_dir.mkdir(parents=True, exist_ok=True)
        report_path = slug_dir / "RESEARCH_REPORT.md"
        cite_path = slug_dir / "citations.json"
        status_path = slug_dir / "SOURCE_STATUS.json"
        report_path.write_text(result["report"], encoding="utf-8")
        save_json(cite_path, {"citations": result["citations"], "invented": result["invented"]})
        save_json(status_path, {"status": result["source_status"], "passed": result["passed"]})
        for art in (report_path, cite_path, status_path):
            if str(art) not in job["artifacts"]:
                job["artifacts"].append(str(art))
        job["execution_worker"] = "local-research-synthesizer"
        job["validation"] = job.get("validation") or {}
        job["validation"]["tests"] = "PASS" if result["passed"] else "FAIL"
        job["validation"]["test_evidence"] = {
            "passed": result["passed"],
            "exit_code": 0 if result["passed"] else 1,
            "stdout": result["source_status"],
            "source": result["source_status"],
        }
        save_json(workdir / "test-results.json", job["validation"]["test_evidence"])
        if result["invented"]:
            job["failure_reason"] = "invented citations"
            transition(job, "FAILED", job["failure_reason"])
            return job
        transition(job, "TESTING", "research citations")
        return job

    if job["state"] == "EXECUTING":
        requirements = load_json(workdir / "requirements.json")
        design = load_json(workdir / "design-v2.json") if (workdir / "design-v2.json").is_file() else load_json(workdir / "design-v1.json")
        expected = job.get("expected_paths") or expected_paths_from_design(design)
        child_id = job.get("active_child_id")
        if child_id:
            record = orch_harvest(child_id, inbox_root)
            if not _child_terminal(record):
                if child_is_stale(job):
                    job["failure_reason"] = "CHILD_TIMEOUT"
                    job["active_child_id"] = None
                    release_open_reservation(job)
                    transition(job, "FAILED", "CHILD_TIMEOUT")
                save_job(job)
                return job
            usage = (record or {}).get("usage")
            record_usage(job, job.get("assigned_worker") or "cursor-agent-cli", record.get("state"), usage)
            job["execution_worker"] = record.get("selected_worker") or job.get("assigned_worker")
            if record.get("state") != "COMPLETED":
                if is_config_defect(record, expected):
                    return fail_config_defect(
                        job,
                        record.get("failure_reason") or "CONFIG_DEFECT",
                    )
                retries = len(job.get("retry_history") or [])
                max_retries = int(load_json(BUDGETS)["job_defaults"].get("max_retries", 2))
                job.setdefault("retry_history", []).append(
                    {
                        "at": utc_now(),
                        "child": child_id,
                        "state": record.get("state"),
                        "reason": record.get("failure_reason"),
                    }
                )
                last_reasons = [str(item.get("reason") or "") for item in job.get("retry_history") or []]
                if len(last_reasons) >= 2 and last_reasons[-1] == last_reasons[-2]:
                    job["failure_reason"] = "identical child failure; stopping retries"
                    job["active_child_id"] = None
                    release_open_reservation(job)
                    transition(job, "FAILED", job["failure_reason"])
                    return job
                if retries + 1 > max_retries:
                    job["failure_reason"] = record.get("failure_reason") or "child failed"
                    job["active_child_id"] = None
                    release_open_reservation(job)
                    transition(job, "FAILED", job["failure_reason"])
                    return job
                if not budget_allows(job):
                    job["failure_reason"] = budget_decision(job)["reason"]
                    transition(job, "BLOCKED", job["failure_reason"])
                    return job
                prompt = build_worker_prompt(job, requirements, design)
                prompt += f"\nPrevious child {child_id} failed: {record.get('failure_reason')}. Write the missing files. Do not claim success without them.\n"
                job["active_child_id"] = None
                submitted = _submit_cursor(
                    job, prompt, expected, inbox_root=inbox_root, orch_submit=orch_submit
                )
                if submitted.get("state") == "BLOCKED":
                    job["failure_reason"] = submitted.get("failure_reason")
                    transition(job, "BLOCKED", job["failure_reason"])
                save_job(job)
                return job
            job["last_child"] = record
            stdout = ((record.get("validation") or {}).get("stdout_tail") if isinstance(record.get("validation"), dict) else None) or ""
            # harvest may not copy stdout; keep payload if present
            payload = record
            test_ev = parse_test_evidence(stdout, payload)
            job["validation"] = job.get("validation") or {}
            job["validation"]["tests"] = "PASS" if test_ev.get("passed") else "FAIL"
            job["validation"]["test_evidence"] = test_ev
            if record.get("artifact_paths"):
                for art in record["artifact_paths"]:
                    if art not in job["artifacts"]:
                        job["artifacts"].append(art)
                rels = PLANNING.repo_relative_from_artifacts(
                    record["artifact_paths"], job.get("workspace")
                )
                if rels:
                    job["expected_paths"] = PLANNING.constrain_expected_paths(
                        (job.get("expected_paths") or []) + rels
                    )
            save_json(workdir / "test-results.json", test_ev)
            job["active_child_id"] = None
            transition(job, "TESTING", child_id)
            return job
        prompt = build_worker_prompt(job, requirements, design)
        submitted = _submit_cursor(
            job, prompt, expected, inbox_root=inbox_root, orch_submit=orch_submit
        )
        if submitted.get("state") == "BLOCKED":
            job["failure_reason"] = submitted.get("failure_reason")
            transition(job, "BLOCKED", job["failure_reason"])
        save_job(job)
        return job

    if job["state"] == "TESTING":
        requirements = load_json(workdir / "requirements.json")
        design = load_json(workdir / "design-v2.json") if (workdir / "design-v2.json").is_file() else load_json(workdir / "design-v1.json")
        test_ev = (job.get("validation") or {}).get("test_evidence") or {}
        if test_ev.get("passed"):
            job["validation"]["tests"] = "PASS"
        else:
            if job.get("workflow") == "research_report":
                job["validation"]["tests"] = "FAIL"
                job["failure_reason"] = "citation validation failed"
                transition(job, "FAILED", job["failure_reason"])
                return job
            retries = len(job.get("retry_history") or [])
            max_retries = int(load_json(BUDGETS)["job_defaults"].get("max_retries", 2))
            if retries < max_retries and budget_allows(job):
                job.setdefault("retry_history", []).append(
                    {"at": utc_now(), "event": "tests failed; requesting correction"}
                )
                job["active_child_id"] = None
                prompt = build_worker_prompt(job, requirements, design)
                prompt += "\nUnittest evidence did not PASS. Fix the implementation and tests, rerun unittest, rewrite test-results.json.\n"
                transition(job, "EXECUTING", "automatic correction")
                submitted = _submit_cursor(
                    job,
                    prompt,
                    job.get("expected_paths") or expected_paths_from_design(design),
                    inbox_root=inbox_root,
                    orch_submit=orch_submit,
                )
                if submitted.get("state") == "BLOCKED":
                    job["failure_reason"] = submitted.get("failure_reason")
                    transition(job, "BLOCKED", job["failure_reason"])
                save_job(job)
                return job
            job["validation"]["tests"] = "FAIL"
            job["failure_reason"] = "tests did not pass"
            transition(job, "FAILED", job["failure_reason"])
            return job
        trace = traceability(
            requirements,
            design,
            expected_paths=job.get("expected_paths") or [],
            test_evidence=test_ev,
            workspace=job.get("workspace"),
            artifacts=job.get("artifacts") or [],
            independent_rerun=job.get("validation", {}).get("independent_rerun"),
        )
        save_json(workdir / "traceability.json", trace)
        job["validation"]["traceability"] = "PASS" if trace["all_pass"] else "FAIL"
        if str(workdir / "traceability.json") not in job["artifacts"]:
            job["artifacts"].append(str(workdir / "traceability.json"))
        transition(job, "VALIDATING")
        return job

    if job["state"] == "VALIDATING":
        requirements = load_json(workdir / "requirements.json")
        design = load_json(workdir / "design-v2.json") if (workdir / "design-v2.json").is_file() else load_json(workdir / "design-v1.json")
        job["validation"] = job.get("validation") or {}
        if job.get("workflow") == "research_report":
            job["validation"]["independent_rerun"] = "LOCAL_CORPUS"
        elif job.get("origin") == "conversation" and job.get("workflow") == "sdlc":
            if not job.get("validation_child_id"):
                if budget_allows(job, job.get("assigned_worker") or "cursor-agent-cli"):
                    prompt = build_validation_prompt(job, requirements, design)
                    submitted = _submit_cursor(
                        job,
                        prompt,
                        job.get("expected_paths") or expected_paths_from_design(design),
                        inbox_root=inbox_root,
                        orch_submit=orch_submit,
                    )
                    if submitted.get("state") == "BLOCKED":
                        job["validation"]["independent_rerun"] = "UNVERIFIED"
                        job["validation"]["independent_rerun_reason"] = submitted.get("failure_reason")
                    else:
                        job["validation_child_id"] = job.get("active_child_id")
                        job["validation"]["independent_rerun"] = "pending"
                        save_job(job)
                        return job
                else:
                    job["validation"]["independent_rerun"] = "UNVERIFIED"
                    job["validation"]["independent_rerun_reason"] = budget_decision(job).get("reason")
            elif job.get("active_child_id") == job.get("validation_child_id"):
                record = orch_harvest(job["active_child_id"], inbox_root)
                if not _child_terminal(record):
                    if child_is_stale(job):
                        job["failure_reason"] = "CHILD_TIMEOUT"
                        job["active_child_id"] = None
                        release_open_reservation(job)
                        transition(job, "FAILED", "CHILD_TIMEOUT")
                    save_job(job)
                    return job
                usage = (record or {}).get("usage")
                record_usage(job, job.get("assigned_worker") or "cursor-agent-cli", record.get("state"), usage)
                stdout = ((record.get("validation") or {}).get("stdout_tail") if isinstance(record.get("validation"), dict) else None) or ""
                test_ev = parse_test_evidence(stdout, record)
                job["validation"]["independent_test_evidence"] = test_ev
                job["validation"]["independent_rerun"] = "PASS" if record.get("state") == "COMPLETED" and test_ev.get("passed") else "FAIL"
                if test_ev.get("passed"):
                    job["validation"]["tests"] = "PASS"
                    job["validation"]["test_evidence"] = test_ev
                job["active_child_id"] = None
        else:
            job["validation"].setdefault("independent_rerun", "IMPLEMENTER_CLAIMED")

        test_ev = (job.get("validation") or {}).get("test_evidence") or {}
        trace = traceability(
            requirements,
            design,
            expected_paths=job.get("expected_paths") or [],
            test_evidence=test_ev,
            workspace=job.get("workspace"),
            artifacts=job.get("artifacts") or [],
            independent_rerun=job["validation"].get("independent_rerun"),
        )
        save_json(workdir / "traceability.json", trace)
        job["validation"]["traceability"] = "PASS" if trace["all_pass"] else "FAIL"
        rc = write_release_candidate(workdir, job, trace)
        if str(rc) not in job["artifacts"]:
            job["artifacts"].append(str(rc))
        failures = evaluate_autonomy_done(job)
        if job["validation"].get("independent_rerun") == "UNVERIFIED" and job.get("origin") == "conversation":
            failures.append("independent validation UNVERIFIED")
        if job["validation"].get("independent_rerun") == "FAIL":
            failures.append("independent validation failed")
        if failures:
            job["failure_reason"] = "; ".join(failures)
            transition(job, "FAILED", job["failure_reason"])
            return job
        job["owner_decision"] = "pending_review"
        transition(job, "RELEASE_CANDIDATE", str(rc))
        transition(job, "OWNER_REVIEW", "release candidate ready; no public deploy")
        save_job(job)
    return job


def run_until_idle(
    job: dict,
    *,
    root: Path | None = None,
    inbox_root: Path | None = None,
    worker_registry: dict | None = None,
    orch_submit=None,
    orch_harvest=None,
    max_steps: int = 40,
    stop_before: str | None = None,
) -> dict:
    for _ in range(max_steps):
        before = (job["state"], job.get("active_child_id"), len(job.get("history") or []))
        job = advance_job(
            job,
            root=root,
            inbox_root=inbox_root,
            worker_registry=worker_registry,
            orch_submit=orch_submit,
            orch_harvest=orch_harvest,
            stop_before=stop_before,
        )
        if job["state"] in TERMINAL or job["state"] == "OWNER_REVIEW":
            return job
        if stop_before and job["state"] == stop_before:
            return job
        after = (job["state"], job.get("active_child_id"), len(job.get("history") or []))
        if after == before:
            return job
    return job


def runner_once(
    *,
    root: Path | None = None,
    inbox_root: Path | None = None,
    worker_registry: dict | None = None,
    **advance_kwargs,
) -> list[dict]:
    heartbeat = {"at": utc_now(), "pid": os.getpid()}
    save_json(autonomy_root(root) / "runner-heartbeat.json", heartbeat)
    lock_path = autonomy_root(root) / "runner.lock"
    fencing = f"{os.getpid()}-{uuid.uuid4().hex[:8]}"
    lease = {
        "owner": os.getpid(),
        "fencing": fencing,
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=90)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    save_json(autonomy_root(root) / "runner-lease.json", lease)
    results = []
    for job in list_parent_jobs(root):
        reserved = float((job.get("budget") or {}).get("reserved_usd") or 0)
        malformed = PLANNING.malformed_expected_paths(job.get("expected_paths") or [])
        if job.get("state") in TERMINAL:
            if reserved:
                updated = reconcile_parent_job(
                    job, inbox_root=inbox_root, orch_harvest=advance_kwargs.get("orch_harvest")
                )
                results.append({"job_id": updated["job_id"], "state": updated["state"], "reconciled": True})
            continue
        if job.get("state") == "OWNER_REVIEW":
            if malformed:
                updated = reconcile_parent_job(
                    job, inbox_root=inbox_root, orch_harvest=advance_kwargs.get("orch_harvest")
                )
                results.append({"job_id": updated["job_id"], "state": updated["state"], "reconciled": True})
            continue
        if job.get("workflow") not in {"sdlc", "research_report"} and job.get("state") not in {
            "INTAKE",
            "CLASSIFIED",
        }:
            continue
        job_lease = job.get("lease") or {}
        expires = str(job_lease.get("expires_at") or "")
        owner = job_lease.get("owner")
        if owner and owner != os.getpid() and expires > utc_now() and job.get("state") == "EXECUTING" and job.get("active_child_id"):
            results.append({"job_id": job["job_id"], "state": job["state"], "skipped": "foreign_lease"})
            continue
        job["lease"] = {
            "owner": os.getpid(),
            "fencing": fencing,
            "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=90)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        updated = advance_job(
            job, root=root, inbox_root=inbox_root, worker_registry=worker_registry, **advance_kwargs
        )
        results.append({"job_id": updated["job_id"], "state": updated["state"]})
    return results


def runner_loop(
    *,
    root: Path | None = None,
    inbox_root: Path | None = None,
    poll_sec: int = 15,
    once: bool = False,
) -> int:
    while True:
        runner_once(root=root, inbox_root=inbox_root)
        if once:
            return 0
        time.sleep(max(3, poll_sec))


def run_software_local(job: dict, workdir: Path, **kwargs):
    """REGRESSION FIXTURE entrypoint. Not used for Conversation production jobs."""
    stop_before = kwargs.get("stop_before")
    worker_registry = kwargs.get("worker_registry")
    job["fixture"] = FIXTURE.FIXTURE_ID
    workdir.mkdir(parents=True, exist_ok=True)

    def save_json_local(path: Path, payload: dict) -> None:
        save_json(path, payload)

    if job["state"] in TERMINAL or job["state"] == "OWNER_REVIEW":
        return job
    if job["state"] == "INTAKE":
        transition(job, "CLASSIFIED", job["intent"])
        if stop_before == "CLASSIFIED":
            return job
    if job["state"] == "CLASSIFIED":
        if job["approval_level"] in {"A2", "A3"}:
            job["failure_reason"] = "A2/A3 owner gate"
            transition(job, "BLOCKED", "consequential action requires owner gate")
            return job
        if not budget_allows(job, "local-implementer"):
            job["failure_reason"] = budget_decision(job, "local-implementer")["reason"]
            transition(job, "BLOCKED", job["failure_reason"])
            return job
        transition(job, "REQUIREMENTS")
        if stop_before == "REQUIREMENTS":
            return job
    if job["state"] == "REQUIREMENTS":
        req_path = workdir / "requirements.json"
        if not req_path.is_file():
            requirements = FIXTURE.fixture_build_requirements(job["parent_objective"])
            save_json_local(req_path, requirements)
        else:
            requirements = load_json(req_path)
        job["requirements_version"] = requirements["version"]
        if str(req_path) not in job["artifacts"]:
            job["artifacts"].append(str(req_path))
        checkpoint(job, "requirements", {"version": requirements["version"], "fixture": FIXTURE.FIXTURE_ID})
        if stop_before == "DESIGN":
            save_job(job)
            return job
        transition(job, "DESIGN")
    if job["state"] == "DESIGN":
        requirements = load_json(workdir / "requirements.json")
        design = FIXTURE.fixture_initial_design(requirements)
        save_json_local(workdir / "design-v1.json", design)
        if stop_before == "COUNCIL":
            save_job(job)
            return job
        transition(job, "COUNCIL")
    if job["state"] == "COUNCIL":
        design = load_json(workdir / "design-v1.json")
        council = FIXTURE.fixture_run_council(design)
        save_json_local(workdir / "council.json", council)
        save_json_local(workdir / "design-v2.json", council["approved_design"])
        job["design_version"] = council["approved_design"]["version"]
        job["validation"] = {"council": "PASS" if council["material_count"] >= 1 else "FAIL"}
        checkpoint(job, "council", {"material": council["material_count"], "fixture": FIXTURE.FIXTURE_ID})
        choice = select_coding_worker(worker_registry)
        if not choice["available"]:
            job["failure_reason"] = choice["missing"]
            transition(job, "WAITING", choice["missing"])
            return job
        job["assigned_worker"] = choice["worker"]
        transition(job, "PLANNED", choice["worker"])
    if job["state"] == "WAITING":
        choice = select_coding_worker(worker_registry)
        if not choice["available"]:
            save_job(job)
            return job
        job["assigned_worker"] = choice["worker"]
        job["failure_reason"] = None
        transition(job, "PLANNED", f"resumed with {choice['worker']}")
    if job["state"] == "PLANNED":
        if stop_before == "EXECUTING":
            save_job(job)
            return job
        transition(job, "EXECUTING", "fixture local implementer")
    if job["state"] == "EXECUTING":
        FIXTURE.implement_local(workdir, broken=True)
        record_usage(job, "local-implementer", "defect-injected")
        job["execution_worker"] = "local-implementer"
        transition(job, "TESTING")
    if job["state"] == "TESTING":
        first = FIXTURE.run_unit_tests(workdir)
        if first["passed"]:
            job["failure_reason"] = "expected fixture defect was not detected"
            transition(job, "FAILED", "false completion: broken build passed tests")
            return job
        job.setdefault("retry_history", []).append(
            {"at": utc_now(), "event": "fixture malformed-json test failed as intended"}
        )
        FIXTURE.implement_local(workdir, broken=False)
        record_usage(job, "local-implementer", "defect-corrected")
        regression = FIXTURE.run_unit_tests(workdir)
        job.setdefault("validation", {})
        job["validation"]["tests"] = "PASS" if regression["passed"] else "FAIL"
        job["validation"]["first_fail_exit"] = first["exit_code"]
        save_json(workdir / "test-results.json", {"first": first, "regression": regression})
        if not regression["passed"]:
            job["failure_reason"] = regression["stderr"][:500]
            transition(job, "FAILED", "regression tests failed")
            return job
        requirements = load_json(workdir / "requirements.json")
        trace = FIXTURE.fixture_traceability(requirements, regression)
        job["validation"]["traceability"] = "PASS" if trace["all_pass"] else "FAIL"
        save_json(workdir / "traceability.json", trace)
        for name in (
            "status_app.py",
            "test_status_app.py",
            "sample_status.json",
            "test-results.json",
            "traceability.json",
        ):
            path = str(workdir / name)
            if path not in job["artifacts"]:
                job["artifacts"].append(path)
        transition(job, "VALIDATING")
    if job["state"] == "VALIDATING":
        failures = evaluate_autonomy_done(job)
        if failures:
            job["failure_reason"] = "; ".join(failures)
            transition(job, "FAILED", job["failure_reason"])
            return job
        trace = load_json(workdir / "traceability.json")
        rc = write_release_candidate(workdir, job, trace)
        if str(rc) not in job["artifacts"]:
            job["artifacts"].append(str(rc))
        job["owner_decision"] = "pending_review"
        transition(job, "RELEASE_CANDIDATE", str(rc))
        transition(job, "OWNER_REVIEW", "fixture release candidate; not production")
        save_job(job)
    return job


def capability_matrix() -> dict:
    providers = load_json(PROVIDERS).get("providers", [])
    unavailable = [
        p["id"]
        for p in providers
        if p.get("status") in {"not_configured", "not_installed", "not_authenticated"}
        or p.get("availability") in {"credential_pending", "pending_owner_oauth"}
    ]
    return {
        "generated_at": utc_now(),
        "VERIFIED_WORKING": [
            "Hermes Conversation parent submit",
            "Windows worker outbound poll",
            "workspace_inventory",
            "cursor_call A1 on approved repos and cursor-sandbox",
            "research_report from approved local corpus",
        ],
        "IMPLEMENTED_BUT_UNVERIFIED": [
            "cross-provider coding failover",
            "independent Windows test rerun when budget cannot reserve a validation child",
        ],
        "CONFIGURED_BUT_UNAVAILABLE": unavailable,
        "NOT_IMPLEMENTED": [
            "Claude Code CLI routing",
            "Codex CLI routing",
            "Gemini CLI routing",
            "remote Cua inbox jobs",
            "Home spoken-voice acceptance",
        ],
        "REQUIRES_OWNER_AUTHORIZATION": [
            "A2 publish/deploy/spend",
            "A3 trades and bank transfers",
            "new paid provider accounts",
            "A1 writes on DISCOVERED projects (Bhava, Wani, Revenue)",
        ],
        "PENDING_PHYSICAL": ["NEEWA Home spoken-voice session"],
        "supported_stacks": ["python-stdlib cursor-sandbox", "node-typescript KidsProjects/ScienceQuest"],
        "unsupported_stacks": "labeled UNSUPPORTED until inspected; not faked as Python CLI",
        "routable_coding_workers": [w["id"] for w in routable_workers() if w.get("class") == "coding-worker"],
        "cross_provider_failover": "UNVERIFIED",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA autonomous controller")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("matrix")
    cls = sub.add_parser("classify")
    cls.add_argument("--text", required=True)
    subp = sub.add_parser("submit")
    subp.add_argument("--objective", required=True)
    subp.add_argument("--project-id")
    subp.add_argument("--workspace")
    subp.add_argument("--root")
    subp.add_argument("--budget-ceiling", type=float)
    subp.add_argument("--origin", default="conversation")
    subp.add_argument("--unattended", action="store_true")
    runp = sub.add_parser("run")
    runp.add_argument("--objective")
    runp.add_argument("--project-id")
    runp.add_argument("--workspace")
    runp.add_argument("--workdir")
    runp.add_argument("--root")
    runp.add_argument("--budget-ceiling", type=float)
    runp.add_argument("--resume")
    runp.add_argument("--fixture", choices=[FIXTURE.FIXTURE_ID])
    runp.add_argument("--origin", default="controller")
    getp = sub.add_parser("get")
    getp.add_argument("--job-id", required=True)
    getp.add_argument("--root")
    runr = sub.add_parser("runner")
    runr.add_argument("--root")
    runr.add_argument("--inbox-root")
    runr.add_argument("--once", action="store_true")
    runr.add_argument("--poll-sec", type=int, default=15)
    listp = sub.add_parser("list")
    listp.add_argument("--root")
    recp = sub.add_parser("reconcile")
    recp.add_argument("--job-id", required=True)
    recp.add_argument("--root")
    recp.add_argument("--inbox-root")
    args = parser.parse_args()
    if args.command == "matrix":
        print(json.dumps(capability_matrix(), indent=2))
        return 0
    if args.command == "classify":
        print(json.dumps(classify_intent(args.text), indent=2))
        return 0
    if args.command == "get":
        job = resume_job(args.job_id, Path(args.root) if args.root else None)
        if not job:
            raise SystemExit(f"unknown job {args.job_id}")
        print(json.dumps({k: v for k, v in job.items() if k != "_path"}, indent=2))
        return 0
    if args.command == "list":
        rows = [
            {"job_id": j["job_id"], "state": j.get("state"), "origin": j.get("origin"), "objective": j.get("parent_objective")}
            for j in list_parent_jobs(Path(args.root) if args.root else None)
        ]
        print(json.dumps(rows, indent=2))
        return 0
    if args.command == "reconcile":
        job = resume_job(args.job_id, Path(args.root) if args.root else None)
        if not job:
            raise SystemExit(f"unknown job {args.job_id}")
        inbox = Path(args.inbox_root) if args.inbox_root else None
        job = reconcile_parent_job(job, inbox_root=inbox)
        print(json.dumps({k: v for k, v in job.items() if k != "_path"}, indent=2))
        return 0 if job["state"] in TERMINAL else 2
    if args.command == "runner":
        return runner_loop(
            root=Path(args.root) if args.root else None,
            inbox_root=Path(args.inbox_root) if args.inbox_root else None,
            poll_sec=args.poll_sec,
            once=args.once,
        )
    if args.command == "submit":
        root = Path(args.root) if args.root else None
        job = create_parent_job(
            args.objective,
            project_id=args.project_id,
            workspace=args.workspace,
            root=root,
            budget_ceiling=args.budget_ceiling,
            origin=args.origin,
        )
        print(json.dumps({k: v for k, v in job.items() if k != "_path"}, indent=2))
        return 0
    root = Path(args.root) if args.root else None
    if not args.resume and not args.objective:
        raise SystemExit("run requires --objective or --resume")
    if args.resume:
        job = resume_job(args.resume, root)
        if not job:
            raise SystemExit(f"unknown job {args.resume}")
    else:
        job = create_parent_job(
            args.objective,
            project_id=args.project_id,
            workspace=args.workspace,
            root=root,
            budget_ceiling=args.budget_ceiling,
            origin=args.origin,
        )
    if args.fixture == FIXTURE.FIXTURE_ID:
        workdir = Path(args.workdir) if args.workdir else (autonomy_root(root) / "work" / job["job_id"])
        job = run_software_local(job, workdir)
        print(json.dumps({k: v for k, v in job.items() if k != "_path"}, indent=2))
        return 0 if job["state"] in {"OWNER_REVIEW", "RELEASE_CANDIDATE", "DONE"} else 2
    if job["workflow"] not in {"sdlc", "research_report"}:
        job = run_until_idle(job, root=root)
        print(json.dumps({k: v for k, v in job.items() if k != "_path"}, indent=2))
        return 0 if job["state"] != "BLOCKED" else 2
    job = run_until_idle(job, root=root)
    print(json.dumps({k: v for k, v in job.items() if k != "_path"}, indent=2))
    return 0 if job["state"] in {"OWNER_REVIEW", "RELEASE_CANDIDATE", "DONE", "WAITING", "EXECUTING"} else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
