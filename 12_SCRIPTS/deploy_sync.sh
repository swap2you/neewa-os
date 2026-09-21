#!/usr/bin/env bash
# Governed atomic NEEWA release synchronizer for user-scoped systemd.
set -euo pipefail

REPO_URL="https://github.com/swap2you/neewa-os.git"
SHA=""
RELEASE_ROOT="${NEEWA_RELEASE_ROOT:-/opt/neewa/releases/neewa-os}"
CURRENT_LINK="${NEEWA_CURRENT_LINK:-/opt/neewa/neewa-os-current}"
SERVICE=""
HEALTH_FILE="${NEEWA_HEALTH_FILE:-/opt/neewa/status/autonomy.json}"
RECEIPT=""
KEEP="5"
HEALTH_ATTEMPTS="${NEEWA_HEALTH_ATTEMPTS:-12}"
HEALTH_SLEEP="${NEEWA_HEALTH_SLEEP:-5}"
UNIT_DIR="${NEEWA_USER_UNIT_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user}"
SYSTEMCTL_BIN="${SYSTEMCTL_BIN:-systemctl --user}"
LOGINCTL_BIN="${LOGINCTL_BIN:-loginctl}"

usage() {
  printf '%s\n' "usage: deploy_sync.sh --sha SHA --service UNIT [--repo-url URL] [--release-root PATH] [--current-link PATH] [--health-file PATH] [--receipt PATH] [--keep N]" >&2
  exit 2
}
while (($#)); do
  case "$1" in
    --sha) SHA="${2:-}"; shift 2;;
    --repo-url) REPO_URL="${2:-}"; shift 2;;
    --release-root) RELEASE_ROOT="${2:-}"; shift 2;;
    --current-link) CURRENT_LINK="${2:-}"; shift 2;;
    --service) SERVICE="${2:-}"; shift 2;;
    --health-file) HEALTH_FILE="${2:-}"; shift 2;;
    --receipt) RECEIPT="${2:-}"; shift 2;;
    --keep) KEEP="${2:-}"; shift 2;;
    *) usage;;
  esac
done
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR: --sha must be a 40-character Git SHA' >&2; exit 2; }
[[ "$SERVICE" =~ ^[A-Za-z0-9_.@:-]+$ ]] || { echo 'ERROR: --service must be a unit name' >&2; exit 2; }
[[ "$KEEP" =~ ^[1-9][0-9]*$ ]] || { echo 'ERROR: --keep must be positive' >&2; exit 2; }
command -v git >/dev/null || { echo 'ERROR: git is required' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'ERROR: python3 is required' >&2; exit 2; }
# shellcheck disable=SC2086
run_systemctl() { ${SYSTEMCTL_BIN} "$@"; }
command -v ${SYSTEMCTL_BIN%% *} >/dev/null || { echo "ERROR: systemctl executor is required: $SYSTEMCTL_BIN" >&2; exit 2; }
command -v ${LOGINCTL_BIN%% *} >/dev/null || { echo "ERROR: loginctl is required for linger checks: $LOGINCTL_BIN" >&2; exit 2; }
case " $SYSTEMCTL_BIN " in
  *" --user "*|"--user "*|*" --user") ;;
  *) echo "ERROR: deploy_sync requires user-scoped systemctl (--user): $SYSTEMCTL_BIN" >&2; exit 2;;
esac
[[ -n "${XDG_RUNTIME_DIR:-}" ]] || { echo 'ERROR: XDG_RUNTIME_DIR must be set for user systemd' >&2; exit 2; }

