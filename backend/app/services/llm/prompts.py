"""Gemini prompt templates only. No Gemini calls or business orchestration."""

from __future__ import annotations

import json

_JSON_OUTPUT_RULES = """OUTPUT RULES (mandatory):
- Return raw JSON only.
- Never return markdown.
- Never return explanations.
- Never wrap JSON inside code blocks.
- Do not include any text before or after the JSON."""


def _email_block(subject: str, email_body: str, *, body_limit: int = 3000) -> str:
    return f"""Subject: {subject}
Body:
\"\"\"{email_body[:body_limit]}\"\"\""""


def classification(email_body: str, subject: str) -> str:
    """Classify category, priority, and whether a reply is awaited."""
    return f"""You are an email classification engine. Analyze the email below and return ONLY a single JSON object.

{_email_block(subject, email_body)}

{_JSON_OUTPUT_RULES}

SCHEMA (return exactly these keys):
{{
  "category": "",
  "priority": "",
  "awaiting_reply": true,
  "confidence": 0.94
}}

FIELD RULES:
- category: exactly one of
  WORK | PERSONAL | FINANCE | SHOPPING | RECRUITMENT | MEETING | SUPPORT | NEWSLETTER | SOCIAL | OTHER
- priority: exactly one of
  LOW | MEDIUM | HIGH | URGENT
- awaiting_reply: true if the sender asks the recipient for an action, confirmation, decision, or response; otherwise false
- confidence: float from 0 to 1 for how confident you are in this classification

Return the JSON object now."""


def task_extraction(email_body: str, subject: str) -> str:
    """Extract actionable tasks and deadlines from an email."""
    return f"""You are a task extraction engine. Analyze the email below and return ONLY a single JSON object.

{_email_block(subject, email_body)}

{_JSON_OUTPUT_RULES}

SCHEMA (return exactly these keys):
{{
  "confidence": 0.94,
  "tasks": [
    {{
      "description": "",
      "deadline": "",
      "confidence": 0.95
    }}
  ]
}}

FIELD RULES:
- confidence: float from 0 to 1 for overall confidence in the task extraction
- tasks: list of actionable items the recipient should do
  - description: short imperative action (e.g. "Submit the report")
  - deadline: ISO 8601 datetime string when a deadline is stated or clearly implied; otherwise ""
  - confidence: float from 0 to 1 for how confident you are that this is a real task
- If there are no tasks, return "tasks": []
- Deadline mapping hints: "EOD"/"ASAP"/"today" → today's end of day; "tomorrow" → tomorrow; parse explicit dates when present

Return the JSON object now."""


def summary_generation(email_body: str, subject: str) -> str:
    """Generate a short email summary."""
    return f"""You are an email summarization engine. Analyze the email below and return ONLY a single JSON object.

{_email_block(subject, email_body)}

{_JSON_OUTPUT_RULES}

SCHEMA (return exactly these keys):
{{
  "summary": "",
  "confidence": 0.94
}}

FIELD RULES:
- summary: concise overview of the email, under 50 words
- confidence: float from 0 to 1 for how confident you are in this summary

Return the JSON object now."""


def relationship_classification(sender_name: str | None, email_body: str) -> str:
    """Classify sender/recipient relationship from tone and content."""
    return f"""Classify the relationship between the email sender and the recipient
based on tone and content. Sender name: {sender_name or "unknown"}.

Email body:
\"\"\"{email_body[:1500]}\"\"\"

{_JSON_OUTPUT_RULES}

Respond with JSON only: {{"relationship_type": "family" | "friend" | "unknown",
"confidence": <float 0-1>}}"""


def draft_generation(
    email_body: str,
    subject: str,
    relationship_type: str,
    tone_descriptor: dict,
    previous_conversations: list[str],
    similar_emails: list[str],
) -> str:
    """Generate a reply draft adapted to relationship, tone, and prior context."""
    previous = (
        "\n---\n".join(previous_conversations) if previous_conversations else "None"
    )
    similar = "\n---\n".join(similar_emails) if similar_emails else "None"
    return f"""You are an email drafting assistant. Write a professional, natural reply.

INPUT EMAIL
{_email_block(subject, email_body)}

CONTEXT TO ADAPT TONE FROM
- Relationship: {relationship_type}
- Stored ToneProfile: {json.dumps(tone_descriptor)}
- Previous conversations with this contact:
{previous}
- Retrieved similar emails:
{similar}

WRITING RULES
- Sound professional and natural; match relationship and ToneProfile.
- Use previous conversations and similar emails only for tone, phrasing, and continuity.
- Never hallucinate facts.
- Never invent dates.
- Never invent attachments.
- Never promise actions the user cannot fulfil.
- Do not invent commitments, availability, file names, ticket numbers, or outcomes.
- If information is missing, acknowledge briefly or ask a clarifying question instead of guessing.
- Prefer a reply subject that keeps the thread (usually "Re: ...") unless a clearer subject is justified by the email content.

{_JSON_OUTPUT_RULES}

SCHEMA (return exactly these keys):
{{
  "subject": "",
  "draft": "",
  "confidence": 0.94
}}

FIELD RULES
- subject: reply subject line
- draft: full email body ready to send
- confidence: float from 0 to 1 for how appropriate and grounded the draft is

Return the JSON object now."""


def classify_and_extract(email_body: str, subject: str) -> str:
    """Combined classification + summary + task extraction for the existing single-call path.

    Keeps the same response schema used by classify_and_extract business logic.
    """
    return f"""You are an email classification engine. Analyze the email below and return ONLY a single JSON object.

{_email_block(subject, email_body)}

{_JSON_OUTPUT_RULES}

SCHEMA (return exactly these keys):
{{
  "category": "",
  "priority": "",
  "awaiting_reply": true,
  "summary": "",
  "confidence": 0.94,
  "tasks": [
    {{
      "description": "",
      "deadline": "",
      "confidence": 0.95
    }}
  ]
}}

FIELD RULES:
- category: exactly one of
  WORK | PERSONAL | FINANCE | SHOPPING | RECRUITMENT | MEETING | SUPPORT | NEWSLETTER | SOCIAL | OTHER
- priority: exactly one of
  LOW | MEDIUM | HIGH | URGENT
- awaiting_reply: true if the sender asks the recipient for an action, confirmation, decision, or response; otherwise false
- summary: concise overview of the email, under 50 words
- confidence: float from 0 to 1 for overall confidence in this analysis
- tasks: list of actionable items the recipient should do
  - description: short imperative action (e.g. "Submit the report")
  - deadline: ISO 8601 datetime string when a deadline is stated or clearly implied; otherwise ""
  - confidence: float from 0 to 1 for how confident you are that this is a real task
- If there are no tasks, return "tasks": []
- Deadline mapping hints: "EOD"/"ASAP"/"today" → today's end of day; "tomorrow" → tomorrow; parse explicit dates when present

Return the JSON object now."""
