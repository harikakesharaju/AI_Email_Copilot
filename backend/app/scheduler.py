import logging
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import text

from app.database import SessionLocal
from app.models import Email, User
from app.services import gmail_service
from app.services.pipeline import process_new_message

logger = logging.getLogger(__name__)

FOLLOW_UP_WINDOW = timedelta(hours=48)
POLL_MAX_RESULTS = 25
# Arbitrary stable integer key for the PostgreSQL session-level advisory lock.
# Prevents two Uvicorn/Gunicorn workers from running the poll concurrently.
_POLL_ADVISORY_LOCK_KEY = 7_380_291


def poll_unread_emails():
    """Every tick: list unread messages newer than the last successful poll per user."""
    db = SessionLocal()
    try:
        # Acquire a non-blocking advisory lock so only one worker runs per interval.
        # pg_try_advisory_lock is session-level: released automatically when db closes.
        acquired = db.execute(
            text("SELECT pg_try_advisory_lock(:key)"), {"key": _POLL_ADVISORY_LOCK_KEY}
        ).scalar()
        if not acquired:
            logger.info("[sync] another worker holds the poll lock — skipping this tick")
            return

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
                logger.info("[sync] starting poll for user=%s since=%s", user.email, user.last_gmail_poll_at)

                message_ids = gmail_service.list_unread_message_ids(
                    user,
                    max_results=POLL_MAX_RESULTS,
                    db=db,
                    newer_than=user.last_gmail_poll_at,
                )
                logger.info("[sync] found %d message(s) for user=%s", len(message_ids), user.email)

                processed = 0
                skipped = 0
                for message_id in message_ids:
                    already_stored = (
                        db.query(Email.id)
                        .filter(
                            Email.gmail_message_id == message_id,
                            Email.user_id == user.id,
                        )
                        .first()
                    )
                    if already_stored:
                        logger.debug("[sync] skipped duplicate message_id=%s user=%s", message_id, user.email)
                        skipped += 1
                        continue
                    process_new_message(db, user, message_id)
                    logger.info("[sync] processed message_id=%s user=%s", message_id, user.email)
                    processed += 1

                logger.info(
                    "[sync] finished user=%s processed=%d skipped=%d",
                    user.email, processed, skipped,
                )
                user.last_gmail_poll_at = poll_started_at
                db.add(user)
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error("[sync] failed for user=%s error=%s", user.email, e)
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
    # next_run_time=datetime.utcnow() makes the first poll fire immediately at startup
    # instead of waiting the full interval before the first check.
    scheduler.add_job(
        poll_unread_emails, "interval", minutes=5, id="poll_unread",
        next_run_time=datetime.utcnow(),
    )
    scheduler.add_job(check_for_follow_ups, "interval", hours=1, id="follow_ups")
    scheduler.start()
    print("[scheduler] started — first Gmail poll will run immediately")
    return scheduler
