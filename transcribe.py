import shutil
from datetime import datetime
from pathlib import Path

import whisper


def _human_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def log(*args: object, **kwargs: object) -> None:
    print(f"[{_human_timestamp()}]", *args, **kwargs)


AUDIO_DIR = Path("audios")
FINISHED_DIR = Path("finished")
TRANSCRIPTIONS_DIR = Path("transcriptions")
AUDIO_SUFFIXES = (".mp3", ".wav", ".m4a", ".flac", ".ogg")


def ensure_output_dirs() -> None:
    FINISHED_DIR.mkdir(exist_ok=True)
    TRANSCRIPTIONS_DIR.mkdir(exist_ok=True)


def iter_audio_files() -> list[Path]:
    if not AUDIO_DIR.is_dir():
        return []
    return sorted(
        (
            path
            for path in AUDIO_DIR.iterdir()
            if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES
        ),
        key=lambda path: path.name.lower(),
    )


def transcript_output_path(audio_path: Path) -> Path:
    return TRANSCRIPTIONS_DIR / f"{audio_path.stem}.txt"


def move_to_finished(audio_path: Path) -> None:
    destination = FINISHED_DIR / audio_path.name
    shutil.move(str(audio_path), str(destination))


def transcribe_file(audio_path: Path, model) -> None:
    transcript_path = transcript_output_path(audio_path)
    try:
        if transcript_path.exists() and transcript_path.stat().st_size > 0:
            log(f"skipping {audio_path.name} (transcript exists)")
            move_to_finished(audio_path)
            return

        log(f"transcribing {audio_path.name}...")
        result = model.transcribe(str(audio_path))
        transcript_path.write_text((result.get("text") or "").strip(), encoding="utf-8")
        move_to_finished(audio_path)
    except Exception as exc:
        log(f"failed to process {audio_path.name}: {exc}")


def main() -> None:
    ensure_output_dirs()
    model = whisper.load_model("small")
    for audio_path in iter_audio_files():
        transcribe_file(audio_path, model)
    log("done.")


if __name__ == "__main__":
    main()
