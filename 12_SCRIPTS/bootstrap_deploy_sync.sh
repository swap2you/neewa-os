#!/usr/bin/env bash
# Download and execute deploy_sync.sh from one exact immutable commit.
set -euo pipefail
COMMIT=""
SHA256=""
DEST="${NEEWA_BOOTSTRAP_DEST:-$(mktemp /tmp/neewa-deploy-sync.XXXXXX.sh)}"
deploy_args=()
while (($#)); do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2;;
    --sha256) SHA256="${2:-}"; shift 2;;
    --dest) DEST="${2:-}"; shift 2;;
    --) shift; deploy_args=("$@"); break;;
    *) echo "usage: $0 --commit SHA --sha256 HASH [--dest PATH] -- [deploy_sync args]" >&2; exit 2;;
  esac
done
[[ "$COMMIT" =~ ^[0-9a-f]{40}$ ]] || { echo 'ERROR: exact 40-character commit is required' >&2; exit 2; }
[[ "$SHA256" =~ ^[0-9a-fA-F]{64}$ ]] || { echo 'ERROR: 64-character SHA-256 is required' >&2; exit 2; }
command -v curl >/dev/null || { echo 'ERROR: curl is required' >&2; exit 2; }
command -v sha256sum >/dev/null || { echo 'ERROR: sha256sum is required' >&2; exit 2; }
tmp="${DEST}.tmp.$$"
trap 'rm -f "$tmp"' EXIT
url="https://raw.githubusercontent.com/swap2you/neewa-os/$COMMIT/12_SCRIPTS/deploy_sync.sh"
curl --fail --location --silent --show-error "$url" -o "$tmp"
actual="$(sha256sum "$tmp" | awk '{print $1}')"
[[ "$actual" == "${SHA256,,}" ]] || { echo "ERROR: checksum mismatch: $actual" >&2; exit 1; }
chmod 0755 "$tmp"
mv -f "$tmp" "$DEST"
trap - EXIT
"$DEST" "${deploy_args[@]}"
rm -f "$DEST"
