import unittest
from types import SimpleNamespace

from app.routers import auth
from app.services.gmail_service import SCOPES


class DummyFlow:
    def __init__(self, exc=None):
        self.exc = exc
        self.fetch_calls = []

    def fetch_token(self, **kwargs):
        self.fetch_calls.append(kwargs)
        if self.exc:
            raise self.exc

    @property
    def credentials(self):
        return SimpleNamespace(token="abc123")


class AuthCallbackTests(unittest.TestCase):
    def test_frontend_redirect_uses_dashboard_path(self):
        response = auth._build_frontend_redirect_response()

        self.assertEqual(response.status_code, 302)
        location = response.headers["location"]
        # Must redirect to /dashboard (not /login or any other route)
        self.assertTrue(location.endswith("/dashboard"), f"Expected /dashboard, got: {location}")
        self.assertNotIn("/login", location)

    def test_scopes_are_canonical(self):
        self.assertEqual(
            SCOPES,
            [
                "openid",
                "https://www.googleapis.com/auth/userinfo.email",
                "https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.send",
            ],
        )

    def test_fetch_credentials_uses_code_and_request_url(self):
        flow = DummyFlow()
        request = SimpleNamespace(
            url="http://localhost:8000/auth/google/callback?code=test-code&state=test-state"
        )

        creds = auth._fetch_credentials_from_code(flow, request, "test-code")

        self.assertEqual(creds.token, "abc123")
        self.assertEqual(
            flow.fetch_calls,
            [
                {
                    "code": "test-code",
                    "authorization_response": "http://localhost:8000/auth/google/callback?code=test-code&state=test-state",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
