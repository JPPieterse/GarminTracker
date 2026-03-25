"""Cloudflare R2 (S3-compatible) storage service via boto3."""

from __future__ import annotations

import uuid

import boto3
from botocore.config import Config

from app.core.config import settings


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        config=Config(signature_version="s3v4"),
        region_name="auto",
    )


async def upload_file(
    file_bytes: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    prefix: str = "uploads",
) -> str:
    """Upload a file to R2 and return the object key."""
    key = f"{prefix}/{uuid.uuid4()}/{filename}"
    client = _get_s3_client()
    client.put_object(
        Bucket=settings.R2_BUCKET_NAME,
        Key=key,
        Body=file_bytes,
        ContentType=content_type,
    )
    return key


async def get_download_url(key: str, expires_in: int = 3600) -> str:
    """Generate a presigned download URL."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.R2_BUCKET_NAME, "Key": key},
        ExpiresIn=expires_in,
    )


async def delete_file(key: str) -> None:
    """Delete an object from R2."""
    client = _get_s3_client()
    client.delete_object(Bucket=settings.R2_BUCKET_NAME, Key=key)
