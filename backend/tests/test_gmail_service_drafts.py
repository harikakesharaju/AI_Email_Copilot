import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import gmail_service


class GmailDraftTests(unittest.TestCase):
    def test_create_draft_calls_gmail_drafts_create(self):
        user = SimpleNamespace(email="user@example.com", google_refresh_token="refresh-token")
        created_payload = {}

        class FakeDrafts:
            def create(self, **kwargs):
                created_payload.update(kwargs)
                return SimpleNamespace(execute=lambda: {"id": "draft-123"})

        class FakeUsers:
            def drafts(self):
                return FakeDrafts()

        class FakeService:
            def users(self):
                return FakeUsers()

        with patch("app.services.gmail_service.build_gmail_client", return_value=FakeService()):
            result = gmail_service.create_draft(
                user,
                to="recipient@example.com",
                subject="Re: hello",
                body="Hi there",
                thread_id="thread-1",
                in_reply_to="msg-1",
            )

        self.assertEqual(result["gmail_draft_id"], "draft-123")
        self.assertEqual(created_payload["userId"], "me")
        self.assertIn("message", created_payload["body"])
        self.assertEqual(created_payload["body"]["message"]["threadId"], "thread-1")


if __name__ == "__main__":
    unittest.main()
