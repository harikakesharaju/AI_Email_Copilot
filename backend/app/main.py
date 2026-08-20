from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import Base, engine
from app.routers import auth, emails
from app.scheduler import start_scheduler
from app.config import settings
from app.services.llm.client import GeminiConfigError, configure_gemini

app = FastAPI(title="AI Email Copilot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(auth.router)
app.include_router(emails.router)


def _ensure_schema():
    """create_all does not add columns to existing tables; patch those here for local dev."""
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                "ALTER TABLE users "
                "ADD COLUMN IF NOT EXISTS last_gmail_poll_at TIMESTAMP"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE drafts "
                "ADD COLUMN IF NOT EXISTS gmail_message_id VARCHAR"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE drafts "
                "ADD COLUMN IF NOT EXISTS subject VARCHAR"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE emails "
                "ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION DEFAULT 0"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE emails "
                "ADD COLUMN IF NOT EXISTS needs_manual_review BOOLEAN DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE emails "
                "ADD COLUMN IF NOT EXISTS sent_at TIMESTAMP"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE emails "
                "ADD COLUMN IF NOT EXISTS awaiting_reply BOOLEAN DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE drafts "
                "ADD COLUMN IF NOT EXISTS mixed_audience BOOLEAN DEFAULT FALSE"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE drafts "
                "ADD COLUMN IF NOT EXISTS confidence DOUBLE PRECISION DEFAULT 0"
            )
        )
        conn.execute(
            text(
                "DO $$ BEGIN "
                "CREATE TYPE draftstatus AS ENUM "
                "('pending','approved','edited','rejected','sent'); "
                "EXCEPTION WHEN duplicate_object THEN null; END $$"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE drafts "
                "ADD COLUMN IF NOT EXISTS status draftstatus DEFAULT 'pending'"
            )
        )
        # Prevent duplicate drafts for the same email (guards against multi-worker race).
        conn.execute(
            text(
                "DO $$ BEGIN "
                "IF NOT EXISTS ("
                "  SELECT 1 FROM pg_constraint WHERE conname = 'uq_drafts_email_id'"
                ") THEN "
                "  ALTER TABLE drafts ADD CONSTRAINT uq_drafts_email_id UNIQUE (email_id); "
                "END IF; "
                "END $$"
            )
        )


@app.on_event("startup")
def on_startup():
    print("Starting AI Email Copilot...")

    _ensure_schema()

    try:
        configure_gemini()
        print("Gemini configured")
    except GeminiConfigError as e:
        print(f"Gemini configuration warning: {e}")

    start_scheduler()

    print("Startup complete.")


@app.get("/health")
def health():
    return {"status": "ok"}
