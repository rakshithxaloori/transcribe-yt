# Napkin

## Corrections
| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|----------------|-------------------|
| 2026-02-13 | self | Added a made-up user preference to this napkin | Only record preferences the user explicitly states or that are clearly observable |
| 2026-02-13 | self | Tried importing `whisper` with system `python3` (not in venv), got `ModuleNotFoundError` | Use the repo’s venv (`../venv/bin/python` or source `../venv/bin/activate`) when running Python commands here |
| 2026-02-13 | self | Read `transcribe.py` before re-reading `.claude/napkin.md` at turn start | Re-open `.claude/napkin.md` first on every turn before repo exploration/editing |
| 2026-02-14 | self | Used `: > urls.txt` while trying to ensure file existence in `download.sh`, which would wipe queued URLs | Use `[ -f "$INPUT_FILE" ] || : > "$INPUT_FILE"` so the file is created only when missing |
| 2026-02-14 | self | `summarize.py` had no local quota guard; `download.sh`'s summarize loop would keep retrying unsummarized files and burn Gemini RPD | Track per-day Gemini usage in a local state file and stop summary requests once daily cap/quota exhaustion is hit |
| 2026-02-14 | self | Implemented this turn's code edits before sharing approach + pseudocode despite a recorded user preference | When user asks for changes, send brief approach + pseudocode first, then patch files |
| 2026-02-14 | self | Initial quota fix treated 429 exhaustion as an all-day block; Gemini can return short retry windows (`retryDelay`) | Parse provider retry delay from error payload and persist a timed cooldown instead of a blanket day-long lock |
| 2026-02-14 | self | Announced that I was reading the napkin; skill says to apply it silently | Read/apply napkin first, but do not state that explicitly in user-facing updates |
| 2026-02-14 | self | Tried importing `summarize.py` with system `python3` and hit `ModuleNotFoundError: openai` during validation | Use repo venv (`../venv/bin/python`) for runtime checks that import dependencies |
| 2026-02-14 | self | During `summarize.py` helper extraction, referenced `quota.daily_cap` instead of `quota.daily_request_cap` | After moving config into dataclasses, run a quick symbol-name pass before validation |
| 2026-02-14 | self | Tried reading Gemini Batch API docs at `/gemini-api/docs/batch` and got 404 | Use `/gemini-api/docs/batch-api` (and note Batch API uses `:batchGenerateContent`, not the OpenAI-compat endpoints) |
| 2026-02-14 | self | `apply_patch` failed due to context mismatch when editing `summarize_helpers.py` | Use `rg`/`nl -ba` to grab exact surrounding lines and apply smaller, targeted hunks |
| 2026-02-14 | self | Announced napkin usage in a user-facing status update again | Apply napkin silently; keep progress updates focused on task actions/results |

## User Preferences
- (accumulate here as you learn them)
- When requesting a change, start with approach + pseudocode before writing code.
- Keep timestamps human readable (e.g., `YYYY-MM-DD HH:MM:SS ±TZ`).

## Patterns That Work
- (approaches that succeeded)
- On this macOS environment (`bash 3.2`), use `mktemp`-backed per-failure files for parallel workers instead of PID vars like `$$`/`$BASHPID`.
- For sandboxed syntax checks on macOS Python, set `PYTHONPYCACHEPREFIX` to a writable path (e.g. `/tmp/pycache`) before `python3 -m py_compile`.
- When collecting temp files via a glob, keep the `mktemp` filename template suffix consistent with that glob (e.g. `fail.XXXXXX.txt` with `*.txt`).
- For queue files in shell scripts, guard creation with `[ -f file ] || : > file` to avoid silently truncating existing work.
- For quota-limited APIs in polling loops, persist a local daily usage counter and bail out before provider hard limits to prevent repeated wasteful retries.
- For Gemini/OpenAI-style quota errors, parse `retryDelay`/retry hints when present and honor that cooldown instead of assuming reset at local midnight.
- Runtime state files like `.state/gemini_usage.json` should be ignored in `.gitignore` to keep git status clean.
- Archive transcripts only after the summary file write succeeds, so failed summary attempts can be retried safely.
- Keep `__pycache__/` ignored for this Python project to avoid noisy git status after local validation runs.
- When a transcript is skipped because its summary already exists, archive the transcript anyway so `transcriptions/` drains.
- For script cleanups, move env/quota/state helpers into a module and keep the CLI file focused on per-file orchestration.
- For cleanup reviews, scan files with `nl -ba` and report opportunities by impact with exact file:line pointers.

## Patterns That Don't Work
- (approaches that failed and why)

## Domain Notes
- `./download.sh` downloads audio to `audios/`, then runs `transcribe.py` (writes `transcriptions/*.txt`, moves audio to `finished/`) and `summarize.py` (writes `summaries/*.md`, skips if summary exists).
- `summarize.py` uses Gemini via the OpenAI SDK with `GEMINI_API_KEY` (also reads `.env.local`).
- `summarize.py` now archives successfully summarized transcripts under `transcriptions/archive/`.
- `transcribe.py` currently loads Whisper once (`small`) and transcribes files in `audios/` sequentially, writing `transcriptions/*.txt` and moving audio to `finished/`.
