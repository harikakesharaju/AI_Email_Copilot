import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models import User
from app.services.gmail_service import build_gmail_client


def main() -> None:
    parser = argparse.ArgumentParser(description="List recent Gmail message IDs for the connected user")
    parser.add_argument("--email", help="Optional user email to target; defaults to the first saved user")
    parser.add_argument("--limit", type=int, default=5)
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

        service = build_gmail_client(user)
        response = service.users().messages().list(userId="me", maxResults=args.limit).execute()
        messages = response.get("messages", [])
        if not messages:
            raise RuntimeError("No messages were found in the mailbox.")

        for item in messages:
            msg = service.users().messages().get(userId="me", id=item["id"], format="metadata", metadataHeaders=["Subject", "From"]).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            print(f"{item['id']} | {headers.get('Subject', '(no subject)')} | {headers.get('From', '')}")
    finally:
        db.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}")
        raise
