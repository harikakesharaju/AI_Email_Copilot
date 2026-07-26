"""Deterministic fallbacks used when Gemini is unavailable or returns invalid output."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from app.models import RelationshipType

_DEFAULT_DRAFT = (
    "Thanks for the reminder. I will take care of it and send the update "
    "by the requested deadline."
)

_ACTION_VERBS = [
    "complete",
    "submit",
    "send",
    "prepare",
    "review",
    "approve",
    "check",
    "share",
    "finish",
    "reply",
    "update",
]


def classify_relationship(_sender_name: str | None, _email_body: str) -> tuple[RelationshipType, float]:
    return RelationshipType.unknown, 0.3


def classify_and_extract(email_body: str, subject: str) -> dict:
    text = f"{subject}\n{email_body}".strip()
    lower_text = text.lower()

    matched_actions = [verb for verb in _ACTION_VERBS if re.search(rf"\b{verb}\b", lower_text)]
    awaiting_reply = bool(matched_actions) or bool(
        re.search(r"\b(please|kindly|can you|could you|would you)\b", lower_text)
    )

    deadline = None
    if re.search(r"\beod\b", lower_text):
        deadline = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)
    elif re.search(r"\basap\b", lower_text):
        deadline = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=0)
    elif re.search(r"\btomorrow\b", lower_text):
        deadline = (datetime.utcnow() + timedelta(days=1)).replace(
            hour=23, minute=59, second=59, microsecond=0
        )

    tasks: list[dict] = []
    if awaiting_reply:
        description = ""
        body_text = email_body.strip()
        for marker in ["please ", "kindly ", "can you ", "could you ", "would you "]:
            if marker in body_text.lower():
                description = body_text.lower().split(marker, 1)[1].strip()
                description = re.sub(r"\s+", " ", description)
                break
        if not description:
            description = re.sub(r"\s+", " ", body_text)
        description = description.rstrip(" .")
        if len(description) > 140:
            description = description[:137].rstrip() + "..."
        tasks.append(
            {
                "description": description,
                "deadline": deadline.isoformat() if deadline else "",
                "confidence": 0.7,
            }
        )

    category = (
        "WORK"
        if any(
            word in lower_text
            for word in ["work", "project", "task", "submit", "ppt", "essay", "deadline"]
        )
        else "OTHER"
    )
    if re.search(r"\b(urgent|asap|immediately)\b", lower_text):
        priority = "URGENT"
    elif re.search(r"\b(eod|today|deadline)\b", lower_text):
        priority = "HIGH"
    else:
        priority = "MEDIUM"
    summary = "" if not text else text.splitlines()[0]
    summary_words = summary.split()
    if len(summary_words) > 50:
        summary = " ".join(summary_words[:50])

    return {
        "category": category,
        "priority": priority,
        "summary": summary,
        "awaiting_reply": awaiting_reply,
        "confidence": 0.55 if awaiting_reply else 0.5,
        "tasks": tasks,
    }


def generate_draft(subject: str = "") -> dict:
    text = (subject or "").strip() or "(no subject)"
    reply_subject = text if text.lower().startswith("re:") else f"Re: {text}"
    return {
        "subject": reply_subject,
        "draft": _DEFAULT_DRAFT,
        "confidence": 0.4,
    }
