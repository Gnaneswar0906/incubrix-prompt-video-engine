"""
IncuBrix Database & Persistence Layer (SQLite / SQLAlchemy)
Stores sessions, jobs, and idempotency records with thread-safe access.
"""

from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, List, Optional
from sqlalchemy import Column, Integer, String, Text, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from service.config import get_settings

Base = declarative_base()


class SessionRecord(Base):
    __tablename__ = "sessions"

    session_id = Column(String(64), primary_key=True)
    created_at = Column(String(32), default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at = Column(String(32), default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    source_media_url = Column(String(512), nullable=True)
    source_media_local_path = Column(String(512), nullable=True)
    source_duration_ms = Column(Integer, default=0)
    transcript_json = Column(Text, nullable=True)
    timeline_json = Column(Text, nullable=True)
    history_json = Column(Text, default="[]")
    status = Column(String(32), default="ready")


class JobRecord(Base):
    __tablename__ = "jobs"

    job_id = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False)
    job_type = Column(String(32), nullable=False)  # intake | instruction | render
    status = Column(String(32), default="queued")   # queued | running | succeeded | failed
    progress = Column(Integer, default=0)           # 0 to 100
    created_at = Column(String(32), default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    updated_at = Column(String(32), default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    result_links_json = Column(Text, default="{}")
    manifest_json = Column(Text, default="{}")
    error_json = Column(Text, nullable=True)
    callback_url = Column(String(512), nullable=True)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_keys"

    idempotency_key = Column(String(128), primary_key=True)
    created_at = Column(String(32), default=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())
    status_code = Column(Integer, nullable=False)
    response_body_json = Column(Text, nullable=False)
    job_id = Column(String(64), nullable=True)


# Database Engine and Session Factory
settings = get_settings()
db_url = settings.database_url

if db_url.startswith("sqlite"):
    db_path = db_url.replace("sqlite:///", "")
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    engine = create_engine(db_url)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency generator for database sessions."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_health() -> bool:
    """Verifies database connectivity."""
    try:
        with SessionLocal() as db:
            db.execute(Base.metadata.tables["sessions"].select().limit(1))
        return True
    except Exception:
        return False
