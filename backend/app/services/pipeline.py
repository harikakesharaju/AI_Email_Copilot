from datetime import datetime
from email.utils import parseaddr

from sqlalchemy.orm import Session

from app.models import User, Thread, Email, Task, Draft, Contact, ToneProfile
from app.services import gmail_service, embeddings
from app.services.llm import classify_and_extract, generate_draft
from app.services.contacts import resolve_contact, resolve_thread_tone

AUTO_DRAFT_MIN_CONFIDENCE = 0.60


def process_new_message(db: Session, user: User, gmail_message_id: str):
    raw = gmail_service.fetch_message(user, gmail_message_id, db=db)

    thread = (
        db.query(Thread)
        .filter(Thread.user_id == user.id, Thread.gmail_thread_id == raw["gmail_thread_id"])
        .first()
    )
    if not thread:
        thread = Thread(user_id=user.id, gmail_thread_id=raw["gmail_thread_id"],
                         subject=raw["subject"], last_message_at=datetime.utcnow())
        db.add(thread)
        db.commit()
        db.refresh(thread)

    sender_name, sender_email = parseaddr(raw["sender"])
    analysis = classify_and_extract(raw["body"], raw["subject"])
    analysis_confidence = float(analysis.get("confidence", 0.0))

    email_row = (
        db.query(Email)
        .filter(Email.gmail_message_id == raw["gmail_message_id"])
        .first()
    )

    if not email_row:
        email_row = Email(
            thread_id=thread.id,
            user_id=user.id,
            gmail_message_id=raw["gmail_message_id"],
            sender=sender_email,
            recipients=raw["recipients"],
            body=raw["body"],
            received_at=datetime.utcnow(),
            category=analysis["category"],
            priority=analysis["priority"],
            summary=analysis["summary"],
            embedding=None,
            awaiting_reply=analysis["awaiting_reply"],
            confidence=analysis_confidence,
            needs_manual_review=False,
        )
        db.add(email_row)
        db.commit()
        db.refresh(email_row)
    else:
        email_row.sender = sender_email
        email_row.recipients = raw["recipients"]
        email_row.body = raw["body"]
        email_row.category = analysis["category"]
        email_row.priority = analysis["priority"]
        email_row.summary = analysis["summary"]
        email_row.embedding = None
        email_row.awaiting_reply = analysis["awaiting_reply"]
        email_row.confidence = analysis_confidence
        db.add(email_row)
        db.commit()
        db.refresh(email_row)

    existing_tasks = db.query(Task).filter(Task.email_id == email_row.id).all()
    if not existing_tasks:
        for task in analysis.get("tasks", []):
            deadline = None
            if task.get("deadline"):
                try:
                    deadline = datetime.fromisoformat(task["deadline"])
                except ValueError:
                    deadline = None
            db.add(Task(user_id=user.id, email_id=email_row.id,
                         description=task["description"], deadline=deadline))
        db.commit()

    # Resolve every participant on the thread to a relationship type
    all_addresses = [sender_email] + raw["recipients"]
    contacts = [
        resolve_contact(db, user, addr, sender_name if addr == sender_email else None, raw["body"])
        for addr in all_addresses if addr and addr != user.email
    ]

    existing_draft = db.query(Draft).filter(Draft.email_id == email_row.id).first()
    if analysis["awaiting_reply"] and contacts and not existing_draft:
        if analysis_confidence < AUTO_DRAFT_MIN_CONFIDENCE:
            _mark_manual_review(db, email_row)
        else:
            _generate_draft(db, user, email_row, raw, contacts)

    return email_row


def _mark_manual_review(db: Session, email_row: Email) -> None:
    email_row.needs_manual_review = True
    db.add(email_row)
    db.commit()


def _email_snippet(row: Email) -> str:
    summary = (row.summary or "").strip()
    body = (row.body or "").strip()
    if summary and body:
        return f"{summary}\n{body[:500]}"
    return summary or body[:500]


def _generate_draft(db: Session, user: User, email_row: Email, raw: dict, contacts: list[Contact]):
    relationship_type, mixed_audience = resolve_thread_tone(contacts)

    tone_profile = (
        db.query(ToneProfile)
        .filter(ToneProfile.user_id == user.id, ToneProfile.relationship_type == relationship_type)
        .first()
    )
    tone_descriptor = tone_profile.tone_descriptor if tone_profile else {
        "formality": "medium", "warmth": "medium", "length": "concise"
    }

    previous_rows = (
        db.query(Email)
        .filter(
            Email.user_id == user.id,
            Email.sender == email_row.sender,
            Email.id != email_row.id,
        )
        .order_by(Email.received_at.desc())
        .limit(3)
        .all()
    )
    previous_conversations = [
        snippet for row in previous_rows if (snippet := _email_snippet(row))
    ]

    # RAG: pull the most similar past emails from this sender for tone/style
    similar_query = (
        db.query(Email)
        .filter(
            Email.user_id == user.id,
            Email.sender == email_row.sender,
            Email.id != email_row.id,
        )
    )
    if email_row.embedding is not None:
        similar_query = similar_query.order_by(
            Email.embedding.cosine_distance(email_row.embedding)
        )
    else:
        similar_query = similar_query.order_by(Email.received_at.desc())
    similar_rows = similar_query.limit(3).all()
    similar_emails = [
        snippet for row in similar_rows if (snippet := _email_snippet(row))
    ]

    result = generate_draft(
        raw["body"],
        raw["subject"],
        relationship_type.value,
        tone_descriptor,
        previous_conversations,
        similar_emails,
    )

    # Mixed-audience threads are always held for review
    confidence = result["confidence"]
    if mixed_audience:
        confidence = min(confidence, 0.4)

    # Always persist the draft so the user can see and review it.
    # Low-confidence drafts are flagged for manual review rather than suppressed.
    needs_review = confidence < AUTO_DRAFT_MIN_CONFIDENCE
    if needs_review:
        _mark_manual_review(db, email_row)

    db.add(
        Draft(
            email_id=email_row.id,
            subject=result["subject"],
            content=result["draft"],
            confidence=confidence,
            mixed_audience=mixed_audience,
        )
    )
    db.commit()
    db.refresh(email_row)

    try:
        gmail_service.create_draft(
            user,
            to=email_row.sender,
            subject=result["subject"],
            body=result["draft"],
            thread_id=raw.get("gmail_thread_id"),
            in_reply_to=None,
            db=db,
        )
    except Exception:
        # Keep the DB draft record even if Gmail draft creation fails.
        pass
