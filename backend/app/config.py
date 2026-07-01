from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    app_access_token: str = "dev-token"
    backend_cors_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+psycopg://factcheck:factcheck@localhost:5432/factcheck"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    storage_backend: Literal["local", "s3"] = "local"
    local_storage_root: str = "./data"
    s3_endpoint_url: str | None = None
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    s3_bucket: str | None = None
    s3_region: str = "auto"

    llm_provider: Literal["mock", "openai_compatible"] = "mock"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"

    retrieval_top_k: int = Field(default=12, ge=1, le=50)
    evidence_top_n: int = Field(default=5, ge=1, le=20)
    embedding_dimensions: int = 384
    openalex_api_key: str | None = None
    openalex_email: str | None = None
    openalex_per_claim_limit: int = Field(default=5, ge=1, le=10)
    openalex_timeout_seconds: float = Field(default=12, gt=0, le=60)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
