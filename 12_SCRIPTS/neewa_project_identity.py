"""Canonical project identity for NEEWA software jobs.

workspace_root, project_name, and project_path are distinct typed fields.
Descriptive phrases are not project names. Prefer an explicit name, then a
project-path basename, then persisted metadata, and only then a generated name.
Never compare project_name with the basename of workspace_root.
"""
from __future__ import annotations

import re

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
    r"(?i)((?:[A-Za-z]:[\\/])(?:[^\\/:*?\"<>|\r\n\s]+[\\/])*[^\\/:*?\"<>|\r\n\s.]+)"
)
_SANDBOX_MARK = "cursor-sandbox"
APPROVED_PERSONAL_ROOTS = (
    r"c:\development\workspace",
    r"c:\users\swap2\neewa-personal",
)
WORKSPACE_ROOT_PATHS = (
    r"c:\development\workspace",
    r"c:\users\swap2\neewa-personal",
    r"c:\users\swap2\neewa-personal\cursor-sandbox",
)


def win_display(path: str | None) -> str:
    text = (path or "").replace("/", "\\").strip()
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text.rstrip("\\")


def win_key(path: str | None) -> str:
    return win_display(path).lower()


def win_parts(path: str | None) -> list[str]:
    return [part for part in win_display(path).split("\\") if part and part != "."]


def win_basename(path: str | None) -> str:
    parts = win_parts(path)
    return parts[-1] if parts else ""


def win_parent(path: str | None) -> str:
    text = win_display(path)
    if "\\" not in text:
        return ""
    parent = text.rsplit("\\", 1)[0]
    if len(parent) == 2 and parent.endswith(":"):
        return parent + "\\"
    return parent


def win_join(root: str | None, name: str) -> str:
    return win_display(root) + "\\" + name


def win_equal(left: str | None, right: str | None) -> bool:
    return bool(left) and bool(right) and win_key(left) == win_key(right)


def has_traversal(path: str | None) -> bool:
    return any(part == ".." for part in win_parts(path))


def is_absolute_win_path(path: str | None) -> bool:
    text = win_display(path)
    return len(text) >= 3 and text[1] == ":" and text[2] == "\\"


def is_under_personal_root(path: str | None) -> bool:
    key = win_key(path)
    if not key:
        return False
    return any(key == root or key.startswith(root + "\\") for root in APPROVED_PERSONAL_ROOTS)


def is_workspace_root_path(path: str | None) -> bool:
    if not path:
        return False
    key = win_key(path)
    if key in WORKSPACE_ROOT_PATHS:
        return True
    return win_basename(path).lower() == _SANDBOX_MARK


def _is_sandbox_root(path: str | None) -> bool:
    return bool(path) and win_basename(path).lower() == _SANDBOX_MARK


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


