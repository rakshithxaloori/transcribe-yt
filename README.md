# Transcribe YT

Automated YouTube transcription + summary generation using Whisper and Gemini.

## Setup

```bash
pip install -r requirements.txt
pip install yt-dlp
```

Set your Gemini API key for summaries (via env var or `.env.local`):

```bash
export GEMINI_API_KEY="your-key"
```

Optional: set a local daily request cap to avoid hitting Gemini free-tier RPD hard limits.  
Default is `18` requests/day (tracked in `.state/gemini_usage.json` and reset daily).

```bash
export GEMINI_DAILY_REQUEST_CAP=18
```

Optional: summarize transcripts in batches to reduce requests/day.  
Default is `5` transcripts per request (set to `1` to disable batching).

```bash
export GEMINI_SUMMARY_BATCH_SIZE=5
```

Optional: fallback cooldown after quota/rate-limit errors when Gemini doesn't provide a retry delay.  
Default is `3600` seconds.

```bash
export GEMINI_QUOTA_COOLDOWN_SECONDS=3600
```

Optional: auto-retry count for quota errors that include a concrete retry delay (for example, `Please retry in 47s`).  
Default is `3`.

```bash
export GEMINI_QUOTA_RETRY_ATTEMPTS=3
```

Optional: choose summary provider explicitly.  
Default is `gemini`; set `openai` to use `OPENAI_API_KEY`.

```bash
export SUMMARY_PROVIDER=gemini
```

## API keys (Gemini + OpenAI)

Gemini (Google AI Studio):
1. Sign in to Google AI Studio and select or create a project.
2. Open the API keys section and create a new key.
3. Export it in your shell:
   ```bash
   export GEMINI_API_KEY="your-key"
   ```

OpenAI:
1. Sign in to the OpenAI Platform.
2. Go to API keys and create a new secret key.
3. Export it in your shell:
   ```bash
   export OPENAI_API_KEY="your-key"
   ```

## Usage

1. Add YouTube URLs to `urls.txt` (one per line)
2. Run:
   ```bash
   chmod +x download.sh
   ./download.sh
   ```

This downloads audio from URLs and transcribes them using Whisper. Processed files go to `finished/`, transcripts to `transcriptions/`.

It also generates markdown summaries in `summaries/`.

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
