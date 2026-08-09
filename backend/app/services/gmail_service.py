import base64
from datetime import datetime, timezone
from email.mime.text import MIMEText

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.models import User


def _to_unix_seconds(dt: datetime) -> int:
    """Gmail `after:` expects a Unix epoch; treat naive datetimes as UTC."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def _credentials_for(user: User) -> Credentials:
    return Credentials(
        token=user.google_access_token,
        refresh_token=user.google_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=SCOPES,
    )


def _persist_access_token(user: User, access_token: str, db: Session | None = None) -> None:
    """Keep the in-memory user and PostgreSQL row in sync after a refresh."""
    user.google_access_token = access_token
    if db is not None:
        db.add(user)
        db.commit()
        return

    session = SessionLocal()
    try:
        row = session.query(User).filter(User.id == user.id).first()
        if row:
            row.google_access_token = access_token
            session.commit()
    finally:
        session.close()


def _refresh_credentials(user: User, creds: Credentials, db: Session | None = None) -> Credentials:
    if not creds.refresh_token:
        raise RefreshError("No Google refresh token on file; user must sign in again.")
    creds.refresh(Request())
    if not creds.token:
        raise RefreshError("Google token refresh did not return an access token.")
    _persist_access_token(user, creds.token, db)
    return creds


def build_gmail_client(user: User, db: Session | None = None):
    creds = _credentials_for(user)
    # Refresh when google-auth knows the token is expired/invalid, or when we
    # only have a refresh token (e.g. access token was cleared).
    if creds.refresh_token and (not creds.valid or not creds.token or creds.expired):
        creds = _refresh_credentials(user, creds, db)
    return build("gmail", "v1", credentials=creds)


def _call_gmail(user: User, fn, db: Session | None = None):
    """Run a Gmail API call; on 401, refresh the access token once and retry."""
    service = build_gmail_client(user, db)
    try:
        return fn(service)
    except HttpError as exc:
        if getattr(exc.resp, "status", None) != 401 or not user.google_refresh_token:
            raise
        # Expiry is not stored in the DB, so a still-"valid" local credential
        # can be rejected by Google — refresh and continue without re-login.
        creds = _refresh_credentials(user, _credentials_for(user), db)
        service = build("gmail", "v1", credentials=creds)
        return fn(service)


def list_unread_message_ids(
    user: User,
    max_results: int = 25,
    db: Session | None = None,
    newer_than: datetime | None = None,
) -> list[str]:
    """Return unread INBOX message IDs (newest first).

    When ``newer_than`` is set, only messages after that time are requested
    (Gmail ``after:<unix>``), which cuts list traffic between polls.
    """
    query = "is:unread in:inbox"
    if newer_than is not None:
        query = f"{query} after:{_to_unix_seconds(newer_than)}"

    def _list(service):
        resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return [m["id"] for m in resp.get("messages", [])]

    return _call_gmail(user, _list, db)


def fetch_message(user: User, message_id: str, db: Session | None = None) -> dict:
    def _fetch(service):
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=message_id, format="full")
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body = _extract_body(msg["payload"])
        return {
            "gmail_message_id": msg["id"],
            "gmail_thread_id": msg["threadId"],
            "subject": headers.get("Subject", ""),
            "sender": headers.get("From", ""),
            "recipients": [r.strip() for r in headers.get("To", "").split(",") if r.strip()],
            "body": body,
        }

    return _call_gmail(user, _fetch, db)


def create_draft(
    user: User,
    *,
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    db: Session | None = None,
) -> dict:
    """Create a Gmail draft using the user's stored OAuth credentials."""
    mime = MIMEText(body, _charset="utf-8")
    mime["To"] = to
    mime["From"] = user.email
    mime["Subject"] = subject
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    payload: dict = {"message": {"raw": raw}}
    if thread_id:
        payload["message"]["threadId"] = thread_id

    def _create(service):
        resp = (
            service.users()
            .drafts()
            .create(userId="me", body=payload)
            .execute()
        )
        return {
            "gmail_draft_id": resp.get("id"),
            "gmail_thread_id": resp.get("message", {}).get("threadId", thread_id),
        }

    return _call_gmail(user, _create, db)


def send(
    user: User,
    *,
    to: str,
    subject: str,
    body: str,
    thread_id: str | None = None,
    in_reply_to: str | None = None,
    db: Session | None = None,
) -> dict:
    """Send an email via Gmail using the user's stored OAuth credentials.

    Returns ``{"gmail_message_id": ..., "gmail_thread_id": ...}``.
    Raises ``HttpError`` / ``RefreshError`` on Gmail failures.
    """
    mime = MIMEText(body, _charset="utf-8")
    mime["To"] = to
    mime["From"] = user.email
    mime["Subject"] = subject
    if in_reply_to:
        mime["In-Reply-To"] = in_reply_to
        mime["References"] = in_reply_to

    raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("ascii")
    payload: dict = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    def _send(service):
        resp = (
            service.users()
            .messages()
            .send(userId="me", body=payload)
            .execute()
        )
        return {
            "gmail_message_id": resp["id"],
            "gmail_thread_id": resp.get("threadId", thread_id),
        }

    return _call_gmail(user, _send, db)


def _extract_body(payload: dict) -> str:
    if payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []):
        text = _extract_body(part)
        if text:
            return text
    return ""
