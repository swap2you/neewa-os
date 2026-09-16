#!/usr/bin/env bash
# NEEWA deterministic, READ-ONLY voice-pipeline readiness + evidence probe.
#
# Runs on the HOST (not the sandbox) because the live gateway logs, venv, and
# model caches are intentionally not mounted into the agent sandbox. Writes a
# JSON + text snapshot to the read-only status dir so NEEWA (and the owner) can
# report authoritative voice facts and the most recent OBSERVED voice events.
#
# It reports both readiness (deps/models/config/RPC) and last observed events
# (wake armed, wake detected, real STT transcription, voice->agent turn, TTS).
# No mutation, no audio retained.
set -euo pipefail

OUT_DIR="${NEEWA_STATUS_DIR:-/opt/neewa/status}"
JSON_OUT="${OUT_DIR}/voice.json"
TEXT_OUT="${OUT_DIR}/voice.txt"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
LOG_DIR="${HERMES_HOME}/logs"
VENV_PY="${HERMES_HOME}/hermes-agent/venv/bin/python"
HERMES_BIN="${HERMES_BIN:-$HOME/.local/bin/hermes}"
mkdir -p "$OUT_DIR" 2>/dev/null || true
now_utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# --- venv voice imports ---
imports_ok="false"
if [ -x "$VENV_PY" ]; then
  if "$VENV_PY" -c "import faster_whisper,sherpa_onnx,edge_tts,sounddevice" >/dev/null 2>&1; then
    imports_ok="true"
  fi
fi

# --- model caches ---
sherpa_present="false"
[ -d "${HERMES_HOME}/cache/wakewords" ] && ls "${HERMES_HOME}/cache/wakewords" 2>/dev/null | grep -qi sherpa && sherpa_present="true"
whisper_cached="false"
find "$HOME/.cache/huggingface" -maxdepth 3 -iname "*faster-whisper*" >/dev/null 2>&1 && \
  [ -n "$(find "$HOME/.cache/huggingface" -maxdepth 3 -iname "*faster-whisper*" 2>/dev/null)" ] && whisper_cached="true"

# --- live config ---
w_enabled="?"; w_provider="?"; w_phrase="?"; w_capture="?"; w_surface="?"; w_sens="?"; stt_en="?"; tts_prov="?"; tts_voice="?"; w_new_sess="?"; v_mode="?"
if [ -x "$HERMES_BIN" ]; then
  w_enabled="$("$HERMES_BIN" config get wake_word.enabled 2>/dev/null | head -1)"
  w_provider="$("$HERMES_BIN" config get wake_word.provider 2>/dev/null | head -1)"
  w_phrase="$("$HERMES_BIN" config get wake_word.phrase 2>/dev/null | head -1)"
  w_capture="$("$HERMES_BIN" config get wake_word.capture 2>/dev/null | head -1)"
  w_surface="$("$HERMES_BIN" config get wake_word.surface 2>/dev/null | head -1)"
  w_sens="$("$HERMES_BIN" config get wake_word.sensitivity 2>/dev/null | head -1)"
  stt_en="$("$HERMES_BIN" config get stt.enabled 2>/dev/null | head -1)"
  tts_prov="$("$HERMES_BIN" config get tts.provider 2>/dev/null | head -1)"
  tts_voice="$("$HERMES_BIN" config get tts.openai.voice 2>/dev/null | head -1)"
  w_new_sess="$("$HERMES_BIN" config get wake_word.start_new_session 2>/dev/null | head -1)"
  v_mode="$("$HERMES_BIN" config get voice.voice_chat_mode 2>/dev/null | head -1)"
fi

# --- voice RPC handlers present in code ---
rpc_ok="false"
if grep -RqsE "wake\.feed|wake\.start" "${HERMES_HOME}/hermes-agent/tui_gateway" 2>/dev/null; then rpc_ok="true"; fi

# --- gateway running ---
gw_running="false"
systemctl --user is-active --quiet hermes-gateway.service 2>/dev/null && gw_running="true"

# --- last observed events (read-only log scan) ---
AGENT_LOG="${LOG_DIR}/agent.log"; GUI_LOG="${LOG_DIR}/gui.log"
last_line() { grep -hE "$2" $1 2>/dev/null | tail -1 | sed 's/"/\\"/g' | cut -c1-240; }

