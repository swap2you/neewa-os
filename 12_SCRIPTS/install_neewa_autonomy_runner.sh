#!/usr/bin/env bash
# Install the NEEWA autonomy runner as a user systemd service.
# Requires linger already enabled. Does not use sudo. Does not expand permissions.
# Migrates existing units that still point at /opt/neewa/neewa-os or a
# checksum/SHA-named checkout onto the stable /opt/neewa/neewa-os-current symlink.
set -euo pipefail

STABLE="${NEEWA_CURRENT_LINK:-/opt/neewa/neewa-os-current}"
LEGACY="${NEEWA_LEGACY_ROOT:-/opt/neewa/neewa-os}"
ROOT="${NEEWA_OS_ROOT:-$STABLE}"
INBOX="${NEEWA_WINDOWS_JOB_INBOX:-/home/ubuntu/.hermes/sandboxes/docker/default/workspace/windows-jobs}"
AUTONOMY="$INBOX/autonomy"
UNIT_NAME="neewa-autonomy-runner.service"
UNIT_DIR="${NEEWA_USER_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}"
UNIT_DST="$UNIT_DIR/$UNIT_NAME"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl --user}"
LOGINCTL_BIN="${LOGINCTL_BIN:-loginctl}"

# shellcheck disable=SC2086
run_systemctl() { ${SYSTEMCTL_BIN} "$@"; }

case " $SYSTEMCTL_BIN " in
  *" --user "*|"--user "*|*" --user") ;;
  *) echo "BLOCKED: installer requires user-scoped systemctl (--user): $SYSTEMCTL_BIN" >&2; exit 2;;
esac

UNIT_SRC=""
for candidate in "$ROOT" "$STABLE" "$LEGACY"; do
  if [ -f "$candidate/12_SCRIPTS/systemd/$UNIT_NAME" ]; then
    UNIT_SRC="$candidate/12_SCRIPTS/systemd/$UNIT_NAME"
    SRC_ROOT="$candidate"
    break
  fi
done
if [ -z "$UNIT_SRC" ]; then
  echo "BLOCKED: unit file missing under $ROOT, $STABLE, or $LEGACY" >&2
  exit 2
fi
if ! command -v ${SYSTEMCTL_BIN%% *} >/dev/null 2>&1; then
  echo "BLOCKED: systemctl not available" >&2
  exit 2
fi
if ! command -v ${LOGINCTL_BIN%% *} >/dev/null 2>&1; then
  echo "BLOCKED: loginctl not available" >&2
  exit 2
fi
# shellcheck disable=SC2086
linger_out="$(${LOGINCTL_BIN} show-user "$(id -un)" -p Linger 2>&1 || true)"
if ! grep -Eq '^Linger=yes$' <<<"$linger_out"; then
  echo "BLOCKED: user lingering is not enabled (required for user-systemd runner)" >&2
  exit 2
fi
if [ -z "${XDG_RUNTIME_DIR:-}" ]; then
  echo "BLOCKED: XDG_RUNTIME_DIR must be set for user systemd" >&2
  exit 2
fi
if [ ! -d "$HOME/.config" ] && ! mkdir -p "$UNIT_DIR"; then
  echo "BLOCKED: cannot create $UNIT_DIR; owner must create ~/.config/systemd/user" >&2
  exit 2
fi
mkdir -p "$UNIT_DIR" "$AUTONOMY"

if [ -e "$STABLE" ] && [ ! -L "$STABLE" ]; then
  echo "BLOCKED: current target is not a symlink: $STABLE" >&2
  exit 2
fi
if [ ! -e "$STABLE" ] && [ ! -L "$STABLE" ]; then
  checkout=""
  if [ -d "$SRC_ROOT" ] && [ "$SRC_ROOT" != "$STABLE" ]; then
    checkout="$SRC_ROOT"
  elif [ -d "$LEGACY" ]; then
    checkout="$LEGACY"
  fi
  if [ -n "$checkout" ]; then
    if mkdir -p "$(dirname "$STABLE")" && ln -s "$checkout" "$STABLE"; then
      echo "created current symlink $STABLE -> $checkout"
    else
      echo "NOTE: could not create $STABLE; deploy_sync or admin must create it" >&2
    fi
  fi
fi

old_existed=false
legacy_or_checksum=false
if [ -f "$UNIT_DST" ]; then
  old_existed=true
  if grep -Eq '/opt/neewa/neewa-os([^[:alnum:]-]|$)' "$UNIT_DST" \
     || grep -Eq '/[0-9a-f]{40}(/|$)' "$UNIT_DST"; then
    legacy_or_checksum=true
  fi
fi

cp "$UNIT_SRC" "$UNIT_DST"
chmod 0644 "$UNIT_DST"
owner="$(stat -c '%u' "$UNIT_DST" 2>/dev/null || stat -f '%u' "$UNIT_DST")"
if [ "$owner" != "$(id -u)" ]; then
  echo "BLOCKED: installed user unit not owned by deploying user: $UNIT_DST" >&2
  exit 2
fi
mode="$(stat -c '%a' "$UNIT_DST" 2>/dev/null || stat -f '%OLp' "$UNIT_DST")"
if [ "$((8#$mode & 0022))" -ne 0 ]; then
  echo "BLOCKED: installed user unit is group/world-writable: $UNIT_DST mode=$mode" >&2
  exit 2
fi

if [ "$legacy_or_checksum" = true ]; then
  echo "migrated existing user unit from legacy/checksum-named path to $STABLE"
elif [ "$old_existed" = true ]; then
  echo "updated existing user unit $UNIT_DST"
fi

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

run_systemctl daemon-reload
run_systemctl enable --now "$UNIT_NAME"
if [ "$old_existed" = true ]; then
  run_systemctl restart "$UNIT_NAME"
fi
run_systemctl status --no-pager "$UNIT_NAME" || true
echo "installed $UNIT_DST"
