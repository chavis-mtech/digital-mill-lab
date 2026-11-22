"""DML-085..090: ROI formulas recomputed by hand, no double counting, disclaimer, sensitivity, exports."""

from __future__ import annotations

import pytest

from app.schemas.roi import ROI_DISCLAIMER, RoiCase, RoiInputs
from app.services.roi import BOUNDS, CASE_MULTIPLIERS, compute_case

from .conftest import FOCUS, err, hdr

DISCLAIMER = "Illustrative business scenario based on adjustable assumptions, not verified financial results of any company."
INP = dict(
    daily_ffb_t=1000, operating_days=300, current_oer_pct=20.0, target_oer_pct=20.5, cpo_price_thb_per_kg=35, downtime_h_per_month=20, processing_capacity_tph=60,
    energy_cost_thb_per_year=5_000_000, maintenance_expense_thb_per_year=8_000_000, efficiency_improvement_pct=5, downtime_reduction_pct=10,
    implementation_cost_thb=6_000_000, recurring_cost_thb_per_year=1_200_000,
)


def inp(**over) -> RoiInputs:
    return RoiInputs(**{**INP, **over})


def test_disclaimer_is_the_exact_required_text():
    assert ROI_DISCLAIMER == DISCLAIMER


def test_expected_case_by_hand():
    c = compute_case(inp(), RoiCase.expected)
    ffb_base = 1000 * 300  # 300,000 t
    cpo_oer = ffb_base * 0.5 / 100  # +0.5 pp on the baseline FFB = 1,500 t
    recovered_h = 20 * 12 * 0.10  # 24 h (headroom (24 - 1000/60) x 300 = 2,200 h is not binding)
    cpo_dt = recovered_h * 60 * 20.0 / 100  # 1,440 t FFB x current OER = 288 t
    gross = (cpo_oer + cpo_dt) * 1000 * 35
    assert (c["cpo_oer_t"], c["recovered_h"], c["cpo_downtime_t"]) == (1500.0, 24.0, pytest.approx(288.0))
    assert c["additional_cpo_t"] == pytest.approx(1788.0) and c["gross_value_thb"] == pytest.approx(gross) == pytest.approx(62_580_000)
    assert c["cost_avoidance_thb"] == pytest.approx((5_000_000 + 8_000_000) * 0.05) == 650_000
    assert c["net_benefit_year1_thb"] == pytest.approx(gross + 650_000 - 6_000_000 - 1_200_000) == pytest.approx(56_030_000)
    assert c["payback_months"] == pytest.approx(6_000_000 / ((gross + 650_000 - 1_200_000) / 12))


def test_no_double_counting_separate_ffb_bases():
    full = compute_case(inp(), RoiCase.expected)
    only_oer = compute_case(inp(downtime_reduction_pct=0), RoiCase.expected)
    only_dt = compute_case(inp(target_oer_pct=20.0), RoiCase.expected)
    assert only_oer["cpo_downtime_t"] == 0 and only_oer["additional_cpo_t"] == only_oer["cpo_oer_t"] == pytest.approx(300_000 * 0.5 / 100)
    assert only_dt["cpo_oer_t"] == 0 and only_dt["additional_cpo_t"] == only_dt["cpo_downtime_t"] == pytest.approx(24 * 60 * 20.0 / 100)
    # the two levers add exactly - no cross term, no overlap
    assert full["additional_cpo_t"] == pytest.approx(only_oer["additional_cpo_t"] + only_dt["additional_cpo_t"])
    assert full["gross_value_thb"] == pytest.approx(only_oer["gross_value_thb"] + only_dt["gross_value_thb"])
    # recovered-hour FFB is valued at the CURRENT OER: applying the target OER to it would overcount
    naive = full["cpo_oer_t"] + full["ffb_recovered_t"] * 20.5 / 100
    assert full["additional_cpo_t"] < naive
    # the OER uplift never touches the recovered FFB: its base is the baseline FFB only
    assert full["ffb_base_t"] == 300_000 and full["cpo_oer_t"] == pytest.approx(full["ffb_base_t"] * full["delta_oer_pp"] / 100)


