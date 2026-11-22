"""Upload endpoint abuse (QA item 5), extending tests/ml/test_cv_uploads.py and tests/test_uploads.py.

POST /api/v1/cv/ffb-assessment stores a sanitised copy on disk under a random name and returns colour statistics.
Added here: polyglots (HTML/PHP/JS tails, metadata payloads), renamed executables/documents, header-declared huge dimensions,
decompression-bomb IDAT streams, chunk floods, truncated/corrupt files, hostile filenames (traversal, NUL, RTL, 5000 chars),
multipart abuse, size boundaries, and role checks. Every case must end in a clean 2xx/4xx - never 5xx, never a file outside the
upload directory, bounded time and memory.
"""

from __future__ import annotations

import resource
import struct
import time
import zlib

import pytest

from app.ml import cv

from .support import assert_clean_error, hdr, make_client, prepare_db

H = hdr("ai_analyst")
P = {"as_of": "2026-11-20T08:00:00Z"}
URL = "/api/v1/cv/ffb-assessment"


def chunk(t: bytes, b: bytes) -> bytes:
    return struct.pack(">I", len(b)) + t + b + struct.pack(">I", zlib.crc32(t + b) & 0xFFFFFFFF)


def png(w=8, h=8, *, extra=(), idat: bytes | None = None, ihdr_wh: tuple[int, int] | None = None, tail=b"") -> bytes:
    raw = b"".join(b"\x00" + bytes((200, 60, 20)) * w for _ in range(h)) if idat is None else b""
    iw, ih = ihdr_wh or (w, h)
    out = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", iw, ih, 8, 2, 0, 0, 0))
    for t, b in extra:
        out += chunk(t, b)
    return out + chunk(b"IDAT", idat if idat is not None else zlib.compress(raw)) + chunk(b"IEND", b"") + tail


JPEG_MIN = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


@pytest.fixture
def uc(tmp_path, monkeypatch):
    monkeypatch.setattr(cv, "UPLOAD_DIR", tmp_path / "uploads")
    client = make_client(prepare_db("qa-upload"), upload_max_bytes=256 * 1024)
    client.upload_dir = tmp_path / "uploads"
    client.tmp = tmp_path
    return client


def post(c, data, name="ffb.png", ctype="image/png", headers=H, field="file", **kw):
    return c.post(URL, params=P, files={field: (name, data, ctype)}, headers=headers, **kw)


def stored(c) -> list:
    return sorted(p for p in c.upload_dir.iterdir()) if c.upload_dir.exists() else []


def no_stray_files(c):
    """Nothing was written anywhere under tmp except inside the upload directory."""
    for p in c.tmp.rglob("*"):
        if p.is_file():
            assert c.upload_dir in p.parents, f"file written outside the upload dir: {p}"


# ---------------------------------------------------------------------------------------------------- polyglots / payloads


@pytest.mark.parametrize(
    "tail",
    [b"<html><script>alert(1)</script></html>", b"<?php system($_GET['c']); ?>", b"PK\x03\x04" + b"\x00" * 30, b"%PDF-1.7\n1 0 obj", b"MZ\x90\x00" + b"\x00" * 60, b"#!/bin/sh\nrm -rf /\n", b"\x7fELF" + b"\x00" * 60, b"GIF89a;<script>"],
    ids=["html", "php", "zip", "pdf", "pe", "shell", "elf", "gif_js"],
)
def test_png_with_any_appended_payload_is_rejected_and_not_stored(uc, tail):
    r = post(uc, png(tail=tail))
    assert_clean_error(r, status=415, code="trailing_data")
    assert stored(uc) == []


@pytest.mark.parametrize("tail", [b"<?php system($_GET[1]); ?>", b"PK\x03\x04", b"<script>"], ids=["php", "zip", "js"])
def test_jpeg_and_webp_with_appended_payload_are_rejected(uc, tail):
    assert post(uc, JPEG_MIN + tail, "x.jpg", "image/jpeg").status_code == 415
    webp = b"RIFF" + struct.pack("<I", 4) + b"WEBP"
    assert post(uc, webp + tail, "x.webp", "image/webp").status_code == 415
    assert stored(uc) == []


