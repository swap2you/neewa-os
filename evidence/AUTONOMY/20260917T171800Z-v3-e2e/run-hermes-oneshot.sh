#!/bin/bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
PROMPT_FILE="$1"
OUT_FILE="$2"
hermes -z "$(cat "$PROMPT_FILE")" --cli --skills windows-worker-bridge > "$OUT_FILE" 2>&1
echo EXIT:$?
