#!/usr/bin/env bash
# NEEWA deterministic, READ-ONLY host status probe.
#
# Purpose: produce authoritative NEEWA *server* (host) health, clearly
# separate from the Docker execution sandbox. It performs no mutations and
# needs no root. It writes a JSON snapshot + human summary to an out-of-repo
# status directory that is mounted READ-ONLY into the agent sandbox, so the
# agent can report real host facts without ever using container stats as if
# they were the host.
#
# Layers this distinguishes (see 07_SETUP/20_SYSTEM_STATUS_REPORTING.md):
#   B. Actual NEEWA server (this host)   <- everything below
#   (A sandbox, C repo/app, D Windows client are reported elsewhere)
#
# Usage:
#   neewa_host_status.sh            # print text summary, refresh snapshot
#   neewa_host_status.sh --json     # print JSON, refresh snapshot
set -euo pipefail

REPO="${NEEWA_REPO:-/opt/neewa/neewa-os}"
OUT_DIR="${NEEWA_STATUS_DIR:-/opt/neewa/status}"
JSON_OUT="${OUT_DIR}/latest.json"
TEXT_OUT="${OUT_DIR}/latest.txt"

mkdir -p "${OUT_DIR}" 2>/dev/null || true

now_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

svc() { systemctl is-active "$1" 2>/dev/null || echo "inactive"; }
usvc() { systemctl --user is-active "$1" 2>/dev/null || echo "inactive"; }

# --- host identity / availability ---
host_name="$(hostname 2>/dev/null || echo unknown)"
uptime_s="$(cut -d. -f1 /proc/uptime 2>/dev/null || echo 0)"
load_avg="$(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null || echo 'n/a')"
cpu_count="$(nproc 2>/dev/null || echo 0)"

# --- memory (host, from /proc/meminfo in kB) ---
mem_total_kb="$(awk '/MemTotal/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
mem_avail_kb="$(awk '/MemAvailable/{print $2}' /proc/meminfo 2>/dev/null || echo 0)"
mem_total_mb=$(( mem_total_kb / 1024 ))
mem_avail_mb=$(( mem_avail_kb / 1024 ))
mem_used_mb=$(( mem_total_mb - mem_avail_mb ))

# --- disk (root fs) ---
disk_line="$(df -PBM / 2>/dev/null | awk 'NR==2{print $2" "$3" "$4" "$5}')"
disk_total_mb="$(echo "$disk_line" | awk '{gsub(/M/,"",$1);print $1}')"
disk_used_mb="$(echo "$disk_line" | awk '{gsub(/M/,"",$2);print $2}')"
disk_avail_mb="$(echo "$disk_line" | awk '{gsub(/M/,"",$3);print $3}')"
disk_use_pct="$(echo "$disk_line" | awk '{print $4}')"

# --- services ---
gateway_state="$(usvc hermes-gateway.service)"
docker_state="$(svc docker.service)"
tailscaled_state="$(svc tailscaled.service)"
ollama_state="$(svc ollama.service)"
autonomy_runner_state="$(usvc neewa-autonomy-runner.service)"

# --- ollama / local model ---
local_model="qwen3:4b-instruct-2507-q4_K_M"
if command -v ollama >/dev/null 2>&1 && ollama list 2>/dev/null | grep -q "$local_model"; then
  local_model_present="true"
else
  local_model_present="false"
fi

# --- tailscale connectivity (read-only) ---
ts_backend="stopped"
ts_peer_online="unknown"
if command -v tailscale >/dev/null 2>&1; then
  if tailscale status >/dev/null 2>&1; then
    ts_backend="running"
    if tailscale status 2>/dev/null | grep -qiE 'neewa-edge-01|active|idle|-'; then
      ts_peer_online="yes"
    else
      ts_peer_online="no"
    fi
  fi
fi
ts_funnel="$(tailscale funnel status 2>/dev/null | head -1 || true)"; [ -z "$ts_funnel" ] && ts_funnel="No funnel"
ts_serve="$(tailscale serve status 2>/dev/null | head -1 || true)"; [ -z "$ts_serve" ] && ts_serve="No serve"

# --- provider / fallback (read-only) ---
HERMES_BIN="${HERMES_BIN:-$HOME/.local/bin/hermes}"
primary_model="unknown"; provider="unknown"; fallback_count="0"
if [ -x "$HERMES_BIN" ]; then
  primary_model="$("$HERMES_BIN" config get model 2>/dev/null | sed -n 's/^default: //p' | head -1)"
  [ -z "$primary_model" ] && primary_model="unknown"
  provider="$("$HERMES_BIN" config get model.provider 2>/dev/null | head -1 || true)"
  [ -z "$provider" ] && provider="nous"
  fallback_count="$("$HERMES_BIN" fallback list 2>/dev/null | grep -cE '^\s+[0-9]+\.' || true)"
  [ -z "$fallback_count" ] && fallback_count="0"
fi

