"""
IncuBrix Structured JSON Logging
Outputs single-line JSON with timestamp, level, job_id, and X-Correlation-Id.
"""

from __future__ import annotations

import contextvars
import datetime
import json
import logging
import sys
from typing import Any, Dict, Optional

correlation_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "correlation_id", default=None
)
job_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "job_id", default=None
)


class JsonLogFormatter(logging.Formatter):
    """
    Formats log records into single-line JSON objects conforming to Integration Standard Point 8.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": correlation_id_ctx.get() or "none",
            "job_id": job_id_ctx.get() or "none",
        }

        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_obj)


def setup_json_logging(level: int = logging.INFO) -> None:
    """Configures root logger with single-line JSON formatter."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    root_logger.addHandler(handler)


def get_logger(name: str = "incubrix") -> logging.Logger:
    return logging.getLogger(name)
