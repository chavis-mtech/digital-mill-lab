"""Computer-vision FFB grading - RESEARCH PROTOTYPE (SPEC 4.G, P2). Owner: ml.

No labelled, properly licensed FFB dataset was available, so there is NO trained grader and NO accuracy claim. This module
only (1) handles uploads safely and (2) computes simple, explainable colour statistics, clearly labelled as not a grade.

Upload safety (on top of app.security.uploads.read_validated_upload: declared-type allow-list, streamed size cap,
magic-byte sniffing): structural validation per format (PNG must end at IEND, JPEG at EOI, WebP RIFF size must match ->
rejects polyglots / appended archives), decompression-bomb limits, metadata stripping (EXIF/XMP/text chunks), storage
under data/uploads/ with a random server-side name (client filename is never used as a path), and a directory quota
with oldest-first eviction. Content is never executed or interpreted beyond pixel decoding.
"""

from __future__ import annotations

import struct
import uuid
import zlib

import numpy as np

from app.config import REPO_ROOT
from app.errors import ApiError

UPLOAD_DIR = REPO_ROOT / "data" / "uploads"
QUOTA_FILES = 200
QUOTA_BYTES = 100 * 1024 * 1024
MAX_PIXELS = 25_000_000  # header-declared dimensions above this are rejected (decompression bomb)
MAX_DECODE_PIXELS = 1_500_000  # pure-python PNG decode limit for colour statistics
EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


def _reject(code: str, msg: str, details: dict | None = None) -> None:
    raise ApiError(415, code, msg, details)


# ---------------------------------------------------------------------------- structure + metadata stripping
def png_chunks(data: bytes) -> list[tuple[bytes, bytes]]:
    pos, out = 8, []
    while pos + 8 <= len(data):
        (n,) = struct.unpack(">I", data[pos : pos + 4])
        typ = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + n]
        if len(body) != n or pos + 12 + n > len(data):
            _reject("malformed_image", "PNG chunk truncated")
        crc = struct.unpack(">I", data[pos + 8 + n : pos + 12 + n])[0]
        if zlib.crc32(typ + body) & 0xFFFFFFFF != crc:
            _reject("malformed_image", "PNG chunk CRC mismatch")
        out.append((typ, body))
        pos += 12 + n
        if typ == b"IEND":
            if pos != len(data):
                _reject("trailing_data", "Data after the PNG end marker (possible polyglot file) is not allowed")
            return out
    _reject("malformed_image", "PNG has no IEND chunk")
    return out


def sanitize_png(data: bytes) -> tuple[bytes, int, int]:
    chunks = png_chunks(data)
    if not chunks or chunks[0][0] != b"IHDR":
        _reject("malformed_image", "PNG must start with IHDR")
    w, h = struct.unpack(">II", chunks[0][1][:8])
    if w * h > MAX_PIXELS or w == 0 or h == 0:
        _reject("image_too_large", "Image dimensions exceed the limit", {"max_pixels": MAX_PIXELS})
    keep = {b"IHDR", b"PLTE", b"IDAT", b"IEND", b"tRNS", b"gAMA", b"sRGB", b"cHRM"}
    out = bytearray(data[:8])
    for typ, body in chunks:
        if typ in keep:
            out += struct.pack(">I", len(body)) + typ + body + struct.pack(">I", zlib.crc32(typ + body) & 0xFFFFFFFF)
    return bytes(out), w, h


def sanitize_jpeg(data: bytes) -> tuple[bytes, int | None, int | None]:
    end = data.rstrip(b"\x00")
    if not end.endswith(b"\xff\xd9"):
        _reject("trailing_data", "JPEG must end with the EOI marker (no appended data)")
    out = bytearray(b"\xff\xd8")
    pos, w, h = 2, None, None
    while pos + 4 <= len(data):
        if data[pos] != 0xFF:
            _reject("malformed_image", "JPEG marker expected")
        marker = data[pos + 1]
        if marker == 0xDA:  # start of scan: copy the rest verbatim
            out += data[pos : len(end)]
            break
        (n,) = struct.unpack(">H", data[pos + 2 : pos + 4])
        seg = data[pos : pos + 2 + n]
        if marker in (0xC0, 0xC1, 0xC2) and n >= 7:
            h, w = struct.unpack(">HH", data[pos + 5 : pos + 9])
        if not (0xE1 <= marker <= 0xEF or marker == 0xFE):  # drop APP1..APP15 (EXIF/XMP/IPTC) and comments
            out += seg
        pos += 2 + n
    if w and h and w * h > MAX_PIXELS:
        _reject("image_too_large", "Image dimensions exceed the limit", {"max_pixels": MAX_PIXELS})
    return bytes(out), w, h


