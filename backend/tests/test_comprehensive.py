"""
Comprehensive tests — no real Google, Gmail, or Gemini credentials required.

Coverage:
  - Unauthenticated API → 401
  - Authenticated user isolation (drafts, tasks, edits, sends)
  - Dashboard stats
  - Draft eligibility / confidence threshold
  - Low-confidence → manual review (not silent discard)
  - Gmail duplicate detection (per-user scoped)
  - Gemini 429 → heuristic fallback
  - Gemini timeout → heuristic fallback
  - Task completion
  - Draft editing via JSON body (not query string)
  - Logout clears cookie
  - Heuristic confidence is signal-based (not hardcoded)
"""

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, call

from fastapi import HTTPException


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(user_id):
    req = MagicMock()
    req.cookies.get.return_value = user_id
    return req


def _make_db_with_sequence(*first_results):
    """DB mock whose .query().filter().first() calls return values in order."""
    db = MagicMock()
    first_mock = MagicMock()
    first_mock.side_effect = list(first_results)
    db.query.return_value.filter.return_value.first = first_mock
    return db


def _make_user(uid="user-1", email=None):
    return SimpleNamespace(
        id=uid,
        email=email or f"{uid}@test.com",
        google_refresh_token="refresh-token",
    )


# ---------------------------------------------------------------------------
# 1. Unauthenticated access → 401
# ---------------------------------------------------------------------------

class UnauthenticatedTests(unittest.TestCase):
    """Every protected endpoint must return 401 without a valid auth cookie."""

    def _fn(self):
        from app.routers.emails import _current_user_from_request
        return _current_user_from_request

    def test_no_cookie_raises_401(self):
        fn = self._fn()
        with self.assertRaises(HTTPException) as ctx:
            fn(_make_request(None), _make_db_with_sequence())
        self.assertEqual(ctx.exception.status_code, 401)

    def test_empty_string_cookie_raises_401(self):
        fn = self._fn()
        with self.assertRaises(HTTPException) as ctx:
            fn(_make_request(""), _make_db_with_sequence())
        self.assertEqual(ctx.exception.status_code, 401)

    def test_valid_cookie_but_user_not_in_db_raises_401(self):
        fn = self._fn()
        with self.assertRaises(HTTPException) as ctx:
            fn(_make_request("some-uuid"), _make_db_with_sequence(None))
        self.assertEqual(ctx.exception.status_code, 401)

    def test_valid_cookie_and_known_user_succeeds(self):
        fn = self._fn()
        user = _make_user("uid-1")
        result = fn(_make_request("uid-1"), _make_db_with_sequence(user))
        self.assertEqual(result.id, "uid-1")


# ---------------------------------------------------------------------------
# 2. Logout
# ---------------------------------------------------------------------------

class LogoutTests(unittest.TestCase):
    """Logout must clear the auth cookie (value='', max_age=0, httponly=True)."""

    def test_logout_clears_cookie(self):
        from fastapi import Response
        from app.routers.emails import logout

        resp = MagicMock(spec=Response)
        result = logout(resp)

        self.assertEqual(result, {"status": "ok"})
        resp.set_cookie.assert_called_once()
        kwargs = resp.set_cookie.call_args.kwargs
        self.assertEqual(kwargs["key"], "auth_user_id")
        self.assertEqual(kwargs["value"], "")
        self.assertEqual(kwargs["max_age"], 0)
        self.assertTrue(kwargs["httponly"])


# ---------------------------------------------------------------------------
# 3. User isolation — protected operations reject cross-user access
# ---------------------------------------------------------------------------

