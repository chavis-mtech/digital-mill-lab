from __future__ import annotations

import asyncio
import io

import pytest
from starlette.datastructures import Headers, UploadFile

from app.errors import ApiError
from app.security.uploads import read_validated_upload, sanitize_filename, sniff_image_type
from tests.conftest import make_settings

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _upload(data: bytes, ctype: str, name: str = "x.png") -> UploadFile:
    return UploadFile(io.BytesIO(data), filename=name, headers=Headers({"content-type": ctype}))


def test_sniff():
    assert sniff_image_type(PNG) == "image/png"
    assert sniff_image_type(b"\xff\xd8\xff\xe0") == "image/jpeg"
    assert sniff_image_type(b"RIFF\x00\x00\x00\x00WEBP") == "image/webp"
    assert sniff_image_type(b"<svg") is None


def test_sanitize_filename():
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("my photo (1).png") == "my_photo_1_.png"
    assert sanitize_filename(None) == "upload"


def test_valid_png():
    up = asyncio.run(read_validated_upload(_upload(PNG, "image/png"), make_settings()))
    assert up.content_type == "image/png" and up.size == len(PNG)


@pytest.mark.parametrize(
    "data,ctype,code",
    [
        (PNG, "image/svg+xml", "unsupported_media_type"),
        (b"GIF89a" + b"\x00" * 10, "image/png", "content_mismatch"),
        (b"", "image/png", "empty_upload"),
        (PNG + b"\x00" * 2048, "image/png", "payload_too_large"),
    ],
)
def test_rejections(data, ctype, code):
    with pytest.raises(ApiError) as exc:
        asyncio.run(read_validated_upload(_upload(data, ctype), make_settings(upload_max_bytes=1024)))
    assert exc.value.code == code
