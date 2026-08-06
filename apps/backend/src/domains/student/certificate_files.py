"""Storage rules for uploaded certificate files.

A thin layer over `domains/storage/client.py`, separate from it for the same
reason `resume/service.py` is: the storage client knows about buckets and
bytes, and this knows what a *certificate* upload is allowed to be — which
types, how large, and whose object key is whose.

**An uploaded certificate is not evidence.** `verify_certificate_task` checks
the `credential_url` against the issuer's domain; a PDF the candidate uploaded
is a document they control and corroborates nothing about itself. It is stored
so a recruiter can look at it, and it never moves `verification_status`. This
module deliberately provides no hook to make it do so.

The key layout is `certificates/{candidate_profile_id}/{uuid}{suffix}` — the
profile id in the path is what makes `owns_key` a cheap authorization check
rather than a database lookup, and the uuid is what stops the client-supplied
filename from ever reaching the object path.
"""

from __future__ import annotations

import uuid
from typing import BinaryIO

import structlog

from src.core.exceptions import ValidationFailed
from src.domains.storage import client as storage

logger = structlog.get_logger(__name__)

_KEY_PREFIX = "certificates"

#: Certificates are shown to recruiters, so the accepted types are the ones a
#: browser can render inline. Anything else — a zip, a .docx, an executable —
#: is refused rather than stored and hoped for.
#:
#: Sniffed from the leading bytes, never taken from the request's
#: `Content-Type` or the filename: both are client claims, and the stored type
#: is what the presigned URL will later serve the file as.
_MAGIC_PREFIXES: tuple[tuple[bytes, str, str], ...] = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
)

#: Smaller than the resume ceiling on purpose: a certificate is one page or one
#: screenshot, and a 10 MB one is a scan nobody needs at that fidelity.
MAX_BYTES = 5 * 1024 * 1024


class UnsupportedCertificateFile(ValidationFailed):
    """The upload is not a PDF, PNG, or JPEG."""

    code = "UNSUPPORTED_FILE_TYPE"


class CertificateFileTooLarge(ValidationFailed):
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

    raise UnsupportedCertificateFile("Upload a PDF, PNG, or JPEG certificate")


def build_key(candidate_profile_id: uuid.UUID, suffix: str) -> str:
    return f"{_KEY_PREFIX}/{candidate_profile_id}/{uuid.uuid4()}{suffix}"


def owns_key(candidate_profile_id: uuid.UUID, key: str) -> bool:
    """Whether `key` was minted for this profile.

    A string comparison, not a query: the profile id is in the path, so this
    answers the question without a round trip and without a table of issued
    keys. It is the check that stops a guessed key from attaching another
    candidate's document to this profile.
    """
    return key.startswith(f"{_KEY_PREFIX}/{candidate_profile_id}/")


def store(
    fileobj: BinaryIO, *, candidate_profile_id: uuid.UUID, size_bytes: int
) -> tuple[str, str, str]:
    """Validate and upload. Returns `(object_key, content_type, suffix)`."""
    if size_bytes <= 0:
        raise UnsupportedCertificateFile("The uploaded file is empty")
    if size_bytes > MAX_BYTES:
        raise CertificateFileTooLarge(
            f"Certificates must be at most {MAX_BYTES // (1024 * 1024)} MB"
        )

    content_type, suffix = detect_content_type(fileobj)
    key = build_key(candidate_profile_id, suffix)
    storage.upload_fileobj(fileobj, key=key, content_type=content_type)
    logger.info("certificate_file_stored", candidate_profile_id=str(candidate_profile_id), key=key)
    return key, content_type, suffix


def download_url(key: str) -> str:
    """Short-lived presigned read URL. The bucket itself stays private."""
    return storage.presigned_url(key)
