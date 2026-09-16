#!/usr/bin/env python3
"""Deterministic NEEWA OS bootstrap, lifecycle, and Done Gate controls."""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "11_CONFIG"
RUNTIME = CONFIG / "runtime.json"
BUDGETS = CONFIG / "budgets.json"
PROJECTS = CONFIG / "projects.json"
PROVIDERS = CONFIG / "providers.json"
RESOURCES = CONFIG / "resources.json"
REQUIRED_GOVERNANCE = (
    "AI-OPS/company/OWNER.md",
    "AI-OPS/company/APPROVAL_MATRIX.md",
    "AI-OPS/company/POLICIES.md",
    "02_CONSTITUTION/NEEWA_CONSTITUTION.md",
    "03_GOVERNANCE/RISK_CLASSIFICATION.md",
    "03_GOVERNANCE/DONE_GATE.md",
)
TRANSITIONS = {
    "NEW": {"TRIAGED", "CANCELLED"},
    "TRIAGED": {"RESEARCHING", "PLANNED", "BLOCKED", "PAUSED", "CANCELLED"},
    "RESEARCHING": {"PLANNED", "BLOCKED", "PAUSED", "CANCELLED"},
    "PLANNED": {"EXECUTING", "BLOCKED", "OWNER_DECISION", "PAUSED", "CANCELLED"},
    "EXECUTING": {"VALIDATING", "REWORK", "BLOCKED", "PAUSED", "FAILED", "CANCELLED"},
    "VALIDATING": {"REWORK", "DONE", "BLOCKED", "OWNER_DECISION", "FAILED"},
    "REWORK": {"EXECUTING", "BLOCKED", "OWNER_DECISION", "PAUSED", "FAILED", "CANCELLED"},
    "BLOCKED": {"TRIAGED", "PLANNED", "EXECUTING", "CANCELLED"},
    "OWNER_DECISION": {"PLANNED", "EXECUTING", "CANCELLED"},
    "PAUSED": {"TRIAGED", "PLANNED", "EXECUTING", "CANCELLED"},
    "FAILED": set(), "CANCELLED": set(), "DONE": set(),
}
TERMINAL_STATES = {"DONE", "FAILED", "CANCELLED"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "openai_key": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    "aws_access_key": re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    "generic_secret_assignment": re.compile(
        r"(?i)(?:^|[{,])\s*['\"]?(?:api[_-]?key|secret[_-]?key|access[_-]?token|password)['\"]?\s*[:=]\s*['\"]?([^\s'\"#]{12,})"
    ),
}
SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules"}


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_files(root: Path = ROOT) -> list[Path]:
    return sorted(
        p for p in root.rglob("*")
        if p.is_file() and not any(part in SKIP_DIRS for part in p.relative_to(root).parts)
    )


def tracked_files(root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"], cwd=root, text=True, capture_output=True, check=True
    )
    return sorted(line for line in result.stdout.splitlines() if line)


def manifest_entries(root: Path = ROOT) -> list[str]:
    entries = []
    for line in (root / "MANIFEST.md").read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"- `(.+)`", line)
        if match:
            entries.append(match.group(1))
    return sorted(entries)


