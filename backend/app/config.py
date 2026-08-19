from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    gemini_api_key: str = ""
    secret_key: str
    frontend_url: str = "http://localhost:4200"
    # Set to "development" in local .env to enable OAuth over HTTP.
    # Must be "production" (or absent) on Render.
    environment: str = "production"

    # Gemini client tuning (override via env: GEMINI_MODEL, etc.)
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_seconds: float = 30.0
    gemini_max_retries: int = 3
    gemini_retry_base_delay_seconds: float = 0.5

    @field_validator("gemini_api_key", mode="before")
    @classmethod
    def _strip_api_key(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value


settings = Settings()