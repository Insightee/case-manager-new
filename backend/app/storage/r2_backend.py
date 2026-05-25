from __future__ import annotations

import boto3
from botocore.exceptions import ClientError

from app.core.config import settings
from app.storage.types import StorageResult


class R2StorageBackend:
    provider = "r2"

    def __init__(self) -> None:
        endpoint = settings.storage_r2_endpoint
        if not endpoint or not settings.r2_bucket_name.strip():
            raise RuntimeError("R2 storage is not configured (endpoint and bucket required)")
        self._bucket = settings.r2_bucket_name.strip()
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=settings.r2_access_key_id.strip(),
            aws_secret_access_key=settings.r2_secret_access_key.strip(),
            region_name="auto",
        )

    def put_bytes(self, key: str, data: bytes, content_type: str) -> StorageResult:
        self._client.put_object(
            Bucket=self._bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
        return StorageResult(
            provider=self.provider,
            key=key,
            size_bytes=len(data),
            content_type=content_type,
        )

    def get_bytes(self, key: str) -> bytes:
        try:
            resp = self._client.get_object(Bucket=self._bucket, Key=key)
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"Object not found: {key}") from e
            raise
        return resp["Body"].read()

    def delete(self, key: str) -> None:
        self._client.delete_object(Bucket=self._bucket, Key=key)

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self._bucket, Key=key)
            return True
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
