"""Canonical project identity for NEEWA software jobs.

Descriptive phrases are not project names. Prefer an explicit name, then a
path basename, then persisted metadata, and only then a generated safe name.
"""
from __future__ import annotations

import re
from pathlib import Path

DESCRIPTOR_WORDS = {
    "a",
    "an",
    "the",
    "isolated",
    "python",
    "standard",
    "library",
    "stdlib",
    "small",
    "simple",
    "new",
    "personal",
    "project",
    "projects",
    "cli",
    "application",
    "app",
    "tool",
    "utility",
    "program",
    "command",
    "line",
    "offline",
    "test",
    "tests",
    "helper",
    "local",
    "approved",
    "workspace",
    "sandbox",
    "cursor",
    "package",
    "module",
    "script",
    "scripts",
}

_NAME_RE = re.compile(
    r"(?i)\b(?:named|called)\s+[\"'`]?([A-Za-z][A-Za-z0-9_-]{1,80})[\"'`]?"
)
_WIN_PATH_RE = re.compile(
    r"(?i)((?:[A-Za-z]:\\)(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n.]+)"
)
_SANDBOX_MARK = "cursor-sandbox"


def normalize_project_name(name: str | None) -> str:
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    return "_".join(tokens)


def is_descriptor_name(name: str | None) -> bool:
    tokens = re.findall(r"[a-z0-9]+", (name or "").lower())
    if not tokens:
        return True
    return all(token in DESCRIPTOR_WORDS for token in tokens)


def extract_explicit_project_name(objective: str) -> str | None:
    match = _NAME_RE.search(objective or "")
    if not match:
        return None
    name = normalize_project_name(match.group(1))
    if not name or is_descriptor_name(name):
        return None
    return name


def extract_explicit_project_path(objective: str) -> str | None:
    match = _WIN_PATH_RE.search(objective or "")
    if not match:
        return None
    raw = match.group(1).rstrip("\\/")
    if raw.lower().endswith(_SANDBOX_MARK):
        return raw
    return raw


def path_basename(path: str | None) -> str | None:
    if not path:
        return None
    leaf = Path(path.replace("/", "\\")).name
    name = normalize_project_name(leaf)
    if not name or is_descriptor_name(name) or name.replace("_", "") == _SANDBOX_MARK.replace("-", ""):
        return None
    return name


def _is_sandbox_root(path: str | None) -> bool:
    if not path:
        return False
    leaf = Path(str(path).replace("/", "\\").rstrip("\\")).name.lower()
    return leaf == _SANDBOX_MARK


def generated_safe_name(objective: str) -> str:
    text = re.sub(r"(?i)^(?:neewa,?\s*|please\s*|owner:\s*)+", "", (objective or "").strip())
    match = re.search(
        r"(?i)(?:build|create|implement|write|make)\s+(?:an?\s+)?(.+?)(?:\s+that\b|\s+which\b|\s+with\b|,|\.|$)",
        text,
    )
    phrase = match.group(1) if match else text[:80]
    tokens = [
        token
        for token in re.findall(r"[a-z0-9]+", phrase.lower())
        if token not in DESCRIPTOR_WORDS
    ][:4]
    return "_".join(tokens) or "task"


def _workspace_root(workspace: str | None, explicit_path: str | None, name: str) -> str:
    if explicit_path:
        path = Path(explicit_path)
        if path.name.lower() == name.replace("_", "-") or normalize_project_name(path.name) == name:
            return str(path.parent)
        if _is_sandbox_root(explicit_path):
            return explicit_path
    if workspace:
        if _is_sandbox_root(workspace):
            return workspace
        if normalize_project_name(Path(workspace).name) == name:
            return str(Path(workspace).parent)
        return workspace
    if explicit_path and _is_sandbox_root(str(Path(explicit_path).parent)):
        return str(Path(explicit_path).parent)
    return workspace or ""


def resolve_project_identity(
    objective: str,
    *,
    workspace: str | None = None,
    persisted: dict | None = None,
) -> dict:
    persisted = persisted or {}
    if persisted.get("project_name") and persisted.get("project_path") and persisted.get("allowed") is not False:
        explicit = extract_explicit_project_name(objective)
        if explicit and explicit != persisted.get("project_name"):
            pass
        else:
            return {
                **persisted,
                "allowed": True,
                "source": persisted.get("source") or "persisted",
            }

    explicit_name = extract_explicit_project_name(objective)
    explicit_path = extract_explicit_project_path(objective)
    basename = path_basename(explicit_path) if explicit_path and not _is_sandbox_root(explicit_path) else None
    if workspace and not _is_sandbox_root(workspace):
        basename = basename or path_basename(workspace)

    if explicit_name and basename and explicit_name != basename:
        return {
            "allowed": False,
            "reason": "PROJECT_PATH_DISAGREEMENT",
            "detail": f"explicit name {explicit_name} does not match path basename {basename}",
            "project_name": None,
            "workspace_root": workspace,
            "project_path": None,
            "source": "disagreement",
            "normalization": {
                "explicit_name": explicit_name,
                "path_basename": basename,
                "generated": None,
                "agreement": False,
            },
        }

    generated = None
    existing_repo = bool(workspace and not _is_sandbox_root(workspace))
    if existing_repo and not (explicit_path and not _is_sandbox_root(explicit_path)):
        name = explicit_name or path_basename(workspace) or persisted.get("project_name")
        if not name:
            generated = generated_safe_name(objective)
            name = generated
            source = "generated"
        elif explicit_name:
            source = "explicit_name"
        elif persisted.get("project_name") and not path_basename(workspace):
            source = "persisted"
        else:
            source = "workspace"
        return {
            "allowed": True,
            "reason": None,
            "project_name": name,
            "workspace_root": str(Path(workspace).parent) if workspace else "",
            "project_path": workspace,
            "source": source,
            "normalization": {
                "explicit_name": explicit_name,
                "path_basename": path_basename(workspace),
                "generated": generated,
                "agreement": True,
            },
        }

    if explicit_name:
        name = explicit_name
        source = "explicit_name"
    elif basename:
        name = basename
        source = "path_basename"
    elif persisted.get("project_name"):
        name = persisted["project_name"]
        source = "persisted"
    else:
        generated = generated_safe_name(objective)
        name = generated
        source = "generated"

    root = _workspace_root(workspace, explicit_path, name)
    if explicit_path and not _is_sandbox_root(explicit_path) and normalize_project_name(Path(explicit_path).name) == name:
        project_path = explicit_path
    elif root:
        project_path = str(Path(root) / name)
    else:
        project_path = name

    return {
        "allowed": True,
        "reason": None,
        "project_name": name,
        "workspace_root": root,
        "project_path": project_path,
        "source": source,
        "normalization": {
            "explicit_name": explicit_name,
            "path_basename": basename,
            "generated": generated,
            "agreement": True,
        },
    }


def expected_paths_for_identity(identity: dict, *, include_release: bool = False, include_readme: bool = False) -> list[str]:
    name = identity.get("project_name") or "task"
    paths = [f"{name}.py", f"test_{name}.py", "test-results.json"]
    if include_readme:
        paths.append("README.md")
    if include_release:
        paths.append("RELEASE_CANDIDATE.md")
    return paths


def public_identity(identity: dict | None) -> dict:
    src = identity or {}
    return {
        "project_name": src.get("project_name"),
        "workspace_root": src.get("workspace_root"),
        "project_path": src.get("project_path"),
        "source": src.get("source"),
        "normalization": src.get("normalization") or {},
        "allowed": src.get("allowed", True),
        "reason": src.get("reason"),
    }
