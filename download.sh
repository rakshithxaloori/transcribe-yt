#!/bin/bash

# yt-dlp + transcription + summary pipeline runner
# usage: put urls in urls.txt (one per line), then run: ./download.sh

INPUT_FILE="urls.txt"
OUTPUT_DIR="./audios"
FINISHED_DIR="./finished"
TRANSCRIPTIONS_DIR="./transcriptions"
SUMMARIES_DIR="./summaries"
MAX_PARALLEL="${MAX_PARALLEL:-4}"
SLEEP_SECONDS=120

case "$MAX_PARALLEL" in
  ''|*[!0-9]*|0)
    echo "MAX_PARALLEL must be a positive integer (got: $MAX_PARALLEL)"
    exit 1
    ;;
esac

mkdir -p "$OUTPUT_DIR" "$FINISHED_DIR" "$TRANSCRIPTIONS_DIR" "$SUMMARIES_DIR"
[ -f "$INPUT_FILE" ] || : > "$INPUT_FILE"

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

download_one() {
  local url="$1"
  local fail_dir="$2"
  local fail_file
  [ -z "$url" ] && return 0
  echo "downloading: $url"
  if yt-dlp --no-progress -x --audio-format mp3 -o "$OUTPUT_DIR/%(title)s.%(ext)s" "$url"; then
    echo "done: $url"
  else
    echo "failed: $url"
    fail_file="$(mktemp "$fail_dir/fail.XXXXXX.txt")"
    printf "%s\n" "$url" > "$fail_file"
  fi
}

run_download_batch() {
  local fail_dir raw_url url
  fail_dir="$(mktemp -d)"
  while IFS= read -r raw_url || [ -n "$raw_url" ]; do
    url="${raw_url%$'\r'}"
    [ -z "$url" ] && continue
    while [ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$MAX_PARALLEL" ]; do
      sleep 0.1
    done
    download_one "$url" "$fail_dir" &
  done < "$INPUT_FILE"
  wait

  if ls "$fail_dir"/*.txt >/dev/null 2>&1; then
    cat "$fail_dir"/*.txt > "$INPUT_FILE"
  else
    : > "$INPUT_FILE"
  fi
  rm -rf "$fail_dir"
}

run_transcribe_once() {
  if has_pending_audio; then
    python3 transcribe.py
  else
    echo "transcribe: no pending audio"
  fi
}

run_summarize_once() {
  if has_pending_transcriptions; then
    python3 summarize.py
  else
    echo "summarize: no pending transcriptions"
  fi
}

downloader_loop() {
  while true; do
    if should_exit; then
      echo "download: no pending work, exiting"
      return 0
    fi
    if has_pending_urls; then
      run_download_batch
    else
      echo "download: no pending urls"
    fi
    if should_exit; then
      echo "download: pipeline drained, exiting"
      return 0
    fi
    sleep "$SLEEP_SECONDS"
  done
}

transcribe_loop() {
  while true; do
    if should_exit; then
      echo "transcribe: no pending work, exiting"
      return 0
    fi
    run_transcribe_once
    if should_exit; then
      echo "transcribe: pipeline drained, exiting"
      return 0
    fi
    sleep "$SLEEP_SECONDS"
  done
}

summarize_loop() {
  while true; do
    if should_exit; then
      echo "summarize: no pending work, exiting"
      return 0
    fi
    run_summarize_once
    if should_exit; then
      echo "summarize: pipeline drained, exiting"
      return 0
    fi
    sleep "$SLEEP_SECONDS"
  done
}

if [ -f .env.local ]; then
  # shellcheck disable=SC1091
  source .env.local
fi
source ../venv/bin/activate

if should_exit; then
  echo "nothing to do. urls/audios/transcriptions are already drained."
  exit 0
fi

downloader_loop &
DOWNLOAD_PID=$!
transcribe_loop &
TRANSCRIBE_PID=$!
summarize_loop &
SUMMARIZE_PID=$!

cleanup_on_signal() {
  trap - INT TERM
  echo
  echo "stopping workers..."
  kill "$DOWNLOAD_PID" "$TRANSCRIBE_PID" "$SUMMARIZE_PID" 2>/dev/null || true
  wait "$DOWNLOAD_PID" "$TRANSCRIBE_PID" "$SUMMARIZE_PID" 2>/dev/null || true
  exit 130
}

trap cleanup_on_signal INT TERM

wait "$DOWNLOAD_PID"
wait "$TRANSCRIBE_PID"
wait "$SUMMARIZE_PID"

trap - INT TERM
echo "all done. urls are empty and there is nothing left in audios/transcriptions to process."