mkdir -p "$RELEASE_ROOT"
release="$RELEASE_ROOT/$SHA"
RECEIPT="${RECEIPT:-$RELEASE_ROOT/deploy-receipts/$SHA.json}"
mkdir -p "$(dirname "$RECEIPT")"
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
old=''
old_sha=''
current_before=''
write_receipt() {
  local result="$1" reason="${2:-}"
  python3 - "$RECEIPT" "$result" "$reason" "$SHA" "$release" "$CURRENT_LINK" "$SERVICE" "$old_sha" "$started_at" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" <<'PY'
import json, pathlib, sys
(pathlib.Path(sys.argv[1])).write_text(json.dumps({
  "result": sys.argv[2], "reason": sys.argv[3], "deployed_sha": sys.argv[4],
  "release": sys.argv[5], "current_link": sys.argv[6], "service": sys.argv[7],
  "rollback_sha": sys.argv[8], "started_at": sys.argv[9], "finished_at": sys.argv[10],
}, indent=2) + "\n", encoding="utf-8")
PY
}
fail() { write_receipt FAILED "$1"; echo "ERROR: $1" >&2; exit 1; }

require_owner_mode() {
  local path="$1" label="$2"
  [[ -e "$path" || -L "$path" ]] || fail "$label missing: $path"
  local owner mode
  owner="$(stat -c '%u' "$path" 2>/dev/null || stat -f '%u' "$path")"
  [[ "$owner" == "$(id -u)" ]] || fail "$label not owned by deploying user: $path"
  # Symlink permission bits are not security-relevant on Linux; check targets/files only.
  if [[ -L "$path" ]]; then
    return 0
  fi
  mode="$(stat -c '%a' "$path" 2>/dev/null || stat -f '%OLp' "$path")"
  [[ "$((8#$mode & 0022))" -eq 0 ]] || fail "$label is group/world-writable: $path mode=$mode"
}

if [[ -e "$CURRENT_LINK" && ! -L "$CURRENT_LINK" ]]; then fail "current target is not a symlink: $CURRENT_LINK"; fi
if [[ -L "$CURRENT_LINK" ]]; then old="$(readlink -f "$CURRENT_LINK")"; old_sha="$(basename "$old")"; current_before="$old"; fi

if [[ ! -d "$release/.git" ]]; then
  tmp="$(mktemp -d "$RELEASE_ROOT/.stage.XXXXXX")"
  trap 'rm -rf "$tmp"' EXIT
  git clone --no-checkout --filter=blob:none "$REPO_URL" "$tmp/repo" || fail "clone failed"
  git -C "$tmp/repo" fetch --no-tags origin "$SHA" || fail "fetch failed"
  git -C "$tmp/repo" cat-file -e "$SHA^{commit}" || fail "requested SHA is not a commit"
  git -C "$tmp/repo" checkout --quiet --detach "$SHA" || fail "checkout failed"
  actual="$(git -C "$tmp/repo" rev-parse HEAD)"
  [[ "$actual" == "$SHA" ]] || fail "fetched SHA mismatch: $actual"
  mv "$tmp/repo" "$release" || fail "cannot stage release"
  trap - EXIT
  rm -rf "$tmp"
fi
actual="$(git -C "$release" rev-parse HEAD)"
[[ "$actual" == "$SHA" ]] || fail "release SHA mismatch: $actual"
[[ -z "$(git -C "$release" status --porcelain)" ]] || fail 'staged release is dirty'
require_owner_mode "$release" "release directory"

# User-scoped unit path, linger, and environment before switching.
unit_path="$UNIT_DIR/$SERVICE"
[[ -f "$unit_path" ]] || fail "installed user unit missing: $unit_path"
require_owner_mode "$unit_path" "installed user unit"
if [[ -e "$CURRENT_LINK" || -L "$CURRENT_LINK" ]]; then
  require_owner_mode "$CURRENT_LINK" "current symlink"
fi
linger_out="$($LOGINCTL_BIN show-user "$(id -un)" -p Linger 2>&1)" || fail "cannot inspect linger: $linger_out"
grep -Eq '^Linger=yes$' <<<"$linger_out" || fail "user lingering is not enabled: $linger_out"

