"""NEEWA Conversation orchestration for the existing Windows job inbox.

Creates durable job records, routes to a verified worker, and tracks states:
QUEUED -> DISPATCHED -> RUNNING -> VALIDATING -> COMPLETED
exceptions: BLOCKED, FAILED, CANCELLED.

Does not open a listener and does not execute caller-supplied shell.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INBOX_MOD = SourceFileLoader(
    "windows_job_inbox", str(ROOT / "12_SCRIPTS" / "windows_job_inbox.py")
).load_module()
WORKERS_PATH = ROOT / "11_CONFIG" / "workers.json"
PROJECTS_PATH = ROOT / "11_CONFIG" / "projects.json"

STATES = (
    "QUEUED",
    "DISPATCHED",
    "RUNNING",
    "WAITING",
    "VALIDATING",
    "COMPLETED",
    "BLOCKED",
    "FAILED",
    "CANCELLED",
)
TERMINAL = {"COMPLETED", "BLOCKED", "FAILED", "CANCELLED"}

CAPABILITY_ROUTE = {
    "code_implementation": {
        "worker": "cursor-agent-cli",
        "action": "cursor_call",
        "approval": "A1",
    },
    "code_review": {
        "worker": "cursor-agent-cli",
        "action": "cursor_call",
        "approval": "A1",
        "write": False,
    },
    "project_inventory": {
        "worker": "neewa-windows-worker",
        "action": "workspace_inventory",
        "approval": "A0",
    },
    "host_status": {
        "worker": "neewa-windows-worker",
        "action": "ping",
        "approval": "A0",
    },
    "gui_operation": {
        "worker": "cua-driver",
        "action": None,
        "approval": "A1",
        "available": False,
        "missing": "remote Cua GUI jobs are not queued through this inbox; local cua-driver is interactive-session only",
    },
    "repo_preflight": {
        "worker": "neewa-windows-worker",
        "action": "repo_preflight",
        "approval": "A0",
        "write": False,
    },
    "scoped_repair_workspace": {
        "worker": "neewa-windows-worker",
        "action": "create_scoped_repair_workspace",
        "approval": "A1",
    },
    "scoped_repair_review": {
        "worker": "neewa-windows-worker",
        "action": "review_scoped_repair_patch",
        "approval": "A0",
        "write": False,
    },
    "scoped_repair_apply": {
        "worker": "neewa-windows-worker",
        "action": "apply_scoped_repair_patch",
        "approval": "A1",
    },
    "scoped_repair_cleanup": {
        "worker": "neewa-windows-worker",
        "action": "cleanup_scoped_repair_workspace",
        "approval": "A1",
    },
    "git_push_feature_branch": {
        "worker": "neewa-windows-worker",
        "action": "git_push_feature_branch",
        "approval": "A2",
    },
    "git_verify_remote_state": {
        "worker": "neewa-windows-worker",
        "action": "git_verify_remote_state",
        "approval": "A0",
        "write": False,
    },
    "git_create_pull_request": {
        "worker": "neewa-windows-worker",
        "action": "git_create_pull_request",
        "approval": "A2",
    },
    "git_merge_approved_pull_request": {
        "worker": "neewa-windows-worker",
        "action": "git_merge_approved_pull_request",
        "approval": "A2",
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def records_root(inbox_root: Path | None = None) -> Path:
    root = inbox_root if inbox_root is not None else INBOX_MOD.resolve_inbox_root()
    path = root / "records"
    path.mkdir(parents=True, exist_ok=True)
    return path


def load_workers() -> dict:
    return json.loads(WORKERS_PATH.read_text(encoding="utf-8"))


def load_projects() -> dict:
    return json.loads(PROJECTS_PATH.read_text(encoding="utf-8"))


def new_job_id(prefix: str = "ORCH") -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"JOB-{stamp}-{prefix}"


def record_path(job_id: str, inbox_root: Path | None = None) -> Path:
    return records_root(inbox_root) / f"{job_id}.json"


def load_record(job_id: str, inbox_root: Path | None = None) -> dict | None:
    path = record_path(job_id, inbox_root)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_record(record: dict, inbox_root: Path | None = None) -> Path:
    path = record_path(record["job_id"], inbox_root)
    path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return path


def append_state(record: dict, state: str, evidence: str | None = None) -> None:
    if state not in STATES:
        raise ValueError(f"unknown state {state}")
    now = utc_now()
    record["state"] = state
    record["updated_at"] = now
    if state in {"DISPATCHED", "RUNNING"} and not record.get("started_at"):
        record["started_at"] = now
    if state in TERMINAL:
        record["completed_at"] = now
    history = record.setdefault("history", [])
    entry = {"state": state, "at": now}
    if evidence:
        entry["evidence"] = evidence
    history.append(entry)


def select_worker(capability: str) -> dict:
    route = CAPABILITY_ROUTE.get(capability)
    if not route:
        return {
            "available": False,
            "missing": f"no verified worker for capability '{capability}'",
        }
    if route.get("available") is False:
        return dict(route)
    workers = load_workers()
    wanted = route["worker"]
    match = next((w for w in workers.get("workers", []) if w.get("id") == wanted), None)
    if not match or match.get("status") not in {
        "verified",
        "active",
        "active-local-worker",
        "auth-pending",
        "available",
    }:
        if match and match.get("status") in {"auth-required", "AUTH_REQUIRED"}:
            return {
                "available": False,
                "worker": wanted,
                "missing": "AUTH_REQUIRED",
                "action": route.get("action"),
            }
        if not match:
            return {
                "available": False,
                "worker": wanted,
                "missing": f"worker '{wanted}' is not in the registry",
            }
    return {
        "available": True,
        "worker": wanted,
        "action": route["action"],
        "approval": route.get("approval", "A1"),
        "write": route.get("write"),
        "registry_status": match.get("status") if match else None,
    }


def resolve_project(project_id: str | None, repo: str | None) -> dict | None:
    data = load_projects()
    if project_id:
        for row in data.get("projects", []):
            if row.get("id") == project_id:
                return row
    if repo:
        repo_norm = str(Path(repo))
        for row in data.get("projects", []):
            ws = row.get("workspace_path")
            if ws and str(Path(ws)).lower() == repo_norm.lower():
                return row
            name = row.get("workspace_name")
            if name and repo_norm.replace("\\", "/").rstrip("/").endswith(name):
                return row
    return None


def create_record(
    *,
    job_id: str,
    objective: str,
    capability: str,
    approval: str,
    project_id: str | None,
    workspace: str | None,
    selected_worker: str | None,
    action: str | None,
    inbox_root: Path | None = None,
) -> dict:
    existing = load_record(job_id, inbox_root)
    if existing and existing.get("state") not in TERMINAL:
        raise ValueError(f"duplicate job_id {job_id} is already {existing.get('state')}")
    if existing and existing.get("state") in TERMINAL:
        return existing
    record = {
        "schema_version": 1,
        "job_id": job_id,
        "project_id": project_id,
        "objective": objective,
        "required_capability": capability,
        "selected_worker": selected_worker,
        "workspace": workspace,
        "approval_level": approval,
        "action": action,
        "state": "QUEUED",
        "started_at": None,
        "completed_at": None,
        "artifact_paths": [],
        "validation": None,
        "failure_reason": None,
        "public_listener": False,
        "unrestricted_shell": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "history": [{"state": "QUEUED", "at": utc_now()}],
    }
    save_record(record, inbox_root)
    return record


def existing_inbox_job(job_id: str, root: Path) -> Path | None:
    for folder in ("inbox", "processing", "done", "failed"):
        path = root / folder / f"{job_id}.json"
        if path.is_file():
            return path
    return None


def submit(
    *,
    job_id: str | None,
    capability: str,
    objective: str,
    repo: str | None = None,
    prompt: str | None = None,
    write: bool = False,
    timeout_sec: int | None = None,
    expected_paths: list[str] | None = None,
    project_id: str | None = None,
    approval: str | None = None,
    inbox_root: Path | None = None,
    markers: list[str] | None = None,
    project_lifecycle: str | None = None,
    workspace_root: str | None = None,
    execution_phase: str | None = None,
    bootstrap_complete: bool | None = None,
    implementation_completed: bool | None = None,
    implementation_child_id: str | None = None,
    implementation_repo: str | None = None,
    test_command: str | None = None,
    files: list[str] | None = None,
    expected_base_sha: str | None = None,
    repository_id: str | None = None,
    operation_id: str | None = None,
) -> dict:
    choice = select_worker(capability)
    if not choice.get("available"):
        job_id = job_id or new_job_id("MISS")
        record = create_record(
            job_id=job_id,
            objective=objective,
            capability=capability,
            approval=approval or "A0",
            project_id=project_id,
            workspace=repo,
            selected_worker=choice.get("worker"),
            action=choice.get("action"),
            inbox_root=inbox_root,
        )
        record["failure_reason"] = choice.get("missing") or "worker unavailable"
        append_state(record, "BLOCKED", record["failure_reason"])
        save_record(record, inbox_root)
        return record

    action = choice["action"]
    approval = approval or choice.get("approval") or "A1"
    if action == "cursor_call" and not prompt:
        raise ValueError("cursor_call requires a prompt")
    if action == "cursor_call" and not repo:
        raise ValueError("cursor_call requires an approved repo")
    if action == "create_scoped_repair_workspace":
        if not repo:
            raise ValueError("create_scoped_repair_workspace requires an approved repo")
        if not files:
            raise ValueError("create_scoped_repair_workspace requires files")
        if not expected_base_sha:
            raise ValueError("create_scoped_repair_workspace requires expected_base_sha")

    project = resolve_project(project_id, repo)
    job_id = job_id or new_job_id("CC" if action == "cursor_call" else "WS")
    root = inbox_root if inbox_root is not None else INBOX_MOD.resolve_inbox_root()
    prior = existing_inbox_job(job_id, root)
    if prior:
        raise ValueError(f"duplicate job_id {job_id} already exists at {prior}")
    existing_record = load_record(job_id, inbox_root)
    if existing_record and existing_record.get("state") in TERMINAL:
        return existing_record
    if existing_record and existing_record.get("state") not in TERMINAL:
        raise ValueError(f"duplicate job_id {job_id} is already {existing_record.get('state')}")

    record = create_record(
        job_id=job_id,
        objective=objective,
        capability=capability,
        approval=approval,
        project_id=(project or {}).get("id") or project_id,
        workspace=repo or (project or {}).get("workspace_path"),
        selected_worker=choice["worker"],
        action=action,
        inbox_root=inbox_root,
    )
    extra = {
        "objective": objective,
        "required_capability": capability,
        "selected_worker": choice["worker"],
        "project_id": record["project_id"],
        "state": "QUEUED",
    }
    if repo:
        extra["repo"] = repo
    if prompt:
        extra["prompt"] = prompt
    if timeout_sec is not None:
        # Preserve timeout_sec=0 (unlimited; no elapsed-time kill on the worker).
        extra["timeout_sec"] = timeout_sec
    if expected_paths:
        extra["expected_paths"] = expected_paths
    if markers:
        extra["markers"] = markers
    if project_lifecycle:
        extra["project_lifecycle"] = project_lifecycle
    if workspace_root:
        extra["workspace_root"] = workspace_root
    if execution_phase:
        extra["execution_phase"] = execution_phase
    if bootstrap_complete:
        extra["bootstrap_complete"] = True
    if implementation_completed:
        extra["implementation_completed"] = True
    if implementation_child_id:
        extra["implementation_child_id"] = implementation_child_id
    if implementation_repo:
        extra["implementation_repo"] = implementation_repo
    if test_command:
        extra["test_command"] = test_command
    if files:
        extra["files"] = files
    if expected_base_sha:
        extra["expected_base_sha"] = expected_base_sha
    if repository_id:
        extra["repository_id"] = repository_id
    if operation_id:
        extra["operation_id"] = operation_id
    extra["write"] = bool(write)

    path = INBOX_MOD.enqueue(job_id, action, approval, root, extra)
    append_state(record, "DISPATCHED", str(path))
    record["inbox_path"] = str(path)
    save_record(record, inbox_root)
    return record


def inspect_folders(job_id: str, root: Path) -> tuple[str | None, dict | None]:
    for folder, inferred in (
        ("inbox", "QUEUED"),
        ("processing", "RUNNING"),
        ("done", "VALIDATING"),
        ("failed", "FAILED"),
    ):
        path = root / folder / f"{job_id}.json"
        if path.is_file():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                payload = {}
            sidecar = root / folder / f"{job_id}-cursor-call.json"
            if sidecar.is_file():
                try:
                    extra = json.loads(sidecar.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    extra = {}
                if isinstance(extra, dict):
                    for key in (
                        "stdout_tail",
                        "usage",
                        "artifact_paths",
                        "status",
                        "reason",
                        "failure_class",
                        "preflight",
                        "authorization",
                        "cli",
                        "exit_code",
                        "duration_sec",
                        "project_lifecycle",
                        "bootstrap",
                        "repo",
                        "execution_phase",
                        "independent_test",
                        "test_results",
                        "cursor_started",
                        "stdout_tail",
                    ):
                        if extra.get(key) not in (None, "", []):
                            payload[key] = extra[key]
            return inferred, payload
    return None, None


def harvest(job_id: str, inbox_root: Path | None = None) -> dict | None:
    record = load_record(job_id, inbox_root)
    if not record:
        return None
    root = inbox_root if inbox_root is not None else INBOX_MOD.resolve_inbox_root()
    folder, payload = inspect_folders(job_id, root)
    if not payload:
        return record
    status = str(payload.get("status") or "").upper()
    if status == "COMPLETE":
        status = "COMPLETED"
    if folder == "QUEUED":
        if record["state"] == "QUEUED":
            pass
        return record
    if folder == "RUNNING" and record["state"] not in TERMINAL:
        if record["state"] != "RUNNING":
            append_state(record, "RUNNING", "windows-jobs/processing")
            save_record(record, inbox_root)
        return record
    if folder in {"VALIDATING", "FAILED"} and status in TERMINAL:
        if record["state"] != "VALIDATING" and status == "COMPLETED":
            append_state(record, "VALIDATING", "windows-jobs/done")
        reason = payload.get("reason")
        artifacts = []
        if payload.get("artifact"):
            artifacts.append(payload["artifact"])
        for key in ("artifact_paths",):
            val = payload.get(key)
            if isinstance(val, list):
                artifacts.extend(val)
        record["artifact_paths"] = artifacts
        record["failure_reason"] = reason
        if payload.get("failure_class"):
            record["failure_class"] = payload.get("failure_class")
        if payload.get("preflight"):
            record["preflight"] = payload.get("preflight")
        if payload.get("authorization"):
            record["authorization"] = payload.get("authorization")
        if payload.get("project_lifecycle"):
            record["project_lifecycle"] = payload.get("project_lifecycle")
        if payload.get("bootstrap"):
            record["bootstrap"] = payload.get("bootstrap")
        if payload.get("repo"):
            record["repo"] = payload.get("repo")
        if payload.get("execution_phase"):
            record["execution_phase"] = payload.get("execution_phase")
        if payload.get("independent_test"):
            record["independent_test"] = payload.get("independent_test")
        if payload.get("test_results"):
            record["test_results"] = payload.get("test_results")
        if payload.get("cursor_started") is False:
            record["cursor_started"] = False
        record["validation"] = {
            "worker_status": payload.get("status"),
            "failure_class": payload.get("failure_class"),
            "host": payload.get("host"),
            "stdout_tail": payload.get("stdout_tail"),
            "preflight": payload.get("preflight"),
        }
        usage = payload.get("usage")
        if isinstance(usage, dict):
            record["usage"] = usage
            record["usage_basis"] = "worker-reported"
        if status == "COMPLETED":
            record["validation"]["result"] = "PASS"
            append_state(record, "COMPLETED", payload.get("artifact"))
        else:
            record["validation"]["result"] = "FAIL"
            append_state(record, status if status in TERMINAL else "FAILED", reason)
        save_record(record, inbox_root)
    return load_record(job_id, inbox_root)


def wait_for(job_id: str, timeout_sec: int = 180, inbox_root: Path | None = None) -> dict:
    deadline = time.time() + timeout_sec
    record = harvest(job_id, inbox_root)
    while time.time() < deadline:
        record = harvest(job_id, inbox_root)
        if record and record.get("state") in TERMINAL:
            return record
        time.sleep(3)
    if record and record.get("state") not in TERMINAL:
        record["failure_reason"] = f"orchestrator wait timed out after {timeout_sec}s"
        append_state(record, "FAILED", record["failure_reason"])
        save_record(record, inbox_root)
    return record or {"job_id": job_id, "state": "FAILED", "failure_reason": "unknown job"}


def list_jobs(inbox_root: Path | None = None, limit: int = 20) -> list[dict]:
    root = records_root(inbox_root)
    rows = []
    for path in sorted(root.glob("JOB-*.json"), reverse=True)[:limit]:
        rows.append(json.loads(path.read_text(encoding="utf-8")))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA development orchestration")
    sub = parser.add_subparsers(dest="command", required=True)
    submit_p = sub.add_parser("submit")
    submit_p.add_argument("--job-id")
    submit_p.add_argument("--capability", required=True, choices=sorted(CAPABILITY_ROUTE))
    submit_p.add_argument("--objective", required=True)
    submit_p.add_argument("--repo")
    submit_p.add_argument("--prompt")
    submit_p.add_argument("--project-id")
    submit_p.add_argument("--project-lifecycle", choices=("create_new", "modify_existing"))
    submit_p.add_argument("--approval")
    submit_p.add_argument("--timeout-sec", type=int)
    submit_p.add_argument("--write", action="store_true")
    submit_p.add_argument("--expected-path", action="append", dest="expected_paths")
    submit_p.add_argument("--file", action="append", dest="files")
    submit_p.add_argument("--base-sha", dest="expected_base_sha")
    submit_p.add_argument("--repo-id", dest="repository_id")
    submit_p.add_argument("--operation-id")
    submit_p.add_argument("--root")
    wait_p = sub.add_parser("wait")
    wait_p.add_argument("--job-id", required=True)
    wait_p.add_argument("--timeout-sec", type=int, default=180)
    wait_p.add_argument("--root")
    get_p = sub.add_parser("get")
    get_p.add_argument("--job-id", required=True)
    get_p.add_argument("--root")
    list_p = sub.add_parser("list")
    list_p.add_argument("--root")
    route_p = sub.add_parser("route")
    route_p.add_argument("--capability", required=True)
    args = parser.parse_args()
    root = Path(args.root) if getattr(args, "root", None) else None
    if args.command == "route":
        print(json.dumps(select_worker(args.capability), indent=2))
        return 0
    if args.command == "submit":
        record = submit(
            job_id=args.job_id,
            capability=args.capability,
            objective=args.objective,
            repo=args.repo,
            prompt=args.prompt,
            write=args.write,
            timeout_sec=args.timeout_sec,
            expected_paths=args.expected_paths,
            project_id=args.project_id,
            project_lifecycle=getattr(args, "project_lifecycle", None),
            approval=args.approval,
            inbox_root=root,
            files=getattr(args, "files", None),
            expected_base_sha=getattr(args, "expected_base_sha", None),
            repository_id=getattr(args, "repository_id", None),
            operation_id=getattr(args, "operation_id", None),
        )
        print(json.dumps(record, indent=2))
        return 0 if record.get("state") not in {"BLOCKED", "FAILED"} else 2
    if args.command == "wait":
        record = wait_for(args.job_id, args.timeout_sec, root)
        print(json.dumps(record, indent=2))
        return 0 if record.get("state") == "COMPLETED" else 2
    if args.command == "get":
        record = harvest(args.job_id, root) or load_record(args.job_id, root)
        if not record:
            raise SystemExit(f"unknown job {args.job_id}")
        print(json.dumps(record, indent=2))
        return 0
    rows = list_jobs(root)
    print(json.dumps(rows, indent=2))
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
