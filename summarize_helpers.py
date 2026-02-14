from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from openai import OpenAI


def _human_timestamp() -> str:
    return datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %z")


def log(*args: object, **kwargs: object) -> None:
    print(f"[{_human_timestamp()}]", *args, **kwargs)


MODEL_NAME = "gemini-2.5-flash"
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

then do a Socratic method-style questions and answers to teach me the key insights of the material.

DO NOT MISS ANYTHING. Expand on key details in the topic outline."""

TRANSCRIPTIONS_DIR = Path("transcriptions")
ARCHIVE_TRANSCRIPTIONS_DIR = TRANSCRIPTIONS_DIR / "archive"
SUMMARIES_DIR = Path("summaries")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
STATE_DIR = Path(".state")
GEMINI_USAGE_PATH = STATE_DIR / "gemini_usage.json"

DEFAULT_GEMINI_DAILY_REQUEST_CAP = 18
DEFAULT_QUOTA_COOLDOWN_SECONDS = 3600
DEFAULT_QUOTA_RETRY_ATTEMPTS = 3
DEFAULT_SUMMARY_BATCH_SIZE = 5
DEFAULT_SUMMARY_PROVIDER = "gemini"
QUOTA_ERROR_SNIPPETS = (
    "429",
    "quota",
    "resource_exhausted",
    "too many requests",
    "rpd",
    "requests per day",
)
RETRY_DELAY_PATTERNS = (
    r"retrydelay['\"]?\s*[:=]\s*['\"]([0-9]+(?:\.[0-9]+)?)s['\"]",
    r"retry in\s+([0-9]+(?:\.[0-9]+)?)s",
)


@dataclass(frozen=True)
class QuotaConfig:
    daily_request_cap: int
    cooldown_seconds: int
    retry_attempts: int


@dataclass(frozen=True)
class BatchSummaryItem:
    item_id: str
    source_name: str
    text: str
    transcript_path: Path


class UsageState:
    def __init__(self, state_path: Path, daily_cap: int) -> None:
        self._state_path = state_path
        self._daily_cap = daily_cap
        self._state = self._init_state()

    @property
    def requests_used(self) -> int:
        return int(self._state.get("requests_used", 0))

    @property
    def daily_cap(self) -> int:
        return self._daily_cap

    def can_send_request(self) -> tuple[bool, str]:
        cooldown_seconds = self.remaining_cooldown_seconds()
        if cooldown_seconds > 0:
            return False, f"gemini cooldown active ({cooldown_seconds}s remaining)"
        if self.requests_used >= self._daily_cap:
            return False, f"local daily request cap reached ({self._daily_cap})"
        return True, ""

    def reserve_daily_request(self) -> None:
        self._state["requests_used"] = self.requests_used + 1
        self._save()

    def set_quota_cooldown(self, seconds: float) -> int:
        delay = max(1, int(float(seconds) + 0.999))
        self._state["cooldown_until_epoch"] = time.time() + delay
        self._save()
        return delay

    def remaining_cooldown_seconds(self) -> int:
        cooldown_until = float(self._state.get("cooldown_until_epoch", 0.0) or 0.0)
        if cooldown_until <= 0:
            return 0

        remaining = int(cooldown_until - time.time() + 0.999)
        if remaining <= 0:
            self._state["cooldown_until_epoch"] = 0.0
            self._save()
            return 0
        return remaining

    def _init_state(self) -> dict[str, object]:
        today = local_day_iso()
        saved_state = self._load()
        if saved_state.get("date") != today:
            state = {
                "date": today,
                "requests_used": 0,
                "cooldown_until_epoch": 0.0,
            }
            self._save_state(state)
            return state

        try:
            requests_used = int(saved_state.get("requests_used", 0))
        except (TypeError, ValueError):
            requests_used = 0

        state = {
            "date": today,
            "requests_used": max(0, requests_used),
            "cooldown_until_epoch": float(saved_state.get("cooldown_until_epoch", 0.0) or 0.0),
        }

        if state["requests_used"] > self._daily_cap:
            state["requests_used"] = self._daily_cap

        self._save_state(state)
        return state

    def _load(self) -> dict[str, object]:
        if not self._state_path.is_file():
            return {}
        try:
            data = json.loads(self._state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        self._save_state(self._state)

    def _save_state(self, state: dict[str, object]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        self._state_path.write_text(
            json.dumps(state, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )


def build_prompt(text: str, source_name: str) -> str:
    return f"{SUMMARY_PROMPT}\n\nSource: {source_name}\n\nTranscript:\n{text}"


def build_batch_prompt(items: list[BatchSummaryItem]) -> str:
    if not items:
        raise ValueError("items must be non-empty")

    lines: list[str] = []
    lines.append(SUMMARY_PROMPT.strip())
    lines.append("")
    lines.append(
        "You will be given multiple transcripts. For each transcript, generate a summary as requested above."
    )
    lines.append(
        "For each transcript, output exactly one summary block with an id that matches the transcript id."
    )
    lines.append("")
    lines.append("Return ONLY blocks in this exact format, one per transcript, in the same order:")
    lines.append('<<<begin_summary id="t1">>>')
    lines.append("<summary text>")
    lines.append("<<<end_summary>>>")
    lines.append("")
    lines.append("Do not add any other text outside these blocks.")
    lines.append("")
    lines.append("Transcripts:")
    for item in items:
        lines.append(
            f'<<<begin_transcript id="{item.item_id}" source="{item.source_name}">>>'
        )
        lines.append(item.text.strip())
        lines.append("<<<end_transcript>>>")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


_BATCH_SUMMARY_BLOCK_RE = re.compile(
    r"<<<\s*begin_summary\s+id\s*=\s*['\"](?P<id>[^'\"]+)['\"]\s*>>>\s*"
    r"(?P<content>.*?)\s*"
    r"<<<\s*end_summary\s*>>>",
    flags=re.DOTALL | re.IGNORECASE,
)


def parse_batch_summaries(text: str) -> dict[str, str]:
    results: dict[str, str] = {}
    for match in _BATCH_SUMMARY_BLOCK_RE.finditer(text or ""):
        item_id = (match.group("id") or "").strip()
        content = (match.group("content") or "").strip()
        if item_id:
            results[item_id] = content
    return results


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


def local_day_iso() -> str:
    return datetime.now().astimezone().date().isoformat()


def load_quota_config() -> QuotaConfig:
    return QuotaConfig(
        daily_request_cap=_get_daily_request_cap(),
        cooldown_seconds=_get_quota_cooldown_seconds(),
        retry_attempts=_get_quota_retry_attempts(),
    )


def is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return any(snippet in message for snippet in QUOTA_ERROR_SNIPPETS)


def parse_retry_delay_seconds(exc: Exception) -> float | None:
    message_lc = str(exc).lower()
    for pattern in RETRY_DELAY_PATTERNS:
        match = re.search(pattern, message_lc)
        if not match:
            continue
        try:
            seconds = float(match.group(1))
        except (TypeError, ValueError):
            continue
        if seconds > 0:
            return seconds
    return None


def get_client() -> OpenAI:
    load_local_env()
    provider = _get_summary_provider()
    if provider == "gemini":
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        return OpenAI(api_key=api_key, base_url=GEMINI_BASE_URL)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")
    return OpenAI(api_key=api_key)


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


def summarize_with_client(client: OpenAI, prompt: str) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def _get_summary_provider() -> str:
    raw = os.getenv("SUMMARY_PROVIDER", DEFAULT_SUMMARY_PROVIDER).strip().lower()
    if raw in {"gemini", "openai"}:
        return raw
    log(f"invalid SUMMARY_PROVIDER={raw!r}; using {DEFAULT_SUMMARY_PROVIDER}")
    return DEFAULT_SUMMARY_PROVIDER


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


def _get_non_negative_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        log(f"invalid {name}={raw!r}; using {default}")
        return default
    if value < 0:
        log(f"{name} must be >= 0 (got {raw!r}); using {default}")
        return default
    return value


def _get_daily_request_cap() -> int:
    return _get_positive_int_env(
        "GEMINI_DAILY_REQUEST_CAP",
        DEFAULT_GEMINI_DAILY_REQUEST_CAP,
    )


def get_summary_batch_size() -> int:
    return _get_positive_int_env(
        "GEMINI_SUMMARY_BATCH_SIZE",
        DEFAULT_SUMMARY_BATCH_SIZE,
    )


def _get_quota_cooldown_seconds() -> int:
    return _get_positive_int_env(
        "GEMINI_QUOTA_COOLDOWN_SECONDS",
        DEFAULT_QUOTA_COOLDOWN_SECONDS,
    )


def _get_quota_retry_attempts() -> int:
    return _get_non_negative_int_env(
        "GEMINI_QUOTA_RETRY_ATTEMPTS",
        DEFAULT_QUOTA_RETRY_ATTEMPTS,
    )