# Verify the service really runs from the release/current structure before switching it.
unit_info="$(run_systemctl show "$SERVICE" -p ExecStart -p WorkingDirectory -p FragmentPath 2>&1)" || fail "cannot inspect service: $unit_info"
grep -Fq "FragmentPath=$unit_path" <<<"$unit_info" || fail "service FragmentPath is not installed user unit: $unit_info"
grep -Eq "(^| )ExecStart=" <<<"$unit_info" || fail "service ExecStart missing: $unit_info"
grep -Eq "(^| )WorkingDirectory=" <<<"$unit_info" || fail "service WorkingDirectory missing: $unit_info"
if ! grep -Fq "$CURRENT_LINK" <<<"$unit_info" && ! grep -Fq "$RELEASE_ROOT" <<<"$unit_info"; then
  fail "service ExecStart/WorkingDirectory do not reference current/release path: $SERVICE"
fi
grep -Fq "$CURRENT_LINK" <<<"$unit_info" || fail "service must reference current symlink path: $CURRENT_LINK"

PYTHONDONTWRITEBYTECODE=1 python3 "$release/12_SCRIPTS/neewa_ops.py" validate >/dev/null || fail 'neewa_ops validation failed'
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s "$release/13_TESTS" -p 'test_*.py' -q || fail 'test suite failed'

# Same-filesystem atomic symlink replacement; never overwrite a real directory.
tmp_link="${CURRENT_LINK}.tmp.$$"
rm -f "$tmp_link"
ln -s "$release" "$tmp_link"
mv -Tf "$tmp_link" "$CURRENT_LINK" || fail 'atomic symlink switch failed'
require_owner_mode "$CURRENT_LINK" "current symlink"
rollback() {
  if [[ -n "$old" ]]; then
    rb="${CURRENT_LINK}.rollback.$$"
    rm -f "$rb"
    ln -s "$old" "$rb"
    mv -Tf "$rb" "$CURRENT_LINK"
    run_systemctl restart "$SERVICE" || true
  fi
}

run_systemctl daemon-reload || { rollback; fail "service daemon-reload failed"; }
run_systemctl enable "$SERVICE" || { rollback; fail "service enable failed"; }
run_systemctl restart "$SERVICE" || { rollback; fail "service restart failed"; }
run_systemctl is-active --quiet "$SERVICE" || { rollback; fail "service is not active after restart"; }

# Wait briefly for the host heartbeat to report the requested SHA.
healthy=false
for _ in $(seq 1 "$HEALTH_ATTEMPTS"); do
  if [[ -f "$HEALTH_FILE" ]] && python3 - "$HEALTH_FILE" "$SHA" <<'PY'
import json, sys
try:
    d=json.load(open(sys.argv[1], encoding='utf-8'))
    versions=d.get('versions') or {}
    raise SystemExit(0 if versions.get('sha') == sys.argv[2] else 1)
except Exception:
    raise SystemExit(1)
PY
  then healthy=true; break; fi
  sleep "$HEALTH_SLEEP"
done
if [[ "$healthy" != true ]]; then rollback; fail "heartbeat SHA did not verify: $SHA"; fi
write_receipt PASS ''
printf '{"result":"PASS","deployed_sha":"%s","release":"%s","current_link":"%s","service":"%s","rollback_sha":"%s","receipt":"%s"}\n' "$SHA" "$release" "$CURRENT_LINK" "$SERVICE" "$old_sha" "$RECEIPT"

# Retain active and rollback releases; remove only older release directories.
protected="$release${old:+ $old}"
find "$RELEASE_ROOT" -mindepth 1 -maxdepth 1 -type d -name '????????????????????????????????????????' -printf '%T@ %p\n' \
  | sort -nr | tail -n +$((KEEP + 1)) | cut -d' ' -f2- \
  | while IFS= read -r candidate; do
      case " $protected " in *" $candidate "*) continue;; esac
      rm -rf -- "$candidate"
    done
