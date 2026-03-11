import json
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
TRANSCRIPTIONS_META_DIR = TRANSCRIPTIONS_DIR / "meta"
AUDIO_SUFFIXES = (".mp3", ".wav", ".m4a", ".flac", ".ogg")


def ensure_output_dirs() -> None:
    FINISHED_DIR.mkdir(exist_ok=True)
    TRANSCRIPTIONS_DIR.mkdir(exist_ok=True)
    TRANSCRIPTIONS_META_DIR.mkdir(parents=True, exist_ok=True)


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


def info_json_path(audio_path: Path) -> Path:
    return audio_path.with_suffix(".info.json")


def metadata_output_path(transcript_path: Path) -> Path:
    return TRANSCRIPTIONS_META_DIR / f"{transcript_path.stem}.json"


def normalize_upload_date(raw_upload_date: object) -> str | None:
    raw = str(raw_upload_date or "").strip()
    if len(raw) == 8 and raw.isdigit():
        return f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
    return None


def load_info_json(audio_path: Path) -> dict[str, object] | None:
    path = info_json_path(audio_path)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"warning: failed to parse {path.name}: {exc}")
        return None
    if isinstance(payload, dict):
        return payload
    log(f"warning: ignoring non-object metadata in {path.name}")
    return None


def write_transcript_metadata(
    *,
    audio_path: Path,
    transcript_path: Path,
    info: dict[str, object] | None,
) -> None:
    if not info:
        return

    metadata: dict[str, str] = {
        "source_audio": audio_path.name,
        "title": str(info.get("title") or "").strip(),
        "video_id": str(info.get("id") or "").strip(),
        "url": str(info.get("webpage_url") or "").strip(),
        "upload_date_raw": str(info.get("upload_date") or "").strip(),
    }

    publish_date = normalize_upload_date(info.get("upload_date"))
    if publish_date:
        metadata["publish_date"] = publish_date

    cleaned = {key: value for key, value in metadata.items() if value}
    if not cleaned:
        return

    out_path = metadata_output_path(transcript_path)
    out_path.write_text(
        json.dumps(cleaned, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )


def move_into_dir(source_path: Path, destination_dir: Path) -> None:
    if not source_path.exists():
        return
    destination = destination_dir / source_path.name
    if destination.exists():
        suffix = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        destination = destination_dir / f"{source_path.stem}-{suffix}{source_path.suffix}"
    shutil.move(str(source_path), str(destination))


def move_to_finished(audio_path: Path) -> None:
    move_into_dir(audio_path, FINISHED_DIR)
    move_into_dir(info_json_path(audio_path), FINISHED_DIR)


def transcribe_file(audio_path: Path, model) -> None:
    transcript_path = transcript_output_path(audio_path)
    info = load_info_json(audio_path)
    try:
        if transcript_path.exists() and transcript_path.stat().st_size > 0:
            log(f"skipping {audio_path.name} (transcript exists)")
            write_transcript_metadata(
                audio_path=audio_path,
                transcript_path=transcript_path,
                info=info,
            )
            move_to_finished(audio_path)
            return

        log(f"transcribing {audio_path.name}...")
        result = model.transcribe(str(audio_path))
        transcript_path.write_text((result.get("text") or "").strip(), encoding="utf-8")
        write_transcript_metadata(
            audio_path=audio_path,
            transcript_path=transcript_path,
            info=info,
        )
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
