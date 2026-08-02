from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import SessionLocal
from app.models import Email, User
from app.services import gmail_service
from app.services.pipeline import process_new_message

FOLLOW_UP_WINDOW = timedelta(hours=48)
POLL_MAX_RESULTS = 25


def poll_unread_emails():
    """Every tick: list unread messages newer than the last successful poll per user."""
    db = SessionLocal()
    try:
        users = (
            db.query(User)
            .filter(User.google_refresh_token.isnot(None))
            .all()
        )
        for user in users:
            try:
                # Capture before the API call so messages that arrive during
                # processing are covered by the next poll window.
                poll_started_at = datetime.utcnow()
                message_ids = gmail_service.list_unread_message_ids(
                    user,
                    max_results=POLL_MAX_RESULTS,
                    db=db,
                    newer_than=user.last_gmail_poll_at,
                )
                for message_id in message_ids:
                    already_stored = (
                        db.query(Email.id)
                        .filter(Email.gmail_message_id == message_id)
                        .first()
                    )
                    if already_stored:
                        continue
                    process_new_message(db, user, message_id)
                user.last_gmail_poll_at = poll_started_at
                db.add(user)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[poll] failed for {user.email}: {e}")
    finally:
        db.close()


def check_for_follow_ups():
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - FOLLOW_UP_WINDOW
        stale = (
            db.query(Email)
            .filter(
                Email.awaiting_reply.is_(True),
                Email.received_at < cutoff,
                Email.sent_at.is_(None),
            )
            .all()
        )
        for email in stale:
            # Phase 3 will turn this into an actual nudge draft; for now, just flag it.
            print(f"[follow-up] No reply sent for email {email.id} since {email.received_at}")
    finally:
        db.close()


def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(poll_unread_emails, "interval", minutes=5, id="poll_unread")
    scheduler.add_job(check_for_follow_ups, "interval", hours=1, id="follow_ups")
    scheduler.start()
    return scheduler
