"""Bound independent-validation receipts for governed merges.

A caller-supplied PASS string is never sufficient. Evidence must name the
repository, pull request, head SHA, test execution, and validator process.
Receipts stored inside the repository under merge are rejected as implementer-writable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
MAX_AGE_SEC = 4 * 60 * 60
VALIDATOR_EXECUTOR = "neewa-independent-validator"
IMPLEMENTER_EXECUTORS = {"neewa-git-ops", "neewa_autonomy.implementer", "implementer"}
SHA_LEN = 7


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def canonical(payload: dict) -> str:
    body = {k: v for k, v in payload.items() if k != "fingerprint"}
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def fingerprint(payload: dict) -> str:
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()


def default_receipt_dir() -> Path:
    override = os.environ.get("NEEWA_VALIDATION_RECEIPT_DIR")
    if override:
        path = Path(override)
    else:
        path = Path(os.environ.get("USERPROFILE") or os.environ.get("HOME") or ".") / "NEEWA-Personal" / "validation-receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_receipt(
    *,
    repository_identity: str,
    pr_number: str,
    head_sha: str,
    test_command: str,
    test_exit_code: int,
    tests_passed: bool,
    executor: str = VALIDATOR_EXECUTOR,
    pid: int | None = None,
    worktree: str | None = None,
    stdout_tail: str = "",
    revoked: bool = False,
    approval_expires_at: str | None = None,
) -> dict:
    result = "PASS" if tests_passed and int(test_exit_code) == 0 else "FAIL"
    row = {
        "schema_version": 1,
        "receipt_id": f"VAL-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8].upper()}",
        "role": "INDEPENDENT_TEST_VALIDATOR",
        "executor": executor,
        "pid": int(pid or os.getpid()),
        "repository_identity": repository_identity,
        "pr_number": str(pr_number),
        "head_sha": (head_sha or "").strip().lower(),
        "test_command": test_command,
        "test_exit_code": int(test_exit_code),
        "tests_passed": bool(tests_passed),
        "result": result,
        "worktree": worktree,
        "stdout_digest": hashlib.sha256((stdout_tail or "").encode("utf-8")).hexdigest()[:32],
        "created_at": utc_now(),
        "revoked": bool(revoked),
        "approval_expires_at": approval_expires_at,
        "independence_class": "separate_process_not_github_user",
    }
    row["fingerprint"] = fingerprint(row)
    return row


def write_receipt(row: dict, directory: Path | None = None) -> Path:
    directory = directory or default_receipt_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{row['receipt_id']}.json"
    path.write_text(json.dumps(row, indent=2) + "\n", encoding="utf-8")
    return path


def load_receipt(path: str | Path) -> dict:
    target = Path(path)
    if not target.is_file():
        raise FileNotFoundError(str(target))
    return json.loads(target.read_text(encoding="utf-8"))


def receipt_inside_repo(receipt_path: Path, repo_path: Path) -> bool:
    try:
        receipt_path.resolve().relative_to(repo_path.resolve())
        return True
    except (ValueError, OSError):
        return False


def _norm_id(value: str) -> str:
    text = (value or "").strip().lower().rstrip("/")
    text = text.replace("git@github.com:", "https://github.com/")
    if text.endswith(".git"):
        text = text[:-4]
    return text


def _sha_match(left: str, right: str) -> bool:
    a = (left or "").strip().lower()
    b = (right or "").strip().lower()
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def verify_receipt(
    receipt: dict,
    *,
    repository_identity: str,
    pr_number: str,
    head_sha: str,
    now: datetime | None = None,
    repo_path: Path | None = None,
    receipt_path: Path | None = None,
) -> dict:
    now = now or datetime.now(timezone.utc)
    if not receipt:
        return {"ok": False, "reason": "MISSING_RECEIPT"}
    expected_fp = fingerprint(receipt)
    if (receipt.get("fingerprint") or "") != expected_fp:
        return {"ok": False, "reason": "RECEIPT_TAMPERED"}
    if receipt.get("revoked"):
        return {"ok": False, "reason": "VALIDATION_REVOKED"}
    expires = receipt.get("approval_expires_at")
    if expires:
        try:
            if now > parse_ts(str(expires)):
                return {"ok": False, "reason": "VALIDATION_REVOKED"}
        except ValueError:
            return {"ok": False, "reason": "VALIDATION_REVOKED"}
    created = receipt.get("created_at")
    try:
        age = (now - parse_ts(str(created))).total_seconds()
    except (TypeError, ValueError):
        return {"ok": False, "reason": "STALE_VALIDATION"}
    if age < 0 or age > MAX_AGE_SEC:
        return {"ok": False, "reason": "STALE_VALIDATION"}
    if str(receipt.get("executor") or "") in IMPLEMENTER_EXECUTORS:
        return {"ok": False, "reason": "IMPLEMENTER_CLAIMED_INSUFFICIENT"}
    if str(receipt.get("executor") or "") != VALIDATOR_EXECUTOR:
        return {"ok": False, "reason": "VALIDATOR_IDENTITY_MISMATCH"}
    if str(receipt.get("role") or "") != "INDEPENDENT_TEST_VALIDATOR":
        return {"ok": False, "reason": "VALIDATOR_IDENTITY_MISMATCH"}
    if _norm_id(str(receipt.get("repository_identity") or "")) != _norm_id(repository_identity):
        return {"ok": False, "reason": "RECEIPT_REPO_MISMATCH"}
    if str(receipt.get("pr_number") or "") != str(pr_number):
        return {"ok": False, "reason": "RECEIPT_PR_MISMATCH"}
    if not _sha_match(str(receipt.get("head_sha") or ""), head_sha):
        return {"ok": False, "reason": "RECEIPT_SHA_MISMATCH"}
    if receipt_path and repo_path and receipt_inside_repo(receipt_path, repo_path):
        return {"ok": False, "reason": "RECEIPT_IN_REPOSITORY"}
    result = str(receipt.get("result") or "").upper()
    if result == "FAIL" or not receipt.get("tests_passed") or int(receipt.get("test_exit_code") or 1) != 0:
        return {"ok": False, "reason": "INDEPENDENT_VALIDATION_FAILED", "result": result}
    if result != "PASS":
        return {"ok": False, "reason": "INDEPENDENT_VALIDATION_REQUIRED", "result": result}
    return {"ok": True, "reason": "BOUND_RECEIPT", "receipt_id": receipt.get("receipt_id"), "result": "PASS"}


def run_tests(worktree: Path, command: list[str] | None = None) -> dict:
    cmd = command or [sys.executable, "-m", "unittest", "discover", "-s", "13_TESTS", "-p", "test_*.py"]
    completed = subprocess.run(
        cmd,
        cwd=str(worktree),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )
    stdout = (completed.stdout or "") + (completed.stderr or "")
    passed = completed.returncode == 0
    return {
        "command": " ".join(cmd),
        "exit_code": completed.returncode,
        "passed": passed,
        "stdout_tail": stdout[-4000:],
    }


def git_sha(worktree: Path) -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(worktree),
        capture_output=True,
        text=True,
        check=False,
    )
    return (completed.stdout or "").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run independent validation and write a bound receipt")
    parser.add_argument("--repo", required=True)
    parser.add_argument("--pr", required=True)
    parser.add_argument("--repository-identity", default="https://github.com/swap2you/neewa-os.git")
    parser.add_argument("--out-dir")
    args = parser.parse_args()
    worktree = Path(args.repo)
    head = git_sha(worktree)
    tests = run_tests(worktree)
    row = build_receipt(
        repository_identity=args.repository_identity,
        pr_number=args.pr,
        head_sha=head,
        test_command=tests["command"],
        test_exit_code=tests["exit_code"],
        tests_passed=tests["passed"],
        worktree=str(worktree),
        stdout_tail=tests["stdout_tail"],
    )
    path = write_receipt(row, Path(args.out_dir) if args.out_dir else None)
    print(json.dumps({"receipt_path": str(path), "receipt": row}, indent=2))
    return 0 if tests["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
