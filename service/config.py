"""
IncuBrix Service Configuration
All settings come from environment variables with sensible defaults. No hard-coded paths.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    # API & Service
    api_title: str = "IncuBrix Prompt-Based Video Editing Engine API"
    api_version: str = "1.0.0"
    api_prefix: str = "/api/v1"
    api_access_token: Optional[str] = Field(
        default_factory=lambda: os.getenv("API_ACCESS_TOKEN")
    )
    rate_limit_per_minute: int = Field(
        default_factory=lambda: int(os.getenv("RATE_LIMIT_PER_MINUTE", "120"))
    )

    # Storage Backend
    # Auto-detects 's3' if MINIO_ENDPOINT is set, otherwise 'local'
    storage_backend: str = Field(
        default_factory=lambda: os.getenv(
            "STORAGE_BACKEND",
            "s3" if os.getenv("MINIO_ENDPOINT") else "local",
        )
    )
    storage_local_dir: str = Field(
        default_factory=lambda: os.getenv("STORAGE_LOCAL_DIR", os.path.abspath("./data/storage"))
    )
    minio_endpoint: Optional[str] = Field(
        default_factory=lambda: os.getenv("MINIO_ENDPOINT")
    )
    minio_access_key: str = Field(
        default_factory=lambda: os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    )
    minio_secret_key: str = Field(
        default_factory=lambda: os.getenv("MINIO_SECRET_KEY", "minioadmin")
    )
    minio_bucket: str = Field(
        default_factory=lambda: os.getenv("MINIO_BUCKET", "incubrix-media")
    )
    minio_secure: bool = Field(
        default_factory=lambda: os.getenv("MINIO_SECURE", "false").lower() == "true"
    )

    # Queue Backend
    # Auto-detects 'redis' if REDIS_URL is set, otherwise 'inprocess'
    queue_backend: str = Field(
        default_factory=lambda: os.getenv(
            "QUEUE_BACKEND",
            "redis" if os.getenv("REDIS_URL") else "inprocess",
        )
    )
    redis_url: Optional[str] = Field(
        default_factory=lambda: os.getenv("REDIS_URL")
    )

    # Database
    database_url: str = Field(
        default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./data/incubrix.db")
    )

    # HMAC Webhooks
    webhook_secret: str = Field(
        default_factory=lambda: os.getenv("WEBHOOK_SECRET", "incubrix-shared-secret-key")
    )

    # AI Models
    whisper_model: str = Field(
        default_factory=lambda: os.getenv("WHISPER_MODEL", "small.en")
    )
    gemini_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("GEMINI_API_KEY")
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
