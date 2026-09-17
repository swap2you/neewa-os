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
PERSONAL_ROOTS = (
    r"c:\development\workspace",
    r"c:\users\swap2\neewa-personal",
)
SECRET_PARTS = (".ssh", ".aws", ".gnupg")
DENIED_CONTAINS_DEFAULT = ("fintech", "employer", "brokerage", "trading")

# Technology names / catalog labels. Never treat these as repository files.
STACK_LABEL_NAMES = {
    "fastapi",
    "next.js",
    "nextjs",
    "node.js",
    "postgresql",
    "postgres",
    "docker-compose",
    "typescript",
    "react",
    "vite",
    "n8n",
}
STACK_LABEL_PATHS = {
    "fastapi/next.js",
    "next.js/postgresql",
    "fastapi/next.js/postgresql",
}
ALLOWED_FILE_SUFFIXES = {".md", ".py", ".ts", ".tsx", ".js", ".json", ".toml", ".yml", ".yaml"}


def normalize_rel_path(path: str) -> str:
    text = (path or "").strip().replace("\\", "/")
    return text.lstrip("./")


def is_repo_relative_file(path: str) -> bool:
    """True only for a repository-relative file path, never a stack label."""
    text = normalize_rel_path(path)
    if not text or ".." in Path(text).parts:
        return False
    if re.match(r"^[a-zA-Z]:", text) or text.startswith("/"):
        return False
    lower = text.lower()
    if lower in STACK_LABEL_PATHS or lower in STACK_LABEL_NAMES:
        return False
    parts = [p.lower() for p in text.split("/") if p]
    if any(part in STACK_LABEL_NAMES for part in parts):
        return False
    suffix = Path(text).suffix.lower()
    if suffix not in ALLOWED_FILE_SUFFIXES:
        return False
    name = Path(text).name.lower()
    if name in STACK_LABEL_NAMES:
        return False
    return True


def extract_mentioned_paths(text: str) -> list[str]:
    raw = re.findall(r"[\w./\\-]+\.(?:md|py|ts|tsx|js|json|toml|yml|yaml)", text or "")
    out = []
    seen = set()
    for item in raw:
        norm = normalize_rel_path(item)
        if not is_repo_relative_file(norm) or norm in seen:
            continue
        seen.add(norm)
        out.append(norm)
    return out


def malformed_expected_paths(paths: list[str] | None) -> list[str]:
    return [p for p in (paths or []) if p and not is_repo_relative_file(p)]


def constrain_expected_paths(paths: list[str] | None, workspace: str | None = None) -> list[str]:
    """Keep only normalized repo-relative files. Do not derive files from stack labels."""
    del workspace  # containment is enforced on the Windows worker against the approved repo
    return [normalize_rel_path(p) for p in (paths or []) if is_repo_relative_file(p)]


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
    catalog_markers: list[str] = []
    catalog_row = (catalog.get("projects") or {}).get(project_id) if project_id else None
    if stack == "unknown":
        if catalog_row:
            stack = catalog_row.get("stack") or "unknown"
            test_command = test_command or catalog_row.get("test_command")
            workspace_l = (workspace or "").replace("/", "\\").lower()
            for child, meta in (catalog_row.get("children") or {}).items():
                if child.lower() in workspace_l:
                    stack = meta.get("stack") or stack
                    test_command = meta.get("test_command") or test_command
        elif workspace and "cursor-sandbox" in workspace.lower():
            stack = "python-stdlib"
            test_command = "python -m unittest"
    stack_label = stack
    if catalog_row:
        stack_label = catalog_row.get("stack_label") or stack_label
        catalog_markers = list(catalog_row.get("markers") or [])
        test_command = test_command or catalog_row.get("test_command")
    return {
        "workspace": workspace,
        "exists_here": exists,
        "host_can_see_workspace": exists,
        "absence_is_not_disproof": (not exists) and bool(workspace),
        "windows_preflight_required": (not exists)
        and bool(workspace)
        and ("\\development\\workspace" in (workspace or "").replace("/", "\\").lower()),
        "markers": markers,
        "catalog_markers": catalog_markers,
        "stack": stack,
        "stack_label": stack_label,
        "test_command": test_command,
        "source": "filesystem" if exists else "catalog",
    }


