"""Receipt-backed A2 authorization for the NEEWA Windows worker.

Prompt wording is never authorization. The Ubuntu receipts retrieved over the
existing verified SSH connection (ubuntu@neewa-core-01) are the source of
truth. Local cache is atomic and advisory only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Mapping

def _load_action_semantics():
    try:
        from neewa_action_semantics import authorize_text as _at
        from neewa_action_semantics import public_authorization as _pa

        return _at, _pa
    except ImportError:
        pass
    from importlib.machinery import SourceFileLoader

    here = Path(__file__).resolve().parent
    candidates = (
        here / "neewa_action_semantics.py",
        here.parent.parent / "12_SCRIPTS" / "neewa_action_semantics.py",
        here.parent / "12_SCRIPTS" / "neewa_action_semantics.py",
    )
    for candidate in candidates:
        if candidate.is_file():
            sem = SourceFileLoader("neewa_action_semantics_a2", str(candidate)).load_module()
            return sem.authorize_text, sem.public_authorization
    raise ImportError("neewa_action_semantics.py is required for A2 receipt authorization")


authorize_text, public_authorization = _load_action_semantics()

AUTHORIZED = "AUTHORIZED"
DENIED = "DENIED"

DEFAULT_SSH_HOST = "ubuntu@neewa-core-01"
SANDBOX_JOBS = "/workspace/windows-jobs"
HOST_JOBS = "/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs"
DEFAULT_CACHE_DIR = r"%LOCALAPPDATA%\NEENEEWA\authorizations"

AUTHORIZATION_FIELDS = (
    "approval_level",
    "approval_receipt_path",
    "approval_receipt_sha256",
    "binding_receipt_path",
    "binding_receipt_sha256",
    "mission_id",
    "parent_id",
    "repository_remote",
    "workspace_path",
    "pr_number",
    "approved_commit",
    "deployment_target",
    "authorized_actions",
)

APPROVAL_REQUIRED = (
    "approval_type",
    "status",
    "mission_id",
    "parent_job_id",
    "repository",
    "pr",
    "validated_head",
    "target",
    "authorized_scope",
)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
SAFE_PATH_RE = re.compile(r"^[/A-Za-z0-9._+=,@-]+$")
A3_FAMILIES = {"financial"}
FAMILY_SCOPE_HINTS = {
    "deploy": re.compile(r"\bdeploy(?:ment)?\b|\broll\s*out\b", re.I),
    "publish": re.compile(r"\bpublish|\brelease\b", re.I),
    "purchase": re.compile(r"\bpurchase|\bbuy\b|\bsubscribe\b", re.I),
    "send_message": re.compile(r"\bemail\b|\bexternal messages?\b", re.I),
    "destructive": re.compile(r"\bdelete everything\b|\bdrop database\b|\brm -rf\b", re.I),
    "make_public": re.compile(r"\bmake public\b|\bvisibility\b|\bpublic internet\b", re.I),
    "credential": re.compile(r"\bcredential\b|\bantivirus\b|\bdefender\b", re.I),
    "release": re.compile(r"\brelease\b", re.I),
}

FetchFn = Callable[[str], bytes]


class ReceiptFetchError(Exception):
    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().lower()


def default_cache_dir() -> Path:
    override = os.environ.get("NEEWA_A2_AUTH_CACHE")
    if override:
        return Path(override)
    expanded = os.path.expandvars(DEFAULT_CACHE_DIR)
    if "%" in expanded or not expanded:
        return Path(tempfile.gettempdir()) / "NEENEEWA" / "authorizations"
    return Path(expanded)


def map_receipt_path(path: str) -> str:
    text = (path or "").strip().replace("\\", "/")
    if text.startswith(SANDBOX_JOBS):
        return HOST_JOBS + text[len(SANDBOX_JOBS) :]
    return text


def _norm_remote(url: str) -> str:
    text = (url or "").strip().lower().rstrip("/")
    if text.endswith(".git"):
        text = text[:-4]
    text = text.replace("git@github.com:", "https://github.com/")
    text = text.replace("ssh://git@github.com/", "https://github.com/")
    return text


def _norm_workspace(path: str) -> str:
    text = os.path.expandvars(path or "").strip().strip('"')
    text = text.replace("/", "\\")
    while "\\\\" in text:
        text = text.replace("\\\\", "\\")
    return os.path.normcase(os.path.normpath(text)).rstrip("\\")


def _norm_host(value: str) -> str:
    return (value or "").strip().lower()


def _norm_commit(value: str) -> str:
    return (value or "").strip().lower()


def _norm_pr(value) -> str:
    text = str(value or "").strip().lower()
    if text.startswith("#"):
        text = text[1:]
    return text


def _norm_scope_item(item: str) -> str:
    return " ".join(str(item).lower().split())


def _as_action_list(value) -> list[str]:
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    return []


def _as_dict(value) -> dict:
    if isinstance(value, dict):
        return value
    if value is None:
        return {}
    if hasattr(value, "items"):
        return dict(value)
    return {}


def structured_authorization(job: Mapping) -> dict | None:
    raw = job.get("authorization") if isinstance(job, Mapping) else None
    if not isinstance(raw, dict):
        return None
    return raw


def authorization_object_is_well_formed(auth: Mapping | None) -> bool:
    if not isinstance(auth, dict):
        return False
    for field in AUTHORIZATION_FIELDS:
        if field not in auth or auth.get(field) in (None, ""):
            return False
    actions = _as_action_list(auth.get("authorized_actions"))
    if not actions:
        return False
    level = str(auth.get("approval_level") or "").strip().upper()
    if level not in {"A2", "A3"}:
        return False
    for key in ("approval_receipt_sha256", "binding_receipt_sha256"):
        if not SHA256_RE.fullmatch(str(auth.get(key) or "").strip().lower()):
            return False
    if not COMMIT_RE.fullmatch(str(auth.get("approved_commit") or "").strip()):
        return False
    return True


def _audit_record(payload: dict) -> dict:
    blocked = ("password", "secret", "token", "api_key", "credential", "private_key", "prompt")
    out = {}
    for key, value in payload.items():
        low = str(key).lower()
        if any(part in low for part in blocked):
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[key] = value
        elif isinstance(value, list) and all(isinstance(item, (str, int)) for item in value):
            out[key] = value
        else:
            out[key] = str(type(value).__name__)
    return out


def _append_audit(cache_dir: Path, record: dict) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    path = cache_dir / "a2-authorization-audit.jsonl"
    line = json.dumps(_audit_record(record), separators=(",", ":")) + "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _atomic_write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def _cache_key(approval_id: str, job_id: str, receipt_hash: str) -> str:
    blob = f"{approval_id}|{job_id}|{receipt_hash}".encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def _load_cache(cache_dir: Path, key: str) -> dict | None:
    path = cache_dir / f"{key}.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def ssh_fetch(path: str, host: str = DEFAULT_SSH_HOST) -> bytes:
    if os.environ.get("NEEWA_A2_DISABLE_SSH") == "1":
        raise ReceiptFetchError("MISSING_SSH", "ssh transport disabled")
    mapped = map_receipt_path(path)
    if not mapped or not SAFE_PATH_RE.fullmatch(mapped):
        raise ReceiptFetchError("MALFORMED_RECEIPT", "unsafe receipt path")
    local_root = os.environ.get("NEEWA_A2_RECEIPT_ROOT")
    if local_root:
        candidate = Path(local_root) / Path(mapped).name
        if candidate.is_file():
            return candidate.read_bytes()
        raise ReceiptFetchError("MISSING_RECEIPT", str(candidate))
    try:
        proc = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=8",
                "-o",
                "LogLevel=ERROR",
                host,
                "cat -- " + shlex.quote(mapped),
            ],
            capture_output=True,
            timeout=20,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ReceiptFetchError("MISSING_SSH", "ssh not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise ReceiptFetchError("MISSING_SSH", "ssh timeout") from exc
    if proc.returncode != 0 or not proc.stdout:
        raise ReceiptFetchError("MISSING_RECEIPT", mapped)
    return proc.stdout


def _parse_json_bytes(raw: bytes, label: str) -> dict:
    if not raw or not raw.strip():
        raise ReceiptFetchError("MALFORMED_RECEIPT", f"{label} empty")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReceiptFetchError("MALFORMED_RECEIPT", f"{label} is not JSON") from exc
    if not isinstance(data, dict):
        raise ReceiptFetchError("MALFORMED_RECEIPT", f"{label} is not an object")
    return data


def _denied(reason: str, **extra) -> dict:
    payload = {
        "allowed": False,
        "decision": DENIED,
        "reason": reason,
        "needed": extra.pop("needed", "A2"),
        "receipt_backed": True,
        "effective_approval": extra.pop("effective_approval", "A2"),
        "replay": False,
    }
    payload.update(extra)
    return public_authorization(payload) | payload


def _granted(**extra) -> dict:
    payload = {
        "allowed": True,
        "decision": AUTHORIZED,
        "reason": extra.pop("reason", "A2_RECEIPT_AUTHORIZED"),
        "needed": extra.pop("needed", "A2"),
        "receipt_backed": True,
        "effective_approval": "A2",
        "replay": bool(extra.pop("replay", False)),
    }
    payload.update(extra)
    return public_authorization(payload) | payload


def _approval_revoked(approval: dict) -> str | None:
    status = str(approval.get("status") or "").strip().upper()
    if status in {"REVOKED", "SUPERSEDED", "DENIED", "EXPIRED", "WITHDRAWN"}:
        return "REVOKED" if status != "SUPERSEDED" else "SUPERSEDED"
    if status != "GRANTED":
        return "REVOKED"
    if approval.get("revoked") or approval.get("revoked_at"):
        return "REVOKED"
    if approval.get("superseded") or approval.get("superseded_by"):
        return "SUPERSEDED"
    return None


def _scope_covers_family(scope: list[str], family: str) -> bool:
    if family in A3_FAMILIES:
        return False
    hint = FAMILY_SCOPE_HINTS.get(family)
    if hint is None:
        return False
    return any(hint.search(item or "") for item in scope)


def _prompt_exceeds_scope(prompt_decision: dict | None, scope: list[str]) -> str | None:
    src = prompt_decision or {}
    families = list(src.get("requested_families") or [])
    for family in families:
        if family in A3_FAMILIES or src.get("needed") == "A3":
            return "A3_NOT_AUTHORIZED"
        if not _scope_covers_family(scope, family):
            return "PROMPT_EXCEEDS_SCOPE"
    matched = str(src.get("matched_rule") or "").strip()
    if matched and not families:
        if src.get("needed") in {"A2", "A3"} and not any(
            matched.lower() in item.lower() for item in scope
        ):
            return "PROMPT_EXCEEDS_SCOPE"
    return None


def authorize_job(
    job: Mapping,
    *,
    fetch: FetchFn | None = None,
    cache_dir: Path | str | None = None,
    prompt_decision: dict | None = None,
    ssh_host: str = DEFAULT_SSH_HOST,
) -> dict:
    """Independently verify Ubuntu A2 receipts and bind them to the job."""
    cache_path = Path(cache_dir) if cache_dir else default_cache_dir()
    fetch_bytes = fetch or (lambda path: ssh_fetch(path, host=ssh_host))
    job_id = str(job.get("job_id") or "").strip()
    auth = structured_authorization(job)
    remote_claim = str((auth or {}).get("repository_remote") or job.get("repository") or "")
    prompt = str(job.get("prompt") or "")
    if prompt_decision is None and prompt:
        prompt_decision = authorize_text(prompt, write=bool(job.get("write")))

    if not auth:
        needed = (prompt_decision or {}).get("needed") or str(job.get("approval") or "A1")
        if needed in {"A0", "A1"} and str(job.get("approval") or "A1") in {"", "A0", "A1"}:
            return public_authorization(prompt_decision or {"allowed": True, "needed": needed, "reason": "ALLOW"})
        result = _denied("MISSING_AUTHORIZATION", job_id=job_id, needed=needed)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    if not authorization_object_is_well_formed(auth):
        result = _denied("MALFORMED_RECEIPT", job_id=job_id, detail="authorization object")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    approval_level = str(auth["approval_level"]).strip().upper()
    if approval_level == "A3":
        result = _denied("A3_NOT_AUTHORIZED", job_id=job_id, needed="A3")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if approval_level != "A2":
        result = _denied("MALFORMED_RECEIPT", job_id=job_id, detail="approval_level")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    expected_approval = str(auth["approval_receipt_sha256"]).strip().lower()
    expected_binding = str(auth["binding_receipt_sha256"]).strip().lower()
    approval_path = str(auth["approval_receipt_path"]).strip()
    binding_path = str(auth["binding_receipt_path"]).strip()

    try:
        approval_raw = fetch_bytes(approval_path)
        binding_raw = fetch_bytes(binding_path)
    except ReceiptFetchError as exc:
        result = _denied(exc.reason, job_id=job_id, detail=exc.detail)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    except Exception as exc:
        result = _denied("MISSING_SSH", job_id=job_id, detail=type(exc).__name__)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    if not approval_raw or not binding_raw:
        result = _denied("MISSING_RECEIPT", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    approval_hash = sha256_bytes(approval_raw)
    binding_hash = sha256_bytes(binding_raw)
    if approval_hash != expected_approval or binding_hash != expected_binding:
        result = _denied(
            "HASH_MISMATCH",
            job_id=job_id,
            approval_sha256=approval_hash,
            binding_sha256=binding_hash,
        )
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    try:
        approval = _parse_json_bytes(approval_raw, "approval")
        binding = _parse_json_bytes(binding_raw, "binding")
    except ReceiptFetchError as exc:
        result = _denied(exc.reason, job_id=job_id, detail=exc.detail)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    for field in APPROVAL_REQUIRED:
        if field not in approval:
            result = _denied("MALFORMED_RECEIPT", job_id=job_id, detail=field)
            _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
            return result

    revoked = _approval_revoked(approval)
    if revoked:
        result = _denied(revoked, job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    if str(approval.get("approval_type") or "").strip().upper() != "A2":
        result = _denied("MALFORMED_RECEIPT", job_id=job_id, detail="approval_type")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    positive = _as_dict(binding.get("positive"))
    if binding.get("positive_pass") is not True or positive.get("approval_granted") is not True:
        result = _denied("REVOKED", job_id=job_id, detail="binding_positive")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    github = _as_dict(binding.get("github"))
    if github and str(github.get("state") or "").upper() not in {"", "OPEN"}:
        result = _denied("SUPERSEDED", job_id=job_id, detail="github_state")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if positive.get("github_open") is False:
        result = _denied("SUPERSEDED", job_id=job_id, detail="github_open")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    claimed_mission = str(auth["mission_id"]).strip()
    claimed_parent = str(auth["parent_id"]).strip()
    if claimed_mission != str(approval.get("mission_id") or "").strip():
        result = _denied("ALTERED_MISSION", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if claimed_parent != str(approval.get("parent_job_id") or "").strip():
        result = _denied("ALTERED_PARENT", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    if _norm_remote(str(auth["repository_remote"])) != _norm_remote(str(approval.get("repository") or "")):
        result = _denied("ALTERED_REPOSITORY", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if remote_claim and _norm_remote(remote_claim) != _norm_remote(str(approval.get("repository") or "")):
        result = _denied("ALTERED_REPOSITORY", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    if _norm_pr(auth["pr_number"]) != _norm_pr(approval.get("pr")):
        result = _denied("ALTERED_PR", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    approved_commit = _norm_commit(str(approval.get("validated_head") or ""))
    if _norm_commit(str(auth["approved_commit"])) != approved_commit:
        result = _denied("ALTERED_COMMIT", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    github_oid = _norm_commit(str(github.get("headRefOid") or ""))
    if github_oid and github_oid != approved_commit:
        result = _denied("ALTERED_COMMIT", job_id=job_id, detail="github_head")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if positive.get("head_exact") is False or positive.get("pr_exact") is False:
        flag = "ALTERED_COMMIT" if positive.get("head_exact") is False else "ALTERED_PR"
        result = _denied(flag, job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    if _norm_host(str(auth["deployment_target"])) != _norm_host(str(approval.get("target") or "")):
        result = _denied("ALTERED_HOST", job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if _norm_host(str(approval.get("target") or "")) != _norm_host(DEFAULT_SSH_HOST):
        result = _denied("ALTERED_HOST", job_id=job_id, detail="ssh_host")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if positive.get("target_exact") is False or positive.get("remote_exact") is False:
        flag = "ALTERED_HOST" if positive.get("target_exact") is False else "ALTERED_REPOSITORY"
        result = _denied(flag, job_id=job_id)
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    receipt_workspace = (
        approval.get("workspace")
        or approval.get("workspace_path")
        or binding.get("workspace")
        or binding.get("workspace_path")
    )
    workspace_values = []
    for raw in (auth.get("workspace_path"), job.get("workspace_path"), job.get("repo")):
        if raw:
            workspace_values.append(_norm_workspace(str(raw)))
    if not workspace_values or len(set(workspace_values)) != 1:
        result = _denied("ALTERED_WORKSPACE", job_id=job_id, detail="job_workspace")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    claimed_workspace = workspace_values[0]
    if receipt_workspace and _norm_workspace(str(receipt_workspace)) != claimed_workspace:
        result = _denied("ALTERED_WORKSPACE", job_id=job_id, detail="receipt_workspace")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    if positive.get("workspace_exact") is False:
        result = _denied("ALTERED_WORKSPACE", job_id=job_id, detail="workspace_exact")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    scope = [str(item) for item in (approval.get("authorized_scope") or []) if str(item).strip()]
    approved_set = {_norm_scope_item(item) for item in scope}
    requested = _as_action_list(auth.get("authorized_actions"))
    if not requested:
        result = _denied("SCOPE_EXCEEDED", job_id=job_id, detail="empty_actions")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result
    extra = [item for item in requested if _norm_scope_item(item) not in approved_set]
    if extra:
        result = _denied("SCOPE_EXCEEDED", job_id=job_id, detail="requested_not_subset")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    prompt_issue = _prompt_exceeds_scope(prompt_decision, requested)
    if prompt_issue:
        result = _denied(prompt_issue, job_id=job_id, needed=(prompt_decision or {}).get("needed") or "A2")
        _append_audit(cache_path, {"event": "deny", "job_id": job_id, **result})
        return result

    approval_id = str(approval.get("approval_id") or f"{claimed_parent}-A2")
    key = _cache_key(approval_id, job_id, approval_hash)
    cached = _load_cache(cache_path, key)
    if cached and cached.get("decision") == AUTHORIZED:
        result = _granted(
            reason="A2_RECEIPT_AUTHORIZED",
            job_id=job_id,
            approval_id=approval_id,
            approval_sha256=approval_hash,
            binding_sha256=binding_hash,
            mission_id=claimed_mission,
            parent_id=claimed_parent,
            replay=True,
            idempotent=True,
            authorized_actions=requested,
        )
        _append_audit(
            cache_path,
            {
                "event": "replay",
                "job_id": job_id,
                "approval_id": approval_id,
                "decision": AUTHORIZED,
            },
        )
        return result

    result = _granted(
        job_id=job_id,
        approval_id=approval_id,
        approval_sha256=approval_hash,
        binding_sha256=binding_hash,
        mission_id=claimed_mission,
        parent_id=claimed_parent,
        pr_number=_norm_pr(auth["pr_number"]),
        approved_commit=approved_commit,
        deployment_target=_norm_host(str(auth["deployment_target"])),
        workspace_path=claimed_workspace,
        repository_remote=_norm_remote(str(auth["repository_remote"])),
        authorized_actions=requested,
        needed=(prompt_decision or {}).get("needed") or "A2",
    )
    _atomic_write_json(
        cache_path / f"{key}.json",
        {
            "key": key,
            "approval_id": approval_id,
            "job_id": job_id,
            "receipt_hash": approval_hash,
            "binding_hash": binding_hash,
            "decision": AUTHORIZED,
            "reason": "A2_RECEIPT_AUTHORIZED",
            "cached_at": utc_now(),
        },
    )
    _append_audit(
        cache_path,
        {
            "event": "authorize",
            "job_id": job_id,
            "approval_id": approval_id,
            "decision": AUTHORIZED,
            "approval_sha256": approval_hash,
            "binding_sha256": binding_hash,
        },
    )
    return result


def merge_prompt_and_receipt(prompt_decision: dict | None, receipt_decision: dict | None) -> dict:
    """Structured receipt hashes win. Prompt text cannot grant or enlarge A2/A3."""
    prompt = public_authorization(prompt_decision or {})
    receipt = receipt_decision or {}
    needed = prompt.get("needed") or "A0"
    if needed == "A3":
        return public_authorization(
            {
                **prompt,
                "allowed": False,
                "reason": receipt.get("reason") or "A3_NOT_AUTHORIZED",
                "receipt_backed": True,
                "effective_approval": "A3",
            }
        )
    if needed in {"A0", "A1"} and not (receipt.get("receipt_backed") or receipt.get("decision")):
        return prompt
    if not receipt.get("allowed"):
        return public_authorization(
            {
                **prompt,
                "allowed": False,
                "reason": receipt.get("reason") or f"{needed}_OWNER_GATE",
                "receipt_backed": True,
                "needed": needed,
                "effective_approval": needed,
            }
        )
    return public_authorization(
        {
            **prompt,
            "allowed": True,
            "reason": "A2_RECEIPT_AUTHORIZED",
            "needed": needed if needed in {"A2"} else prompt.get("needed"),
            "receipt_backed": True,
            "effective_approval": "A2",
            "replay": bool(receipt.get("replay")),
        }
    )


def decide_from_job(job: Mapping, **kwargs) -> dict:
    return authorize_job(job, **kwargs)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NEEWA receipt-backed A2 authorization")
    parser.add_argument("--job-file")
    parser.add_argument("--cache-dir")
    parser.add_argument("--prompt-auth-file")
    args = parser.parse_args(argv)
    if not args.job_file:
        parser.error("--job-file is required")
    job = json.loads(Path(args.job_file).read_text(encoding="utf-8"))
    prompt_decision = None
    if args.prompt_auth_file:
        prompt_decision = json.loads(Path(args.prompt_auth_file).read_text(encoding="utf-8"))
    result = authorize_job(
        job,
        cache_dir=args.cache_dir,
        prompt_decision=prompt_decision,
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
