"""Centralized Gemini client: retries, timeouts, JSON repair, and structured logging."""

from __future__ import annotations

import json
import logging
import os
import re
import time
from typing import Any

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions

from app.config import settings

logger = logging.getLogger(__name__)

_API_KEY_ENV = "GEMINI_API_KEY"
_configured = False

_RETRYABLE_STATUS_CODES = {429, 500, 503}
_RETRYABLE_EXCEPTIONS = (
    google_exceptions.TooManyRequests,
    google_exceptions.InternalServerError,
    google_exceptions.ServiceUnavailable,
    google_exceptions.ResourceExhausted,
    TimeoutError,
)


class GeminiError(Exception):
    """Raised when a Gemini call fails after retries or returns unusable output."""


class GeminiConfigError(RuntimeError):
    """Raised at startup when GEMINI_API_KEY is missing."""


def validate_gemini_api_key() -> str:
    """Load and validate the API key from the environment only.

    `.env` values are synced into ``os.environ`` by the app settings layer so
    callers never read secrets from application code.
    """
    key = (os.environ.get(_API_KEY_ENV) or "").strip()
    if not key:
        # pydantic-settings may have loaded .env into Settings without exporting
        # to os.environ — promote it so all Gemini calls use the env only.
        key = (settings.gemini_api_key or "").strip()
        if key:
            os.environ[_API_KEY_ENV] = key

    if not key:
        raise GeminiConfigError(
            "GEMINI_API_KEY is missing or empty. Set it in your environment "
            "(or in the .env file as GEMINI_API_KEY) before starting the server."
        )
    return key


def configure_gemini() -> None:
    """Configure the generativeai SDK once using the env API key."""
    global _configured
    api_key = validate_gemini_api_key()
    genai.configure(api_key=api_key)
    _configured = True
    logger.info(
        "Gemini configured model=%s timeout_s=%s max_retries=%s",
        settings.gemini_model,
        settings.gemini_timeout_seconds,
        settings.gemini_max_retries,
    )


def _ensure_configured() -> None:
    if not _configured:
        configure_gemini()


def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, _RETRYABLE_EXCEPTIONS):
        return True
    status = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status in _RETRYABLE_STATUS_CODES:
        return True
    # google.generativeai sometimes wraps transport errors with a message only
    message = str(exc).lower()
    return any(
        token in message
        for token in ("429", "500", "503", "resource exhausted", "unavailable", "timed out", "timeout")
    )


def _sleep_before_retry(attempt: int) -> None:
    delay = settings.gemini_retry_base_delay_seconds * (2 ** (attempt - 1))
    time.sleep(delay)


def repair_json_text(raw: str) -> str:
    """Best-effort cleanup so slightly malformed model output can still parse."""
    text = (raw or "").strip()
    if not text:
        raise GeminiError("Empty Gemini response")

    fence = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if fence:
        text = fence.group(1).strip()

    if not text.startswith("{") and not text.startswith("["):
        start_obj, start_arr = text.find("{"), text.find("[")
        starts = [i for i in (start_obj, start_arr) if i >= 0]
        if starts:
            start = min(starts)
            end_char = "}" if text[start] == "{" else "]"
            end = text.rfind(end_char)
            if end > start:
                text = text[start : end + 1]

    # Trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Smart quotes → standard quotes
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    return text.strip()


def parse_json_response(raw: str, *, prompt_type: str) -> Any:
    """Validate that the response is JSON, repairing common malformations first."""
    candidates = [raw, repair_json_text(raw)]
    seen: set[str] = set()
    last_error: Exception | None = None

    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc

    logger.error(
        "gemini_parse_error prompt_type=%s error=%s raw_preview=%r",
        prompt_type,
        last_error,
        (raw or "")[:240],
    )
    raise GeminiError(f"Gemini response was not valid JSON: {last_error}") from last_error


def _generate_content(prompt: str, *, expect_json: bool) -> str:
    _ensure_configured()
    model = genai.GenerativeModel(settings.gemini_model)
    generation_config = {"response_mime_type": "application/json"} if expect_json else None
    response = model.generate_content(
        prompt,
        generation_config=generation_config,
        request_options={"timeout": settings.gemini_timeout_seconds},
    )
    text = getattr(response, "text", None)
    if not text or not str(text).strip():
        raise GeminiError("Gemini returned an empty response")
    return str(text)


def call_gemini(
    prompt: str,
    *,
    prompt_type: str,
    expect_json: bool = False,
) -> str | Any:
    """Call Gemini with retries/backoff. Returns parsed JSON or plain text.

    Raises ``GeminiError`` when all attempts fail so callers can fall back.
    """
    model_name = settings.gemini_model
    max_attempts = max(1, settings.gemini_max_retries + 1)
    started = time.perf_counter()
    last_error: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            raw = _generate_content(prompt, expect_json=expect_json)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            if expect_json:
                parsed = parse_json_response(raw, prompt_type=prompt_type)
                logger.info(
                    "gemini_ok prompt_type=%s model=%s elapsed_ms=%s attempt=%s fallback=false",
                    prompt_type,
                    model_name,
                    elapsed_ms,
                    attempt,
                )
                return parsed

            logger.info(
                "gemini_ok prompt_type=%s model=%s elapsed_ms=%s attempt=%s fallback=false",
                prompt_type,
                model_name,
                elapsed_ms,
                attempt,
            )
            return raw.strip()
        except Exception as exc:  # noqa: BLE001 — centralized boundary; callers fall back
            last_error = exc
            retryable = _is_retryable(exc)
            logger.warning(
                "gemini_error prompt_type=%s model=%s attempt=%s/%s retryable=%s error=%s",
                prompt_type,
                model_name,
                attempt,
                max_attempts,
                retryable,
                exc,
            )
            if not retryable or attempt >= max_attempts:
                break
            _sleep_before_retry(attempt)

    elapsed_ms = int((time.perf_counter() - started) * 1000)
    logger.error(
        "gemini_failed prompt_type=%s model=%s elapsed_ms=%s fallback=true error=%s",
        prompt_type,
        model_name,
        elapsed_ms,
        last_error,
    )
    raise GeminiError(str(last_error) if last_error else "Gemini call failed") from last_error