def repo_relative_from_artifacts(artifacts: list | None, workspace: str | None) -> list[str]:
    """Convert worker artifact paths to constrained repo-relative files."""
    ws = (workspace or "").replace("/", "\\").rstrip("\\")
    out = []
    seen = set()
    for art in artifacts or []:
        text = str(art).replace("/", "\\")
        rel = None
        if ws and text.lower().startswith(ws.lower() + "\\"):
            rel = text[len(ws) + 1 :].replace("\\", "/")
        else:
            rel = str(art).replace("\\", "/")
        rel = normalize_rel_path(rel)
        if rel.lower() in {"release_candidate.md"} or rel.lower().endswith("/release_candidate.md"):
            continue
        if not is_repo_relative_file(rel) or rel in seen:
            continue
        seen.add(rel)
        out.append(rel)
    return out


def _norm_win(path: str | None) -> str:
    text = (path or "").replace("/", "\\").strip().lower()
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text.rstrip("\\")


def _path_parts(path: str | None) -> list[str]:
    return [p for p in _norm_win(path).split("\\") if p]


def _policy_denies() -> tuple[list[str], list[str]]:
    policy = _load(POLICY)
    equals = [str(x).lower() for x in (policy.get("denied_name_equals") or [])]
    contains = [str(x).lower() for x in (policy.get("denied_name_contains") or [])]
    if not contains:
        contains = list(DENIED_CONTAINS_DEFAULT)
    return equals, contains


def is_denied_workspace(workspace: str | None) -> bool:
    if not workspace:
        return False
    n = _norm_win(workspace)
    parts = _path_parts(workspace)
    equals, contains = _policy_denies()
    if any(part in equals for part in parts):
        return True
    if any(frag and frag in n for frag in contains):
        return True
    return any(secret in parts for secret in SECRET_PARTS)


def is_workspace_root(workspace: str | None) -> bool:
    return _norm_win(workspace) == r"c:\development\workspace"


def is_personal_workspace(workspace: str | None) -> bool:
    if not workspace or is_denied_workspace(workspace) or is_workspace_root(workspace):
        return False
    n = _norm_win(workspace)
    return any(n == root or n.startswith(root + "\\") for root in PERSONAL_ROOTS)


def workspace_authorization(workspace: str | None) -> dict:
    """Path-shape authorization. Linux cannot see Windows disks; absence is not a deny."""
    if not workspace:
        return {"allowed": True, "reason": None}
    if is_denied_workspace(workspace):
        return {"allowed": False, "reason": "UNAUTHORIZED_REPO"}
    if is_workspace_root(workspace):
        return {"allowed": False, "reason": "WORKSPACE_ROOT_NOT_A_REPO"}
    if not is_personal_workspace(workspace):
        return {"allowed": False, "reason": "UNAUTHORIZED_REPO"}
    return {"allowed": True, "reason": None}


def resolve_project(project_id: str | None, workspace: str | None = None) -> dict:
    """Registry metadata is descriptive. Authorization is personal-root minus deny-list."""
    data = _load(PROJECTS)
    projects = {p["id"]: p for p in data.get("projects") or []}
    path_gate = workspace_authorization(workspace)
    if not path_gate["allowed"]:
        return {
            "allowed": False,
            "reason": path_gate["reason"],
            "project": projects.get(project_id) if project_id else None,
            "workspace": workspace,
        }
    if not project_id:
        return {
            "allowed": True,
            "reason": None,
            "project": None,
            "workspace": workspace,
            "discovered": bool(workspace),
        }
    row = projects.get(project_id)
    if not row:
        return {
            "allowed": True,
            "reason": "UNREGISTERED_PERSONAL",
            "project": None,
            "workspace": workspace,
            "discovered": True,
        }
    canonical = row.get("workspace_path")
    chosen = workspace or canonical
    if chosen and chosen != workspace:
        chosen_gate = workspace_authorization(chosen)
        if not chosen_gate["allowed"]:
            return {
                "allowed": False,
                "reason": chosen_gate["reason"],
                "project": row,
                "workspace": chosen,
            }
    if workspace and canonical:
        ws = _norm_win(workspace)
        can = _norm_win(canonical)
        sandbox = r"c:\users\swap2\neewa-personal\cursor-sandbox"
        if ws != can and not ws.startswith(can + "\\") and sandbox not in ws:
            # Mismatch is informational when both paths are still personal.
            if not (is_personal_workspace(workspace) and is_personal_workspace(canonical)):
                return {
                    "allowed": False,
                    "reason": "WORKSPACE_PROJECT_MISMATCH",
                    "project": row,
                }
    stage = row.get("access_stage")
    return {
        "allowed": True,
        "reason": None,
        "project": row,
        "workspace": chosen,
        "access_stage": stage,
        "discovered": stage not in WRITE_STAGES or not row.get("a1_development"),
    }


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
    requirements["stack_label"] = inspect.get("stack_label")
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
