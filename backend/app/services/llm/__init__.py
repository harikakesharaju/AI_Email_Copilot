"""Public LLM API: Gemini primary path with heuristic fallbacks."""

from __future__ import annotations

import logging
from typing import Any

from app.models import RelationshipType
from app.services.llm import heuristics, prompts
from app.services.llm.client import GeminiError, call_gemini

logger = logging.getLogger(__name__)

_VALID_CATEGORIES = {
    "WORK",
    "PERSONAL",
    "FINANCE",
    "SHOPPING",
    "RECRUITMENT",
    "MEETING",
    "SUPPORT",
    "NEWSLETTER",
    "SOCIAL",
    "OTHER",
}
_VALID_PRIORITIES = {"LOW", "MEDIUM", "HIGH", "URGENT"}
_MAX_SUMMARY_WORDS = 50
_RELATIONSHIP_TYPES = {
    "family": RelationshipType.family,
    "friend": RelationshipType.friend,
    "unknown": RelationshipType.unknown,
}


def _log_fallback(prompt_type: str, reason: str) -> None:
    logger.warning(
        "gemini_fallback prompt_type=%s fallback=true reason=%s",
        prompt_type,
        reason,
    )


def _normalize_enum(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.strip().upper() or None


def _truncate_summary(summary: str) -> str:
    words = summary.split()
    if len(words) <= _MAX_SUMMARY_WORDS:
        return summary.strip()
    return " ".join(words[:_MAX_SUMMARY_WORDS]).strip()


def _validate_classification(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None

    category = _normalize_enum(payload.get("category"))
    priority = _normalize_enum(payload.get("priority"))
    summary = payload.get("summary")
    awaiting_reply = payload.get("awaiting_reply")
    tasks = payload.get("tasks")

    if category not in _VALID_CATEGORIES:
        return None
    if priority not in _VALID_PRIORITIES:
        return None
    if not isinstance(summary, str):
        return None
    if not isinstance(awaiting_reply, bool):
        # tolerate common JSON quirks
        if isinstance(awaiting_reply, str) and awaiting_reply.lower() in {"true", "false"}:
            awaiting_reply = awaiting_reply.lower() == "true"
        else:
            return None
    if not isinstance(tasks, list):
        return None

    normalized_tasks: list[dict] = []
    for task in tasks:
        if not isinstance(task, dict):
            return None
        description = task.get("description")
        if not isinstance(description, str) or not description.strip():
            return None
        deadline = task.get("deadline")
        if deadline is None:
            deadline = ""
        if not isinstance(deadline, str):
            return None
        try:
            confidence = float(task.get("confidence", 0.5))
        except (TypeError, ValueError):
            return None
        confidence = max(0.0, min(1.0, confidence))
        normalized_tasks.append(
            {
                "description": description.strip(),
                "deadline": deadline.strip(),
                "confidence": confidence,
            }
        )

    return {
        "category": category,
        "priority": priority,
        "summary": _truncate_summary(summary),
        "awaiting_reply": awaiting_reply,
        "tasks": normalized_tasks,
    }


def _validate_relationship(payload: Any) -> tuple[RelationshipType, float] | None:
    if not isinstance(payload, dict):
        return None
    raw_type = payload.get("relationship_type")
    if not isinstance(raw_type, str):
        return None
    relationship = _RELATIONSHIP_TYPES.get(raw_type.strip().lower())
    if relationship is None:
        return None
    try:
        confidence = float(payload.get("confidence"))
    except (TypeError, ValueError):
        return None
    confidence = max(0.0, min(1.0, confidence))
    return relationship, confidence


def classify_relationship_llm(
    sender_name: str | None, email_body: str
) -> tuple[RelationshipType, float]:
    prompt_type = "classify_relationship"
    try:
        result = call_gemini(
            prompts.relationship_classification(sender_name, email_body),
            prompt_type=prompt_type,
            expect_json=True,
        )
        validated = _validate_relationship(result)
        if validated is not None:
            return validated
        logger.error(
            "gemini_parse_error prompt_type=%s error=invalid_relationship_payload payload=%r",
            prompt_type,
            result,
        )
        _log_fallback(prompt_type, "invalid_relationship_payload")
    except GeminiError as exc:
        _log_fallback(prompt_type, str(exc))
    except Exception as exc:  # noqa: BLE001
        _log_fallback(prompt_type, f"unexpected:{exc}")
    return heuristics.classify_relationship(sender_name, email_body)


def classify_and_extract(email_body: str, subject: str) -> dict:
    """Single call: category, priority, summary, and any tasks/deadlines."""
    prompt_type = "classify_and_extract"
    try:
        result = call_gemini(
            prompts.email_classification(email_body, subject),
            prompt_type=prompt_type,
            expect_json=True,
        )
        validated = _validate_classification(result)
        if validated is not None:
            return validated
        logger.error(
            "gemini_parse_error prompt_type=%s error=invalid_classification_payload payload=%r",
            prompt_type,
            result,
        )
        _log_fallback(prompt_type, "invalid_classification_payload")
    except GeminiError as exc:
        _log_fallback(prompt_type, str(exc))
    except Exception as exc:  # noqa: BLE001
        _log_fallback(prompt_type, f"unexpected:{exc}")
    return heuristics.classify_and_extract(email_body, subject)


def generate_draft(
    email_body: str,
    subject: str,
    tone_descriptor: dict,
    context_snippets: list[str],
) -> str:
    prompt_type = "generate_draft"
    try:
        text = call_gemini(
            prompts.draft_reply(email_body, subject, tone_descriptor, context_snippets),
            prompt_type=prompt_type,
            expect_json=False,
        )
        if isinstance(text, str) and text.strip():
            return text.strip()
        _log_fallback(prompt_type, "empty_draft")
    except GeminiError as exc:
        _log_fallback(prompt_type, str(exc))
    except Exception as exc:  # noqa: BLE001
        _log_fallback(prompt_type, f"unexpected:{exc}")
    return heuristics.generate_draft()
