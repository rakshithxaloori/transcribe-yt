from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib import error, request


def _human_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def log(*args: object, **kwargs: object) -> None:
    print(f"[{_human_timestamp()}]", *args, **kwargs)


DEFAULT_OLLAMA_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_OLLAMA_TIMEOUT_SECONDS = 600

SYSTEM_PROMPT = """Don't worry about formalities.

Please be as terse as possible while still conveying substantially all information relevant to any question.

If content policy prevents you from generating an image or otherwise responding, be explicit about what policy was violated and why.

write all responses in lowercase letters ONLY, except where you mean to emphasize, in which case the emphasized word should be all caps. Initial Letter Capitalization can and should be used to express sarcasm, or disrespect for a given capitalized noun.

you are encouraged to occasionally use obscure words or make subtle puns. don't point them out, I'll know. drop lots of abbreviations like "rn" and "bc." use "afaict" and "idk" regularly, wherever they might be appropriate given your level of understanding and your interest in actually answering the question. be critical of the quality of your information

if you find any request irritating respond dismisively like "be real" or "that's crazy man" or "lol no"

take however smart you're acting right now and write in the same style but as if you were +2sd smarter

use late millenial slang not boomer slang. mix in zoomer slang in tonally-inappropriate circumstances occasionally

priotirize esoteric interpretations of literature, art, and philosophy. if your answer on such topics is not obviously straussian, make it strongly straussian."""
SUMMARY_PROMPT = """Generate a topic-wise outline with key details,

DO NOT MISS ANYTHING. Expand on key details in the topic outline.

Follow the standard Markdown output format."""

TRANSCRIPTIONS_DIR = Path("transcriptions")
ARCHIVE_TRANSCRIPTIONS_DIR = TRANSCRIPTIONS_DIR / "archive"
SUMMARIES_DIR = Path("summaries")

_INLINE_THINKING_RE = re.compile(r"<think>.*?</think>", flags=re.DOTALL | re.IGNORECASE)
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")


@dataclass(frozen=True)
class OllamaClient:
    model: str
    base_url: str
    timeout_seconds: int = DEFAULT_OLLAMA_TIMEOUT_SECONDS


def load_local_env() -> None:
    env_path = Path(__file__).with_name(".env.local")
    if not env_path.is_file():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_ollama_client() -> OllamaClient:
    load_local_env()

    model = (os.getenv("OLLAMA_MODEL") or "").strip()
    if not model:
        raise RuntimeError("OLLAMA_MODEL is not set")

    return OllamaClient(
        model=model,
        base_url=(os.getenv("OLLAMA_BASE_URL") or DEFAULT_OLLAMA_BASE_URL)
        .strip()
        .rstrip("/"),
        timeout_seconds=_get_positive_int_env(
            "OLLAMA_TIMEOUT_SECONDS",
            DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        ),
    )


def build_prompt(text: str, source_name: str) -> str:
    return f"{SUMMARY_PROMPT}\n\nSource: {source_name}\n\nTranscript:\n{text}"


def archive_transcript(transcript_path: Path) -> Path:
    ARCHIVE_TRANSCRIPTIONS_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = ARCHIVE_TRANSCRIPTIONS_DIR / transcript_path.name
    if archive_path.exists():
        suffix = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
        archive_path = ARCHIVE_TRANSCRIPTIONS_DIR / (
            f"{transcript_path.stem}-{suffix}{transcript_path.suffix}"
        )
    transcript_path.replace(archive_path)
    return archive_path


def summarize_with_ollama(client: OllamaClient, prompt: str) -> str:
    payload = _build_ollama_payload(client, prompt, include_think_flag=True)
    try:
        response_payload = _post_ollama_chat(client, payload)
    except RuntimeError as exc:
        if not _should_retry_without_think(exc):
            raise
        response_payload = _post_ollama_chat(
            client,
            _build_ollama_payload(client, prompt, include_think_flag=False),
        )

    content = _extract_ollama_content(response_payload)
    return _strip_inline_thinking(content)


def _build_ollama_payload(
    client: OllamaClient,
    prompt: str,
    *,
    include_think_flag: bool,
) -> bytes:
    payload: dict[str, object] = {
        "model": client.model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
    }
    if include_think_flag:
        payload["think"] = False
    return json.dumps(payload).encode("utf-8")


def _post_ollama_chat(client: OllamaClient, payload: bytes) -> dict[str, object]:
    req = request.Request(
        url=f"{client.base_url}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=client.timeout_seconds) as response:
            raw_payload = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ollama request failed ({exc.code}): {body}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"ollama request failed: {exc.reason}") from exc

    if not isinstance(raw_payload, dict):
        raise RuntimeError("ollama returned a non-object response")
    return raw_payload


def _extract_ollama_content(payload: dict[str, object]) -> str:
    ollama_error = str(payload.get("error") or "").strip()
    if ollama_error:
        raise RuntimeError(f"ollama error: {ollama_error}")

    message = payload.get("message")
    if not isinstance(message, dict):
        raise RuntimeError("ollama response missing message.content")

    return str(message.get("content") or "").strip()


def _strip_inline_thinking(text: str) -> str:
    # Some models still leak inline <think> blocks even when thinking is disabled.
    cleaned = _INLINE_THINKING_RE.sub("", text or "")
    cleaned = _EXCESS_BLANK_LINES_RE.sub("\n\n", cleaned)
    return cleaned.strip()


def _should_retry_without_think(exc: RuntimeError) -> bool:
    message = str(exc).lower()
    return "think" in message and "unknown field" in message


def _get_positive_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        log(f"invalid {name}={raw!r}; using {default}")
        return default
    if value <= 0:
        log(f"{name} must be > 0 (got {raw!r}); using {default}")
        return default
    return value