def extract_windows_paths(objective: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()
    for match in _WIN_PATH_RE.finditer(objective or ""):
        raw = win_display(match.group(1))
        key = win_key(raw)
        if not raw or key in seen:
            continue
        seen.add(key)
        found.append(raw)
    return found


def extract_explicit_project_path(objective: str) -> str | None:
    projects = [path for path in extract_windows_paths(objective) if not is_workspace_root_path(path)]
    if not projects:
        return None
    return max(projects, key=lambda path: len(win_display(path)))


def extract_workspace_root(objective: str) -> str | None:
    roots = [path for path in extract_windows_paths(objective) if is_workspace_root_path(path)]
    if not roots:
        return None
    return max(roots, key=lambda path: len(win_display(path)))


def path_basename(path: str | None) -> str | None:
    if not path or is_workspace_root_path(path):
        return None
    name = normalize_project_name(win_basename(path))
    if not name or is_descriptor_name(name):
        return None
    return name


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


def _unique_project_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for path in paths:
        key = win_key(path)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(win_display(path))
    return out


def _reject(reason: str, detail: str, **fields) -> dict:
    return {
        "allowed": False,
        "reason": reason,
        "detail": detail,
        "project_name": fields.get("project_name"),
        "workspace_root": fields.get("workspace_root"),
        "project_path": fields.get("project_path"),
        "source": fields.get("source") or reason.lower(),
        "normalization": fields.get("normalization")
        or {
            "explicit_name": fields.get("explicit_name"),
            "path_basename": fields.get("path_basename"),
            "generated": None,
            "agreement": False,
        },
    }


def _guard_path(path: str | None, *, label: str) -> dict | None:
    if not path:
        return None
    if has_traversal(path):
        return _reject("PATH_TRAVERSAL", f"{label} contains path traversal")
    if is_absolute_win_path(path) and not is_under_personal_root(path):
        return _reject("OUTSIDE_PERSONAL_ROOT", f"{label} is outside approved personal roots")
    return None


def resolve_project_identity(
    objective: str,
    *,
    workspace: str | None = None,
    workspace_root: str | None = None,
    project_name: str | None = None,
    project_path: str | None = None,
    persisted: dict | None = None,
) -> dict:
    persisted = persisted or {}
    if (
        persisted.get("project_name")
        and persisted.get("project_path")
        and persisted.get("workspace_root")
        and persisted.get("allowed") is not False
    ):
        explicit = extract_explicit_project_name(objective)
        if not (explicit and explicit != persisted.get("project_name")):
            return {
                **persisted,
                "allowed": True,
                "source": persisted.get("source") or "persisted",
            }

    explicit_name = normalize_project_name(project_name) if project_name else extract_explicit_project_name(objective)
    if explicit_name and is_descriptor_name(explicit_name):
        explicit_name = None

    text_paths = extract_windows_paths(objective)
    text_roots = [path for path in text_paths if is_workspace_root_path(path)]
    text_projects = _unique_project_paths(
        [path for path in text_paths if not is_workspace_root_path(path)]
    )
    supplied_projects = _unique_project_paths(
        [path for path in [project_path] if path] + text_projects
    )
    if len(supplied_projects) > 1:
        return _reject(
            "AMBIGUOUS_PROJECT_PATH",
            "multiple distinct project paths were supplied",
            explicit_name=explicit_name,
        )

    root = workspace_root or (text_roots[-1] if text_roots else None)
    if not root and workspace and is_workspace_root_path(workspace):
        root = workspace
    path = project_path or (supplied_projects[0] if supplied_projects else None)
    if not path and workspace and not is_workspace_root_path(workspace):
        path = workspace
    if not root and path and is_workspace_root_path(win_parent(path)):
        root = win_parent(path)

    for raw, label in (
        (root, "workspace_root"),
        (path, "project_path"),
        (workspace if workspace and is_workspace_root_path(workspace) else None, "workspace_root"),
        (workspace if workspace and not is_workspace_root_path(workspace) else None, "project_path"),
    ):
        blocked = _guard_path(raw, label=label)
        if blocked:
            blocked["workspace_root"] = root
            blocked["project_path"] = path
            blocked["normalization"] = {
                "explicit_name": explicit_name,
                "path_basename": path_basename(path),
                "generated": None,
                "agreement": False,
            }
            return blocked

    path_leaf = path_basename(path)
    if explicit_name and path_leaf and explicit_name != path_leaf:
        return _reject(
            "PROJECT_PATH_DISAGREEMENT",
            f"explicit name {explicit_name} does not match path basename {path_leaf}",
            workspace_root=root,
            explicit_name=explicit_name,
            path_basename=path_leaf,
            source="disagreement",
        )

    generated = None
    if explicit_name:
        name = explicit_name
        source = "explicit_name"
    elif path_leaf:
        name = path_leaf
        source = "path_basename"
    elif persisted.get("project_name"):
        name = persisted["project_name"]
        source = "persisted"
    else:
        generated = generated_safe_name(objective)
        name = generated
        source = "generated"

    if name and root and not path:
        path = win_join(root, name)
    elif path:
        path = win_display(path)
    elif name:
        path = name
    if not root and path and is_absolute_win_path(path):
        root = win_parent(path)

    if name and root and path and is_absolute_win_path(path):
        same_parent = win_equal(win_parent(path), root)
        same_leaf = normalize_project_name(win_basename(path)) == normalize_project_name(name)
        if not (same_parent and same_leaf):
            return _reject(
                "PROJECT_PATH_DISAGREEMENT",
                "project_path does not equal workspace_root joined with project_name",
                project_name=name,
                workspace_root=root,
                project_path=path,
                explicit_name=explicit_name,
                path_basename=path_leaf,
                source="disagreement",
            )

    if root:
        root = win_display(root)
    if path and is_absolute_win_path(path):
        path = win_display(path)

    return {
        "allowed": True,
        "reason": None,
        "project_name": name,
        "workspace_root": root,
        "project_path": path,
        "source": source,
        "normalization": {
            "explicit_name": explicit_name,
            "path_basename": path_leaf,
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
