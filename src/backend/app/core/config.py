from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_name: str = "MissionReady AI API"
    app_env: str = "development"
    app_port: int = 8000

    # Database
    database_url: str

    # Auth
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # CORS — comma-separated list of allowed origins
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Google OAuth (optional)
    google_client_id: str | None = None

    # IBM watsonx.ai (optional — required for copilot in Phase 11)
    watsonx_api_key: str | None = None
    watsonx_project_id: str | None = None
    watsonx_url: str = "https://us-south.ml.cloud.ibm.com"

    # Groq (optional — fallback LLM if watsonx.ai is unavailable)
    groq_api_key: str | None = None
    groq_model: str = "compound-beta"

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        # .env lives at src/.env — four levels up from this file
        env_file=Path(__file__).resolve().parents[3] / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
