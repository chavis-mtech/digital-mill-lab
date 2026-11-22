"""Safe upload handling: size cap (streamed), declared-type allow-list, magic-byte sniffing, filename sanitising.

Uploaded bytes are processed in memory and never written under a user-controlled path.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import UploadFile

from app.config import Settings
from app.errors import ApiError

_CHUNK = 64 * 1024
_SAFE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class ValidatedUpload:
    filename: str
    content_type: str
    size: int
    data: bytes


def sniff_image_type(head: bytes) -> str | None:
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def sanitize_filename(name: str | None) -> str:
    base = (name or "upload").replace("\\", "/").rsplit("/", 1)[-1]
    base = _SAFE_NAME.sub("_", base).strip("._") or "upload"
    return base[:100]


async def read_validated_upload(file: UploadFile, settings: Settings) -> ValidatedUpload:
    allowed = settings.allowed_upload_types
    declared = (file.content_type or "").lower()
    if declared not in allowed:
        raise ApiError(415, "unsupported_media_type", "File type not allowed", {"allowed": sorted(allowed)})
    buf = bytearray()
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > settings.upload_max_bytes:
            raise ApiError(413, "payload_too_large", "File too large", {"max_bytes": settings.upload_max_bytes})
    if not buf:
        raise ApiError(422, "empty_upload", "Uploaded file is empty")
    sniffed = sniff_image_type(bytes(buf[:16]))
    if sniffed is None or sniffed != declared:
        raise ApiError(415, "content_mismatch", "File content does not match an allowed image type", {"declared": declared})
    return ValidatedUpload(filename=sanitize_filename(file.filename), content_type=sniffed, size=len(buf), data=bytes(buf))
