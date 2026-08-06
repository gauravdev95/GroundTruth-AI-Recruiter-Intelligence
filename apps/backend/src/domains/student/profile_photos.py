"""Storage rules for a student's profile photo.

The same shape as `certificate_files.py` — a thin layer over
`domains/storage/client.py` that knows what a *profile photo* is allowed to
be — and deliberately a separate module rather than a parameter on that one,
because the two answer differently on every rule that matters: a photo is
images only (no PDF), is capped at 2 MB rather than 5, and is singular per
profile rather than one of a list.

**A profile photo is not evidence, and nothing here treats it as any.** It
never touches `verification_status`, earns no completeness points, and is
read by no worker. It exists so a recruiter sees a person. This module
provides no hook to make it mean anything more, for the same reason
`certificate_files` provides none.

**One photo per profile, and replacing it deletes the old object.** Unlike
certificates — where each row keeps its own file and history is worth
preserving — a superseded photo is nothing anyone can want, and leaving it
in the bucket would accumulate an unreferenced object per re-upload with no
row pointing at it to ever clean up.

The key layout is `profile-photos/{candidate_profile_id}/{uuid}{suffix}`, so
`owns_key` stays a string comparison rather than a lookup, and the
client-supplied filename never reaches the object path.
"""

from __future__ import annotations

import uuid
from typing import BinaryIO

import structlog

from src.core.exceptions import ValidationFailed
from src.domains.storage import client as storage

logger = structlog.get_logger(__name__)

_KEY_PREFIX = "profile-photos"

#: JPEG and PNG only, sniffed from the leading bytes rather than read from the
#: request's `Content-Type` or the filename — both are client claims, and the
#: sniffed type is what the presigned URL will serve the object as.
#:
#: No PDF, unlike certificates: this image is rendered in an `<img>` on the
#: dashboard and in recruiter search results, and a PDF there is a broken
#: avatar on every screen it appears on.
_MAGIC_PREFIXES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)

#: Smaller than the certificate ceiling: this is a face at avatar size, and the
#: client crops to a square before upload. 2 MB is generous for that and still
#: refuses a phone camera's full-resolution original.
MAX_BYTES = 2 * 1024 * 1024


class UnsupportedProfilePhoto(ValidationFailed):
    """The upload is not a PNG or JPEG."""

    code = "UNSUPPORTED_FILE_TYPE"


class ProfilePhotoTooLarge(ValidationFailed):
    """The upload exceeds `MAX_BYTES`."""

    status_code = 413
    code = "FILE_TOO_LARGE"


def detect_content_type(fileobj: BinaryIO) -> tuple[str, str]:
    """Return `(content_type, filename_suffix)` sniffed from the leading bytes.

    Rewinds afterwards so the caller can still upload the whole object — the
    stream is read for identification only.
    """
    head = fileobj.read(16)
    fileobj.seek(0)

    for magic, content_type, suffix in _MAGIC_PREFIXES:
        if head.startswith(magic):
            return content_type, suffix

    raise UnsupportedProfilePhoto("Upload a PNG or JPEG image")


def build_key(candidate_profile_id: uuid.UUID, suffix: str) -> str:
    return f"{_KEY_PREFIX}/{candidate_profile_id}/{uuid.uuid4()}{suffix}"


def owns_key(candidate_profile_id: uuid.UUID, key: str) -> bool:
    """Whether `key` was minted for this profile. A string comparison, not a
    query — the profile id is in the path."""
    return key.startswith(f"{_KEY_PREFIX}/{candidate_profile_id}/")


def store(fileobj: BinaryIO, *, candidate_profile_id: uuid.UUID, size_bytes: int) -> tuple[str, str]:
    """Validate and upload. Returns `(object_key, content_type)`."""
    if size_bytes <= 0:
        raise UnsupportedProfilePhoto("The uploaded file is empty")
    if size_bytes > MAX_BYTES:
        raise ProfilePhotoTooLarge(f"Photos must be at most {MAX_BYTES // (1024 * 1024)} MB")

    content_type, suffix = detect_content_type(fileobj)
    key = build_key(candidate_profile_id, suffix)
    storage.upload_fileobj(fileobj, key=key, content_type=content_type)
    logger.info("profile_photo_stored", candidate_profile_id=str(candidate_profile_id), key=key)
    return key, content_type


def discard(key: str | None) -> None:
    """Best-effort delete of a superseded photo.

    Failure is logged and swallowed on purpose. This runs *after* the
    replacement is already stored and the profile row already points at it, so
    a storage error here means one orphaned object — not a broken profile — and
    raising would fail an upload that has, from the student's side, entirely
    succeeded.
    """
    if key is None:
        return
    try:
        storage.delete_object(key)
    except Exception:  # noqa: BLE001 - see docstring
        logger.warning("profile_photo_discard_failed", key=key, exc_info=True)


def download_url(key: str) -> str:
    """Short-lived presigned read URL. The bucket itself stays private."""
    return storage.presigned_url(key)
