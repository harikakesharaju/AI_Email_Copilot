import os

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi import Response
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
from sqlalchemy.orm import Session

os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

from app.config import settings
from app.database import get_db
from app.models import User
from app.services.gmail_service import SCOPES

router = APIRouter(prefix="/auth/google", tags=["auth"])

CLIENT_CONFIG = {
    "web": {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": [settings.google_redirect_uri],
    }
}


class OAuthExchangeError(Exception):
    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _fetch_credentials_from_code(flow: Flow, request: Request, code: str | None):
    authorization_response = str(request.url)

    try:
        if code:
            flow.fetch_token(code=code, authorization_response=authorization_response)
        else:
            flow.fetch_token(authorization_response=authorization_response)
    except InvalidGrantError:
        raise
    except Exception as exc:
        raise OAuthExchangeError(str(exc)) from exc

    creds = getattr(flow, "credentials", None)
    if creds is None or not getattr(creds, "token", None):
        raise OAuthExchangeError("Google did not return an access token for the callback exchange.")

    return creds


def _build_frontend_redirect_response() -> RedirectResponse:
    frontend_base_url = settings.frontend_url
    if frontend_base_url.startswith("http://localhost") or frontend_base_url.startswith("http://127.0.0.1"):
        frontend_base_url = "https://ai-email-copilot-green.vercel.app"
    return RedirectResponse(url=f"{frontend_base_url.rstrip('/')}/dashboard", status_code=302)


@router.get("/login")
def login():
    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES,
                                    redirect_uri=settings.google_redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        prompt="consent",
    )
    return RedirectResponse(auth_url)


@router.get("/callback")
def callback(request: Request, response: Response, code: str | None = None, state: str | None = None, db: Session = Depends(get_db)):
    if not code:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "The Google callback did not include an authorization code.",
            },
        )

    flow = Flow.from_client_config(CLIENT_CONFIG, scopes=SCOPES,
                                    redirect_uri=settings.google_redirect_uri)

    try:
        creds = _fetch_credentials_from_code(flow, request, code)
    except InvalidGrantError as exc:
        return JSONResponse(
            status_code=400,
            content={
                "detail": "Google OAuth token exchange failed. This usually means the redirect URI in Google Cloud Console does not exactly match the one in your .env file, or the authorization code expired.",
                "error": str(exc),
            },
        )
    except OAuthExchangeError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "detail": exc.message,
            },
        )
    except Exception as exc:
        message = str(exc)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "OAuth callback failed unexpectedly.",
                "error_type": type(exc).__name__,
                "error": message,
            },
        )

    # Get the user's email address from the ID token if available, otherwise use Google userinfo.
    import google.oauth2.id_token
    import google.auth.transport.requests
    from googleapiclient.discovery import build

    request = google.auth.transport.requests.Request()
    email = None

    if creds.id_token:
        try:
            id_info = google.oauth2.id_token.verify_oauth2_token(
                creds.id_token,
                request,
                settings.google_client_id,
            )
            email = id_info.get("email")
        except Exception:
            email = None

    if not email and creds.token:
        try:
            userinfo_service = build("oauth2", "v2", credentials=creds)
            userinfo = userinfo_service.userinfo().get().execute()
            email = userinfo.get("email")
        except Exception:
            email = None

    if not email:
        return JSONResponse(
            status_code=400,
            content={"detail": "Could not determine the Google account email from the OAuth response."},
        )

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email)

    user.google_access_token = creds.token
    user.google_refresh_token = creds.refresh_token or user.google_refresh_token
    db.add(user)
    db.commit()
    db.refresh(user)

    response.set_cookie(
        key="auth_user_id",
        value=str(user.id),
        httponly=True,
        samesite="none",
        secure=True,
        max_age=60 * 60 * 24 * 7,
    )

    redirect_response = _build_frontend_redirect_response()
    redirect_response.set_cookie(
        key="auth_user_id",
        value=str(user.id),
        httponly=True,
        samesite="none",
        secure=True,
        max_age=60 * 60 * 24 * 7,
    )
    return redirect_response
