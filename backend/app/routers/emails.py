from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from google.auth.exceptions import RefreshError
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (
    Email,
    Draft,
    Task,
    DraftStatus,
    FeedbackEvent,
    Contact,
    User,
    Thread,
)
from app.services import gmail_service

router = APIRouter(prefix="/api", tags=["emails"])

_SENDABLE_STATUSES = {DraftStatus.pending, DraftStatus.approved, DraftStatus.edited}


def _reply_subject(subject: str | None) -> str:
    text = (subject or "").strip() or "(no subject)"
    if text.lower().startswith("re:"):
        return text
    return f"Re: {text}"


def _current_user_from_request(request: Request, db: Session) -> User:
    user_id = request.cookies.get("auth_user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


@router.get("/emails")
def list_emails(request: Request, db: Session = Depends(get_db)):
    user = _current_user_from_request(request, db)
    rows = (
        db.query(Email)
        .filter(Email.user_id == user.id)
        .order_by(Email.received_at.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "id": r.id,
            "sender": r.sender,
            "category": r.category,
            "priority": r.priority,
            "summary": r.summary,
            "confidence": r.confidence,
            "needs_manual_review": r.needs_manual_review,
            "received_at": r.received_at,
        }
        for r in rows
    ]


@router.get("/tasks")
def list_tasks(request: Request, db: Session = Depends(get_db)):
    user = _current_user_from_request(request, db)
    rows = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status == "open")
        .order_by(Task.deadline)
        .all()
    )
    return [{"id": r.id, "description": r.description, "deadline": r.deadline} for r in rows]


@router.post("/drafts/{draft_id}/approve")
def approve_draft(draft_id: str, request: Request, db: Session = Depends(get_db)):
    user = _current_user_from_request(request, db)
    draft = db.query(Draft).join(Email).filter(Draft.id == draft_id, Email.user_id == user.id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    draft.status = DraftStatus.approved
    db.commit()
    return {"status": "approved"}


@router.post("/drafts/{draft_id}/send")
def send_draft(draft_id: str, request: Request, db: Session = Depends(get_db)):
    """Send a pending (or approved/edited) draft via Gmail and mark it sent."""
    user = _current_user_from_request(request, db)
    draft = db.query(Draft).join(Email).filter(Draft.id == draft_id, Email.user_id == user.id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")
    if draft.status == DraftStatus.sent:
        raise HTTPException(400, "Draft already sent")
    if draft.status not in _SENDABLE_STATUSES:
        raise HTTPException(400, f"Draft cannot be sent in status '{draft.status.value}'")
    if not draft.content or not draft.content.strip():
        raise HTTPException(400, "Draft has no content to send")

    email = db.query(Email).filter(Email.id == draft.email_id).first()
    if not email:
        raise HTTPException(404, "Email not found for draft")
    if not email.sender:
        raise HTTPException(400, "Original email has no sender to reply to")

    user = db.query(User).filter(User.id == email.user_id).first()
    if not user or not user.google_refresh_token:
        raise HTTPException(401, "Google account is not connected; sign in again.")

    thread = db.query(Thread).filter(Thread.id == email.thread_id).first()
    subject = (draft.subject or "").strip() or _reply_subject(
        thread.subject if thread else None
    )

    try:
        sent = gmail_service.send(
            user,
            to=email.sender,
            subject=subject,
            body=draft.content,
            thread_id=thread.gmail_thread_id if thread else None,
            db=db,
        )
    except RefreshError as exc:
        raise HTTPException(
            401,
            "Google credentials expired; sign in again.",
        ) from exc
    except HttpError as exc:
        status = int(getattr(exc.resp, "status", 502) or 502)
        detail = getattr(exc, "reason", None) or str(exc) or "Gmail send failed."
        raise HTTPException(status_code=status, detail=detail) from exc

    now = datetime.utcnow()
    draft.gmail_message_id = sent["gmail_message_id"]
    draft.status = DraftStatus.sent
    email.sent_at = now
    email.awaiting_reply = False
    db.add(draft)
    db.add(email)
    db.commit()

    return {
        "status": "sent",
        "draft_id": draft.id,
        "gmail_message_id": draft.gmail_message_id,
        "sent_at": email.sent_at,
    }

@router.get("/drafts")
def list_drafts(request: Request, db: Session = Depends(get_db)):
    user = _current_user_from_request(request, db)

    drafts = (
        db.query(Draft)
        .join(Email)
        .filter(Email.user_id == user.id)
        .order_by(Draft.created_at.desc())
        .all()
    )

    response = []

    for draft in drafts:

        email = (
            db.query(Email)
            .filter(Email.id == draft.email_id)
            .first()
        )

        response.append({

            "id": draft.id,

            "content": draft.content,

            "confidence": draft.confidence,

            "status": draft.status,

            "created_at": draft.created_at,

            "mixed_audience": draft.mixed_audience,

            "gmail_message_id": draft.gmail_message_id,

            "email_id": draft.email_id,

            # Extra information for frontend

            "sender": email.sender if email else None,

            "summary": email.summary if email else None,

            "category": email.category if email else None,

            "priority": email.priority if email else None,

            "received_at": email.received_at if email else None,

            # use draft subject if available,
            # otherwise fall back to summary

            "subject": (
                draft.subject
                if draft.subject
                else (email.summary if email else None)
            )

        })

    return response

@router.post("/drafts/{draft_id}/edit")
def edit_draft(draft_id: str, new_text: str, request: Request, db: Session = Depends(get_db)):
    """Every edit is logged as a feedback event, scoped to the relationship type
    of the thread — this is what lets tone_profiles improve over time."""
    user = _current_user_from_request(request, db)
    draft = db.query(Draft).join(Email).filter(Draft.id == draft_id, Email.user_id == user.id).first()
    if not draft:
        raise HTTPException(404, "Draft not found")

    email = db.query(Email).filter(Email.id == draft.email_id).first()
    contact = db.query(Contact).filter(Contact.email == email.sender).first()
    relationship_type = contact.relationship_type if contact else None

    db.add(FeedbackEvent(
        user_id=email.user_id, draft_id=draft.id, relationship_type=relationship_type,
        original_text=draft.content, edited_text=new_text,
    ))
    draft.content = new_text
    draft.status = DraftStatus.edited
    db.commit()
    return {"status": "edited"}
