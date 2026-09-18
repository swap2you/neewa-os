#!/usr/bin/env bash
# Install the NEEWA autonomy runner as a user systemd service.
# Requires linger already enabled. Does not use sudo. Does not expand permissions.
set -euo pipefail
ROOT="${NEEWA_OS_ROOT:-/opt/neewa/neewa-os}"
INBOX="${NEEWA_WINDOWS_JOB_INBOX:-/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs}"
AUTONOMY="$INBOX/autonomy"
UNIT_SRC="$ROOT/12_SCRIPTS/systemd/neewa-autonomy-runner.service"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_DST="$UNIT_DIR/neewa-autonomy-runner.service"

if [ ! -f "$UNIT_SRC" ]; then
  echo "BLOCKED: unit file missing at $UNIT_SRC" >&2
  exit 2
fi
if ! command -v systemctl >/dev/null 2>&1; then
  echo "BLOCKED: systemctl not available" >&2
  exit 2
fi
if [ ! -d "$HOME/.config" ] && ! mkdir -p "$UNIT_DIR"; then
  echo "BLOCKED: cannot create $UNIT_DIR; owner must create ~/.config/systemd/user" >&2
  exit 2
fi
mkdir -p "$UNIT_DIR" "$AUTONOMY"
cp "$UNIT_SRC" "$UNIT_DST"

if [ -f "$AUTONOMY/runner.pid" ]; then
  old_pid="$(tr -d '[:space:]' < "$AUTONOMY/runner.pid" || true)"
  if [ -n "${old_pid:-}" ] && [ -d "/proc/$old_pid" ]; then
    cmd="$(tr '\0' ' ' < "/proc/$old_pid/cmdline" || true)"
    case "$cmd" in
      *neewa_autonomy_runner.sh*|*neewa_autonomy.py*)
        echo "stopping orphan runner pid $old_pid"
        kill "$old_pid" || true
        sleep 2
        ;;
    esac
  fi
fi

systemctl --user daemon-reload
systemctl --user enable --now neewa-autonomy-runner.service
systemctl --user status --no-pager neewa-autonomy-runner.service || true
echo "installed $UNIT_DST"
