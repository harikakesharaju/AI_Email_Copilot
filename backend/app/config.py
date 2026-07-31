from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    google_client_id: str
    google_client_secret: str
    google_redirect_uri: str
    gemini_api_key: str = ""
    secret_key: str
    frontend_url: str = "http://localhost:3000"

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


print("Current working directory:", os.getcwd())
print("Does .env exist here?", Path(".env").resolve())
print("Env file exists:", Path(".env").exists())

settings = Settings()

print("Loaded GEMINI_API_KEY =", settings.gemini_api_key)