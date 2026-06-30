from __future__ import annotations

import tempfile
from pathlib import Path
from uuid import UUID

import boto3
from fastapi import UploadFile

from app.config import settings


class Storage:
    def save_upload(self, project_id: UUID, document_id: UUID, file: UploadFile) -> str:
        key = f"uploads/{project_id}/{document_id}/{file.filename}"
        payload = file.file.read()
        self.write_bytes(key, payload, content_type=file.content_type)
        return key

    def write_report(self, run_id: UUID, markdown: str) -> str:
        key = f"reports/{run_id}/factcheck_report_{run_id}.md"
        self.write_bytes(key, markdown.encode("utf-8"), content_type="text/markdown; charset=utf-8")
        return key

    def write_bytes(self, key: str, payload: bytes, content_type: str | None = None) -> None:
        if settings.storage_backend == "s3":
            self._s3().put_object(Bucket=settings.s3_bucket, Key=key, Body=payload, ContentType=content_type or "application/octet-stream")
            return
        path = Path(settings.local_storage_root) / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)

    def read_bytes(self, key: str) -> bytes:
        if settings.storage_backend == "s3":
            obj = self._s3().get_object(Bucket=settings.s3_bucket, Key=key)
            return obj["Body"].read()
        return (Path(settings.local_storage_root) / key).read_bytes()

    def materialize(self, key: str) -> str:
        if settings.storage_backend == "local":
            return str(Path(settings.local_storage_root) / key)
        suffix = Path(key).suffix
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        handle.write(self.read_bytes(key))
        handle.close()
        return handle.name

    def _s3(self):
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        return boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            region_name=settings.s3_region,
        )


storage = Storage()