# --- repository (NEEWA app/repo health) ---
repo_head="unknown"; repo_dirty="unknown"; repo_branch="unknown"
if [ -d "${REPO}/.git" ]; then
  repo_head="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  repo_branch="$(git -C "$REPO" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
  if [ -z "$(git -C "$REPO" status --porcelain 2>/dev/null)" ]; then repo_dirty="clean"; else repo_dirty="dirty"; fi
fi

# --- scheduled jobs (health + morning brief) ---
health_job="unknown"; brief_job="unknown"
if [ -x "$HERMES_BIN" ]; then
  cron_dump="$("$HERMES_BIN" cron list 2>/dev/null || true)"
  health_job="$(printf '%s' "$cron_dump" | awk '/neewa-daily-health/{f=1} f&&/Last run:/{print $3" "$4;exit}')"
  brief_job="$(printf '%s' "$cron_dump" | awk '/neewa-morning-brief/{f=1} f&&/Last run:/{print $3" "$4;exit}')"
  [ -z "$health_job" ] && health_job="unknown"
  [ -z "$brief_job" ] && brief_job="unknown"
fi

# --- failed system units (read-only) ---
failed_units="$(systemctl --failed --no-legend --plain 2>/dev/null | awk '{print $1}' | paste -sd, - || true)"
[ -z "$failed_units" ] && failed_units="none"

# --- overall verdict ---
overall="ok"
[ "$gateway_state" = "active" ] || overall="degraded"
[ "$docker_state" = "active" ] || overall="degraded"
[ "$tailscaled_state" = "active" ] || overall="degraded"

json_escape() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g'; }

read -r -d '' JSON <<EOF || true
{
  "source": "neewa-host",
  "layer": "B_actual_neewa_server",
  "note": "Authoritative host facts. NOT sandbox container stats.",
  "generated_at": "${now_utc}",
  "host": "$(json_escape "$host_name")",
  "overall": "${overall}",
  "availability": {"uptime_seconds": ${uptime_s:-0}, "load_avg": "$(json_escape "$load_avg")"},
  "cpu": {"count": ${cpu_count:-0}},
  "memory_mb": {"total": ${mem_total_mb:-0}, "used": ${mem_used_mb:-0}, "available": ${mem_avail_mb:-0}},
  "disk_root_mb": {"total": ${disk_total_mb:-0}, "used": ${disk_used_mb:-0}, "available": ${disk_avail_mb:-0}, "use_percent": "$(json_escape "${disk_use_pct:-n/a}")"},
  "services": {"hermes_gateway": "${gateway_state}", "docker": "${docker_state}", "tailscaled": "${tailscaled_state}", "ollama": "${ollama_state}", "neewa_autonomy_runner": "${autonomy_runner_state}"},
  "local_model": {"name": "${local_model}", "present": ${local_model_present}},
  "tailscale": {"backend": "${ts_backend}", "peer_online": "${ts_peer_online}", "funnel": "$(json_escape "$ts_funnel")", "serve": "$(json_escape "$ts_serve")"},
  "provider": {"primary_model": "$(json_escape "$primary_model")", "provider": "$(json_escape "$provider")", "fallback_entries": ${fallback_count:-0}},
  "repository": {"path": "$(json_escape "$REPO")", "branch": "$(json_escape "$repo_branch")", "head": "$(json_escape "$repo_head")", "state": "${repo_dirty}"},
  "jobs": {"neewa_daily_health_last": "$(json_escape "$health_job")", "neewa_morning_brief_last": "$(json_escape "$brief_job")"},
  "failed_units": "$(json_escape "$failed_units")"
}
EOF

# atomic write
tmp_json="$(mktemp "${OUT_DIR}/.latest.json.XXXXXX" 2>/dev/null || echo "${JSON_OUT}.tmp")"
printf '%s\n' "$JSON" > "$tmp_json" && mv -f "$tmp_json" "$JSON_OUT" 2>/dev/null || printf '%s\n' "$JSON" > "$JSON_OUT"
chmod 644 "$JSON_OUT" 2>/dev/null || true

read -r -d '' TEXT <<EOF || true
NEEWA SERVER STATUS (actual host: ${host_name}) — ${now_utc}
Source: neewa-host snapshot (NOT the Docker sandbox)
Overall: ${overall}
Uptime(s): ${uptime_s}   Load: ${load_avg}   CPU cores: ${cpu_count}
Memory: ${mem_used_mb} / ${mem_total_mb} MB used (${mem_avail_mb} MB free)
Disk /: ${disk_used_mb} / ${disk_total_mb} MB used (${disk_use_pct} used, ${disk_avail_mb} MB free)
Services: gateway=${gateway_state} docker=${docker_state} tailscaled=${tailscaled_state} ollama=${ollama_state} autonomy_runner=${autonomy_runner_state}
Local model ${local_model}: present=${local_model_present}
Tailscale: backend=${ts_backend} peer_online=${ts_peer_online} | ${ts_funnel} | ${ts_serve}
Provider: primary=${primary_model} via ${provider}; fallback entries=${fallback_count}
Repository: ${REPO} @ ${repo_branch}/${repo_head} (${repo_dirty})
Jobs: daily-health last=${health_job}; morning-brief last=${brief_job}
Failed units: ${failed_units}
EOF

tmp_txt="$(mktemp "${OUT_DIR}/.latest.txt.XXXXXX" 2>/dev/null || echo "${TEXT_OUT}.tmp")"
printf '%s\n' "$TEXT" > "$tmp_txt" && mv -f "$tmp_txt" "$TEXT_OUT" 2>/dev/null || printf '%s\n' "$TEXT" > "$TEXT_OUT"
chmod 644 "$TEXT_OUT" 2>/dev/null || true

if [ "${1:-}" = "--json" ]; then
  cat "$JSON_OUT"
else
  cat "$TEXT_OUT"
fi
