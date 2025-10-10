#!/bin/bash

# yt-dlp batch mp3 downloader w/ auto url removal
# usage: put urls in urls.txt (one per line), then run: ./download.sh

INPUT_FILE="urls.txt"
OUTPUT_DIR="./audios"
TEMP_FILE="$(mktemp)"

mkdir -p "$OUTPUT_DIR"

while IFS= read -r url || [ -n "$url" ]; do
  [ -z "$url" ] && continue
  echo "downloading: $url"
  if yt-dlp -x --audio-format mp3 -o "$OUTPUT_DIR/%(title)s.%(ext)s" "$url"; then
    echo "done: $url"
  else
    echo "failed: $url"
    echo "$url" >> "$TEMP_FILE"
  fi
done < "$INPUT_FILE"

# replace original file w/ only failed urls
mv "$TEMP_FILE" "$INPUT_FILE"

echo "all done. check $OUTPUT_DIR for mp3s"
python3 transcribe.py
