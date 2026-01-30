#!/bin/bash

# yt-dlp batch mp3 downloader w/ auto url removal
# usage: put urls in urls.txt (one per line), then run: ./download.sh

INPUT_FILE="urls.txt"
OUTPUT_DIR="./audios"
FAIL_DIR="$(mktemp -d)"
MAX_PARALLEL="${MAX_PARALLEL:-4}"

mkdir -p "$OUTPUT_DIR"

export OUTPUT_DIR FAIL_DIR
download_one() {
  url="$1"
  [ -z "$url" ] && exit 0
  echo "downloading: $url"
  if yt-dlp -x --audio-format mp3 -o "$OUTPUT_DIR/%(title)s.%(ext)s" "$url"; then
    echo "done: $url"
  else
    echo "failed: $url"
    printf "%s\n" "$url" >> "$FAIL_DIR/$$.txt"
  fi
}
export -f download_one

# parallelize downloads, keep transcriptions serial
< "$INPUT_FILE" tr -d '\r' | xargs -I {} -P "$MAX_PARALLEL" bash -lc 'download_one "$@"' _ {}

# replace original file w/ only failed urls
if ls "$FAIL_DIR"/*.txt >/dev/null 2>&1; then
  cat "$FAIL_DIR"/*.txt > "$INPUT_FILE"
else
  : > "$INPUT_FILE"
fi
rm -rf "$FAIL_DIR"

echo "all done. check $OUTPUT_DIR for mp3s"
if [ -f .env.local ]; then
  # shellcheck disable=SC1091
  source .env.local
fi
source ../venv/bin/activate
python3 transcribe.py
python3 summarize.py
