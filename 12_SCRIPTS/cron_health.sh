#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/neewa/neewa-os"
cd "$ROOT"
python3 12_SCRIPTS/neewa_ops.py validate >/dev/null
systemctl --user is-active --quiet hermes-gateway.service
docker info >/dev/null 2>&1
printf 'NEEWA health PASS\n'
