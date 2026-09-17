"""Collect a secret-free local Windows-bridge evidence pack."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAMP = os.environ.get("NEEWA_EVIDENCE_STAMP") or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
EVIDENCE = ROOT / "evidence" / "LOCAL_WINDOWS_BRIDGE" / STAMP


def run(cmd: list[str], timeout: int = 60) -> dict:
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            cwd=ROOT,
        )
        out = (completed.stdout or "") + (completed.stderr or "")
        return {"cmd": cmd, "exit": completed.returncode, "ok": completed.returncode == 0, "tail": out.strip()[-800:]}
    except FileNotFoundError:
        return {"cmd": cmd, "exit": None, "ok": False, "tail": "not found"}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "exit": None, "ok": False, "tail": "timeout"}


def which_version(names: list[str], extra: list[str] | None = None) -> dict:
    extra = extra or ["--version"]
    for name in names:
        probe = shutil.which(name)
        if not probe:
            continue
        result = run([probe, *extra], timeout=20)
        first = result["tail"].splitlines()[0] if result["tail"] else ""
        return {"status": "AVAILABLE" if result["ok"] else "ERROR", "path": probe, "detail": first[:240]}
    return {"status": "NOT INSTALLED", "path": None, "detail": ""}


def main() -> int:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    tools = {
        "git": which_version(["git"]),
        "gh": which_version(["gh"]),
        "cursor": which_version(["cursor", "cursor.cmd"]),
        "node": which_version(["node"]),
        "python": which_version(["python"]),
        "cua-driver": which_version(["cua-driver"]),
        "hermes": which_version(["hermes"]),
    }
    cua_bin = shutil.which("cua-driver") or str(
        Path.home() / "AppData/Local/Programs/Cua/cua-driver/bin/cua-driver.exe"
    )
    tools["cua-driver-doctor"] = run([cua_bin, "doctor", "--json"], timeout=30)
    tools["hermes-computer-use-doctor"] = run(["hermes", "computer-use", "doctor"], timeout=45)
    copilot = {"note": "help/extension probe only; no token printed"}
    if shutil.which("gh"):
        copilot.update(run(["gh", "copilot", "--help"], timeout=15))
    ext_root = Path.home() / ".cursor" / "extensions"
    names = []
    if ext_root.is_dir():
        names = sorted(p.name for p in ext_root.iterdir() if p.is_dir() and "copilot" in p.name.lower())
    copilot["cursor_extensions"] = names
    copilot["cursor_copilot"] = "AVAILABLE" if names else "NOT INSTALLED"
    copilot["gh_copilot_cli"] = "AVAILABLE" if copilot.get("ok") else "NOT INSTALLED"
    tools["copilot"] = copilot
    if not tools["cua-driver"].get("path") and Path(cua_bin).is_file():
        tools["cua-driver"] = which_version([cua_bin])
    worker = ROOT / "16_WINDOWS_CLIENT" / "worker"
    tools["worker_path"] = {
        "status": "AVAILABLE",
        "invoke": str(worker / "Invoke-NeewaWindowsJob.ps1"),
        "poller": str(worker / "Start-NeewaWindowsWorker.ps1"),
        "transport": "outbound Tailscale SSH poll",
        "git_writer": "Cursor",
        "public_listener": False,
        "unrestricted_shell": False,
    }
    (EVIDENCE / "tool-status.json").write_text(json.dumps(tools, indent=2) + "\n", encoding="utf-8")
    constraints = {
        "transport": "outbound Tailscale SSH poll",
        "public_listener": False,
        "tailscale_funnel": False,
        "unrestricted_shell": False,
        "git_writer": "Cursor",
        "workspace_root": r"C:\Development\Workspace",
        "mode": "read_only_metadata",
        "exclusions": [
            "secrets",
            "credentials",
            "employer data",
            "banking/trading data",
            "browser profiles",
            ".git internals",
        ],
    }
    (EVIDENCE / "constraints.json").write_text(json.dumps(constraints, indent=2) + "\n", encoding="utf-8")
    raw = Path.home() / "NEEWA-Personal" / "inventory" / "workspace-inventory.json"
    if raw.is_file():
        data = json.loads(raw.read_text(encoding="utf-8-sig"))
        projects = data.get("projects") or []
        summary = {
            "generated_at": data.get("generated_at"),
            "workspace_root": data.get("workspace_root"),
            "mode": data.get("mode"),
            "write_access": data.get("write_access"),
            "file_contents_read": data.get("file_contents_read"),
            "unrestricted_desktop": data.get("unrestricted_desktop"),
            "personal_inventoried": [
                {
                    "name": row["name"],
                    "is_git": row.get("is_git"),
                    "status_doc": row.get("status_doc"),
                    "top_level_count": len(row.get("top_level") or []),
                }
                for row in projects
                if row.get("classification") == "personal" and row.get("inventoried")
            ],
            "denied_skipped": [row["name"] for row in projects if row.get("classification") == "denied"],
            "unclassified_skipped": [row["name"] for row in projects if row.get("classification") == "unclassified"],
            "raw_artifact": "%USERPROFILE%\\NEEWA-Personal\\inventory\\workspace-inventory.json",
            "raw_committed": False,
        }
        (EVIDENCE / "inventory-summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (EVIDENCE / "README.md").write_text(
        "# Local Windows bridge evidence\n\n"
        "Sanitized pack. No secrets, credentials, employer trees, banking/trading data, "
        "browser profiles, or `.git` internals.\n",
        encoding="utf-8",
    )
    proc = run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$p = @(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'Start-NeewaWindowsWorker' }); "
            "if ($p.Count -gt 0) { 'RUNNING pid=' + (($p | ForEach-Object ProcessId) -join ',') } else { 'NOT_RUNNING' }",
        ],
        timeout=20,
    )
    run_keys = run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            "$r = Get-ItemProperty 'HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run' -ErrorAction SilentlyContinue; "
            "'worker=' + [bool]$r.'NEEWA-WindowsWorker' + '; cua=' + [bool]$r.'NEEWA-CuaDriver'",
        ],
        timeout=15,
    )
    worker_status = {
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "process": (proc.get("tail") or "UNKNOWN").strip().splitlines()[-1],
        "hkcu": (run_keys.get("tail") or "").strip().splitlines()[-1] if run_keys.get("tail") else "",
        "transport": "outbound Tailscale SSH poll",
        "public_listener": False,
        "unrestricted_shell": False,
        "git_writer": "Cursor",
    }
    (EVIDENCE / "worker-status.json").write_text(json.dumps(worker_status, indent=2) + "\n", encoding="utf-8")
    print(EVIDENCE)
    print(STAMP)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