last_wake_start="$(last_line "$AGENT_LOG $GUI_LOG" 'wake\.start\(')"
last_wake_detect="$(last_line "$AGENT_LOG" 'phrase detected')"
last_transcription="$(last_line "$AGENT_LOG" 'Transcribed .*whisper')"
last_turn_done="$(last_line "$AGENT_LOG $GUI_LOG" 'tui turn finished')"
last_tts="$(last_line "$AGENT_LOG" 'text_to_speech completed|Edge TTS')"

b() { [ -n "$1" ] && echo true || echo false; }
wake_armed_seen="$(b "$last_wake_start")"
wake_detected_seen="$(b "$last_wake_detect")"
stt_seen="$(b "$last_transcription")"
turn_seen="$(b "$last_turn_done")"
tts_seen="$(b "$last_tts")"

overall="not_yet_exercised"
if [ "$wake_detected_seen" = "true" ] && [ "$stt_seen" = "true" ] && [ "$turn_seen" = "true" ]; then
  overall="voice_pipeline_observed_working"
elif [ "$imports_ok" = "true" ] && [ "$rpc_ok" = "true" ] && [ "$gw_running" = "true" ]; then
  overall="ready_awaiting_speech"
fi

read -r -d '' JSON <<EOF || true
{
  "source": "neewa-host",
  "layer": "voice_pipeline",
  "generated_at": "${now_utc}",
  "overall": "${overall}",
  "readiness": {
    "venv_imports_ok": ${imports_ok},
    "sherpa_kws_model_present": ${sherpa_present},
    "faster_whisper_cached": ${whisper_cached},
    "voice_rpc_handlers_present": ${rpc_ok},
    "gateway_running": ${gw_running}
  },
  "config": {
    "wake_enabled": "${w_enabled}", "wake_provider": "${w_provider}", "wake_phrase": "${w_phrase}",
    "wake_capture": "${w_capture}", "wake_surface": "${w_surface}", "wake_sensitivity": "${w_sens}",
    "wake_start_new_session": "${w_new_sess}", "voice_chat_mode": "${v_mode}",
    "stt_enabled": "${stt_en}", "tts_provider": "${tts_prov}", "tts_openai_voice": "${tts_voice}"
  },
  "last_observed_events": {
    "wake_listener_armed": ${wake_armed_seen}, "wake_start_line": "${last_wake_start}",
    "wake_detected": ${wake_detected_seen}, "wake_detected_line": "${last_wake_detect}",
    "real_speech_transcribed": ${stt_seen}, "transcription_line": "${last_transcription}",
    "voice_to_agent_turn": ${turn_seen}, "turn_line": "${last_turn_done}",
    "tts_generated": ${tts_seen}, "tts_line": "${last_tts}"
  }
}
EOF
tmp="$(mktemp "${OUT_DIR}/.voice.json.XXXXXX" 2>/dev/null || echo "${JSON_OUT}.tmp")"
printf '%s\n' "$JSON" > "$tmp" && mv -f "$tmp" "$JSON_OUT" 2>/dev/null || printf '%s\n' "$JSON" > "$JSON_OUT"
chmod 0644 "$JSON_OUT" 2>/dev/null || true

read -r -d '' TEXT <<EOF || true
NEEWA VOICE READINESS — ${now_utc}
Overall: ${overall}
Readiness: imports=${imports_ok} sherpa_model=${sherpa_present} whisper_cached=${whisper_cached} rpc=${rpc_ok} gateway=${gw_running}
Config: wake=${w_enabled}/${w_provider}/'${w_phrase}' capture=${w_capture} surface=${w_surface} start_new_session=${w_new_sess} stt=${stt_en} tts=${tts_prov} voice_mode=${v_mode}
Last observed events:
  wake armed:        ${last_wake_start:-none}
  wake detected:     ${last_wake_detect:-none}
  speech transcribed:${last_transcription:-none}
  voice->agent turn: ${last_turn_done:-none}
  tts generated:     ${last_tts:-none}
EOF
tmp2="$(mktemp "${OUT_DIR}/.voice.txt.XXXXXX" 2>/dev/null || echo "${TEXT_OUT}.tmp")"
printf '%s\n' "$TEXT" > "$tmp2" && mv -f "$tmp2" "$TEXT_OUT" 2>/dev/null || printf '%s\n' "$TEXT" > "$TEXT_OUT"
chmod 0644 "$TEXT_OUT" 2>/dev/null || true

if [ "${1:-}" = "--json" ]; then cat "$JSON_OUT"; else cat "$TEXT_OUT"; fi
