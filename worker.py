"""
IncuBrix Background Worker
Listens to Redis queue (when QUEUE_BACKEND=redis) or runs in standalone mode.
Conforms to Integration Standard Points 4, 6, and 9.
"""

from __future__ import annotations

import logging
import os
import sys
import time

from service.config import get_settings
from service.logging import setup_json_logging

setup_json_logging()
logger = logging.getLogger("incubrix.worker")


def main():
    settings = get_settings()
    logger.info(f"Starting IncuBrix Worker with backend='{settings.queue_backend}'")

    if settings.queue_backend == "redis" and settings.redis_url:
        try:
            import redis
            from rq import Connection, Queue, Worker

            conn = redis.from_url(settings.redis_url)
            with Connection(conn):
                queues = [Queue("default")]
                worker = Worker(queues)
                logger.info("RQ Worker listening on 'default' queue...")
                worker.work()
        except Exception as e:
            logger.exception(f"RQ Worker failed: {e}")
            sys.exit(1)
    else:
        logger.info("InProcess/Standalone mode: Background jobs are processed directly via ThreadPoolExecutor.")
        logger.info("Worker process idling in standby mode...")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            logger.info("Worker shut down gracefully.")


if __name__ == "__main__":
    main()
