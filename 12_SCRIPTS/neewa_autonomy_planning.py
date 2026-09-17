"""Stack-aware planning helpers for neewa_autonomy (RFC-v4)."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECTS = ROOT / "11_CONFIG" / "projects.json"
STACKS = ROOT / "11_CONFIG" / "project_stacks.json"
POLICY = ROOT / "16_WINDOWS_CLIENT" / "worker" / "cursor-call-policy.json"

WRITE_STAGES = {"ACCESS_APPROVED", "CONNECTED", "BUILD_VERIFIED", "DELEGATION_VERIFIED"}


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_workspace(workspace: str | None, project_id: str | None = None) -> dict:
    markers = []
    stack = "unknown"
    test_command = None
    path = Path(workspace) if workspace else None
    exists = bool(path and path.exists())
    if exists and path:
        for name in (
            "package.json",
            "pyproject.toml",
            "requirements.txt",
            "Cargo.toml",
            "go.mod",
            "README.md",
        ):
            if (path / name).is_file():
                markers.append(name)
        if "package.json" in markers:
            stack = "node-typescript" if (path / "tsconfig.json").is_file() else "node"
            pkg = json.loads((path / "package.json").read_text(encoding="utf-8"))
            scripts = pkg.get("scripts") or {}
            test_command = "npm test" if "test" in scripts else None
        elif "pyproject.toml" in markers or "requirements.txt" in markers:
            stack = "python"
            test_command = "python -m unittest"
        elif (path / "Cargo.toml").is_file():
            stack = "rust"
        elif (path / "go.mod").is_file():
            stack = "go"
    catalog = _load(STACKS)
    if stack == "unknown":
        if project_id and project_id in (catalog.get("projects") or {}):
            row = catalog["projects"][project_id]
            stack = row.get("stack") or "unknown"
            test_command = test_command or row.get("test_command")
            workspace_l = (workspace or "").replace("/", "\\").lower()
            for child, meta in (row.get("children") or {}).items():
                if child.lower() in workspace_l:
                    stack = meta.get("stack") or stack
                    test_command = meta.get("test_command") or test_command
        elif workspace and "cursor-sandbox" in workspace.lower():
            stack = "python-stdlib"
            test_command = "python -m unittest"
    return {
        "workspace": workspace,
        "exists_here": exists,
        "markers": markers,
        "stack": stack,
        "test_command": test_command,
        "source": "filesystem" if exists else "catalog",
    }


def resolve_project(project_id: str | None, workspace: str | None = None) -> dict:
    data = _load(PROJECTS)
    projects = {p["id"]: p for p in data.get("projects") or []}
    if not project_id:
        return {"allowed": True, "reason": None, "project": None, "workspace": workspace}
    row = projects.get(project_id)
    if not row:
        return {"allowed": False, "reason": "UNKNOWN_PROJECT", "project": None}
    stage = row.get("access_stage")
    if not row.get("a1_development") or stage not in WRITE_STAGES:
        return {
            "allowed": False,
            "reason": "PROJECT_NOT_CONNECTED",
            "project": row,
            "detail": stage,
        }
    canonical = row.get("workspace_path")
    chosen = workspace or canonical
    if workspace and canonical:
        ws = workspace.replace("/", "\\").lower().rstrip("\\")
        can = canonical.replace("/", "\\").lower().rstrip("\\")
        if ws != can and not ws.startswith(can + "\\"):
            sandbox = r"c:\users\swap2\neewa-personal\cursor-sandbox"
            if sandbox not in ws:
                return {
                    "allowed": False,
                    "reason": "WORKSPACE_PROJECT_MISMATCH",
                    "project": row,
                }
    return {"allowed": True, "reason": None, "project": row, "workspace": chosen}


def attach_acceptance_checks(requirements: dict, inspect: dict, workflow: str) -> dict:
    for req in requirements.get("requirements") or []:
        kind = req.get("kind")
        if workflow == "research_report":
            if kind == "provenance":
                req["ac"] = "Every citation id exists in the approved corpus"
                req["check"] = "citation"
            elif kind == "domain":
                req["ac"] = "Owner-choice items listed"
                req["check"] = "report_contains_owner_choice"
            elif kind == "release":
                req["ac"] = "Document is not published"
                req["check"] = "no_publish"
            else:
                req["ac"] = "Report exists and cites corpus or SOURCE_PENDING"
                req["check"] = "report_file"
        else:
            if kind == "quality":
                req["ac"] = f"Independent rerun of {inspect.get('test_command') or 'project tests'} passes"
                req["check"] = "independent_tests"
            elif kind == "security":
                req["ac"] = "Workspace is allowlisted and not a denied tree"
                req["check"] = "workspace_boundary"
            elif kind == "release":
                req["ac"] = "RELEASE_CANDIDATE.md exists after tests"
                req["check"] = "file_exists:RELEASE_CANDIDATE.md"
            elif kind == "reliability":
                req["ac"] = "Negative-path test observed in independent output"
                req["check"] = "negative_path"
            else:
                req["ac"] = f"Objective clause is implemented in stack {inspect.get('stack')}"
                req["check"] = "artifact_or_test"
    requirements["stack"] = inspect.get("stack")
    requirements["test_command"] = inspect.get("test_command")
    return requirements


def corpus_files(objective: str) -> list[Path]:
    lower = objective.lower()
    files: list[Path] = []
    if any(w in lower for w in ("neewa", "access", "project", "owner", "authority", "registry", "briefing")):
        files.extend(
            [
                ROOT / "AI-OPS" / "company" / "OWNER.md",
                ROOT / "AI-OPS" / "delivery" / "PROJECT_ACCESS.md",
                ROOT / "11_CONFIG" / "projects.json",
            ]
        )
    if any(w in lower for w in ("ganesh", "ganesha", "ganapati", "chaturthi", "katha", "devotional")):
        files.append(ROOT / "14_REFERENCE" / "devotional_sources" / "SOURCE_PACK.md")
    if not files:
        files.extend(
            [
                ROOT / "AI-OPS" / "company" / "OWNER.md",
                ROOT / "AI-OPS" / "delivery" / "PROJECT_ACCESS.md",
            ]
        )
    out = []
    seen = set()
    for path in files:
        if path in seen or not path.is_file():
            continue
        seen.add(path)
        out.append(path)
    return out


def synthesize_from_corpus(objective: str, requirements: dict, design: dict) -> dict:
    files = corpus_files(objective)
    excerpts = []
    for path in files:
        text = path.read_text(encoding="utf-8")
        excerpts.append({"id": path.name, "path": str(path), "text": text[:4000]})
    if not excerpts:
        return {
            "report": f"# Research report\n\nObjective: {objective}\n\nSOURCE_PENDING: no approved corpus files matched this request. Citations were not invented.\n",
            "citations": [],
            "source_status": "SOURCE_PENDING",
            "slug": design.get("product_slug") or "research",
            "invented": [],
            "passed": False,
            "word_count": 0,
        }
    words = []
    lines = [
        f"# Research report — {design.get('product_slug') or 'research'}",
        "",
        f"Objective: {objective}",
        "This report cites only approved local corpus files. It is not a publication.",
        "",
        "## Findings",
        "",
    ]
    for ex in excerpts:
        lines.append(f"### {ex['id']}")
        snippet = re.sub(r"\s+", " ", ex["text"]).strip()[:1800]
        lines.append(snippet)
        lines.append("")
        lines.append(f"Citation: `{ex['id']}`")
        lines.append("")
        words.extend(snippet.split())
    lines += [
        "## Owner decisions still required",
        "- Any publication, production deploy, or access expansion remains A2/A3.",
        "",
        "## Limits",
        "- Claims not present in the cited files are SOURCE_PENDING.",
        "",
    ]
    report = "\n".join(lines) + "\n"
    wc = len(report.split())
    return {
        "report": report,
        "citations": [{"id": e["id"], "path": e["path"], "exists": True} for e in excerpts],
        "source_status": "PASS",
        "slug": design.get("product_slug") or "research",
        "invented": [],
        "passed": wc >= 80 and bool(excerpts),
        "word_count": wc,
        "corpus": [e["path"] for e in excerpts],
    }