def test_recovered_hours_cannot_exceed_free_hours_in_the_day():
    c = compute_case(inp(daily_ffb_t=1400, downtime_h_per_month=744, downtime_reduction_pct=100), RoiCase.expected)  # 1400/60 = 23.3 h/day used
    assert c["capped"] is True and c["recovered_h"] == pytest.approx((24 - 1400 / 60) * 300)
    assert c["recovered_h"] < c["recovered_h_raw"]
    c0 = compute_case(inp(daily_ffb_t=1440, downtime_reduction_pct=100), RoiCase.expected)  # already 24 h/day
    assert c0["recovered_h"] == 0 and c0["cpo_downtime_t"] == 0


def test_cases_baseline_zero_and_monotonic():
    res = {c: compute_case(inp(), c) for c in RoiCase}
    b = res[RoiCase.baseline]
    assert (b["additional_cpo_t"], b["gross_value_thb"], b["cost_avoidance_thb"], b["implementation_thb"], b["recurring_thb"], b["net_benefit_year1_thb"]) == (0, 0, 0, 0, 0, 0) and b["payback_months"] is None
    order = [RoiCase.baseline, RoiCase.conservative, RoiCase.expected, RoiCase.optimistic]
    gross = [res[c]["gross_value_thb"] for c in order]
    assert gross == sorted(gross) and len(set(gross)) == 4
    assert res[RoiCase.conservative]["implementation_thb"] == pytest.approx(6_000_000 * CASE_MULTIPLIERS["conservative"]["implementation_cost_factor"])
    assert res[RoiCase.expected]["multipliers"] == CASE_MULTIPLIERS["expected"]


def test_payback_none_when_run_rate_not_positive():
    c = compute_case(inp(target_oer_pct=20.0, downtime_reduction_pct=0, efficiency_improvement_pct=0), RoiCase.expected)
    assert c["run_rate_thb"] < 0 and c["payback_months"] is None
    assert compute_case(inp(implementation_cost_thb=0), RoiCase.expected)["payback_months"] == 0.0


# ---------------------------------------------------------------- API
def _post(client, path, body, role="public_viewer"):
    return client.post(f"/api/v1/roi/{path}", params={"as_of": FOCUS}, json=body, headers=hdr(role, None))


def test_calculate_api_returns_four_cases_formulas_and_disclaimer(client):
    r = _post(client, "calculate", INP)
    assert r.status_code == 200, r.text
    j = r.json()
    assert [c["case"] for c in j["cases"]] == ["baseline", "conservative", "expected", "optimistic"]
    assert j["disclaimer"]["text_en"] == DISCLAIMER and j["disclaimer"]["text_th"] and j["provenance"]["kind"] == "what_if"
    exp = [c for c in j["cases"] if c["case"] == "expected"][0]
    f = {x["key"]: x for x in j["formulas"]}
    assert f["expected.gross_value_thb"]["result"] == exp["gross_value_uplift_thb"] == 62_580_000
    assert f["expected.cpo_oer_t"]["inputs"]["delta_oer_pp"] == 0.5 and f["expected.recovered_h"]["result"] == 24.0
    assert len([x for x in j["formulas"] if x["key"].startswith("optimistic.")]) == 11 and "separate" in j["double_counting_note"]
    assert any(a["key"] == "separate_bases" for a in j["assumptions"]) and {a["tag"] for a in j["assumptions"]} <= {"engineering_assumption"}


def test_defaults_come_from_the_synthetic_baseline(client):
    d = _post_get(client)
    i = d["inputs"]
    assert 800 < i["daily_ffb_t"] < 1000 and 18 < i["current_oer_pct"] < 19 and i["target_oer_pct"] == pytest.approx(i["current_oer_pct"] + 0.10, abs=0.011) and i["processing_capacity_tph"] == 60
    assert d["disclaimer"]["text_en"] == DISCLAIMER and set(d["case_multipliers"]) == {"baseline", "conservative", "expected", "optimistic"}
    tags = {a["key"]: a["tag"] for a in d["assumptions"]}
    assert tags["implementation_cost_thb"] == "engineering_assumption" and tags["daily_ffb_t"] == "synthetic_demonstration_data"
    assert _post(client, "calculate", i).status_code == 200  # defaults are valid inputs


