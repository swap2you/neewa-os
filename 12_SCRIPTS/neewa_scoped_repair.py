"""Governed scoped repair workspaces for personal NEEWA repositories.

Creates a small isolated Git checkout of an explicit file allowlist so Cursor
can work without opening the full authoritative tree. Does not run caller
shell, does not choose arbitrary destinations, and does not modify the
authoritative repository during create/review/cleanup.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import posixpath
import re
import shutil
import stat
import subprocess
import tarfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "16_WINDOWS_CLIENT" / "worker" / "cursor-call-policy.json"
NEEWA_MARKERS = ("12_SCRIPTS", "16_WINDOWS_CLIENT")
RECEIPT_NAME = ".neewa-scoped-repair.json"
SCOPED_DIR_NAME = "scoped-repair"
DEFAULT_TTL_SEC = 24 * 3600
GIT_TIMEOUT_SEC = 60
MAX_FILES = 40
ALLOWED_SUFFIXES = {
    ".py",
    ".ps1",
    ".json",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".toml",
    ".js",
    ".ts",
    ".tsx",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_policy() -> dict:
    if POLICY.is_file():
        return json.loads(POLICY.read_text(encoding="utf-8"))
    return {}


def _norm(path: str | None) -> str:
    text = (path or "").replace("/", "\\").strip().lower()
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return text.rstrip("\\")


def default_repair_root() -> Path:
    env = os.environ.get("NEEWA_SCOPED_REPAIR_ROOT")
    if env:
        return Path(env)
    return Path.home() / "NEEWA-Personal" / SCOPED_DIR_NAME


def receipts_dir(repair_root: Path) -> Path:
    path = repair_root / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{uuid.uuid4().hex}.tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def force_rmtree(path: Path) -> None:
    def _handle(func, name, _exc) -> None:
        try:
            os.chmod(name, stat.S_IWRITE)
            func(name)
        except OSError:
            pass

    if not path.exists():
        return
    try:
        shutil.rmtree(path, onexc=_handle)
    except TypeError:
        shutil.rmtree(path, onerror=_handle)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def new_operation_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"SCOPED-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def receipt(
    *,
    operation_id: str,
    status: str,
    repo_id: str | None = None,
    authoritative_repo: str | None = None,
    workspace_path: str | None = None,
    base_sha: str | None = None,
    selected_files: list[str] | None = None,
    authorization: dict | None = None,
    reason: str | None = None,
    extra: dict | None = None,
) -> dict:
    row = {
        "schema_version": 1,
        "operation": "create_scoped_repair_workspace",
        "operation_id": operation_id,
        "status": status,
        "repository_id": repo_id,
        "authoritative_repo": authoritative_repo,
        "workspace_path": workspace_path,
        "base_sha": base_sha,
        "selected_files": list(selected_files or []),
        "created_at": utc_now(),
        "authorization": authorization or {"allowed": status == "COMPLETED", "reason": reason},
        "failure_reason": reason if status != "COMPLETED" else None,
        "public_listener": False,
        "unrestricted_shell": False,
    }
    if extra:
        row.update(extra)
    return row


def blocked(operation_id: str, reason: str, **kwargs) -> dict:
    return receipt(operation_id=operation_id, status="BLOCKED", reason=reason, **kwargs)


def failed(operation_id: str, reason: str, **kwargs) -> dict:
    return receipt(operation_id=operation_id, status="FAILED", reason=reason, **kwargs)


def denied_parts(policy: dict | None = None) -> tuple[list[str], list[str]]:
    policy = policy or load_policy()
    equals = [str(x).lower() for x in (policy.get("denied_name_equals") or [])]
    contains = [str(x).lower() for x in (policy.get("denied_name_contains") or [])]
    return equals, contains


def is_denied_path(path: str, policy: dict | None = None) -> bool:
    n = _norm(path)
    parts = [p for p in n.split("\\") if p]
    equals, contains = denied_parts(policy)
    if any(part in equals for part in parts):
        return True
    if any(frag and frag in n for frag in contains):
        return True
    return any(secret in parts for secret in (".ssh", ".aws", ".gnupg"))


def personal_roots(policy: dict | None = None) -> list[str]:
    policy = policy or load_policy()
    roots = []
    for item in (policy.get("personal_roots") or []) + [policy.get("sandbox_repo")]:
        if not item:
            continue
        expanded = os.path.expandvars(str(item))
        roots.append(_norm(expanded))
    roots.extend(
        [
            r"c:\development\workspace",
            _norm(str(Path.home() / "NEEWA-Personal")),
        ]
    )
    extra = os.environ.get("NEEWA_SCOPED_REPAIR_PERSONAL_ROOT")
    if extra:
        roots.append(_norm(extra))
    seen = []
    for root in roots:
        if root and root not in seen:
            seen.append(root)
    return seen


def is_personal_path(path: str, policy: dict | None = None) -> bool:
    if is_denied_path(path, policy):
        return False
    n = _norm(path)
    if n == r"c:\development\workspace":
        return False
    return any(n == root or n.startswith(root + "\\") for root in personal_roots(policy))


def git(args: list[str], *, cwd: Path, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SEC,
        check=check,
    )


def git_head(repo: Path) -> str | None:
    completed = git(["rev-parse", "HEAD"], cwd=repo)
    if completed.returncode != 0:
        return None
    return completed.stdout.strip()


def git_has_commit(repo: Path, sha: str) -> bool:
    completed = git(["cat-file", "-t", sha], cwd=repo)
    return completed.returncode == 0 and completed.stdout.strip() == "commit"


def git_status_porcelain(repo: Path) -> str:
    completed = git(["status", "--porcelain"], cwd=repo)
    return completed.stdout if completed.returncode == 0 else "STATUS_UNAVAILABLE"


def is_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if hasattr(path, "is_junction") and path.is_junction():
            return True
        st = path.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        return bool(getattr(st, "st_file_attributes", 0) & reparse)
    except OSError:
        return False


def validate_relative(rel: str) -> str | None:
    raw = (rel or "").strip().replace("\\", "/")
    if not raw:
        return "empty path"
    if raw.startswith("/") or re.match(r"^[a-zA-Z]:", raw):
        return "absolute path is not allowed"
    if raw.startswith("~"):
        return "home-relative path is not allowed"
    normalized = posixpath.normpath(raw)
    if normalized.startswith("../") or normalized == ".." or "/../" in f"/{normalized}/":
        return "parent-directory traversal is not allowed"
    if ".." in Path(normalized).parts:
        return "parent-directory traversal is not allowed"
    suffix = Path(normalized).suffix.lower()
    if suffix and suffix not in ALLOWED_SUFFIXES:
        return f"file suffix {suffix} is not in the scoped-repair allowlist"
    return None


def resolve_inside(root: Path, rel: str) -> tuple[Path | None, str | None]:
    err = validate_relative(rel)
    if err:
        return None, err
    posix = posixpath.normpath(rel.replace("\\", "/"))
    current = root
    for part in Path(posix).parts:
        current = current / part
        if current.exists() and is_reparse(current):
            try:
                target = current.resolve()
                target.relative_to(root.resolve())
            except (OSError, ValueError):
                return None, "symlink or junction escape is not allowed"
    candidate = (root / posix).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None, "path escapes the repository root"
    return candidate, None


def authorize_source_repo(repo: Path, *, repo_id: str | None, policy: dict | None = None) -> dict:
    if not repo.exists() or not repo.is_dir():
        return {"allowed": False, "reason": "MISSING_REPO"}
    if is_denied_path(str(repo), policy):
        return {"allowed": False, "reason": "DENIED_REPO"}
    if not is_personal_path(str(repo), policy):
        return {"allowed": False, "reason": "UNAPPROVED_PATH"}
    leaf = repo.name
    identity = (repo_id or leaf or "").strip()
    if identity.lower() == "neewa-os":
        missing = [name for name in NEEWA_MARKERS if not (repo / name).is_dir()]
        if missing:
            return {"allowed": False, "reason": "NOT_NEEWA_OS", "missing_markers": missing}
        if (repo / ".git").exists() is False and not (repo / ".git").is_file():
            git_dir = git(["rev-parse", "--is-inside-work-tree"], cwd=repo)
            if git_dir.returncode != 0:
                return {"allowed": False, "reason": "NOT_A_GIT_REPO"}
    return {"allowed": True, "reason": "ALLOW", "repository_id": identity or leaf}


def is_scoped_repair_path(path: str | Path, repair_root: Path | None = None) -> bool:
    n = _norm(str(path))
    root = _norm(str(repair_root or default_repair_root()))
    if n == root or n.startswith(root + "\\"):
        return True
    return f"\\{SCOPED_DIR_NAME}\\" in f"\\{n}\\"


def authorize_cursor_workspace(
    workspace: str,
    *,
    repair_root: Path | None = None,
    now: datetime | None = None,
) -> dict:
    """Cursor may use a scoped workspace only with a live trusted receipt."""
    repair_root = repair_root or default_repair_root()
    if not workspace:
        return {"allowed": False, "reason": "MISSING_WORKSPACE"}
    if not is_scoped_repair_path(workspace, repair_root):
        return {"allowed": True, "reason": "NOT_SCOPED_REPAIR", "scoped": False}
    full = Path(workspace)
    try:
        resolved = full.resolve()
        resolved.relative_to(repair_root.resolve())
    except (OSError, ValueError):
        return {"allowed": False, "reason": "UNAPPROVED_PATH", "scoped": True}
    if resolved == receipts_dir(repair_root).resolve() or resolved == repair_root.resolve():
        return {"allowed": False, "reason": "INVALID_DESTINATION", "scoped": True}
    marker = resolved / RECEIPT_NAME
    if not marker.is_file():
        return {"allowed": False, "reason": "MISSING_SCOPED_RECEIPT", "scoped": True}
    try:
        local = load_json(marker)
    except (OSError, json.JSONDecodeError):
        return {"allowed": False, "reason": "INVALID_SCOPED_RECEIPT", "scoped": True}
    op_id = str(local.get("operation_id") or "")
    trusted_path = receipts_dir(repair_root) / f"{op_id}.json"
    if not trusted_path.is_file():
        return {"allowed": False, "reason": "MISSING_TRUSTED_RECEIPT", "scoped": True}
    try:
        trusted = load_json(trusted_path)
    except (OSError, json.JSONDecodeError):
        return {"allowed": False, "reason": "INVALID_TRUSTED_RECEIPT", "scoped": True}
    if trusted.get("status") != "COMPLETED":
        return {"allowed": False, "reason": "RECEIPT_NOT_COMPLETED", "scoped": True}
    if trusted.get("cleaned"):
        return {"allowed": False, "reason": "WORKSPACE_CLEANED", "scoped": True}
    if _norm(str(trusted.get("workspace_path"))) != _norm(str(resolved)):
        return {"allowed": False, "reason": "WORKSPACE_RECEIPT_MISMATCH", "scoped": True}
    created = trusted.get("created_at")
    try:
        created_dt = datetime.strptime(str(created), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return {"allowed": False, "reason": "RECEIPT_EXPIRED", "scoped": True}
    age = (now or datetime.now(timezone.utc)) - created_dt
    if age.total_seconds() > int(trusted.get("ttl_sec") or DEFAULT_TTL_SEC):
        return {"allowed": False, "reason": "RECEIPT_EXPIRED", "scoped": True}
    if not resolved.is_dir():
        return {"allowed": False, "reason": "WORKSPACE_MISSING", "scoped": True}
    return {
        "allowed": True,
        "reason": "SCOPED_RECEIPT",
        "scoped": True,
        "operation_id": op_id,
        "workspace_path": str(resolved),
        "base_sha": trusted.get("base_sha"),
    }


def _copy_files_at_sha(source: Path, sha: str, files: list[str], dest: Path) -> str | None:
    raw = subprocess.run(
        ["git", "archive", "--format=tar", sha, "--", *files],
        cwd=str(source),
        capture_output=True,
        timeout=GIT_TIMEOUT_SEC,
        check=False,
    )
    if raw.returncode != 0:
        return (raw.stderr.decode("utf-8", errors="replace") or "git archive failed")[:400]
    try:
        with tarfile.open(fileobj=io.BytesIO(raw.stdout), mode="r:") as archive:
            dest.mkdir(parents=True, exist_ok=True)
            try:
                archive.extractall(dest, filter="data")
            except TypeError:
                archive.extractall(dest)
    except (tarfile.TarError, OSError) as exc:
        return f"archive extract failed: {exc}"
    return None


def create_scoped_repair_workspace(
    *,
    repo: str,
    files: list[str],
    expected_base_sha: str,
    operation_id: str | None = None,
    repo_id: str | None = None,
    destination: str | None = None,
    repair_root: Path | None = None,
    policy: dict | None = None,
) -> dict:
    op_id = operation_id or new_operation_id()
    policy = policy or load_policy()
    repair_root = repair_root or default_repair_root()
    if destination:
        return blocked(op_id, "INVALID_DESTINATION: callers cannot choose the workspace path", repo_id=repo_id)
    if not expected_base_sha or not re.fullmatch(r"[0-9a-fA-F]{7,40}", expected_base_sha.strip()):
        return blocked(op_id, "INVALID_BASE_SHA", repo_id=repo_id, base_sha=expected_base_sha)
    source = Path(repo)
    auth = authorize_source_repo(source, repo_id=repo_id, policy=policy)
    if not auth.get("allowed"):
        return blocked(op_id, auth.get("reason") or "UNAPPROVED_PATH", repo_id=repo_id, authorization=auth)
    identity = auth.get("repository_id") or repo_id or source.name
    if not (source / ".git").exists():
        inside = git(["rev-parse", "--is-inside-work-tree"], cwd=source)
        if inside.returncode != 0:
            return failed(op_id, "NOT_A_GIT_REPO", repo_id=identity, authoritative_repo=str(source))
    before = git_status_porcelain(source)
    parsed = git(["rev-parse", expected_base_sha.strip()], cwd=source)
    if parsed.returncode != 0:
        return blocked(
            op_id,
            "STALE_OR_UNKNOWN_BASE_SHA",
            repo_id=identity,
            authoritative_repo=str(source.resolve()),
            base_sha=expected_base_sha,
            authorization=auth,
        )
    sha = parsed.stdout.strip()
    head = git_head(source)
    if not head or head.lower() != sha.lower():
        return blocked(
            op_id,
            "STALE_OR_UNKNOWN_BASE_SHA",
            repo_id=identity,
            authoritative_repo=str(source.resolve()),
            base_sha=expected_base_sha,
            authorization=auth,
            extra={"actual_head": head},
        )

    if not files:
        return blocked(op_id, "EMPTY_FILE_SCOPE", repo_id=identity, authoritative_repo=str(source), base_sha=sha)
    if len(files) > MAX_FILES:
        return blocked(op_id, "FILE_SCOPE_TOO_LARGE", repo_id=identity, authoritative_repo=str(source), base_sha=sha)

    selected = []
    for rel in files:
        full, err = resolve_inside(source, rel)
        if err:
            reason = (
                "PATH_TRAVERSAL"
                if "traversal" in err
                else "ABSOLUTE_PATH"
                if "absolute" in err or "home-relative" in err
                else "SYMLINK_ESCAPE"
                if "symlink" in err or "junction" in err
                else "UNAUTHORIZED_SOURCE_FILE"
            )
            return blocked(
                op_id,
                f"{reason}: {err}",
                repo_id=identity,
                authoritative_repo=str(source.resolve()),
                base_sha=sha,
                authorization=auth,
            )
        listed = posixpath.normpath(rel.replace("\\", "/")).lstrip("./")
        blob = git(["cat-file", "-e", f"{sha}:{listed}"], cwd=source)
        if blob.returncode != 0:
            return blocked(
                op_id,
                f"UNAUTHORIZED_SOURCE_FILE: {listed} is not in {sha}",
                repo_id=identity,
                authoritative_repo=str(source.resolve()),
                base_sha=sha,
                selected_files=selected,
                authorization=auth,
            )
        selected.append(listed)

    try:
        repair_root.mkdir(parents=True, exist_ok=True)
        dest = (repair_root.resolve() / op_id).resolve()
        dest.relative_to(repair_root.resolve())
    except (OSError, ValueError):
        return blocked(op_id, "INVALID_DESTINATION", repo_id=identity)
    if dest.exists():
        return failed(op_id, "WORKSPACE_EXISTS", repo_id=identity, workspace_path=str(dest))
    if is_denied_path(str(dest), policy):
        return blocked(op_id, "INVALID_DESTINATION", repo_id=identity, workspace_path=str(dest))

    err = _copy_files_at_sha(source, sha, selected, dest)
    if err:
        force_rmtree(dest)
        return failed(op_id, f"COPY_FAILED: {err}", repo_id=identity, authoritative_repo=str(source), base_sha=sha)

    init = git(["init"], cwd=dest)
    if init.returncode != 0:
        force_rmtree(dest)
        return failed(op_id, "GIT_INIT_FAILED", repo_id=identity, workspace_path=str(dest))
    git(["config", "user.email", "neewa-scoped-repair@local"], cwd=dest)
    git(["config", "user.name", "NEEWA scoped repair"], cwd=dest)
    git(["config", "commit.gpgsign", "false"], cwd=dest)
    payload = {
        "operation_id": op_id,
        "repository_id": identity,
        "authoritative_repo": str(source.resolve()),
        "workspace_path": str(dest),
        "base_sha": sha,
        "selected_files": selected,
        "created_at": utc_now(),
        "ttl_sec": DEFAULT_TTL_SEC,
        "status": "COMPLETED",
    }
    save_json(dest / RECEIPT_NAME, payload)
    git(["add", "-A"], cwd=dest)
    commit = git(["commit", "-m", f"scoped repair snapshot of {identity}@{sha[:12]}"], cwd=dest)
    if commit.returncode != 0:
        force_rmtree(dest)
        return failed(op_id, "GIT_COMMIT_FAILED", repo_id=identity, workspace_path=str(dest))

    after = git_status_porcelain(source)
    if after != before:
        force_rmtree(dest)
        return failed(
            op_id,
            "AUTHORITATIVE_REPO_MUTATED",
            repo_id=identity,
            authoritative_repo=str(source.resolve()),
            base_sha=sha,
        )

    trusted = receipt(
        operation_id=op_id,
        status="COMPLETED",
        repo_id=identity,
        authoritative_repo=str(source.resolve()),
        workspace_path=str(dest),
        base_sha=sha,
        selected_files=selected,
        authorization=auth,
        extra={"ttl_sec": DEFAULT_TTL_SEC, "cleaned": False, "receipt_kind": "create"},
    )
    save_json(receipts_dir(repair_root) / f"{op_id}.json", trusted)
    save_json(dest / RECEIPT_NAME, {**payload, "trusted_receipt": str(receipts_dir(repair_root) / f"{op_id}.json")})
    return trusted


def _load_trusted(operation_id: str, repair_root: Path) -> dict | None:
    path = receipts_dir(repair_root) / f"{operation_id}.json"
    if not path.is_file():
        return None
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return None


def review_scoped_repair_patch(
    *,
    operation_id: str,
    repair_root: Path | None = None,
) -> dict:
    repair_root = repair_root or default_repair_root()
    trusted = _load_trusted(operation_id, repair_root)
    if not trusted:
        return failed(operation_id, "MISSING_TRUSTED_RECEIPT")
    gate = authorize_cursor_workspace(trusted.get("workspace_path") or "", repair_root=repair_root)
    if not gate.get("allowed"):
        return blocked(operation_id, gate.get("reason") or "UNAPPROVED_PATH", extra={"receipt_kind": "review"})
    workspace = Path(trusted["workspace_path"])
    source = Path(trusted["authoritative_repo"])
    allow = set(trusted.get("selected_files") or [])
    porcelain = git_status_porcelain(workspace)
    changed = []
    for line in porcelain.splitlines():
        name = line[3:].strip().replace("\\", "/")
        if " -> " in name:
            name = name.split(" -> ", 1)[-1]
        name = name.strip().strip('"')
        if name and name != RECEIPT_NAME:
            changed.append(name)
    unexpected = [name for name in changed if name not in allow]
    current_head = git_head(source)
    source_moved = bool(current_head and current_head != trusted.get("base_sha"))
    dirty = git_status_porcelain(source).strip()
    patch = git(["diff", "HEAD", "--", *sorted(allow)], cwd=workspace)
    result = receipt(
        operation_id=operation_id,
        status="BLOCKED" if unexpected or not workspace.is_dir() else "COMPLETED",
        repo_id=trusted.get("repository_id"),
        authoritative_repo=str(source),
        workspace_path=str(workspace),
        base_sha=trusted.get("base_sha"),
        selected_files=list(allow),
        extra={
            "receipt_kind": "review",
            "changed_files": changed,
            "unexpected_files": unexpected,
            "source_head": current_head,
            "source_moved": source_moved,
            "authoritative_dirty": bool(dirty),
            "patch": patch.stdout,
            "independent_validation_required": True,
            "apply_allowed": not unexpected and not source_moved and not dirty,
            "apply_block_reason": (
                "UNEXPECTED_CHANGED_FILES"
                if unexpected
                else "SOURCE_MOVED"
                if source_moved
                else "UNCOMMITTED_OWNER_CHANGES"
                if dirty
                else None
            ),
        },
    )
    if unexpected:
        result["failure_reason"] = "UNEXPECTED_CHANGED_FILES"
        result["status"] = "BLOCKED"
    return result


def apply_scoped_repair_patch(
    *,
    operation_id: str,
    repair_root: Path | None = None,
) -> dict:
    """Apply a reviewed patch to the authoritative repo. Does not commit or push."""
    review = review_scoped_repair_patch(operation_id=operation_id, repair_root=repair_root)
    review["operation"] = "apply_scoped_repair_patch"
    unexpected = list(review.get("unexpected_files") or [])
    if unexpected:
        review["status"] = "BLOCKED"
        review["failure_reason"] = "UNEXPECTED_CHANGED_FILES"
        review["applied"] = False
        return review
    if review.get("authoritative_dirty"):
        review["status"] = "BLOCKED"
        review["failure_reason"] = "UNCOMMITTED_OWNER_CHANGES"
        review["applied"] = False
        return review
    patch_text = review.get("patch") or ""
    if not patch_text.strip():
        review["status"] = "COMPLETED"
        review["failure_reason"] = None
        review["applied"] = False
        review["note"] = "no file changes to apply"
        return review
    source = Path(review["authoritative_repo"])
    check = subprocess.run(
        ["git", "apply", "--check", "-"],
        cwd=str(source),
        input=patch_text,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SEC,
        check=False,
    )
    if check.returncode != 0:
        review["status"] = "BLOCKED"
        review["failure_reason"] = "PATCH_CONFLICT"
        review["applied"] = False
        review["apply_stderr"] = (check.stderr or check.stdout)[:500]
        return review
    if review.get("source_moved"):
        review["status"] = "BLOCKED"
        review["failure_reason"] = "SOURCE_MOVED"
        review["applied"] = False
        return review
    apply = subprocess.run(
        ["git", "apply", "-"],
        cwd=str(source),
        input=patch_text,
        capture_output=True,
        text=True,
        timeout=GIT_TIMEOUT_SEC,
        check=False,
    )
    if apply.returncode != 0:
        review["status"] = "FAILED"
        review["failure_reason"] = "PATCH_APPLY_FAILED"
        review["applied"] = False
        review["apply_stderr"] = (apply.stderr or apply.stdout)[:500]
        return review
    review["status"] = "COMPLETED"
    review["failure_reason"] = None
    review["applied"] = True
    review["committed"] = False
    review["pushed"] = False
    review["note"] = "patch applied as uncommitted files; commit remains owner/Cursor; push is not performed"
    return review


def cleanup_scoped_repair_workspace(
    *,
    operation_id: str,
    target: str | None = None,
    repair_root: Path | None = None,
) -> dict:
    repair_root = repair_root or default_repair_root()
    trusted = _load_trusted(operation_id, repair_root)
    if not trusted:
        return blocked(operation_id, "MISSING_TRUSTED_RECEIPT", extra={"receipt_kind": "cleanup"})
    workspace = Path(trusted.get("workspace_path") or "")
    source = Path(trusted.get("authoritative_repo") or "")
    if target:
        requested = Path(target).resolve()
        if _norm(str(requested)) != _norm(str(workspace)):
            return blocked(
                operation_id,
                "CLEANUP_REFUSED_UNRELATED_DIRECTORY",
                workspace_path=str(requested),
                extra={"receipt_kind": "cleanup"},
            )
    try:
        resolved = workspace.resolve()
        resolved.relative_to(repair_root.resolve())
    except (OSError, ValueError):
        return blocked(operation_id, "CLEANUP_REFUSED_UNRELATED_DIRECTORY", extra={"receipt_kind": "cleanup"})
    if source.exists() and resolved == source.resolve():
        return blocked(operation_id, "CLEANUP_REFUSED_AUTHORITATIVE_REPO", extra={"receipt_kind": "cleanup"})
    if resolved == repair_root.resolve() or resolved == receipts_dir(repair_root).resolve():
        return blocked(operation_id, "CLEANUP_REFUSED_UNRELATED_DIRECTORY", extra={"receipt_kind": "cleanup"})
    if resolved.is_dir():
        force_rmtree(resolved)
    trusted["cleaned"] = True
    trusted["cleaned_at"] = utc_now()
    save_json(receipts_dir(repair_root) / f"{operation_id}.json", trusted)
    return receipt(
        operation_id=operation_id,
        status="COMPLETED",
        repo_id=trusted.get("repository_id"),
        authoritative_repo=str(source),
        workspace_path=str(workspace),
        base_sha=trusted.get("base_sha"),
        extra={"receipt_kind": "cleanup", "cleaned": True},
    )


def dispatch(job: dict, *, repair_root: Path | None = None) -> dict:
    action = str(job.get("action") or "create_scoped_repair_workspace")
    op_id = str(job.get("operation_id") or job.get("job_id") or new_operation_id())
    repair_root = repair_root or default_repair_root()
    if action == "create_scoped_repair_workspace":
        files = job.get("files") or job.get("selected_files") or []
        if isinstance(files, str):
            files = [files]
        return create_scoped_repair_workspace(
            repo=str(job.get("repo") or job.get("authoritative_repo") or ""),
            files=list(files),
            expected_base_sha=str(job.get("expected_base_sha") or job.get("base_sha") or ""),
            operation_id=op_id,
            repo_id=job.get("repository_id") or job.get("repo_id"),
            destination=job.get("destination") or job.get("workspace_path_override"),
            repair_root=repair_root,
        )
    if action == "review_scoped_repair_patch":
        return review_scoped_repair_patch(operation_id=op_id, repair_root=repair_root)
    if action == "apply_scoped_repair_patch":
        return apply_scoped_repair_patch(operation_id=op_id, repair_root=repair_root)
    if action == "cleanup_scoped_repair_workspace":
        return cleanup_scoped_repair_workspace(
            operation_id=op_id, target=job.get("target") or job.get("path"), repair_root=repair_root
        )
    if action == "authorize_scoped_cursor_workspace":
        gate = authorize_cursor_workspace(str(job.get("repo") or job.get("workspace") or ""), repair_root=repair_root)
        return {
            "operation_id": op_id,
            "operation": action,
            "status": "COMPLETED" if gate.get("allowed") else "BLOCKED",
            "authorization": gate,
            "failure_reason": None if gate.get("allowed") else gate.get("reason"),
            "workspace_path": job.get("repo") or job.get("workspace"),
        }
    return failed(op_id, f"unknown scoped-repair action {action}")


def main() -> int:
    parser = argparse.ArgumentParser(description="NEEWA scoped repair workspace")
    parser.add_argument("command", choices=("create", "review", "apply", "cleanup", "authorize-cursor", "dispatch"))
    parser.add_argument("--repo")
    parser.add_argument("--workspace")
    parser.add_argument("--base-sha")
    parser.add_argument("--file", action="append", dest="files")
    parser.add_argument("--operation-id")
    parser.add_argument("--repo-id")
    parser.add_argument("--destination")
    parser.add_argument("--repair-root")
    parser.add_argument("--target")
    parser.add_argument("--job-file")
    args = parser.parse_args()
    repair_root = Path(args.repair_root) if args.repair_root else None
    if args.command == "dispatch":
        job = load_json(Path(args.job_file))
        result = dispatch(job, repair_root=repair_root)
        print(json.dumps(result, indent=2))
        return 0 if result.get("status") == "COMPLETED" else 2
    if args.command == "create":
        result = create_scoped_repair_workspace(
            repo=args.repo or "",
            files=args.files or [],
            expected_base_sha=args.base_sha or "",
            operation_id=args.operation_id,
            repo_id=args.repo_id,
            destination=args.destination,
            repair_root=repair_root,
        )
    elif args.command == "review":
        result = review_scoped_repair_patch(operation_id=args.operation_id or "", repair_root=repair_root)
    elif args.command == "apply":
        result = apply_scoped_repair_patch(operation_id=args.operation_id or "", repair_root=repair_root)
    elif args.command == "cleanup":
        result = cleanup_scoped_repair_workspace(
            operation_id=args.operation_id or "", target=args.target, repair_root=repair_root
        )
    else:
        gate = authorize_cursor_workspace(args.workspace or args.repo or "", repair_root=repair_root)
        result = {"status": "COMPLETED" if gate.get("allowed") else "BLOCKED", "authorization": gate}
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "COMPLETED" else 2


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    raise SystemExit(main())
