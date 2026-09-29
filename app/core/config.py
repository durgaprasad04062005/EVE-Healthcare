"""
Application configuration.

Reads from environment variables (and optionally a .env file).
All settings are typed and validated by Pydantic.
Import `settings` wherever config values are needed — do not call
os.getenv() anywhere else in the codebase.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ----- Database -----
    DATABASE_URL: str

    # ----- JWT -----
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ----- App -----
    APP_ENV: str = "development"

    # Tell pydantic-settings to look for a .env file in the project root.
    # The file is optional so the app still works when env vars are injected
    # directly (e.g. Docker, CI).
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


# Single shared instance — import this everywhere.
settings = Settings()
