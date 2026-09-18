#!/usr/bin/env bash
# Host-side unattended autonomy runner. Survives Conversation disconnect.
# Polls parent jobs on the worker-visible bind-mount and advances one step
# per job per iteration. Does not open a listener.
set -euo pipefail
ROOT="${NEEWA_OS_ROOT:-/opt/neewa/neewa-os}"
INBOX="${NEEWA_WINDOWS_JOB_INBOX:-/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs}"
AUTONOMY="$INBOX/autonomy"
LOCK="$AUTONOMY/runner.lock"
mkdir -p "$AUTONOMY"
exec 9>"$LOCK"
if ! flock -n 9; then
  if [ "${NEEWA_RUNNER_SYSTEMD:-}" = "1" ]; then
    echo "runner lock held; failing so systemd can retry"
    exit 75
  fi
  echo "runner already active"
  exit 0
fi
echo "$$" > "$AUTONOMY/runner.pid"
export PYTHONUTF8=1
while true; do
  sudo -n chown -R ubuntu:ubuntu "$AUTONOMY" 2>/dev/null || true
  python3 "$ROOT/12_SCRIPTS/neewa_autonomy.py" runner --once --root "$AUTONOMY" --inbox-root "$INBOX" || echo "runner step failed"
  sleep "${NEEWA_AUTONOMY_POLL_SEC:-15}"
done
