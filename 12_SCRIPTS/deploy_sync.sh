#!/usr/bin/env bash
# Governed atomic NEEWA release synchronizer.
# Requires an existing host deployment wrapper to invoke this script.
set -euo pipefail

REPO_URL="https://github.com/swap2you/neewa-os.git"
SHA=""
RELEASE_ROOT="${NEEWA_RELEASE_ROOT:-/opt/neewa/releases/neewa-os}"
CURRENT_LINK="${NEEWA_CURRENT_LINK:-/opt/neewa/neewa-os-current}"
SERVICE=""
KEEP="5"

usage() {
  printf '%s\n' "usage: deploy_sync.sh --sha SHA [--repo-url URL] [--release-root PATH] [--current-link PATH] [--service USER@SERVICE] [--keep N]" >&2
  exit 2
}
while (($#)); do
  case "$1" in
    --sha) SHA="$2"; shift 2;;
    --repo-url) REPO_URL="$2"; shift 2;;
    --release-root) RELEASE_ROOT="$2"; shift 2;;
    --current-link) CURRENT_LINK="$2"; shift 2;;
    --service) SERVICE="$2"; shift 2;;
    --keep) KEEP="$2"; shift 2;;
    *) usage;;
  esac
done
[[ "$SHA" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR: --sha must be a 40-character Git SHA' >&2; exit 2; }
command -v git >/dev/null || { echo 'ERROR: git is required' >&2; exit 2; }
command -v python3 >/dev/null || { echo 'ERROR: python3 is required' >&2; exit 2; }

mkdir -p "$RELEASE_ROOT"
release="$RELEASE_ROOT/$SHA"
if [[ -e "$release" && ! -d "$release" ]]; then echo "ERROR: release path is not a directory: $release" >&2; exit 1; fi
if [[ ! -d "$release/.git" ]]; then
  tmp="$(mktemp -d "$RELEASE_ROOT/.stage.XXXXXX")"
  trap 'rm -rf "$tmp"' EXIT
  git clone --no-checkout --filter=blob:none "$REPO_URL" "$tmp/repo"
  git -C "$tmp/repo" fetch --no-tags origin "$SHA"
  git -C "$tmp/repo" cat-file -e "$SHA^{commit}"
  git -C "$tmp/repo" checkout --quiet --detach "$SHA"
  actual="$(git -C "$tmp/repo" rev-parse HEAD)"
  [[ "$actual" == "$SHA" ]] || { echo "ERROR: fetched SHA mismatch: $actual" >&2; exit 1; }
  mv "$tmp/repo" "$release"
  trap - EXIT
  rm -rf "$tmp"
fi
actual="$(git -C "$release" rev-parse HEAD)"
[[ "$actual" == "$SHA" ]] || { echo "ERROR: release SHA mismatch: $actual" >&2; exit 1; }
[[ -z "$(git -C "$release" status --porcelain)" ]] || { echo 'ERROR: staged release is dirty' >&2; exit 1; }

python3 "$release/12_SCRIPTS/neewa_ops.py" validate >/dev/null
python3 -m unittest discover -s "$release/13_TESTS" -p 'test_*.py' -q

if [[ -e "$CURRENT_LINK" && ! -L "$CURRENT_LINK" ]]; then
  echo "ERROR: current target exists and is not a symlink; refusing overwrite: $CURRENT_LINK" >&2
  exit 1
fi
old=''
if [[ -L "$CURRENT_LINK" ]]; then old="$(readlink -f "$CURRENT_LINK")"; fi
ln -sfn "$release" "$CURRENT_LINK"
rollback() {
  if [[ -n "$old" ]]; then ln -sfn "$old" "$CURRENT_LINK"; fi
}
if [[ -n "$SERVICE" ]]; then
  systemctl "$SERVICE" restart
  systemctl "$SERVICE" is-active --quiet || { rollback; echo 'ERROR: service health failed; rolled back' >&2; exit 1; }
fi
printf '{"deployed_sha":"%s","release":"%s","current_link":"%s","service":"%s"}\n' "$SHA" "$release" "$CURRENT_LINK" "$SERVICE"
find "$RELEASE_ROOT" -mindepth 1 -maxdepth 1 -type d -name '????????????????????????????????????????' -printf '%T@ %p\n' | sort -nr | tail -n +$((KEEP + 1)) | cut -d' ' -f2- | xargs -r rm -rf
