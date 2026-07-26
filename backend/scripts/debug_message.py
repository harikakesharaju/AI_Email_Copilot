import argparse
import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User
from app.services import gmail_service
from app.services.llm import classify_and_extract


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug Gmail message classification")
    parser.add_argument("message_id", help="A Gmail message ID to inspect")
    parser.add_argument("--email", help="Optional user email to target; defaults to the first saved user")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            raise RuntimeError("No user found in the database. Complete the Google login flow first.")

        if args.email:
            user = next((u for u in users if u.email == args.email), None)
            if not user:
                available = ", ".join(u.email for u in users if u.email)
                raise RuntimeError(f"No user found for email '{args.email}'. Available users: {available}")
        else:
            user = users[0]

        if not user.google_access_token:
            raise RuntimeError("The selected user does not have a Google access token yet.")

        print(f"Fetching message {args.message_id} for {user.email}...")
        raw = gmail_service.fetch_message(user, args.message_id)
        
        print("\n=== MESSAGE CONTENT ===")
        print(f"Subject: {raw['subject']}")
        print(f"From: {raw['sender']}")
        print(f"Body:\n{raw['body']}")
        
        print("\n=== LLM CLASSIFICATION ===")
        analysis = classify_and_extract(raw["body"], raw["subject"])
        print(json.dumps(analysis, indent=2))
        
        print("\n=== EXTRACTED VALUES ===")
        print(f"category: {analysis.get('category')}")
        print(f"priority: {analysis.get('priority')}")
        print(f"awaiting_reply: {analysis.get('awaiting_reply')}")
        print(f"tasks count: {len(analysis.get('tasks', []))}")
        print(f"tasks: {analysis.get('tasks', [])}")
        
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