def test_metadata_chunks_with_script_text_are_stripped_from_the_stored_copy(uc):
    evil = b"<script>alert(1)</script>"
    r = post(uc, png(extra=[(b"tEXt", b"Comment\x00" + evil), (b"iTXt", b"XML:com.adobe.xmp\x00\x00\x00\x00\x00" + evil), (b"eXIf", b"GPS 13.7N 100.5E" + evil), (b"zTXt", b"k\x00\x00" + zlib.compress(evil))]))
    assert r.status_code == 200, r.text[:300]
    files = stored(uc)
    assert len(files) == 1
    blob = files[0].read_bytes()
    assert b"script" not in blob and b"GPS" not in blob and b"tEXt" not in blob and b"iTXt" not in blob and b"eXIf" not in blob
    assert "script" not in r.text and r.json()["validated"] is False


def test_jpeg_comment_and_exif_segments_are_stripped(uc):
    app1 = b"\xff\xe1" + struct.pack(">H", 2 + 40) + b"Exif\x00\x00" + b"GPS-SECRET-LOCATION".ljust(34, b"\x00")
    com = b"\xff\xfe" + struct.pack(">H", 2 + 18) + b"<?php evil(); ?>   "
    data = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00" + app1 + com + b"\xff\xd9"
    r = post(uc, data, "x.jpg", "image/jpeg")
    assert r.status_code == 200, r.text[:300]
    blob = stored(uc)[0].read_bytes()
    assert b"GPS-SECRET" not in blob and b"<?php" not in blob


# ---------------------------------------------------------------------------------------------------- renamed / mislabelled


