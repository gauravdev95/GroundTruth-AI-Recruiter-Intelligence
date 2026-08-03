"""S3-compatible object storage.

One adapter serves MinIO in development and S3/R2 in production — MinIO speaks
the S3 API, so only the endpoint and credentials differ. Nothing above this
module knows which is in use.

Resumes are personal data, so the bucket is private: objects are never public,
and the only read path for a browser is a short-lived presigned URL.
"""

from __future__ import annotations

import uuid
from functools import lru_cache
from typing import BinaryIO

import boto3
import structlog
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError

from src.config.config import get_storage_settings
from src.core.exceptions import AppError

logger = structlog.get_logger(__name__)


class StorageError(AppError):
    """Object storage is unavailable or rejected the operation."""

    status_code = 502
    code = "STORAGE_ERROR"


class StorageNotConfigured(AppError):
    """Object storage credentials are not configured."""

    status_code = 503
    code = "STORAGE_NOT_CONFIGURED"


@lru_cache
def _client():
    settings = get_storage_settings()
    if not settings.is_configured:
        raise StorageNotConfigured()

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url or None,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key_id,
        aws_secret_access_key=settings.s3_secret_access_key,
        config=Config(
            signature_version="s3v4",
            retries={"max_attempts": 3, "mode": "standard"},
            # MinIO requires path-style addressing; S3 accepts it too, so one
            # setting works for both rather than branching on the endpoint.
            s3={"addressing_style": "path"},
        ),
    )


def build_object_key(candidate_profile_id: uuid.UUID, filename_suffix: str) -> str:
    """Namespace objects per candidate with an unguessable key.

    The stored key never contains the client-supplied filename: that value is
    untrusted and would otherwise let a caller influence the object path.
    """
    return f"resumes/{candidate_profile_id}/{uuid.uuid4()}{filename_suffix}"


def upload_fileobj(fileobj: BinaryIO, *, key: str, content_type: str) -> None:
    settings = get_storage_settings()
    try:
        _client().upload_fileobj(
            fileobj,
            settings.s3_resume_bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage_upload_failed", key=key, error=str(exc))
        raise StorageError("Could not store the uploaded file") from exc


def download_bytes(key: str) -> bytes:
    """Read an object into memory.

    Safe because uploads are capped at `resume_max_bytes` before they are
    accepted, so nothing here can be larger than that ceiling.
    """
    settings = get_storage_settings()
    try:
        response = _client().get_object(Bucket=settings.s3_resume_bucket, Key=key)
        return response["Body"].read()
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage_download_failed", key=key, error=str(exc))
        raise StorageError("Could not read the stored file") from exc


def presigned_url(key: str) -> str:
    """Short-lived read URL. The bucket itself stays private."""
    settings = get_storage_settings()
    try:
        return _client().generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_resume_bucket, "Key": key},
            ExpiresIn=settings.s3_presign_expiry_seconds,
        )
    except (BotoCoreError, ClientError) as exc:
        logger.error("storage_presign_failed", key=key, error=str(exc))
        raise StorageError("Could not generate a download link") from exc


def delete_object(key: str) -> None:
    """Best-effort delete. Never raises — used on cleanup paths where the
    caller's own failure is the thing worth reporting."""
    settings = get_storage_settings()
    try:
        _client().delete_object(Bucket=settings.s3_resume_bucket, Key=key)
    except (BotoCoreError, ClientError) as exc:
        logger.warning("storage_delete_failed", key=key, error=str(exc))


def ensure_bucket() -> None:
    """Create the bucket if absent. For local MinIO bootstrap only."""
    settings = get_storage_settings()
    client = _client()
    try:
        client.head_bucket(Bucket=settings.s3_resume_bucket)
    except ClientError:
        try:
            client.create_bucket(Bucket=settings.s3_resume_bucket)
            logger.info("storage_bucket_created", bucket=settings.s3_resume_bucket)
        except (BotoCoreError, ClientError) as exc:
            logger.error("storage_bucket_create_failed", error=str(exc))
            raise StorageError("Could not create the storage bucket") from exc
