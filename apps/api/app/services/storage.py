"""S3-compatible object storage.

Storage keys follow `tenants/{tenant_id}/documents/{doc_id}/{filename}` so the
prefix alone enforces a tenant boundary at the bucket level — useful when we
need to grant scoped IAM access to a downstream tool.
"""
from __future__ import annotations

from io import BytesIO
from typing import BinaryIO
from uuid import UUID

import boto3
from botocore.client import Config

from app.core.config import settings


def _s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(
            signature_version="s3v4",
            s3={"addressing_style": "path" if settings.s3_force_path_style else "auto"},
        ),
    )


def storage_key_for(tenant_id: UUID, document_id: UUID, filename: str) -> str:
    return f"tenants/{tenant_id}/documents/{document_id}/{filename}"


def ensure_bucket() -> None:
    """Idempotently create the bucket. Called on app startup."""
    s3 = _s3_client()
    try:
        s3.head_bucket(Bucket=settings.s3_bucket)
    except Exception:  # noqa: BLE001 - boto raises various error types
        s3.create_bucket(Bucket=settings.s3_bucket)


def upload_fileobj(key: str, data: BinaryIO, content_type: str) -> None:
    s3 = _s3_client()
    s3.upload_fileobj(
        Fileobj=data,
        Bucket=settings.s3_bucket,
        Key=key,
        ExtraArgs={"ContentType": content_type},
    )


def download_to_memory(key: str) -> bytes:
    s3 = _s3_client()
    buf = BytesIO()
    s3.download_fileobj(Bucket=settings.s3_bucket, Key=key, Fileobj=buf)
    return buf.getvalue()


def presigned_download_url(key: str, expires_in: int = 900) -> str:
    s3 = _s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket, "Key": key},
        ExpiresIn=expires_in,
    )
