"""Full 120-day build + validation (opt-in: DML_FULL_SEED_TEST=1; ~15 s). Compares with MANIFEST.json if present."""

from __future__ import annotations

import json
import os

import pytest

from app.db.session import get_engine
from app.seed.build import MANIFEST_PATH, build
from app.seed.validate import validate

pytestmark = pytest.mark.skipif(os.environ.get("DML_FULL_SEED_TEST") != "1", reason="set DML_FULL_SEED_TEST=1 to run the full build")


def test_full_build_validates_and_matches_manifest(tmp_path):
    url = f"sqlite:///{tmp_path / 'full.db'}"
    s = build(url, days=120, write_manifest=False, log=lambda *_: None)
    manifest = json.loads(MANIFEST_PATH.read_text()) if MANIFEST_PATH.exists() else None
    rep = validate(get_engine(url), manifest)
    assert rep.passed, [f"{c.name}: {c.detail}" for c in rep.checks if not c.ok and c.level == "fail"]
    assert s["timing_s"]["total"] < 60
    if manifest and manifest.get("seed") == s["seed"] and manifest.get("anchor") == s["anchor"]:
        assert s["checksum_sha256"] == manifest["checksum_sha256"]
