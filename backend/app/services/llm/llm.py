"""Gemini call orchestration with heuristic fallbacks. Prompts live in prompts.py."""

from __future__ import annotations

import logging
from typing import Any

from app.models import RelationshipType
from . import heuristics, prompts
from .client import GeminiError, call_gemini

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


def _parse_confidence(value: Any) -> float | None:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


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
    confidence = _parse_confidence(payload.get("confidence"))

    if category not in _VALID_CATEGORIES:
        return None
    if priority not in _VALID_PRIORITIES:
        return None
    if not isinstance(summary, str):
        return None
    if confidence is None:
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
        task_confidence = _parse_confidence(task.get("confidence", 0.5))
        if task_confidence is None:
            return None
        normalized_tasks.append(
            {
                "description": description.strip(),
                "deadline": deadline.strip(),
                "confidence": task_confidence,
            }
        )

    return {
        "category": category,
        "priority": priority,
        "summary": _truncate_summary(summary),
        "awaiting_reply": awaiting_reply,
        "confidence": confidence,
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
    confidence = _parse_confidence(payload.get("confidence"))
    if confidence is None:
        return None
    return relationship, confidence


def _validate_draft(payload: Any) -> dict | None:
    if not isinstance(payload, dict):
        return None

    subject = payload.get("subject")
    draft = payload.get("draft")
    if not isinstance(subject, str) or not subject.strip():
        return None
    if not isinstance(draft, str) or not draft.strip():
        return None
    confidence = _parse_confidence(payload.get("confidence"))
    if confidence is None:
        return None

    return {
        "subject": subject.strip(),
        "draft": draft.strip(),
        "confidence": confidence,
    }


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
            prompts.classify_and_extract(email_body, subject),
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
    relationship_type: str,
    tone_descriptor: dict,
    previous_conversations: list[str],
    similar_emails: list[str],
) -> dict:
    """Return {"subject", "draft", "confidence"} for a reply."""
    prompt_type = "generate_draft"
    try:
        result = call_gemini(
            prompts.draft_generation(
                email_body,
                subject,
                relationship_type,
                tone_descriptor,
                previous_conversations,
                similar_emails,
            ),
            prompt_type=prompt_type,
            expect_json=True,
        )
        validated = _validate_draft(result)
        if validated is not None:
            return validated
        logger.error(
            "gemini_parse_error prompt_type=%s error=invalid_draft_payload payload=%r",
            prompt_type,
            result,
        )
        _log_fallback(prompt_type, "invalid_draft_payload")
    except GeminiError as exc:
        _log_fallback(prompt_type, str(exc))
    except Exception as exc:  # noqa: BLE001
        _log_fallback(prompt_type, f"unexpected:{exc}")
    return heuristics.generate_draft(subject)
