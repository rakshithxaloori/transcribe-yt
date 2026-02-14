# Napkin

## Corrections
| Date | Source | What Went Wrong | What To Do Instead |
|------|--------|----------------|-------------------|
| 2026-02-13 | self | Added a made-up user preference to this napkin | Only record preferences the user explicitly states or that are clearly observable |
| 2026-02-13 | self | Tried importing `whisper` with system `python3` (not in venv), got `ModuleNotFoundError` | Use the repo’s venv (`../venv/bin/python` or source `../venv/bin/activate`) when running Python commands here |
| 2026-02-13 | self | Read `transcribe.py` before re-reading `.claude/napkin.md` at turn start | Re-open `.claude/napkin.md` first on every turn before repo exploration/editing |
| 2026-02-14 | self | Used `: > urls.txt` while trying to ensure file existence in `download.sh`, which would wipe queued URLs | Use `[ -f "$INPUT_FILE" ] || : > "$INPUT_FILE"` so the file is created only when missing |

## User Preferences
- (accumulate here as you learn them)
- When requesting a change, start with approach + pseudocode before writing code.

## Patterns That Work
- (approaches that succeeded)
- On this macOS environment (`bash 3.2`), use `mktemp`-backed per-failure files for parallel workers instead of PID vars like `$$`/`$BASHPID`.
- For sandboxed syntax checks on macOS Python, set `PYTHONPYCACHEPREFIX` to a writable path (e.g. `/tmp/pycache`) before `python3 -m py_compile`.
- When collecting temp files via a glob, keep the `mktemp` filename template suffix consistent with that glob (e.g. `fail.XXXXXX.txt` with `*.txt`).
- For queue files in shell scripts, guard creation with `[ -f file ] || : > file` to avoid silently truncating existing work.

## Patterns That Don't Work
- (approaches that failed and why)

## Domain Notes
- `./download.sh` downloads audio to `audios/`, then runs `transcribe.py` (writes `transcriptions/*.txt`, moves audio to `finished/`) and `summarize.py` (writes `summaries/*.md`, skips if summary exists).
- `summarize.py` uses Gemini via the OpenAI SDK with `GEMINI_API_KEY` (also reads `.env.local`).
- `transcribe.py` currently loads Whisper once (`small`) and transcribes files in `audios/` sequentially, writing `transcriptions/*.txt` and moving audio to `finished/`.
