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
  echo "runner already active"
  exit 0
fi
echo "$$" > "$AUTONOMY/runner.pid"
export PYTHONUTF8=1
while true; do
  python3 "$ROOT/12_SCRIPTS/neewa_autonomy.py" runner --once --root "$AUTONOMY" --inbox-root "$INBOX" || true
  sleep "${NEEWA_AUTONOMY_POLL_SEC:-15}"
done
