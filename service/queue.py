"""
IncuBrix Background Job Queue Layer
Supports In-Process ThreadPool (Single-Container / Cloud) or Redis/RQ (Distributed)
"""

from __future__ import annotations

import concurrent.futures
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
from service.config import get_settings

logger = logging.getLogger("incubrix.queue")


class JobQueue(ABC):
    """Abstract interface for background task submission."""

    @abstractmethod
    def enqueue(self, func: Callable, *args, **kwargs) -> Any:
        """Submits a callable to the background queue."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Verifies queue broker connectivity."""
        pass


class InProcessJobQueue(JobQueue):
    """
    Built-in ThreadPoolExecutor job queue.
    Zero external dependencies; runs within the single container on Cloud/CI.
    """

    def __init__(self, max_workers: int = 4):
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)

    def enqueue(self, func: Callable, *args, **kwargs) -> Any:
        logger.info(f"Submitting background job to InProcessJobQueue: {func.__name__}")
        return self.executor.submit(func, *args, **kwargs)

    def is_healthy(self) -> bool:
        return not self.executor._shutdown


class RedisJobQueue(JobQueue):
    """
    Distributed Redis / RQ job queue for multi-container Docker Compose deployments.
    """

    def __init__(self, redis_url: Optional[str] = None):
        import redis
        from rq import Queue

        settings = get_settings()
        url = redis_url or settings.redis_url or "redis://localhost:6379/0"
        self.conn = redis.from_url(url)
        self.queue = Queue(connection=self.conn)

    def enqueue(self, func: Callable, *args, **kwargs) -> Any:
        logger.info(f"Enqueuing job to Redis queue: {func.__name__}")
        return self.queue.enqueue(func, *args, **kwargs)

    def is_healthy(self) -> bool:
        try:
            return bool(self.conn.ping())
        except Exception as e:
            logger.error(f"RedisQueue health check failed: {e}")
            return False


_queue_singleton: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Singleton factory returning appropriate queue backend."""
    global _queue_singleton
    if _queue_singleton is None:
        settings = get_settings()
        if settings.queue_backend == "redis" and settings.redis_url:
            try:
                _queue_singleton = RedisJobQueue()
            except Exception as e:
                logger.warning(f"Redis queue connection failed ({e}); falling back to InProcessJobQueue.")
                _queue_singleton = InProcessJobQueue()
        else:
            _queue_singleton = InProcessJobQueue()
    return _queue_singleton
