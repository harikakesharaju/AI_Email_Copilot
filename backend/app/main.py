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


@app.on_event("startup")
def on_startup():
    print("1. Startup begins")

    print("2. Creating tables...")
    Base.metadata.create_all(bind=engine)
    print("3. Tables created")

    print("4. Starting scheduler...")
    start_scheduler()
    print("5. Scheduler started")


@app.get("/health")
def health():
    return {"status": "ok"}
