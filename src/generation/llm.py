"""Minimal Groq chat-completions client (the project's only LLM provider).

Uses Groq's OpenAI-compatible HTTP endpoint through the standard library, so no
extra dependency is needed. Configuration comes from the environment:

    GROQ_API_KEY   required for any LLM call
    GROQ_MODEL     default ``openai/gpt-oss-20b`` (a model available on Groq's free tier)

Nothing here runs unless a caller explicitly asks for an LLM path; tests and CI
never reach it.
"""
from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "openai/gpt-oss-20b"
MAX_RETRIES = 3


class LLMError(RuntimeError):
    """Raised when a Groq call cannot be completed."""


def groq_model() -> str:
    """Model id from GROQ_MODEL, defaulting to a free-tier Groq model."""
    return os.environ.get("GROQ_MODEL", DEFAULT_MODEL)


def groq_available() -> bool:
    """True when a Groq API key is configured."""
    return bool(os.environ.get("GROQ_API_KEY", "").strip())


def groq_chat(messages: list[dict], *, model: str | None = None, max_tokens: int = 600,
              temperature: float = 0.0, json_mode: bool = False, timeout: float = 60.0) -> str:
    """Send a chat completion request to Groq and return the message text.

    Retries on HTTP 429 (free-tier rate limit) honouring ``Retry-After``. Raises
    ``LLMError`` on a missing key, HTTP errors, network errors, or an empty reply.
    """
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise LLMError("GROQ_API_KEY is not set")

    payload: dict = {
        "model": model or groq_model(),
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "reasoning_effort": "low",  # gpt-oss models spend tokens on hidden reasoning otherwise
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    body = json.dumps(payload).encode()
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "groundtruth/0.1"}

    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(GROQ_URL, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < MAX_RETRIES:
                wait = min(float(e.headers.get("Retry-After", 2 * attempt)), 20.0)
                logger.warning("Groq rate limit hit; retrying in %.1fs", wait)
                time.sleep(wait)
                continue
            detail = e.read().decode(errors="replace")[:300]
            raise LLMError(f"Groq HTTP {e.code}: {detail}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            raise LLMError(f"Groq request failed: {e}") from None

    try:
        text = (data["choices"][0]["message"].get("content") or "").strip()
    except (KeyError, IndexError, TypeError):
        raise LLMError("Unexpected Groq response shape") from None
    if not text:
        raise LLMError("Groq returned an empty reply (try raising max_tokens)")
    return text
