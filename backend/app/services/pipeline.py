from datetime import datetime
from email.utils import parseaddr

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import User, Thread, Email, Task, Draft, Contact, ToneProfile
from app.services import gmail_service, embeddings
from app.services.llm import classify_and_extract, generate_draft
from app.services.contacts import resolve_contact, resolve_thread_tone


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
            embedding=embeddings.embed_text(raw["body"]),
            awaiting_reply=analysis["awaiting_reply"],
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
        email_row.embedding = embeddings.embed_text(raw["body"])
        email_row.awaiting_reply = analysis["awaiting_reply"]
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
        _generate_draft(db, user, email_row, raw, contacts)

    return email_row


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

    # RAG: pull the most similar past emails from/to this sender for context
    context_rows = (
        db.query(Email)
        .filter(Email.user_id == user.id, Email.sender == email_row.sender)
        .order_by(Email.embedding.cosine_distance(email_row.embedding))
        .limit(3)
        .all()
    )
    context_snippets = [row.summary for row in context_rows if row.summary]

    draft_text = generate_draft(raw["body"], raw["subject"], tone_descriptor, context_snippets)

    # Mixed-audience threads are always held for review, never auto-considered high confidence
    confidence = 0.4 if mixed_audience else 0.75

    db.add(Draft(email_id=email_row.id, content=draft_text,
                  confidence=confidence, mixed_audience=mixed_audience))
    db.commit()
