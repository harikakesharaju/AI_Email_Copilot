"""
Resolves a sender's email address to a relationship_type (work, family, friend,
recruiter_hr, vendor_support, unknown), cheaply where possible.

Order of resolution:
1. Existing contact already labeled by the user -> trust it completely.
2. Domain heuristics (free, instant, no API call).
3. LLM classification as a fallback for ambiguous cases (uses Gemini free tier).
4. Anything still low-confidence gets surfaced in the dashboard for the user to confirm.
"""

import re
from sqlalchemy.orm import Session

from app.models import Contact, RelationshipType, User
from app.services.llm import classify_relationship_llm

RECRUITING_DOMAINS = {"greenhouse.io", "lever.co", "myworkday.com", "smartrecruiters.com",
                       "ashbyhq.com", "linkedin.com"}
PERSONAL_EMAIL_DOMAINS = {"gmail.com", "yahoo.com", "icloud.com", "outlook.com", "hotmail.com"}


def _domain(email: str) -> str:
    return email.split("@")[-1].lower()


def resolve_contact(db: Session, user: User, sender_email: str, sender_name: str | None,
                     email_body: str) -> Contact:
    existing = (
        db.query(Contact)
        .filter(Contact.user_id == user.id, Contact.email == sender_email)
        .first()
    )
    if existing and existing.labeled_by_user:
        return existing

    domain = _domain(sender_email)
    user_domain = _domain(user.email)

    relationship_type = RelationshipType.unknown
    confidence = 0.0

    if domain == user_domain:
        relationship_type, confidence = RelationshipType.work, 0.9
    elif domain in RECRUITING_DOMAINS or re.search(r"\b(recruiter|talent acquisition|hiring)\b",
                                                     email_body, re.IGNORECASE):
        relationship_type, confidence = RelationshipType.recruiter_hr, 0.85
    elif domain in PERSONAL_EMAIL_DOMAINS:
        # Personal-provider domains are ambiguous between family/friend/other —
        # don't guess, let the LLM take a pass, then surface for user confirmation.
        relationship_type, confidence = classify_relationship_llm(sender_name, email_body)
    else:
        relationship_type, confidence = RelationshipType.vendor_support, 0.5

    if existing:
        existing.relationship_type = relationship_type
        existing.confidence = confidence
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    contact = Contact(
        user_id=user.id,
        email=sender_email,
        name=sender_name,
        relationship_type=relationship_type,
        confidence=confidence,
        labeled_by_user=False,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def resolve_thread_tone(contacts: list[Contact]) -> tuple[RelationshipType, bool]:
    """Given all contacts on a thread, pick the tone to draft in.
    If relationship types are mixed, default to the most formal one present
    and flag the thread so the draft is always held for review rather than
    auto-sent — blending tones reads as inconsistent, so we fail safe instead."""
    FORMALITY_ORDER = [
        RelationshipType.recruiter_hr,
        RelationshipType.work,
        RelationshipType.vendor_support,
        RelationshipType.unknown,
        RelationshipType.friend,
        RelationshipType.family,
    ]
    types = {c.relationship_type for c in contacts}
    if len(types) <= 1:
        return (types.pop() if types else RelationshipType.unknown), False

    most_formal = min(types, key=lambda t: FORMALITY_ORDER.index(t))
    return most_formal, True