def sanitize_webp(data: bytes) -> tuple[bytes, int | None, int | None]:
    (size,) = struct.unpack("<I", data[4:8])
    if size + 8 != len(data):
        _reject("trailing_data", "WebP RIFF size does not match the file (possible polyglot file)")
    pos, keep, w, h = 12, bytearray(), None, None
    while pos + 8 <= len(data):
        fourcc = data[pos : pos + 4]
        (n,) = struct.unpack("<I", data[pos + 4 : pos + 8])
        body = data[pos + 8 : pos + 8 + n]
        pad = n & 1
        if fourcc == b"VP8X" and n >= 10:
            w = 1 + int.from_bytes(body[4:7], "little")
            h = 1 + int.from_bytes(body[7:10], "little")
            body = bytes([body[0] & ~0x0C]) + body[1:]  # clear EXIF/XMP flags
        if fourcc == b"VP8 " and n >= 10:
            w, h = struct.unpack("<HH", body[6:10])
            w, h = w & 0x3FFF, h & 0x3FFF
        if fourcc not in (b"EXIF", b"XMP "):
            keep += fourcc + struct.pack("<I", n) + body + (b"\x00" if pad else b"")
        pos += 8 + n + pad
    out = b"RIFF" + struct.pack("<I", len(keep) + 4) + b"WEBP" + bytes(keep)
    return out, w, h


def sanitize(content_type: str, data: bytes) -> tuple[bytes, int | None, int | None]:
    if content_type == "image/png":
        return sanitize_png(data)
    if content_type == "image/jpeg":
        return sanitize_jpeg(data)
    return sanitize_webp(data)


