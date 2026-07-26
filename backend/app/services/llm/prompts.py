"""Prompt templates for Gemini. Keep these separate from call / fallback logic."""

from __future__ import annotations

import json


def relationship_classification(sender_name: str | None, email_body: str) -> str:
    return f"""Classify the relationship between the email sender and the recipient
based on tone and content. Sender name: {sender_name or "unknown"}.

Email body:
\"\"\"{email_body[:1500]}\"\"\"

Respond with JSON only: {{"relationship_type": "family" | "friend" | "unknown",
"confidence": <float 0-1>}}"""


def email_classification(email_body: str, subject: str) -> str:
    return f"""You are an email classification engine. Analyze the email below and return ONLY a single JSON object.

Subject: {subject}
Body:
\"\"\"{email_body[:3000]}\"\"\"

OUTPUT RULES (mandatory):
- Return raw JSON only.
- Never return markdown.
- Never return explanations.
- Never wrap JSON inside code blocks.
- Do not include any text before or after the JSON.

SCHEMA (return exactly these keys):
{{
  "category": "",
  "priority": "",
  "awaiting_reply": true,
  "summary": "",
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
- tasks: list of actionable items the recipient should do
  - description: short imperative action (e.g. "Submit the report")
  - deadline: ISO 8601 datetime string when a deadline is stated or clearly implied; otherwise ""
  - confidence: float from 0 to 1 for how confident you are that this is a real task
- If there are no tasks, return "tasks": []
- Deadline mapping hints: "EOD"/"ASAP"/"today" → today's end of day; "tomorrow" → tomorrow; parse explicit dates when present

Return the JSON object now."""


def draft_reply(
    email_body: str,
    subject: str,
    tone_descriptor: dict,
    context_snippets: list[str],
) -> str:
    context = "\n---\n".join(context_snippets) if context_snippets else "None"
    return f"""Write a reply to this email in the voice described below. Only output
the reply text, nothing else.

Tone to use: {json.dumps(tone_descriptor)}

Relevant past context from this contact:
{context}

Subject: {subject}
Email to reply to:
\"\"\"{email_body[:3000]}\"\"\"
"""
