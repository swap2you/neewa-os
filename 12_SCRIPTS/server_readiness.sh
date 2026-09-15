#!/usr/bin/env bash
set -euo pipefail

echo "== OS =="
uname -a
cat /etc/os-release || true

echo "== CPU/RAM =="
nproc
free -h

echo "== Disk =="
df -h /

echo "== Docker =="
docker --version || true
docker info >/dev/null 2>&1 && echo "Docker OK" || echo "Docker not ready"

echo "== Node/npm =="
node --version || true
npm --version || true

echo "Read-only readiness check complete."
