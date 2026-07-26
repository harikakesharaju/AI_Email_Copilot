import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User
from app.services.pipeline import process_new_message


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Gmail-to-pipeline sync for one message")
    parser.add_argument("message_id", help="A Gmail message ID to process")
    parser.add_argument("--email", help="Optional user email to target; defaults to the first saved user")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(User)
        if args.email:
            query = query.filter(User.email == args.email)
        user = query.first()
        if not user:
            raise RuntimeError("No user found in the database. Complete the Google login flow first.")
        if not user.google_access_token:
            raise RuntimeError("The selected user does not have a Google access token yet.")

        print(f"Processing message {args.message_id} for {user.email}")
        email_row = process_new_message(db, user, args.message_id)
        print(f"Completed: email_id={email_row.id} thread_id={email_row.thread_id}")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
