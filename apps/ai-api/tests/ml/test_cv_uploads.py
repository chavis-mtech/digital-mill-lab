"""CV prototype upload security + honesty."""

from __future__ import annotations

import struct
import zlib

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.ml import cv
from tests.conftest import make_settings

H = {"X-Demo-Role": "ai_analyst"}


def png(w: int = 8, h: int = 8, extra: list[tuple[bytes, bytes]] | None = None, rgb=(200, 60, 20)) -> bytes:
    def chunk(t, b):
        return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * w for _ in range(h))
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
    for t, b in extra or []:
        out += chunk(t, b)
    return out + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setattr(cv, "UPLOAD_DIR", tmp_path / "uploads")
    return TestClient(create_app(make_settings(upload_max_bytes=64 * 1024)))


def post(client, data, name="ffb.png", ctype="image/png", headers=H):
    return client.post("/api/v1/cv/ffb-assessment", files={"file": (name, data, ctype)}, headers=headers)


def test_valid_png_returns_prototype_stats_not_a_grade(client, tmp_path):
    r = post(client, png(16, 12, extra=[(b"tEXt", b"Comment\x00secret gps")]))
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["status"] == "prototype" and j["validated"] is False and j["requires_human_review"] is True
    assert (j["width"], j["height"]) == (16, 12)
    assert "NOT a ripeness grade" in j["assessment"]
    fr = j["image_stats"]["colour_region_fractions"]
    assert abs(sum(fr.values()) - 1) < 1e-6 and fr["orange_red"] > 0.9
    stored = tmp_path / "uploads" / j["image_stats"]["stored_as"]
    assert stored.exists() and b"tEXt" not in stored.read_bytes() and b"secret" not in stored.read_bytes()


def test_oversize_rejected(client):
    big = png(200, 200, extra=[(b"zzZz", b"\x01" * 70_000)])
    assert post(client, big).status_code == 413


def test_wrong_declared_type_rejected(client):
    assert post(client, b"hello", name="a.txt", ctype="text/plain").status_code == 415


def test_renamed_file_rejected(client):
    gif = b"GIF89a" + b"\x00" * 100
    assert post(client, gif, name="a.png").status_code == 415
    assert post(client, png(), name="a.jpg", ctype="image/jpeg").status_code == 415  # declared jpeg, content png


def test_polyglot_with_appended_archive_rejected(client):
    r = post(client, png() + b"PK\x03\x04" + b"\x00" * 50)
    assert r.status_code == 415 and r.json()["error"]["code"] == "trailing_data"


def test_jpeg_with_trailing_payload_rejected(client):
    jpg = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9" + b"<?php system($_GET[1]); ?>"
    assert post(client, jpg, name="x.jpg", ctype="image/jpeg").status_code == 415


def test_path_traversal_filename_is_neutralised(client, tmp_path):
    r = post(client, png(), name="../../../etc/passwd.png")
    assert r.status_code == 200
    j = r.json()
    assert "/" not in j["filename"] and ".." not in j["filename"]
    stored = j["image_stats"]["stored_as"]
    assert "/" not in stored and stored.endswith(".png") and len(stored) == 36
    assert (tmp_path / "uploads" / stored).exists()


def test_bad_crc_rejected(client):
    p = bytearray(png())
    p[30] ^= 0xFF  # corrupt IHDR body
    assert post(client, bytes(p)).status_code == 415


def test_quota_evicts_oldest(client, tmp_path, monkeypatch):
    monkeypatch.setattr(cv, "QUOTA_FILES", 2)
    for _ in range(4):
        assert post(client, png()).status_code == 200
    assert len(list((tmp_path / "uploads").iterdir())) == 2


def test_role_without_upload_permission_denied(client):
    assert post(client, png(), headers={"X-Demo-Role": "public_viewer"}).status_code == 403


def test_protocol_is_honest(client):
    j = client.get("/api/v1/cv/protocol", headers=H).json()
    assert j["status"] == "prototype"
    assert any("No properly licensed" in s for s in j["dataset_requirements"])