def _post_get(client):
    r = client.get("/api/v1/roi/defaults", params={"as_of": FOCUS}, headers=hdr("public_viewer", None))
    assert r.status_code == 200
    return r.json()


def test_sensitivity_tornado_sorted_and_clamped(client):
    j = _post(client, "sensitivity", {"inputs": INP, "swing_pct": 20}).json()
    swings = [abs(b["net_benefit_high_thb"] - b["net_benefit_low_thb"]) for b in j["bars"]]
    assert swings == sorted(swings, reverse=True) and j["base_net_benefit_thb"] == 56_030_000
    price = [b for b in j["bars"] if b["variable"] == "cpo_price_thb_per_kg"][0]
    assert price["low_value"] == 28.0 and price["high_value"] == 42.0
    # price is linear: net = base + gross*(+-20%)
    assert price["net_benefit_high_thb"] - price["net_benefit_low_thb"] == pytest.approx(0.4 * 62_580_000, rel=1e-9)
    tgt = [b for b in j["bars"] if b["variable"] == "target_oer_pct"][0]
    assert "improvement" in tgt["note"] and tgt["low_value"] == pytest.approx(20.4) and tgt["high_value"] == pytest.approx(20.6)  # the 0.5 pp gap swings, not the 20% level
    wide = _post(client, "sensitivity", {"inputs": INP, "variables": ["efficiency_improvement_pct", "downtime_reduction_pct"], "swing_pct": 100}).json()
    assert {b["variable"]: b["high_value"] for b in wide["bars"]} == {"efficiency_improvement_pct": 10.0, "downtime_reduction_pct": 20.0}
    clamp = _post(client, "sensitivity", {"inputs": {**INP, "efficiency_improvement_pct": 90}, "variables": ["efficiency_improvement_pct"], "swing_pct": 50}).json()
    assert clamp["bars"][0]["high_value"] == 100  # clamped to the valid bound, not 135
    r = _post(client, "sensitivity", {"inputs": INP, "variables": ["nonsense"]})
    assert r.status_code == 422 and err(r) == "unknown_variable"
    assert set(BOUNDS) == {f for f in RoiInputs.model_fields}


@pytest.mark.parametrize("over", [{"daily_ffb_t": 0}, {"daily_ffb_t": 10001}, {"operating_days": 400}, {"current_oer_pct": 36}, {"efficiency_improvement_pct": 101}, {"downtime_h_per_month": 745}, {"cpo_price_thb_per_kg": -1}, {"implementation_cost_thb": -1}])
def test_roi_inputs_are_bounded(client, over):
    r = _post(client, "calculate", {**INP, **over})
    assert r.status_code == 422 and err(r) == "validation_error"


def test_exports_carry_disclaimer_and_formulas(client):
    for fmt, ext in (("csv", "csv"), ("markdown", "md"), ("json", "json")):
        r = _post(client, "export", {"inputs": INP, "format": fmt})
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["format"] == fmt and d["filename"].endswith(f".{ext}") and DISCLAIMER in d["content"] and d["disclaimers"][0]["text_en"] == DISCLAIMER
        assert "expected.gross_value_thb" in d["content"] or fmt == "markdown"
    assert "Formulas" in _post(client, "export", {"inputs": INP, "format": "markdown"}).json()["content"]
    r = _post(client, "export/printable", {"inputs": INP})
    doc = r.json()
    assert r.status_code == 200 and doc["media_type"] == "text/html" and doc["filename"].endswith(".html") and doc["disclaimers"][0]["text_en"] == DISCLAIMER
    assert doc["html"].count(DISCLAIMER) == 2 and "@media print" in doc["html"] and "<script" not in doc["html"] and doc["html"].startswith("<!doctype html>")
    assert "Not an official system of any company" in doc["html"]


def test_roi_calculation_is_available_to_every_role(client):
    for role in ("public_viewer", "executive", "logistics_officer", "system_admin"):
        assert _post(client, "calculate", INP, role).status_code == 200 and _post(client, "export", {"inputs": INP}, role).status_code == 200