def scan_secrets(root: Path = ROOT) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for path in repo_files(root):
        rel = path.relative_to(root).as_posix()
        try:
            raw = path.read_bytes()
            if b"\0" in raw:
                continue
            text = raw.decode("utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            if rel.endswith(".env.example") and re.search(r"=\s*$", line):
                continue
            for name, pattern in SECRET_PATTERNS.items():
                match = pattern.search(line)
                if not match:
                    continue
                if name == "generic_secret_assignment" and (
                    "os.environ/" in line or "${" in line or "example" in line.lower()
                ):
                    continue
                findings.append({"file": rel, "line": number, "pattern": name})
    return findings


def check(name: str, passed: bool, detail: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail}


def validate_repository(root: Path = ROOT, require_manifest: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for rel in REQUIRED_GOVERNANCE:
        checks.append(check(f"governance:{rel}", (root / rel).is_file(), "required authority file"))

    json_files = ["runtime.json", "budgets.json", "projects.json", "providers.json", "resources.json", "models.json", "workers.json", "automation.json", "subscriptions.json", "skills.json", "risks.json", "approvals.json"]
    loaded: dict[str, dict[str, Any]] = {}
    for filename in json_files:
        try:
            loaded[filename] = load_json(root / "11_CONFIG" / filename)
            checks.append(check(f"json:{filename}", True, "valid JSON"))
        except (OSError, json.JSONDecodeError) as exc:
            checks.append(check(f"json:{filename}", False, str(exc)))

    runtime = loaded.get("runtime.json", {})
    checks.append(check("runtime:mode", runtime.get("mode") in {"RUN", "PAUSE", "LOCKDOWN"}, str(runtime.get("mode"))))
    checks.append(check("runtime:retry_limit", runtime.get("max_autonomous_remediation_cycles") == 2, str(runtime.get("max_autonomous_remediation_cycles"))))

    budgets = loaded.get("budgets.json", {})
    checks.append(check("budget:90_day_ceiling", budgets.get("first_90_days_ceiling") == 1000.0, str(budgets.get("first_90_days_ceiling"))))
    checks.append(check("budget:owner_gate", budgets.get("owner_approval_required_above_budget") is True, "must be true"))

    projects = loaded.get("projects.json", {}).get("projects", [])
    ids = [item.get("id") for item in projects]
    checks.append(check("projects:unique_ids", len(ids) == len(set(ids)) and len(ids) >= 6, f"{len(ids)} projects"))
    for project in projects:
        path = root / str(project.get("path", "")) / "PROJECT.md"
        checks.append(check(f"project:{project.get('id')}", path.is_file(), path.relative_to(root).as_posix()))

    providers = loaded.get("providers.json", {}).get("providers", [])
    resources = loaded.get("resources.json", {}).get("resources", [])
    checks.append(check("providers:registry", bool(providers), f"{len(providers)} providers"))
    checks.append(check("resources:registry", bool(resources), f"{len(resources)} resources"))
    models = loaded.get("models.json", {}).get("models", [])
    checks.append(check("models:verified_primary", any(m.get("id") == "neewa-premium" and m.get("availability") == "verified" for m in models), f"{len(models)} models"))
    checks.append(check("models:verified_local_fallback", any(m.get("id") == "neewa-local" and m.get("location") == "local" and m.get("availability") == "verified" for m in models), "local fallback required"))
    workers = loaded.get("workers.json", {}).get("workers", [])
    checks.append(check("workers:registry", bool(workers), f"{len(workers)} workers"))
    checks.append(check("workers:unique_ids", len([w.get("id") for w in workers]) == len(set(w.get("id") for w in workers)), "worker IDs"))
    checks.append(check("workers:required_fields", all(w.get("id") and w.get("class") and w.get("status") for w in workers), "id/class/status"))
    automation = loaded.get("automation.json", {}).get("jobs", [])
    checks.append(check("automation:registry", len(automation) >= 2, f"{len(automation)} jobs"))
    checks.append(check("automation:unique_ids", len([j.get("id") for j in automation]) == len(set(j.get("id") for j in automation)), "automation IDs"))
    checks.append(check("automation:valid_status", all(j.get("status") in {"active", "prepared", "paused", "blocked"} for j in automation), "job status values"))
    for registry_name, required in {"subscriptions.json":["provider","status"],"skills.json":["id","status"],"risks.json":["id","risk","control","status"]}.items():
        key = registry_name.replace(".json", "")
        rows = loaded.get(registry_name, {}).get(key, [])
        checks.append(check(f"{key}:registry", bool(rows), f"{len(rows)} entries"))
        checks.append(check(f"{key}:required_fields", all(all(row.get(field) is not None and row.get(field) != "" for field in required) for row in rows), ",".join(required)))
    approvals = loaded.get("approvals.json", {})
    authorized = set(approvals.get("authorized", [])); deferred = set(approvals.get("deferred", []))
    checks.append(check("approvals:standing_authorization", bool(authorized), "authorized actions"))
    checks.append(check("approvals:no_overlap", not (authorized & deferred), "authorized/deferred disjoint"))

    findings = scan_secrets(root)
    checks.append(check("security:secret_scan", not findings, f"{len(findings)} finding(s)"))

    if require_manifest:
        expected = sorted(p.relative_to(root).as_posix() for p in repo_files(root))
        actual = manifest_entries(root)
        checks.append(check("repository:manifest", expected == actual, f"expected={len(expected)} actual={len(actual)}"))

    failed = [item for item in checks if not item["passed"]]
    return {"schema_version": 1, "generated_at": utc_now(), "passed": not failed, "checks": checks, "secret_findings": findings}


def generate_manifest(root: Path = ROOT) -> None:
    entries = sorted(p.relative_to(root).as_posix() for p in repo_files(root))
    body = "# File Manifest\n\n" + "\n".join(f"- `{entry}`" for entry in entries) + "\n"
    (root / "MANIFEST.md").write_text(body, encoding="utf-8")


def control_mode(root: Path | None = None) -> str:
    root = root or ROOT
    return str(load_json(root / "11_CONFIG" / "runtime.json")["mode"])


def next_job_id(directory: Path, now: dt.datetime | None = None) -> str:
    now = now or dt.datetime.now(dt.timezone.utc)
    prefix = f"JOB-{now:%Y%m%d}-"
    used = []
    if directory.exists():
        for path in directory.glob(f"{prefix}*.json"):
            try:
                used.append(int(path.stem.rsplit("-", 1)[1]))
            except ValueError:
                continue
    return f"{prefix}{max(used, default=0) + 1:03d}"


def create_job(
    project_id: str, objective: str, risk: str, budget: float,
    state_dir: Path = ROOT / "04_MEMORY/jobs", approval_level: str | None = None,
) -> Path:
    if control_mode() != "RUN":
        raise ValueError(f"new jobs are blocked while Governor mode is {control_mode()}")
    project_ids = {item["id"] for item in load_json(PROJECTS)["projects"]}
    if project_id not in project_ids:
        raise ValueError(f"unknown project: {project_id}")
    default_max = float(load_json(BUDGETS)["job_defaults"]["max_cost"])
    if budget < 0 or budget > default_max:
        raise ValueError(f"budget {budget:.2f} exceeds autonomous default {default_max:.2f}")
    risk = risk.lower()
    minimum_approval = {"low": "A0", "medium": "A1", "high": "A2", "critical": "A3"}[risk]
    approval_level = (approval_level or minimum_approval).upper()
    approval_rank = {"A0": 0, "A1": 1, "A2": 2, "A3": 3}
    if approval_level not in approval_rank:
        raise ValueError(f"unknown approval level: {approval_level}")
    if approval_rank[approval_level] < approval_rank[minimum_approval]:
        raise ValueError(f"{risk} risk requires at least {minimum_approval}")
    owner_required = approval_level in {"A2", "A3"}
    job_id = next_job_id(state_dir)
    record = {
        "schema_version": 1, "job_id": job_id, "project_id": project_id,
        "owner": "NEEWA", "objective": objective, "risk": risk,
        "approval_level": approval_level,
        "state": "NEW", "budget": {"ceiling": budget, "actual": 0.0, "currency": "USD"},
        "remediation_cycles": 0, "automated_checks": [], "independent_review": {"required": risk != "low", "status": "pending"},
        "owner_gate": {"required": owner_required, "status": "pending" if owner_required else "not_required"}, "evidence": [],
        "history": [{"state": "NEW", "at": utc_now()}], "created_at": utc_now(), "updated_at": utc_now(),
    }
    path = state_dir / f"{job_id}.json"
    save_json(path, record)
    return path


def transition_job(path: Path, destination: str) -> dict[str, Any]:
    job = load_json(path)
    source = str(job["state"])
    destination = destination.upper()
    if destination not in TRANSITIONS.get(source, set()):
        raise ValueError(f"invalid transition: {source} -> {destination}")
    if destination == "REWORK":
        job["remediation_cycles"] = int(job.get("remediation_cycles", 0)) + 1
        maximum = int(load_json(RUNTIME)["max_autonomous_remediation_cycles"])
        if job["remediation_cycles"] > maximum:
            raise ValueError(f"remediation limit exceeded ({maximum})")
    job["state"] = destination
    job["updated_at"] = utc_now()
    job.setdefault("history", []).append({"state": destination, "at": job["updated_at"]})
    save_json(path, job)
    return job


def evaluate_done(job: dict[str, Any], root: Path = ROOT) -> list[str]:
    failures = []
    if job.get("state") != "VALIDATING": failures.append("job is not in VALIDATING")
    budget = job.get("budget", {})
    if float(budget.get("actual", 0)) > float(budget.get("ceiling", 0)): failures.append("job budget exceeded")
    checks = job.get("automated_checks", [])
    if not checks or any(item.get("status") != "passed" for item in checks): failures.append("automated checks missing or failed")
    review = job.get("independent_review", {})
    if review.get("required") and review.get("status") != "passed": failures.append("independent review missing or failed")
    gate = job.get("owner_gate", {})
    if gate.get("required") and gate.get("status") != "approved": failures.append("owner approval is pending")
    evidence = job.get("evidence", [])
    if not evidence: failures.append("evidence is missing")
    configured = load_json(root / "11_CONFIG" / "runtime.json").get("evidence_directory", "evidence")
    evidence_root = (root / configured).resolve()
    for rel in evidence:
        candidate = Path(rel)
        if candidate.is_absolute() or ".." in candidate.parts:
            failures.append(f"invalid evidence path: {rel}")
            continue
        resolved = (root / candidate).resolve()
        if not resolved.is_relative_to(evidence_root):
            failures.append(f"evidence outside configured directory: {rel}")
        elif not resolved.is_file():
            failures.append(f"evidence file does not exist: {rel}")
    if int(job.get("remediation_cycles", 0)) > int(load_json(RUNTIME)["max_autonomous_remediation_cycles"]): failures.append("remediation limit exceeded")
    return failures


def gate_job(path: Path, root: Path = ROOT) -> tuple[bool, list[str]]:
    job = load_json(path)
    failures = evaluate_done(job, root)
    if failures: return False, failures
    transition_job(path, "DONE")
    return True, []


def command_validate(args: argparse.Namespace) -> int:
    result = validate_repository(ROOT, require_manifest=not args.skip_manifest)
    payload = json.dumps(result, indent=2)
    if args.json_out:
        save_json(Path(args.json_out), result)
    print(payload)
    return 0 if result["passed"] else 1


def command_job_create(args: argparse.Namespace) -> int:
    path = create_job(args.project, args.objective, args.risk, args.budget, Path(args.state_dir), args.approval_level)
    print(path)
    return 0


def command_job_transition(args: argparse.Namespace) -> int:
    job = transition_job(Path(args.job), args.to)
    print(json.dumps({"job_id": job["job_id"], "state": job["state"]}, indent=2))
    return 0


def command_job_gate(args: argparse.Namespace) -> int:
    passed, failures = gate_job(Path(args.job))
    print(json.dumps({"passed": passed, "failures": failures}, indent=2))
    return 0 if passed else 1


def command_record_validation(args: argparse.Namespace) -> int:
    path = Path(args.job)
    job = load_json(path)
    prior_checks = {item.get("name"): item for item in job.get("automated_checks", [])}
    prior_checks.update({name: {"name": name, "status": "passed"} for name in args.check})
    job["automated_checks"] = list(prior_checks.values())
    job["evidence"] = list(dict.fromkeys([*job.get("evidence", []), *args.evidence]))
    job["updated_at"] = utc_now()
    save_json(path, job)
    print(json.dumps({"job_id": job["job_id"], "checks": len(job["automated_checks"]), "evidence": len(job["evidence"])}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="validate governance, registries, projects, manifest, and secret hygiene")
    validate.add_argument("--json-out")
    validate.add_argument("--skip-manifest", action="store_true")
    validate.set_defaults(func=command_validate)
    manifest = sub.add_parser("generate-manifest", help="regenerate MANIFEST.md deterministically")
    manifest.set_defaults(func=lambda args: (generate_manifest(), print(ROOT / "MANIFEST.md"), 0)[2])
    status = sub.add_parser("governor-status", help="print the declarative Governor mode")
    status.set_defaults(func=lambda args: (print(control_mode()), 0)[1])
    create = sub.add_parser("job-create", help="create a bounded job")
    create.add_argument("--project", required=True)
    create.add_argument("--objective", required=True)
    create.add_argument("--risk", choices=["low", "medium", "high", "critical"], default="low")
    create.add_argument("--budget", type=float, default=0.0)
    create.add_argument("--approval-level", choices=["A0", "A1", "A2", "A3"])
    create.add_argument("--state-dir", default=str(ROOT / "04_MEMORY/jobs"))
    create.set_defaults(func=command_job_create)
    transition = sub.add_parser("job-transition", help="apply a valid lifecycle transition")
    transition.add_argument("--job", required=True)
    transition.add_argument("--to", required=True)
    transition.set_defaults(func=command_job_transition)
    gate = sub.add_parser("job-gate", help="apply the deterministic Done Gate")
    gate.add_argument("--job", required=True)
    gate.set_defaults(func=command_job_gate)
    record = sub.add_parser("job-record-validation", help="record passed automated checks and repository evidence")
    record.add_argument("--job", required=True)
    record.add_argument("--check", action="append", required=True)
    record.add_argument("--evidence", action="append", required=True)
    record.set_defaults(func=command_record_validation)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
