# Transcribe YT

Automated YouTube transcription plus local summary generation with Whisper and Ollama.

## Setup

```bash
pip install -r requirements.txt
pip install yt-dlp
ollama serve
ollama pull gemma4:e4b
```

Set your Ollama model, either in your shell or in `.env.local`:

```bash
export OLLAMA_MODEL="gemma4:e4b"
```

Optional settings:

```bash
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export OLLAMA_TIMEOUT_SECONDS=600
```

The summarizer uses Ollama's `/api/chat` endpoint, sends `think: false`, strips inline `<think>...</think>` blocks if they leak into `message.content`, and processes transcripts one at a time.

## Usage

1. Add YouTube URLs to `urls.txt` (one per line)
2. Run:
   ```bash
   chmod +x download.sh
   ./download.sh
   ```

`download.sh` starts background polling workers for download, transcription, and summarization. The summarizer worker still processes transcripts one at a time.

Processed files go to `finished/`, transcripts to `transcriptions/`, and transcript metadata sidecars to `transcriptions/meta/`.

It also generates markdown summaries in `summaries/`. If YouTube metadata is available, each summary includes frontmatter like:

```md
---
date: 2026-02-14
video_url: https://www.youtube.com/watch?v=abc123xyz
---
```

## Manual transcription only

```bash
python3 transcribe.py
```

## Manual summarization only

```bash
python3 summarize.py
```

## Credits

Built with help from OpenAI Codex.
