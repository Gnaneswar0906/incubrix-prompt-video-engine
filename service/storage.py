"""
IncuBrix Storage Layer
Dual Backend: S3/MinIO (Boto3) or Local File Storage (Single-Container / Cloud)
"""

from __future__ import annotations

import logging
import os
import shutil
import uuid
from abc import ABC, abstractmethod
from typing import Optional
from service.config import get_settings

logger = logging.getLogger("incubrix.storage")


class StorageClient(ABC):
    """Abstract interface for storing and retrieving media assets."""

    @abstractmethod
    def upload_file(self, local_path: str, destination_name: str) -> str:
        """Uploads a local file and returns its public or download URL."""
        pass

    @abstractmethod
    def download_file(self, identifier: str, local_destination: str) -> str:
        """Downloads a file to local_destination path and returns local path."""
        pass

    @abstractmethod
    def get_file_path(self, file_id: str) -> Optional[str]:
        """Returns direct filesystem path if available locally."""
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """Verifies storage connectivity and write permissions."""
        pass


class LocalStorageClient(StorageClient):
    """
    Local filesystem storage. Serves files under /api/v1/files/{file_id}.
    Ideal for single-container cloud deployments (Hugging Face Spaces, Render).
    """

    def __init__(self, base_dir: Optional[str] = None):
        settings = get_settings()
        self.base_dir = os.path.abspath(base_dir or settings.storage_local_dir)
        os.makedirs(self.base_dir, exist_ok=True)

    def upload_file(self, local_path: str, destination_name: str) -> str:
        ext = os.path.splitext(destination_name)[1]
        file_id = f"{uuid.uuid4().hex[:12]}_{os.path.basename(destination_name)}"
        target_path = os.path.join(self.base_dir, file_id)

        if os.path.abspath(local_path) != os.path.abspath(target_path):
            shutil.copy2(local_path, target_path)

        settings = get_settings()
        return f"{settings.api_prefix}/files/{file_id}"

    def download_file(self, identifier: str, local_destination: str) -> str:
        file_id = os.path.basename(identifier)
        src = os.path.join(self.base_dir, file_id)
        if not os.path.exists(src):
            raise FileNotFoundError(f"Local storage file not found: {file_id}")

        os.makedirs(os.path.dirname(os.path.abspath(local_destination)), exist_ok=True)
        shutil.copy2(src, local_destination)
        return local_destination

    def get_file_path(self, file_id: str) -> Optional[str]:
        cleaned_id = os.path.basename(file_id)
        path = os.path.join(self.base_dir, cleaned_id)
        return path if os.path.exists(path) else None

    def is_healthy(self) -> bool:
        try:
            test_file = os.path.join(self.base_dir, ".health_check")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return True
        except Exception as e:
            logger.error(f"LocalStorage health check failed: {e}")
            return False


class S3StorageClient(StorageClient):
    """
    S3-compatible storage client using Boto3 (MinIO, AWS S3).
    Auto-creates destination bucket on initialization if missing.
    """

    def __init__(self):
        import boto3
        from botocore.client import Config

        settings = get_settings()
        self.bucket = settings.minio_bucket

        endpoint_url = settings.minio_endpoint
        if endpoint_url and not endpoint_url.startswith("http"):
            protocol = "https" if settings.minio_secure else "http"
            endpoint_url = f"{protocol}://{endpoint_url}"

        self.s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        try:
            self.s3.head_bucket(Bucket=self.bucket)
        except Exception:
            try:
                self.s3.create_bucket(Bucket=self.bucket)
                logger.info(f"Created S3 bucket: {self.bucket}")
            except Exception as e:
                logger.warning(f"Could not auto-create S3 bucket '{self.bucket}': {e}")

    def upload_file(self, local_path: str, destination_name: str) -> str:
        key = f"{uuid.uuid4().hex[:8]}_{os.path.basename(destination_name)}"
        self.s3.upload_file(local_path, self.bucket, key)
        settings = get_settings()
        # Return public/presigned or endpoint URL
        if settings.minio_endpoint:
            proto = "https" if settings.minio_secure else "http"
            return f"{proto}://{settings.minio_endpoint}/{self.bucket}/{key}"
        return f"/api/v1/files/{key}"

    def download_file(self, identifier: str, local_destination: str) -> str:
        key = os.path.basename(identifier)
        os.makedirs(os.path.dirname(os.path.abspath(local_destination)), exist_ok=True)
        self.s3.download_file(self.bucket, key, local_destination)
        return local_destination

    def get_file_path(self, file_id: str) -> Optional[str]:
        return None

    def is_healthy(self) -> bool:
        try:
            self.s3.head_bucket(Bucket=self.bucket)
            return True
        except Exception as e:
            logger.error(f"S3StorageClient health check failed: {e}")
            return False


_storage_singleton: Optional[StorageClient] = None


def get_storage_client() -> StorageClient:
    """Singleton factory returning appropriate storage backend."""
    global _storage_singleton
    if _storage_singleton is None:
        settings = get_settings()
        if settings.storage_backend == "s3" and settings.minio_endpoint:
            try:
                _storage_singleton = S3StorageClient()
            except Exception as e:
                logger.warning(f"S3 initialization failed ({e}); falling back to local storage.")
                _storage_singleton = LocalStorageClient()
        else:
            _storage_singleton = LocalStorageClient()
    return _storage_singleton