@pytest.mark.parametrize(
    "name,data,ctype",
    [
        ("evil.png", b"MZ\x90\x00\x03" + b"\x00" * 200, "image/png"),
        ("evil.jpg", b"%PDF-1.4\n" + b"0" * 100, "image/jpeg"),
        ("evil.png", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>", "image/png"),
        ("evil.webp", b"<html><body onload=alert(1)>", "image/webp"),
        ("evil.png", b"\x1f\x8b\x08" + b"\x00" * 50, "image/png"),
        ("evil.png", b"\x7fELF" + b"\x00" * 50, "image/png"),
        ("evil.png", b"PK\x03\x04" + b"\x00" * 50, "image/png"),
        ("a.jpg", png(), "image/jpeg"),
        ("a.png", JPEG_MIN, "image/png"),
        ("a.png", b"\x89PNG\r\n\x1a", "image/png"),  # truncated magic
        ("a.png", b"\x00" * 64, "image/png"),
        ("a.png", b" \x89PNG\r\n\x1a\n", "image/png"),  # leading space
    ],
    ids=lambda v: v if isinstance(v, str) and v.startswith(("image", "evil", "a.")) else None,
)
def test_files_that_are_not_what_they_claim_to_be_are_rejected(uc, name, data, ctype):
    r = post(uc, data, name, ctype)
    assert r.status_code in (415, 422), (r.status_code, r.text[:200])
    assert_clean_error(r)
    assert stored(uc) == []


@pytest.mark.parametrize("ctype", ["application/octet-stream", "text/html", "image/svg+xml", "image/gif", "image/png; charset=binary", "image/png\x00", "", "image/*", "multipart/mixed", "application/pdf"])
def test_disallowed_declared_types_are_rejected(uc, ctype):
    r = post(uc, png(), "a.png", ctype)
    assert r.status_code in (415, 422), (ctype, r.status_code)
    assert_clean_error(r)


def test_declared_type_is_case_insensitive_but_must_match_content(uc):
    assert post(uc, png(), "a.png", "IMAGE/PNG").status_code == 200
    assert post(uc, JPEG_MIN, "a.png", "IMAGE/PNG").status_code == 415


# ---------------------------------------------------------------------------------------------------- dimensions / bombs


@pytest.mark.parametrize("wh", [(65535, 65535), (2**31 - 1, 2**31 - 1), (2**32 - 1, 2**32 - 1), (5001, 5000), (1, 100_000_000), (0, 0), (0, 10), (10, 0)])
def test_header_declared_huge_or_zero_dimensions_are_rejected_without_decoding(uc, wh):
    t0 = time.perf_counter()
    r = post(uc, png(ihdr_wh=wh))
    assert time.perf_counter() - t0 < 1.0
    assert r.status_code in (413, 415, 422), (wh, r.status_code, r.text[:200])
    assert_clean_error(r)
    assert stored(uc) == []


def test_dimensions_at_the_limit_are_accepted_without_pixel_decoding(uc):
    r = post(uc, png(ihdr_wh=(5000, 5000)))  # 25 MP: allowed by the header check, far above the pure-python decode limit
    assert r.status_code == 200, r.text[:200]
    assert "colour_stats_unavailable" in r.json()["image_stats"] or "colour_region_fractions" in r.json()["image_stats"]


def test_idat_decompression_bomb_is_bounded_in_time_and_memory(uc):
    """A 3 KB file that inflates to ~300 MB of zeros declared as an 8x8 image must not be inflated."""
    bomb = zlib.compress(b"\x00" * (300 * 1024 * 1024), 9)
    assert len(bomb) < 400 * 1024
    before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS, KiB on Linux
    t0 = time.perf_counter()
    r = post(uc, png(idat=bomb, ihdr_wh=(8, 8)))
    elapsed = time.perf_counter() - t0
    grown_mb = (resource.getrusage(resource.RUSAGE_SELF).ru_maxrss - before) / (1024 * 1024 if before > 10**8 else 1024)
    assert r.status_code in (200, 413, 415, 422), (r.status_code, r.text[:200])
    assert elapsed < 3.0 and grown_mb < 120, (elapsed, grown_mb)
    if r.status_code != 200:
        assert_clean_error(r)


def test_chunk_flood_is_bounded(uc):
    flood = [(b"zzZz", b"")] * 15_000  # ~180 KB of empty ancillary chunks inside the 256 KiB cap
    t0 = time.perf_counter()
    r = post(uc, png(extra=flood))
    assert time.perf_counter() - t0 < 3.0
    assert r.status_code in (200, 413, 415, 422)


@pytest.mark.parametrize("variant", ["bad_zlib", "truncated", "no_iend", "length_overflow", "bad_crc_idat", "zero_idat", "idat_before_ihdr", "palette_without_plte", "palette_bad_plte", "short_scanlines", "bad_filter_byte"])
def test_corrupt_pngs_are_client_errors(uc, variant):
    good = png()
    if variant == "bad_zlib":
        data = png(idat=b"\x78\x9c" + b"\xff" * 40)
    elif variant == "truncated":
        data = good[: len(good) // 2]
    elif variant == "no_iend":
        data = good[:-12]
    elif variant == "length_overflow":
        data = good[:8] + struct.pack(">I", 2**31) + good[12:]
    elif variant == "bad_crc_idat":
        b = bytearray(good)
        b[-20] ^= 0xFF
        data = bytes(b)
    elif variant == "zero_idat":
        data = png(idat=b"")
    elif variant in ("palette_without_plte", "palette_bad_plte"):
        extra = [(b"PLTE", b"\x01\x02")] if variant == "palette_bad_plte" else []
        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 3, 0, 0, 0))
        data = b"\x89PNG\r\n\x1a\n" + ihdr + b"".join(chunk(t, b) for t, b in extra) + chunk(b"IDAT", zlib.compress((b"\x00" + b"\x07" * 4) * 4)) + chunk(b"IEND", b"")
    elif variant == "short_scanlines":
        data = png(idat=zlib.compress(b"\x00" * 10), ihdr_wh=(8, 8))
    elif variant == "bad_filter_byte":
        data = png(idat=zlib.compress((b"\x09" + bytes((200, 60, 20)) * 8) * 8))
    else:
        data = good[:8] + chunk(b"IDAT", zlib.compress(b"\x00" * 200)) + good[8:]
    r = post(uc, data)
    assert r.status_code in (200, 415, 422), (variant, r.status_code, r.text[:200])
    if r.status_code != 200:
        assert_clean_error(r)
        assert stored(uc) == [], "a rejected image must not be stored"


# ---------------------------------------------------------------------------------------------------- filenames


@pytest.mark.parametrize(
    "name",
    ["../../../etc/passwd.png", "..\\..\\windows\\system32\\evil.png", "/etc/shadow", "C:\\boot.ini", "a\x00.png", "x\x00../../y.png", "." * 300, "a" * 5000 + ".png", "\u202egnp.exe", "\u0e1b\u0e23\u0e30\u0e01\u0e32\u0e28.png", ".htaccess", "%2e%2e%2fetc%2fpasswd.png", "con", "ffb.png\r\nSet-Cookie: x=1", "<script>alert(1)</script>.png", "'; DROP TABLE alerts;--.png", ""],
    ids=lambda n: repr(n[:18]),
)
def test_hostile_filenames_never_reach_the_filesystem_or_the_response_unsanitised(uc, name):
    r = post(uc, png(), name)
    assert r.status_code in (200, 400, 422), (name[:20], r.status_code, r.text[:200])  # 400: the multipart parser refuses absurd header lines
    if r.status_code == 200:
        j = r.json()
        for bad in ("/", "\\", "..", "\x00", "\r", "\n", "<", ">", "'", "\u202e", ";"):
            assert bad not in j["filename"], (name[:20], j["filename"])
        assert len(j["filename"]) <= 100
        stored_as = j["image_stats"]["stored_as"]
        assert len(stored_as) == 36 and stored_as.endswith(".png") and "/" not in stored_as and ".." not in stored_as
    no_stray_files(uc)
    assert all(p.parent == uc.upload_dir for p in stored(uc))


