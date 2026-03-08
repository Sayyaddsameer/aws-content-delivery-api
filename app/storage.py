"""
S3 / MinIO storage module using boto3.
All operations use the bucket configured in settings.
"""

import io
from typing import AsyncGenerator

import boto3
from botocore.config import Config

from app.config import settings

_s3_client = None


def get_s3_client():
    global _s3_client
    if _s3_client is None:
        kwargs = dict(
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            config=Config(signature_version="s3v4"),
        )
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def upload_object(key: str, data: bytes, content_type: str) -> None:
    """Upload bytes to S3/MinIO under the given key."""
    client = get_s3_client()
    client.put_object(
        Bucket=settings.s3_bucket_name,
        Key=key,
        Body=data,
        ContentType=content_type,
    )


def download_object(key: str) -> bytes:
    """Download a full object from S3/MinIO as bytes."""
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
    return response["Body"].read()


def stream_object(key: str, chunk_size: int = 1024 * 64):
    """
    Yield chunks of the object body for streaming HTTP responses.
    Yields (body_generator, content_length).
    """
    client = get_s3_client()
    response = client.get_object(Bucket=settings.s3_bucket_name, Key=key)
    content_length: int = response["ContentLength"]
    body = response["Body"]

    def _iter():
        while True:
            chunk = body.read(chunk_size)
            if not chunk:
                break
            yield chunk

    return _iter(), content_length


def get_object_metadata(key: str) -> dict:
    """Head an object (no body download) to get size/content-type."""
    client = get_s3_client()
    response = client.head_object(Bucket=settings.s3_bucket_name, Key=key)
    return {
        "content_length": response["ContentLength"],
        "content_type": response.get("ContentType", "application/octet-stream"),
    }