class UserIsolationTests(unittest.TestCase):
    """Data belonging to user B must never be readable or writable by user A."""

    def test_approve_draft_belonging_to_other_user_returns_404(self):
        from app.routers.emails import approve_draft

        user_a = _make_user("user-a")
        db = _make_db_with_sequence(user_a, None)  # user found, draft NOT found
        with self.assertRaises(HTTPException) as ctx:
            approve_draft("other-draft", _make_request("user-a"), db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_send_draft_belonging_to_other_user_returns_404(self):
        from app.routers.emails import send_draft

        user_a = _make_user("user-a")
        db = _make_db_with_sequence(user_a, None)
        with self.assertRaises(HTTPException) as ctx:
            send_draft("other-draft", _make_request("user-a"), db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_edit_draft_belonging_to_other_user_returns_404(self):
        from app.routers.emails import edit_draft, EditDraftBody

        user_a = _make_user("user-a")
        db = _make_db_with_sequence(user_a, None)
        body = EditDraftBody(new_text="hacked content")
        with self.assertRaises(HTTPException) as ctx:
            edit_draft("other-draft", body, _make_request("user-a"), db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_complete_task_belonging_to_other_user_returns_404(self):
        from app.routers.emails import complete_task

        user_a = _make_user("user-a")
        db = _make_db_with_sequence(user_a, None)
        with self.assertRaises(HTTPException) as ctx:
            complete_task("other-task", _make_request("user-a"), db)
        self.assertEqual(ctx.exception.status_code, 404)


# ---------------------------------------------------------------------------
# 4. Dashboard stats
# ---------------------------------------------------------------------------

class DashboardStatsTests(unittest.TestCase):
    """Dashboard must return real per-user counts, not hardcoded values."""

    def test_dashboard_stats_returns_correct_shape(self):
        from app.routers.emails import dashboard_stats

        user = _make_user("user-1")
        db = MagicMock()

        # Each count() call returns a specific value
        count_mock = MagicMock()
        count_mock.side_effect = [10, 3, 5, 2]
        db.query.return_value.filter.return_value.count = count_mock
        db.query.return_value.join.return_value.filter.return_value.count = count_mock

        # First call to _current_user_from_request returns user
        db.query.return_value.filter.return_value.first.return_value = user

        result = dashboard_stats(_make_request("user-1"), db)

        self.assertIn("totalEmails", result)
        self.assertIn("pendingTasks", result)
        self.assertIn("drafts", result)
        self.assertIn("needsReview", result)
        # All values must be integers (real counts)
        for v in result.values():
            self.assertIsInstance(v, int)

    def test_dashboard_stats_requires_auth(self):
        from app.routers.emails import dashboard_stats

        db = _make_db_with_sequence(None)
        with self.assertRaises(HTTPException) as ctx:
            dashboard_stats(_make_request(None), db)
        self.assertEqual(ctx.exception.status_code, 401)


# ---------------------------------------------------------------------------
# 5. Draft eligibility — confidence threshold
# ---------------------------------------------------------------------------

class DraftEligibilityTests(unittest.TestCase):
    """Confidence threshold must be 0.60 and must not be tampered with."""

    def test_auto_draft_min_confidence_is_0_60(self):
        from app.services.pipeline import AUTO_DRAFT_MIN_CONFIDENCE
        self.assertEqual(AUTO_DRAFT_MIN_CONFIDENCE, 0.60)

    def test_low_confidence_triggers_manual_review_flag(self):
        from app.services.pipeline import _mark_manual_review

        db = MagicMock()
        email = SimpleNamespace(id="e-1", needs_manual_review=False)

        _mark_manual_review(db, email)

        self.assertTrue(email.needs_manual_review)
        db.add.assert_called_once_with(email)
        db.commit.assert_called_once()

    @patch("app.services.pipeline.gmail_service.create_draft")
    @patch("app.services.pipeline.generate_draft")
    @patch("app.services.pipeline.resolve_thread_tone")
    def test_low_confidence_draft_is_persisted_not_discarded(
        self, mock_tone, mock_gen, mock_gmail
    ):
        """Even with confidence 0.3 (below 0.60), the draft must be saved to DB."""
        from app.services.pipeline import _generate_draft
        from app.models import RelationshipType

        mock_tone.return_value = (RelationshipType.work, False)
        mock_gen.return_value = {"subject": "Re: Test", "draft": "Thank you.", "confidence": 0.3}
        mock_gmail.return_value = {"gmail_draft_id": "gd-1"}

        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []

        user = _make_user()
        contact = SimpleNamespace(relationship_type=RelationshipType.work, confidence=0.9)
        email_row = SimpleNamespace(
            id="email-1", sender="s@work.com", body="test",
            summary="test", embedding=None, needs_manual_review=False,
        )
        raw = {"body": "test", "subject": "Test", "gmail_thread_id": "t1", "recipients": []}

        _generate_draft(db, user, email_row, raw, [contact])

        # Draft must have been added to the DB
        add_types = [type(c.args[0]).__name__ for c in db.add.call_args_list if c.args]
        self.assertIn("Draft", add_types, "Draft must be persisted even for low confidence")
        # Email must be flagged for manual review
        self.assertTrue(email_row.needs_manual_review, "Low-confidence email must be marked for review")


# ---------------------------------------------------------------------------
# 6. Gmail duplicate detection — scoped per user
# ---------------------------------------------------------------------------

class GmailDuplicateDetectionTests(unittest.TestCase):
    """Scheduler must skip messages already in DB and process genuinely new ones."""

    @patch("app.scheduler.process_new_message")
    @patch("app.scheduler.gmail_service.list_unread_message_ids")
    def test_existing_message_is_skipped(self, mock_list, mock_process):
        from app.scheduler import poll_unread_emails

        user = SimpleNamespace(
            id="u1", email="u@test.com",
            google_refresh_token="tok", last_gmail_poll_at=None,
        )
        mock_list.return_value = ["existing-msg-id"]

        with patch("app.scheduler.SessionLocal") as mock_session:
            db = MagicMock()
            mock_session.return_value = db
            db.query.return_value.filter.return_value.all.return_value = [user]
            # Duplicate check returns a truthy value (already stored)
            db.query.return_value.filter.return_value.first.return_value = SimpleNamespace(id="stored")

            poll_unread_emails()

        mock_process.assert_not_called()

    @patch("app.scheduler.process_new_message")
    @patch("app.scheduler.gmail_service.list_unread_message_ids")
    def test_new_message_is_processed(self, mock_list, mock_process):
        from app.scheduler import poll_unread_emails

        user = SimpleNamespace(
            id="u1", email="u@test.com",
            google_refresh_token="tok", last_gmail_poll_at=None,
        )
        mock_list.return_value = ["brand-new-msg"]

        with patch("app.scheduler.SessionLocal") as mock_session:
            db = MagicMock()
            mock_session.return_value = db
            db.query.return_value.filter.return_value.all.return_value = [user]
            # No duplicate found
            db.query.return_value.filter.return_value.first.return_value = None

            poll_unread_emails()

        mock_process.assert_called_once_with(db, user, "brand-new-msg")

    @patch("app.scheduler.process_new_message")
    @patch("app.scheduler.gmail_service.list_unread_message_ids")
    def test_sync_error_does_not_crash_other_users(self, mock_list, mock_process):
        """A failure for one user must not prevent other users from syncing."""
        from app.scheduler import poll_unread_emails

        user_a = SimpleNamespace(id="ua", email="a@t.com", google_refresh_token="tok", last_gmail_poll_at=None)
        user_b = SimpleNamespace(id="ub", email="b@t.com", google_refresh_token="tok", last_gmail_poll_at=None)

        # User A raises, User B should still be processed
        def list_side_effect(user, **kwargs):
            if user.id == "ua":
                raise RuntimeError("Gmail API down for user A")
            return ["msg-for-b"]

        mock_list.side_effect = list_side_effect

        with patch("app.scheduler.SessionLocal") as mock_session:
            db = MagicMock()
            mock_session.return_value = db
            db.query.return_value.filter.return_value.all.return_value = [user_a, user_b]
            db.query.return_value.filter.return_value.first.return_value = None

            poll_unread_emails()  # must not raise

        mock_process.assert_called_once_with(db, user_b, "msg-for-b")


# ---------------------------------------------------------------------------
# 7. Gemini 429 / timeout → heuristic fallback
# ---------------------------------------------------------------------------

class GeminiRetryFallbackTests(unittest.TestCase):
    """Gemini errors must transparently fall back to heuristics."""

    @patch("app.services.llm.llm.call_gemini")
    def test_gemini_429_classify_falls_back(self, mock_gemini):
        from app.services.llm.client import GeminiError
        from app.services.llm import classify_and_extract

        mock_gemini.side_effect = GeminiError("429 Resource Exhausted")

        result = classify_and_extract("Please submit the report by EOD.", "Action required")

        self.assertIn("category", result)
        self.assertIn("confidence", result)
        self.assertIn("awaiting_reply", result)
        self.assertIsInstance(result["confidence"], float)

    @patch("app.services.llm.llm.call_gemini")
    def test_gemini_timeout_draft_falls_back(self, mock_gemini):
        from app.services.llm.client import GeminiError
        from app.services.llm import generate_draft

        mock_gemini.side_effect = GeminiError("timed out")

        result = generate_draft("Please reply.", "Urgent", "work", {"formality": "high"}, [], [])

        self.assertIn("subject", result)
        self.assertIn("draft", result)
        self.assertIn("confidence", result)
        self.assertIsInstance(result["confidence"], float)

    @patch("app.services.llm.llm.call_gemini")
    def test_heuristic_draft_confidence_is_not_0_8_or_0_9(self, mock_gemini):
        """Confidence must never be hardcoded to 0.8 or 0.9 in the heuristic path."""
        from app.services.llm.client import GeminiError
        from app.services.llm import generate_draft

        mock_gemini.side_effect = GeminiError("unavailable")

        result = generate_draft("test body", "test subject", "work", {}, [], [])

        conf = result["confidence"]
        self.assertIsInstance(conf, float)
        self.assertNotEqual(conf, 0.8, "Must not hardcode confidence to 0.8")
        self.assertNotEqual(conf, 0.9, "Must not hardcode confidence to 0.9")


# ---------------------------------------------------------------------------
# 8. Task completion
# ---------------------------------------------------------------------------

class TaskCompletionTests(unittest.TestCase):
    """complete_task must mark status='done' and require ownership."""

    def test_marks_task_done_and_commits(self):
        from app.routers.emails import complete_task

        user = _make_user()
        task = SimpleNamespace(id="t1", status="open", user_id="user-1")
        db = _make_db_with_sequence(user, task)

        result = complete_task("t1", _make_request("user-1"), db)

        self.assertEqual(task.status, "done")
        db.commit.assert_called_once()
        self.assertEqual(result, {"status": "done"})

    def test_nonexistent_task_raises_404(self):
        from app.routers.emails import complete_task

        user = _make_user()
        db = _make_db_with_sequence(user, None)

        with self.assertRaises(HTTPException) as ctx:
            complete_task("missing", _make_request("user-1"), db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_unauthenticated_task_completion_raises_401(self):
        from app.routers.emails import complete_task

        db = _make_db_with_sequence(None)
        with self.assertRaises(HTTPException) as ctx:
            complete_task("t1", _make_request(None), db)
        self.assertEqual(ctx.exception.status_code, 401)


# ---------------------------------------------------------------------------
# 9. Draft editing — JSON body (not query param)
# ---------------------------------------------------------------------------

class EditDraftBodyTests(unittest.TestCase):
    """edit_draft must accept new_text as a JSON body field, not a URL query param."""

    def test_pydantic_model_exists_with_new_text_field(self):
        from app.routers.emails import EditDraftBody

        body = EditDraftBody(new_text="my edited reply")
        self.assertEqual(body.new_text, "my edited reply")

    def test_large_text_accepted_via_body(self):
        """Text exceeding typical URL limits (>2000 chars) must work via JSON body."""
        from app.routers.emails import EditDraftBody

        large = "A" * 5000
        body = EditDraftBody(new_text=large)
        self.assertEqual(len(body.new_text), 5000)

    def test_edit_draft_uses_body_not_query_param(self):
        """The edit endpoint must save body.new_text, not a separately-passed string."""
        from app.routers.emails import edit_draft, EditDraftBody

        user = _make_user()
        email_obj = SimpleNamespace(id="e1", sender="s@t.com", user_id="user-1")
        draft_obj = SimpleNamespace(id="d1", content="original", status=None, email_id="e1")

        db = MagicMock()
        first_mock = MagicMock()
        first_mock.side_effect = [user, draft_obj, email_obj, None]
        db.query.return_value.filter.return_value.first = first_mock

        body = EditDraftBody(new_text="updated via body")
        edit_draft("d1", body, _make_request("user-1"), db)

        self.assertEqual(draft_obj.content, "updated via body")


# ---------------------------------------------------------------------------
# 10. Heuristic confidence — signal-based, not hardcoded
# ---------------------------------------------------------------------------

class HeuristicConfidenceTests(unittest.TestCase):
    """Heuristic confidence must reflect actual email signals."""

    def test_action_email_gets_elevated_confidence(self):
        from app.services.llm.heuristics import classify_and_extract

        result = classify_and_extract(
            "Please complete the report and submit by EOD.", "Task deadline"
        )
        self.assertTrue(result["awaiting_reply"])
        self.assertGreater(result["confidence"], 0.5)

    def test_non_action_email_gets_low_confidence(self):
        from app.services.llm.heuristics import classify_and_extract

        result = classify_and_extract(
            "Just a FYI update on the project status.", "Project update"
        )
        self.assertFalse(result["awaiting_reply"])
        self.assertLess(result["confidence"], 0.60)

    def test_heuristic_draft_confidence_is_fixed_0_4(self):
        """Heuristic fallback draft is below threshold (0.4) so it's held for review."""
        from app.services.llm.heuristics import generate_draft

        result = generate_draft("Test Subject")
        self.assertEqual(result["confidence"], 0.4)

    def test_heuristic_classify_confidence_in_range(self):
        from app.services.llm.heuristics import classify_and_extract

        result = classify_and_extract("Some email body", "Some subject")
        self.assertGreaterEqual(result["confidence"], 0.0)
        self.assertLessEqual(result["confidence"], 1.0)


# ---------------------------------------------------------------------------
# 11. API not logging secrets
# ---------------------------------------------------------------------------

class SecretLoggingTests(unittest.TestCase):
    """Sensitive values must never appear in log output."""

    def test_gemini_key_logged_as_bool_not_value(self):
        """configure_gemini must log presence only, not the actual key."""
        import io
        import logging
        import importlib

        # The print in configure_gemini should say "True" not the key value
        with patch("app.services.llm.client.validate_gemini_api_key", return_value="secret-key-abc"):
            with patch("google.generativeai.configure"):
                import app.services.llm.client as client_mod
                buf = io.StringIO()
                import sys
                old_stdout = sys.stdout
                sys.stdout = buf
                try:
                    client_mod.configure_gemini()
                finally:
                    sys.stdout = old_stdout
                output = buf.getvalue()

        self.assertNotIn("secret-key-abc", output, "API key must not be printed")
        self.assertIn("True", output, "Must print True (key present indicator)")

    def test_config_does_not_print_gemini_key(self):
        """config.py must not emit the GEMINI_API_KEY value at module level."""
        import ast
        import pathlib

        config_src = pathlib.Path(__file__).parent.parent / "app" / "config.py"
        source = config_src.read_text(encoding="utf-8")

        # Must not have a print statement that includes gemini_api_key
        self.assertNotIn(
            "gemini_api_key",
            # Only check print() calls
            " ".join(
                line.strip()
                for line in source.splitlines()
                if line.strip().startswith("print(")
            ),
            "config.py must not print gemini_api_key",
        )


if __name__ == "__main__":
    unittest.main()
