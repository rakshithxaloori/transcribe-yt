# Transcribe YT

Automated YouTube video transcription system using Whisper.

## Setup

```bash
pip install -r requirements.txt
pip install yt-dlp
```

Set your Gemini API key for summaries:

```bash
export GEMINI_API_KEY="your-key"
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
