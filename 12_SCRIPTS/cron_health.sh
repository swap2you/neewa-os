#!/usr/bin/env bash
set -euo pipefail
ROOT="/opt/neewa/neewa-os"
cd "$ROOT"
python3 12_SCRIPTS/neewa_ops.py validate >/dev/null
systemctl --user is-active --quiet hermes-gateway.service
systemctl is-active --quiet docker.service
systemctl is-active --quiet tailscaled.service
systemctl is-active --quiet ollama.service
ollama list | grep -q 'qwen3:4b-instruct-2507-q4_K_M'
hermes fallback list | grep -q 'qwen3:4b-instruct-2507-q4_K_M'
python3 12_SCRIPTS/resource_governor.py --offline >/dev/null
printf 'NEEWA health PASS\n'
