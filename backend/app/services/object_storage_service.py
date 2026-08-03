from __future__ import annotations

from pathlib import Path

from app.settings import get_settings


class ObjectStorageService:
    def __init__(self) -> None:
        settings = get_settings()
        self.enabled = settings.object_storage_enabled
        self.bucket = settings.object_storage_bucket
        self.client = None
        if self.enabled:
            from minio import Minio

            endpoint = settings.object_storage_endpoint.removeprefix("http://").removeprefix("https://")
            self.client = Minio(endpoint, access_key=settings.object_storage_access_key, secret_key=settings.object_storage_secret_key, secure=settings.object_storage_endpoint.startswith("https://"))
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)

    def put_file(self, object_key: str, path: Path, content_type: str = "application/octet-stream") -> str | None:
        if not self.enabled or self.client is None:
            return None
        self.client.fput_object(self.bucket, object_key, str(path), content_type=content_type)
        return object_key


_service: ObjectStorageService | None = None


def get_object_storage_service() -> ObjectStorageService:
    global _service
    if _service is None:
        _service = ObjectStorageService()
    return _service
