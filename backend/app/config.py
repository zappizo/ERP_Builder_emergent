from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="AI ERP Builder Backend", alias="APP_NAME")
    api_prefix: str = Field(default="/api", alias="API_PREFIX")
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8001, alias="API_PORT")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    database_url: str = Field(
        default="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/erp_builder_emergent",
        alias="DATABASE_URL",
    )
    cors_origins_raw: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
        alias="CORS_ORIGINS",
    )

    jwt_secret_key: str = Field(default="change-me-in-env", alias="JWT_SECRET_KEY")
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=60, alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=60 * 24 * 30, alias="REFRESH_TOKEN_EXPIRE_MINUTES")
    auth_required: bool = Field(default=False, alias="AUTH_REQUIRED")
    bootstrap_admin_email: str = Field(default="admin@local.dev", alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="Admin123!", alias="BOOTSTRAP_ADMIN_PASSWORD")

    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="deepseek/deepseek-v3.2-speciale", alias="OPENROUTER_MODEL")
    openrouter_models: str = Field(default="", alias="OPENROUTER_MODELS")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1/chat/completions",
        alias="OPENROUTER_BASE_URL",
    )
    openrouter_timeout: int = Field(default=120, alias="OPENROUTER_TIMEOUT")
    openrouter_site_url: str = Field(default="http://127.0.0.1:3001", alias="OPENROUTER_SITE_URL")
    openrouter_app_name: str = Field(default="AI ERP Builder", alias="OPENROUTER_APP_NAME")
    enable_interviewer_llm: bool = Field(default=True, alias="ENABLE_INTERVIEWER_LLM")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

