import time

from pathlib import Path
from typing import Callable

from summarize_helpers import (
    GEMINI_USAGE_PATH,
    SUMMARIES_DIR,
    TRANSCRIPTIONS_DIR,
    BatchSummaryItem,
    QuotaConfig,
    UsageState,
    archive_transcript,
    build_batch_prompt,
    build_prompt,
    get_client,
    get_summary_batch_size,
    is_quota_error,
    log,
    load_quota_config,
    parse_batch_summaries,
    parse_retry_delay_seconds,
    summarize_with_client,
)


def write_summary(out_path: Path, title: str, summary: str) -> None:
    with out_path.open("w", encoding="utf-8") as file:
        file.write(f"# Summary: {title}\n\n")
        file.write(summary + "\n")


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


def handle_quota_exception(
    exc: Exception,
    usage_state: UsageState,
    quota: QuotaConfig,
    file_quota_retries: int,
) -> tuple[bool, int]:
    if not is_quota_error(exc):
        return False, file_quota_retries

    retry_delay = parse_retry_delay_seconds(exc)
    cooldown = usage_state.set_quota_cooldown(
        retry_delay if retry_delay is not None else quota.cooldown_seconds
    )

    if retry_delay is not None and file_quota_retries < quota.retry_attempts:
        next_retry = file_quota_retries + 1
        log(
            "gemini reported quota/rate exhaustion; "
            f"pausing requests for {cooldown}s before retrying "
            f"({next_retry}/{quota.retry_attempts})."
        )
        time.sleep(cooldown)
        return True, next_retry

    log(
        "gemini reported quota/rate exhaustion; "
        f"pausing requests for {cooldown}s."
    )
    return False, file_quota_retries


def execute_summary_request(
    *,
    usage_state: UsageState,
    quota: QuotaConfig,
    retry_target: str,
    request_log: str,
    failure_prefix: str,
    request_fn: Callable[[], str],
) -> tuple[str | None, bool]:
    quota_retries = 0
    while True:
        allowed, reason = usage_state.can_send_request()
        if not allowed:
            cooldown_remaining = usage_state.remaining_cooldown_seconds()
            if cooldown_remaining > 0 and quota_retries < quota.retry_attempts:
                next_retry = quota_retries + 1
                log(
                    f"cooldown active; waiting {cooldown_remaining}s before retrying {retry_target} "
                    f"({next_retry}/{quota.retry_attempts})"
                )
                quota_retries = next_retry
                time.sleep(cooldown_remaining)
                continue
            log(f"stopping summary run: {reason}")
            return None, True

        usage_state.reserve_daily_request()
        log(request_log)
        try:
            return request_fn(), False
        except Exception as exc:
            log(f"{failure_prefix}: {exc}")
            should_retry, quota_retries = handle_quota_exception(
                exc,
                usage_state,
                quota,
                quota_retries,
            )
            if should_retry:
                continue
            return None, is_quota_error(exc)


def summarize_transcript(
    transcript_path: Path,
    client,
    usage_state: UsageState,
    quota: QuotaConfig,
) -> bool:
    filename = transcript_path.name
    text = transcript_path.read_text(encoding="utf-8").strip()
    if not text:
        return False

    if has_existing_summary(transcript_path):
        return False

    summary, stop_run = execute_summary_request(
        usage_state=usage_state,
        quota=quota,
        retry_target=filename,
        request_log=f"summarizing {filename}...",
        failure_prefix=f"failed to summarize {filename}",
        request_fn=lambda: summarize_with_client(client, build_prompt(text, filename)),
    )
    if stop_run:
        return True
    if summary is None:
        return False
    if not summary:
        log(f"empty summary for {filename}; skipping write")
        return False

    write_summary(summary_output_path(transcript_path), transcript_path.stem, summary)
    maybe_archive(
        transcript_path,
        "warning: summary generated, but failed to archive",
    )
    return False


def summarize_batch(
    transcript_paths: list[Path],
    client,
    usage_state: UsageState,
    quota: QuotaConfig,
) -> bool:
    items: list[BatchSummaryItem] = []

    for transcript_path in transcript_paths:
        filename = transcript_path.name
        text = transcript_path.read_text(encoding="utf-8").strip()
        if not text:
            continue

        if has_existing_summary(transcript_path):
            continue

        item_id = f"t{len(items) + 1}"
        items.append(
            BatchSummaryItem(
                item_id=item_id,
                source_name=filename,
                text=text,
                transcript_path=transcript_path,
            )
        )

    if not items:
        return False

    raw, stop_run = execute_summary_request(
        usage_state=usage_state,
        quota=quota,
        retry_target="batch",
        request_log=f"summarizing batch ({len(items)} transcripts)...",
        failure_prefix="failed to summarize batch",
        request_fn=lambda: summarize_with_client(client, build_batch_prompt(items)),
    )
    if stop_run:
        return True
    if raw is None:
        return False

    summaries = parse_batch_summaries(raw)
    for item in items:
        transcript_path = item.transcript_path
        filename = transcript_path.name
        if has_existing_summary(transcript_path):
            continue

        summary = (summaries.get(item.item_id) or "").strip()
        if not summary:
            log(f"warning: missing/empty summary for {filename}; leaving transcript for retry")
            continue

        write_summary(summary_output_path(transcript_path), transcript_path.stem, summary)
        maybe_archive(
            transcript_path,
            "warning: summary generated, but failed to archive",
        )

    return False


def transcript_files() -> list[Path]:
    if not TRANSCRIPTIONS_DIR.is_dir():
        return []
    return sorted(TRANSCRIPTIONS_DIR.glob("*.txt"), key=lambda path: path.name.lower())


def main():
    client = get_client()
    quota = load_quota_config()
    batch_size = get_summary_batch_size()
    usage_state = UsageState(GEMINI_USAGE_PATH, quota.daily_request_cap)

    SUMMARIES_DIR.mkdir(exist_ok=True)
    log(
        "gemini request usage today: "
        f"{usage_state.requests_used}/{quota.daily_request_cap}"
    )
    log(f"summary batch size: {batch_size}")
    cooldown_seconds = usage_state.remaining_cooldown_seconds()
    if cooldown_seconds > 0:
        log(f"gemini cooldown active: {cooldown_seconds}s")

    if batch_size <= 1:
        for transcript_path in transcript_files():
            stop_run = summarize_transcript(transcript_path, client, usage_state, quota)
            if stop_run:
                break
    else:
        batch: list[Path] = []
        stop_run = False
        for transcript_path in transcript_files():
            batch.append(transcript_path)
            if len(batch) < batch_size:
                continue
            stop_run = summarize_batch(batch, client, usage_state, quota)
            batch = []
            if stop_run:
                break
        if not stop_run and batch:
            summarize_batch(batch, client, usage_state, quota)

    log("done.")


if __name__ == "__main__":
    main()
