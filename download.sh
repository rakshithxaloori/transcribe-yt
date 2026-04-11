#!/bin/bash

set -euo pipefail

INPUT_FILE="urls.txt"
OUTPUT_DIR="./audios"
TRANSCRIPTIONS_DIR="./transcriptions"
SUMMARIES_DIR="./summaries"
POLL_SECONDS="${POLL_SECONDS:-120}"

log() {
  local ts
  ts="$(date '+%Y-%m-%d %H:%M:%S %z')"
  if [ "$#" -eq 0 ]; then
    printf '[%s]\n' "$ts"
  else
    printf '[%s] %s\n' "$ts" "$*"
  fi
}

case "$POLL_SECONDS" in
  ''|*[!0-9]*|0)
    log "POLL_SECONDS must be a positive integer (got: $POLL_SECONDS)"
    exit 1
    ;;
esac

has_pending_urls() {
  grep -q '[^[:space:]]' "$INPUT_FILE"
}

has_pending_audio() {
  find "$OUTPUT_DIR" -maxdepth 1 -type f \
    \( -iname '*.mp3' -o -iname '*.wav' -o -iname '*.m4a' -o -iname '*.flac' -o -iname '*.ogg' \) \
    | grep -q .
}

has_pending_transcriptions() {
  local transcript base_name summary_path
  while IFS= read -r -d '' transcript; do
    base_name="$(basename "$transcript" .txt)"
    summary_path="$SUMMARIES_DIR/$base_name.md"
    if [ ! -s "$summary_path" ]; then
      return 0
    fi
  done < <(find "$TRANSCRIPTIONS_DIR" -maxdepth 1 -type f -name '*.txt' -print0)
  return 1
}

should_exit() {
  ! has_pending_urls && ! has_pending_audio && ! has_pending_transcriptions
}

download_urls() {
  local next_input raw_url url
  next_input="$(mktemp)"

  while IFS= read -r raw_url || [ -n "$raw_url" ]; do
    url="${raw_url%$'\r'}"
    [ -z "$url" ] && continue

    log "downloading: $url"
    if yt-dlp \
      --no-progress \
      -x \
      --audio-format mp3 \
      --write-info-json \
      --no-write-playlist-metafiles \
      -o "$OUTPUT_DIR/%(title)s.%(ext)s" \
      "$url"; then
      log "done: $url"
    else
      log "failed: $url"
      printf '%s\n' "$url" >> "$next_input"
    fi
  done < "$INPUT_FILE"

  mv "$next_input" "$INPUT_FILE"
}

run_download_once() {
  if has_pending_urls; then
    download_urls
  fi
}

run_transcribe_once() {
  if has_pending_audio; then
    python3 transcribe.py
  fi
}

run_summarize_once() {
  if has_pending_transcriptions; then
    python3 summarize.py
  fi
}

worker_loop() {
  local worker_name="$1"
  local run_once_fn="$2"
  while true; do
    if should_exit; then
      log "$worker_name: no pending work, exiting"
      return 0
    fi
    "$run_once_fn"
    if should_exit; then
      log "$worker_name: pipeline drained, exiting"
      return 0
    fi
    sleep "$POLL_SECONDS"
  done
}

mkdir -p "$OUTPUT_DIR" "$TRANSCRIPTIONS_DIR" "$SUMMARIES_DIR"
[ -f "$INPUT_FILE" ] || : > "$INPUT_FILE"

if [ -f .env.local ]; then
  # shellcheck disable=SC1091
  source .env.local
fi
source ../venv/bin/activate

if should_exit; then
  log "nothing to do. urls/audios/transcriptions are already drained."
  exit 0
fi

worker_loop "download" run_download_once &
DOWNLOAD_PID=$!
worker_loop "transcribe" run_transcribe_once &
TRANSCRIBE_PID=$!
worker_loop "summarize" run_summarize_once &
SUMMARIZE_PID=$!

cleanup_on_signal() {
  trap - INT TERM
  log
  log "stopping workers..."
  kill "$DOWNLOAD_PID" "$TRANSCRIBE_PID" "$SUMMARIZE_PID" 2>/dev/null || true
  wait "$DOWNLOAD_PID" "$TRANSCRIBE_PID" "$SUMMARIZE_PID" 2>/dev/null || true
  exit 130
}

trap cleanup_on_signal INT TERM

wait "$DOWNLOAD_PID"
wait "$TRANSCRIBE_PID"
wait "$SUMMARIZE_PID"

trap - INT TERM
log "all done. urls are empty and there is nothing left in audios/transcriptions to process."
