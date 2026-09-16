#!/usr/bin/env python3
"""Deterministic NEEWA morning brief.

Runs correctly in two contexts:

* HOST: the NEEWA server, where systemctl and the read-only host probe
  (~/.hermes/scripts/neewa_host_status.sh) are available. If the authoritative
  snapshot is missing or stale, it is refreshed before reporting.
* SANDBOX: the isolated Docker execution container, where host-only binaries
  (systemctl/swapon) do NOT exist. Here the brief consumes the authoritative
  read-only snapshot at /opt/neewa/status/latest.json and never invokes
  unavailable host commands.

Failure handling is explicit: missing, stale, malformed, and partial snapshots
are reported as such. A service is NEVER reported healthy when its status is
unknown, and the exit code is non-zero unless the snapshot is fresh and every
key service is active.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
from pathlib import Path

def _resolve_root() -> Path:
    """Locate the repo root robustly.

    The script runs both from the repo checkout (…/neewa-os/12_SCRIPTS/) and
    from a deployed host copy (~/.hermes/scripts/), where parents[1] is NOT the
    repo. Prefer NEEWA_REPO, then a parent that actually contains 11_CONFIG,
    then the canonical server path."""
    env = os.environ.get("NEEWA_REPO")
    if env and (Path(env) / "11_CONFIG").is_dir():
        return Path(env)
    here = Path(__file__).resolve().parents[1]
    if (here / "11_CONFIG").is_dir():
        return here
    canonical = Path("/opt/neewa/neewa-os")
    if (canonical / "11_CONFIG").is_dir():
        return canonical
    return here


ROOT = _resolve_root()
STATUS_DIR = Path(os.environ.get("NEEWA_STATUS_DIR", "/opt/neewa/status"))
SNAPSHOT = STATUS_DIR / "latest.json"
HOST_PROBE = Path.home() / ".hermes" / "scripts" / "neewa_host_status.sh"
MAX_AGE_S = int(os.environ.get("NEEWA_SNAPSHOT_MAX_AGE_S", "1200"))  # 20 min
KEY_SERVICES = ("hermes_gateway", "docker", "tailscaled", "ollama")


def on_host() -> bool:
    """Host mode = the read-only host probe exists AND systemctl is usable.

    In the sandbox neither is true (the probe lives under ~ which maps to the
    container home and is not mounted; systemctl is absent). Any stat error
    (e.g. an unreadable path in a restricted namespace) fails closed to
    sandbox mode."""
    try:
        return HOST_PROBE.is_file() and shutil.which("systemctl") is not None
    except OSError:
        return False


def refresh_snapshot_on_host() -> None:
    """Best-effort: run the read-only host probe to refresh the snapshot.

    Host-only. Never raises; failures leave the (possibly stale/missing)
    snapshot in place and are surfaced downstream as stale/unavailable."""
    try:
        subprocess.run(["bash", str(HOST_PROBE)], capture_output=True, text=True, timeout=60)
    except Exception:
        pass


def load_snapshot() -> tuple[dict | None, str]:
    """Return (snapshot_or_None, state). state in {ok, missing, malformed}."""
    if not SNAPSHOT.is_file():
        return None, "missing"
    try:
        data = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None, "malformed"
        return data, "ok"
    except (OSError, json.JSONDecodeError):
        return None, "malformed"


def snapshot_age_seconds(snapshot: dict) -> float | None:
    raw = snapshot.get("generated_at")
    if not isinstance(raw, str):
        return None
    try:
        ts = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = dt.datetime.now(dt.timezone.utc)
    return (now - ts).total_seconds()


def read_repo_json(rel: str) -> dict:
    try:
        return json.loads((ROOT / rel).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def main() -> int:
    context = "host" if on_host() else "sandbox"

    # On the host, keep the authoritative snapshot fresh before reading it.
    if context == "host":
        snapshot, state = load_snapshot()
        age = snapshot_age_seconds(snapshot) if snapshot else None
        if state != "ok" or age is None or age > MAX_AGE_S:
            refresh_snapshot_on_host()

    snapshot, state = load_snapshot()
    age = snapshot_age_seconds(snapshot) if snapshot else None
    stale = age is None or age > MAX_AGE_S

    lines: list[str] = ["NEEWA MORNING BRIEF", f"Context: {context}"]

    # --- snapshot freshness ---
    if state == "missing":
        lines.append("Host snapshot: UNAVAILABLE (no /opt/neewa/status/latest.json)")
    elif state == "malformed":
        lines.append("Host snapshot: UNAVAILABLE (malformed JSON)")
    elif stale:
        shown = f"{int(age)}s old" if age is not None else "no timestamp"
        lines.append(f"Host snapshot: STALE ({shown}; threshold {MAX_AGE_S}s) — treating host facts as unknown")
    else:
        lines.append(f"Host snapshot: fresh (generated_at={snapshot.get('generated_at')}, {int(age)}s old)")

    healthy_snapshot = state == "ok" and not stale
    services = snapshot.get("services", {}) if isinstance(snapshot, dict) else {}

    # --- services: unknown unless the fresh snapshot says active ---
    svc_report = []
    all_active = True
    for svc in KEY_SERVICES:
        if healthy_snapshot and isinstance(services, dict) and svc in services:
            value = str(services.get(svc))
        else:
            value = "unknown"
        if value != "active":
            all_active = False
        svc_report.append(f"{svc}={value}")
    lines.append("Services: " + ", ".join(svc_report))

    # --- repository (from fresh snapshot only; else unknown) ---
    if healthy_snapshot and isinstance(snapshot.get("repository"), dict):
        repo = snapshot["repository"]
        lines.append(f"Repository: {repo.get('branch','?')}/{repo.get('head','?')} ({repo.get('state','?')})")
    else:
        lines.append("Repository: unknown (no fresh host snapshot)")

    # --- local fallback model (from repo registry — available in both contexts) ---
    models = read_repo_json("11_CONFIG/models.json").get("models", [])
    local = next((m.get("model") for m in models if m.get("location") == "local"), None)
    lines.append(f"Local fallback: {local or 'unknown'}")

    # --- scheduled jobs (from repo registry) ---
    jobs = read_repo_json("11_CONFIG/automation.json").get("jobs", [])
    job_names = ", ".join(j.get("name", "?") for j in jobs) if jobs else "none"
    lines.append(f"Scheduled jobs: {len(jobs)} ({job_names})")

    # --- provider/fallback from fresh snapshot when present ---
    if healthy_snapshot and isinstance(snapshot.get("provider"), dict):
        prov = snapshot["provider"]
        lines.append(f"Provider: {prov.get('primary_model','?')} via {prov.get('provider','?')}; fallback entries={prov.get('fallback_entries','?')}")

    lines.append("Owner action: run the Windows bootstrap and complete private Desktop sign-in.")

    print("\n".join(lines))

    # Exit 0 only when the snapshot is fresh AND every key service is active.
    return 0 if (healthy_snapshot and all_active) else 1


if __name__ == "__main__":
    raise SystemExit(main())
