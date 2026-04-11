import json
import re

from pathlib import Path

from summarize_helpers import (
    SUMMARIES_DIR,
    TRANSCRIPTIONS_DIR,
    OllamaClient,
    archive_transcript,
    build_prompt,
    get_ollama_client,
    log,
    summarize_with_ollama,
)

TRANSCRIPTIONS_META_DIR = TRANSCRIPTIONS_DIR / "meta"
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def write_summary(
    out_path: Path,
    title: str,
    summary: str,
    metadata: dict[str, str] | None = None,
) -> None:
    frontmatter = metadata or {}
    with out_path.open("w", encoding="utf-8") as file:
        if frontmatter:
            file.write("---\n")
            for key, value in frontmatter.items():
                file.write(f"{key}: {value}\n")
            file.write("---\n\n")
        file.write(f"# {title}\n\n")
        file.write(summary + "\n")


def load_summary_metadata(transcript_path: Path) -> dict[str, str]:
    metadata_path = TRANSCRIPTIONS_META_DIR / f"{transcript_path.stem}.json"
    if not metadata_path.is_file():
        return {}

    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"warning: failed to parse {metadata_path.name}: {exc}")
        return {}

    if not isinstance(payload, dict):
        return {}

    metadata: dict[str, str] = {}
    publish_date = str(payload.get("publish_date") or "").strip()
    if publish_date and ISO_DATE_RE.fullmatch(publish_date):
        metadata["date"] = publish_date

    video_url = str(payload.get("url") or "").strip()
    if video_url:
        metadata["video_url"] = video_url

    return metadata


def maybe_archive(transcript_path: Path, warning_prefix: str) -> None:
    try:
        archive_path = archive_transcript(transcript_path)
        log(f"archived transcript: {archive_path}")
    except Exception as exc:
        log(f"{warning_prefix} {transcript_path.name}: {exc}")


def summary_output_path(transcript_path: Path) -> Path:
    return SUMMARIES_DIR / f"{transcript_path.stem}.md"


def has_existing_summary(transcript_path: Path) -> bool:
    filename = transcript_path.name
    out_path = summary_output_path(transcript_path)
    if out_path.exists() and out_path.stat().st_size > 0:
        log(f"skipping {filename} (summary exists)")
        maybe_archive(
            transcript_path,
            "warning: summary exists, but failed to archive",
        )
        return True

    return False


def request_summary(
    *,
    client: OllamaClient,
    prompt: str,
    request_log: str,
    failure_prefix: str,
) -> str | None:
    log(request_log)
    try:
        return summarize_with_ollama(client, prompt)
    except Exception as exc:
        log(f"{failure_prefix}: {exc}")
        return None


def summarize_transcript(transcript_path: Path, client: OllamaClient) -> None:
    filename = transcript_path.name
    text = transcript_path.read_text(encoding="utf-8").strip()
    if not text or has_existing_summary(transcript_path):
        return

    summary = request_summary(
        client=client,
        prompt=build_prompt(text, filename),
        request_log=f"summarizing {filename}...",
        failure_prefix=f"failed to summarize {filename}",
    )
    if summary is None:
        return
    if not summary:
        log(f"empty summary for {filename}; skipping write")
        return

    write_summary(
        summary_output_path(transcript_path),
        transcript_path.stem,
        summary,
        metadata=load_summary_metadata(transcript_path),
    )
    maybe_archive(
        transcript_path,
        "warning: summary generated, but failed to archive",
    )


def transcript_files() -> list[Path]:
    if not TRANSCRIPTIONS_DIR.is_dir():
        return []
    return sorted(TRANSCRIPTIONS_DIR.glob("*.txt"), key=lambda path: path.name.lower())


def main() -> None:
    client = get_ollama_client()

    SUMMARIES_DIR.mkdir(exist_ok=True)
    log(f"ollama model: {client.model}")
    log(f"ollama base url: {client.base_url}")
    for transcript_path in transcript_files():
        summarize_transcript(transcript_path, client)

    log("done.")


if __name__ == "__main__":
    main()
