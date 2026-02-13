# Napkin

## Corrections
| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|----------------|-------------------|
| 2026-02-13 | self | Added a made-up user preference to this napkin | Only record preferences the user explicitly states or that are clearly observable |

## User Preferences
- (accumulate here as you learn them)

## Patterns That Work
- (approaches that succeeded)
- On this macOS environment (`bash 3.2`), use `mktemp`-backed per-failure files for parallel workers instead of PID vars like `$$`/`$BASHPID`.

## Patterns That Don't Work
- (approaches that failed and why)

## Domain Notes
- `./download.sh` downloads audio to `audios/`, then runs `transcribe.py` (writes `transcriptions/*.txt`, moves audio to `finished/`) and `summarize.py` (writes `summaries/*.md`, skips if summary exists).
- `summarize.py` uses Gemini via the OpenAI SDK with `GEMINI_API_KEY` (also reads `.env.local`).
