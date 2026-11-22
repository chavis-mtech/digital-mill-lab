"""The generator's parameter snapshot must match the researcher's DOMAIN_PARAMETERS.json; deviations stay in range."""

from __future__ import annotations

import json

import pytest

from app.config import REPO_ROOT
from app.seed.assumptions import ASSUMED, DEVIATIONS, P
from app.seed.params import PARAMS, PROFILES

SRC = REPO_ROOT / "docs/business/DOMAIN_PARAMETERS.json"


@pytest.mark.skipif(not SRC.exists(), reason="docs tree not present (e.g. Docker image)")
def test_snapshot_matches_domain_parameters():
    d = json.loads(SRC.read_text(encoding="utf-8"))
    src = {p["key"]: (p["nominal"], p["min"], p["max"], p["unit"], p["category"], p["source_id"], p["confidence"]) for p in d["parameters"]}
    assert src == PARAMS, "params.py is stale: run scripts/seed/snapshot_params.py and re-seed"
    assert {p["key"]: p["values"] for p in d["profiles"]} == PROFILES


def test_deviations_are_known_keys_inside_sourced_ranges():
    for key, (val, reason) in DEVIATIONS.items():
        assert key in PARAMS, key
        _, lo, hi, *_ = PARAMS[key]
        assert lo <= val <= hi, f"{key}={val} outside [{lo}, {hi}]"
        assert len(reason) > 40
        assert P(key) == val


def test_assumptions_are_categorised():
    allowed = {"Engineering Assumption", "Industry Practice", "Synthetic Demonstration Data"}
    for key, (cat, _val, reason) in ASSUMED.items():
        assert cat in allowed, key
        assert reason