def test_stored_names_are_random_and_never_client_controlled(uc):
    names = {post(uc, png(), "same.png").json()["image_stats"]["stored_as"] for _ in range(6)}
    assert len(names) == 6 and not any("same" in n for n in names)


# ---------------------------------------------------------------------------------------------------- multipart abuse


def test_missing_wrong_or_duplicate_file_fields(uc):
    assert_clean_error(uc.post(URL, params=P, headers=H), status=422)
    assert_clean_error(post(uc, png(), field="upload"), status=422)
    assert_clean_error(uc.post(URL, params=P, headers=H, data={"file": "just text"}), status=422)
    two = uc.post(URL, params=P, headers=H, files=[("file", ("a.png", png(), "image/png")), ("file", ("b.png", png(), "image/png"))])
    assert two.status_code in (200, 422) and two.status_code < 500
    assert len(stored(uc)) <= 1


def test_multipart_field_flood_and_malformed_bodies(uc):
    many = {f"f{i}": "x" for i in range(3000)}
    r = uc.post(URL, params=P, headers=H, data=many, files={"file": ("a.png", png(), "image/png")})
    assert r.status_code in (200, 400, 413, 422) and r.status_code < 500
    for body, ctype in (
        (b"--x\r\nContent-Disposition: form-data; name=file; filename=a.png\r\n\r\n" + png(), "multipart/form-data; boundary=x"),  # no closing boundary
        (b"garbage", "multipart/form-data; boundary=zzz"),
        (b"", "multipart/form-data; boundary=zzz"),
        (png(), "multipart/form-data"),  # boundary missing
        (b"--x--\r\n", "multipart/form-data; boundary=x"),
        (b"--x\r\nContent-Disposition: form-data; name=" + b"n" * 20_000 + b"\r\n\r\nv\r\n--x--\r\n", "multipart/form-data; boundary=x"),
    ):
        r = uc.post(URL, params=P, content=body, headers={**H, "content-type": ctype})
        assert r.status_code in (400, 413, 415, 422), (ctype, r.status_code, r.text[:160])
        assert_clean_error(r)


# ---------------------------------------------------------------------------------------------------- size + roles


def test_size_boundary(uc):
    limit = 256 * 1024
    ok = png(extra=[(b"zzZz", b"\x01" * (limit - 200))])
    assert len(ok) <= limit
    assert post(uc, ok).status_code == 200
    over = png(extra=[(b"zzZz", b"\x01" * (limit + 10))])
    assert_clean_error(post(uc, over), status=413, code="payload_too_large")
    way_over = b"\x89PNG\r\n\x1a\n" + b"\x00" * (3 * 1024 * 1024)  # beyond the route's raw-body cap: refused by the body limiter
    assert_clean_error(post(uc, way_over), status=413, code="payload_too_large")


@pytest.mark.parametrize("role", ["public_viewer", "executive", "factory_manager", "maintenance_engineer", "logistics_officer"])
def test_roles_without_upload_permission_get_403_and_store_nothing(uc, role):
    r = post(uc, png(), headers=hdr(role))
    assert_clean_error(r, status=403, code="forbidden")
    assert stored(uc) == []


@pytest.mark.parametrize("role", ["production_engineer", "ai_analyst", "system_admin"])
def test_permitted_roles_upload_and_response_is_labelled_prototype(uc, role):
    j = post(uc, png(), headers=hdr(role)).json()
    assert j["status"] == "prototype" and j["validated"] is False and j["requires_human_review"] is True
    assert "NOT a ripeness grade" in j["assessment"]


def test_upload_quota_holds_under_a_flood(uc, monkeypatch):
    monkeypatch.setattr(cv, "QUOTA_FILES", 5)
    for _ in range(40):
        assert post(uc, png()).status_code == 200
    assert len(stored(uc)) == 5