# ---------------------------------------------------------------------------- PNG decode (pure python + numpy)
def decode_png(data: bytes) -> np.ndarray | None:
    """RGB uint8 array for 8-bit non-interlaced PNG (gray/RGB/RGBA/palette); None if unsupported or too large."""
    chunks = png_chunks(data)
    w, h, depth, ctype, _c, _f, interlace = struct.unpack(">IIBBBBB", chunks[0][1][:13])
    if depth != 8 or interlace != 0 or w * h > MAX_DECODE_PIXELS:
        return None
    bpp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(ctype)
    if bpp is None:
        return None
    dec = zlib.decompressobj()
    raw = dec.decompress(b"".join(b for t, b in chunks if t == b"IDAT"), (w * bpp + 1) * h + 1)
    if len(raw) < (w * bpp + 1) * h:
        return None
    stride = w * bpp
    img = np.zeros((h, stride), dtype=np.uint8)
    prev = np.zeros(stride, dtype=np.int32)
    for y in range(h):
        f = raw[y * (stride + 1)]
        line = np.frombuffer(raw, dtype=np.uint8, count=stride, offset=y * (stride + 1) + 1).astype(np.int32)
        if f == 0:
            cur = line
        elif f == 1:
            cur = np.cumsum(line.reshape(-1, bpp), axis=0).reshape(-1) % 256
        elif f == 2:
            cur = (line + prev) % 256
        elif f in (3, 4):
            cur = np.zeros(stride, dtype=np.int32)
            for x in range(stride):
                a = cur[x - bpp] if x >= bpp else 0
                b = prev[x]
                if f == 3:
                    cur[x] = (line[x] + (a + b) // 2) % 256
                else:
                    c = prev[x - bpp] if x >= bpp else 0
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                    cur[x] = (line[x] + pr) % 256
        else:
            return None
        img[y] = cur
        prev = cur
    px = img.reshape(h, w, bpp)
    if ctype == 3:
        pal = next((b for t, b in chunks if t == b"PLTE"), b"")
        lut = np.frombuffer(pal, dtype=np.uint8).reshape(-1, 3)
        return lut[np.clip(px[..., 0], 0, len(lut) - 1)]
    if ctype in (0, 4):
        return np.repeat(px[..., :1], 3, axis=2)
    return px[..., :3]


def _try_pillow(data: bytes) -> np.ndarray | None:
    try:
        import io  # noqa: PLC0415

        from PIL import Image  # type: ignore[import-not-found]  # noqa: PLC0415

        im = Image.open(io.BytesIO(data))
        im.thumbnail((512, 512))
        return np.asarray(im.convert("RGB"))
    except Exception:  # noqa: BLE001 - Pillow optional / undecodable
        return None


# ---------------------------------------------------------------------------- explainable colour statistics
COLOUR_REGIONS = {
    "dark_red_purple_black": "very dark or deep red/purple pixels (often associated with ripe fruitlets - heuristic only)",
    "orange_red": "orange/red pixels (often associated with ripe/over-ripe fruitlets - heuristic only)",
    "green_dark_green": "green pixels (unripe fruitlets, stalk, or background vegetation - ambiguous)",
    "brown_yellow": "brown/yellow pixels (stalk, empty spikelets, soil, or lighting - ambiguous)",
    "other_background": "everything else (sky, ground, truck bed, white balance artefacts)",
}


def colour_stats(rgb: np.ndarray) -> dict:
    step = max(1, int(np.ceil(max(rgb.shape[:2]) / 256)))
    a = rgb[::step, ::step].astype(np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(axis=2), a.min(axis=2)
    v, s = mx, np.where(mx > 0, (mx - mn) / np.maximum(mx, 1e-6), 0)
    d = np.maximum(mx - mn, 1e-6)
    hue = np.where(mx == r, ((g - b) / d) % 6, np.where(mx == g, (b - r) / d + 2, (r - g) / d + 4)) * 60
    cls = np.full(v.shape, 4, dtype=np.int8)
    cls[(hue >= 60) & (hue < 170) & (s > 0.25) & (v > 0.15)] = 2
    cls[((hue >= 20) & (hue < 60)) & (s > 0.3)] = 3
    cls[((hue < 20) | (hue >= 330)) & (s > 0.35) & (v > 0.35)] = 1
    cls[(v < 0.22) | (((hue >= 270) | (hue < 15)) & (v < 0.4) & (s > 0.2))] = 0
    names = list(COLOUR_REGIONS)
    frac = {names[i]: round(float(np.mean(cls == i)), 4) for i in range(5)}
    gh, gw = 12, 12
    ys = np.linspace(0, cls.shape[0], gh + 1).astype(int)
    xs = np.linspace(0, cls.shape[1], gw + 1).astype(int)
    grid = []
    for i in range(gh):
        row = []
        for j in range(gw):
            cell = cls[ys[i] : ys[i + 1], xs[j] : xs[j + 1]]
            row.append(names[int(np.bincount(cell.ravel(), minlength=5).argmax())] if cell.size else None)
        grid.append(row)
    hist = np.histogram(hue[s > 0.2], bins=12, range=(0, 360))[0]
    return {
        "analysed_pixels": int(cls.size), "mean_rgb": [round(float(x) * 255, 1) for x in (r.mean(), g.mean(), b.mean())],
        "mean_brightness": round(float(v.mean()), 4), "mean_saturation": round(float(s.mean()), 4),
        "hue_histogram_30deg": [int(x) for x in hist], "colour_region_fractions": frac, "colour_region_definitions": COLOUR_REGIONS,
        "dominant_region_grid_12x12": grid,
        "method": "HSV thresholds on a <=256 px downsample; grid = most frequent colour region per cell (visual explanation)",
    }


# ---------------------------------------------------------------------------- storage with quota
def store(content_type: str, data: bytes) -> str:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{EXT[content_type]}"
    path = UPLOAD_DIR / name
    files = sorted((p for p in UPLOAD_DIR.iterdir() if p.is_file()), key=lambda p: p.stat().st_mtime)
    total = sum(p.stat().st_size for p in files)
    while files and (len(files) >= QUOTA_FILES or total + len(data) > QUOTA_BYTES):
        old = files.pop(0)
        total -= old.stat().st_size
        old.unlink(missing_ok=True)
    assert path.parent == UPLOAD_DIR  # random name, never client-controlled
    path.write_bytes(data)
    return name


def assess(content_type: str, data: bytes) -> dict:
    clean, w, h = sanitize(content_type, data)
    try:
        rgb = decode_png(clean) if content_type == "image/png" else None
    except (zlib.error, ValueError, IndexError, struct.error, OverflowError, MemoryError):
        # QA-14: structurally valid chunks (CRC ok) around an undecodable IDAT stream / palette used to end in HTTP 500
        _reject("corrupt_image", "The image data could not be decoded")
    stored = store(content_type, clean)  # only stored once it is known to decode (or to be a format we do not decode)
    if rgb is None:
        rgb = _try_pillow(clean)
    if rgb is not None and (w is None or h is None):
        h, w = rgb.shape[:2]
    stats = {"stored_as": stored, "metadata_stripped": True, "bytes_after_stripping": len(clean)}
    if rgb is not None:
        stats.update(colour_stats(rgb))
        text = ("Colour-region summary only (research prototype): " + ", ".join(
            f"{k.replace('_', ' ')} {v:.0%}" for k, v in stats["colour_region_fractions"].items()) +
                ". This is NOT a ripeness grade; a human grader must assess the bunch.")
    else:
        stats["colour_stats_unavailable"] = ("Pixel decoding for this format/size needs Pillow (not installed in this demo); "
                                             "only metadata validation and stripping were performed.")
        text = "Image accepted and metadata stripped; no colour statistics computed for this format. Not a grade - human review required."
    return {"width": w, "height": h, "image_stats": stats, "assessment": text}


def protocol() -> dict:
    return {
        "status": "prototype",
        "dataset_requirements": [
            "No properly licensed, labelled FFB image dataset was available for this demo; none was used.",
            ">= 3,000 bunch images per mill (pilot), >= 300 per class, from >= 3 mills / seasons / supplier groups to avoid site bias",
            "Images captured at the grading platform under the operating lighting, linked to the official manual grade and weighbridge ticket",
            "Licence/consent from the mill and suppliers; no faces or plates; retention policy",
            "Hold-out by date and by supplier (temporal + group split) - never random image split",
        ],
        "camera_position": "Fixed industrial camera 2.5-3 m above the grading floor / truck bed, perpendicular, covering a 2 x 2 m area; "
                           "second oblique camera (45 deg) for bunch underside; calibration target in view.",
        "lighting": "Diffuse LED lighting (5000-6500 K, CRI > 90) under a canopy to remove sun/shadow; colour checker card for white "
                    "balance; exposure locked; night operation with the same lights.",
        "labelling_protocol": [
            "Two certified graders label each bunch independently using the mill's grading standard; disagreements adjudicated by a senior grader",
            "Record inter-rater agreement (Cohen's kappa) - the model cannot be judged better than human agreement",
            "Label per bunch with bounding box + class; flag occlusion, dirt, and image quality",
            "Audit 5 % of labels monthly",
        ],
        "class_definitions": {
            "unripe": "Black/dark purple bunch, no or very few loose fruitlets (mill standard threshold)",
            "under_ripe": "Reddish-black, fewer loose fruitlets than the ripe threshold",
            "ripe": "Reddish-orange, loose fruitlets at or above the mill threshold",
            "over_ripe": "Dark red/orange with many loose fruitlets, partly rotten",
            "empty_bunch": "Mostly empty spikelets",
            "long_stalk": "Stalk longer than the mill limit (separate attribute)",
        },
        "evaluation_plan": [
            "Per-class precision/recall, macro-F1 and confusion matrix on the temporal + supplier hold-out",
            "Compare against inter-grader agreement and a colour-histogram baseline",
            "Calibration of class probabilities (reliability diagram) before any automated use",
            "Robustness: lighting, rain, dirt, occlusion, camera shift slices",
        ],
        "pilot_validation_plan": [
            "Shadow mode for 4-8 weeks: model suggests, graders decide; log disagreements",
            "Success criteria agreed with QC before the pilot (e.g. kappa vs graders >= human-human kappa)",
            "Measure business effect separately (deduction disputes, grading time) - not assumed",
            "Human grader keeps the final decision; supplier dispute process unchanged",
        ],
    }



