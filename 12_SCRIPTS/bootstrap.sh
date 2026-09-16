#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
JOB_ID="JOB-20260916-001"
EVIDENCE="evidence/NEEWA_OS/$JOB_ID"
mkdir -p "$EVIDENCE" 04_MEMORY/jobs
touch "$EVIDENCE/repository-validation.json" "$EVIDENCE/unit-tests.txt" "$EVIDENCE/docker-sandbox.txt" "$EVIDENCE/automation-audit.json"

python3 12_SCRIPTS/neewa_ops.py generate-manifest >/dev/null
python3 12_SCRIPTS/neewa_ops.py validate --json-out "$EVIDENCE/repository-validation.json" >/dev/null
python3 -m unittest discover -s 13_TESTS -p 'test_*.py' -v 2>&1 | tee "$EVIDENCE/unit-tests.txt"
bash -n 12_SCRIPTS/bootstrap.sh 12_SCRIPTS/server_readiness.sh

if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
  IMAGE="nikolaik/python-nodejs@sha256:8f958bdc1b4a422bfafd97cab4f69836401f616ae985d4b57a53d254f5bcb038"
  docker run --rm --network none --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
    -v "$ROOT:/workspace:ro" -w /workspace "$IMAGE" \
    python -c 'from pathlib import Path; assert Path("README.md").is_file(); print("sandbox repo read-only: PASS")' \
    | tee "$EVIDENCE/docker-sandbox.txt"
else
  echo "Docker unavailable" | tee "$EVIDENCE/docker-sandbox.txt"
  exit 1
fi

python3 12_SCRIPTS/neewa_ops.py job-record-validation \
  --job "04_MEMORY/jobs/$JOB_ID.json" \
  --check repository-validation \
  --check unit-tests \
  --check shell-syntax \
  --check docker-sandbox \
  --evidence "$EVIDENCE/repository-validation.json" \
  --evidence "$EVIDENCE/unit-tests.txt" \
  --evidence "$EVIDENCE/docker-sandbox.txt" \
  --evidence "$EVIDENCE/system-audit.json" \
  --evidence "$EVIDENCE/automation-audit.json" >/dev/null

printf 'NEEWA A0/A1 bootstrap checks: PASS\nDone Gate: PENDING independent review\nEvidence: %s\n' "$EVIDENCE"
