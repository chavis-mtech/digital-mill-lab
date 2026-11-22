"""Deterministic answer composer (DML-076): writes the answer ONLY from tool results.

Every number printed here is read from a ToolResult fact (or echoed user input) so the grounding verifier can match it.
Causal wording is always "possible contributing factors (statistical association, not proven cause)". Designed-intent
text of scenario_runs is never read. ML output is described with what the model is and its measured limits.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.copilot.tools import ToolResult

CAUSAL_EN = "possible contributing factors (statistical association, not proven cause)"
CAUSAL_TH = "ปัจจัยที่อาจเกี่ยวข้อง (ความสัมพันธ์เชิงสถิติ ไม่ใช่สาเหตุที่พิสูจน์แล้ว)"
WO_SCREEN = "/demo/maintenance/work-orders"

CAPABILITIES = {
    "en": ["Why did OER drop today?", "Which machine should I inspect first?", "When is downtime highest?",
           "What if we cut downtime by 2 hours?", "Why did energy per tonne rise?", "How many trucks are waiting?",
           "Give me a daily summary", "Prioritise the plant issues", "Prepare an executive meeting brief", "How is OER defined?"],
    "th": ["ทำไม OER วันนี้ลดลง", "ควรตรวจเครื่องไหนก่อน", "downtime สูงสุดช่วงเวลาใด", "ถ้าลด downtime 2 ชั่วโมงจะได้อะไร",
           "ทำไมพลังงานต่อตันสูงขึ้น", "รถบรรทุกรอกี่คัน", "สรุปวันนี้", "จัดลำดับปัญหาในโรงงาน", "สรุปสำหรับประชุมผู้บริหาร", "OER คืออะไร"],
}  # fmt: skip


INTENT_LABELS = {
    "oer_value": ("OER / production figures", "ตัวเลข OER และการผลิต"), "oer_why": ("why OER changed", "สาเหตุที่ OER เปลี่ยน"),
    "inspect_first": ("which equipment to inspect first", "เครื่องที่ควรตรวจก่อน"), "equipment_status": ("health of one equipment item", "สถานะเครื่องจักรเครื่องเดียว"),
    "downtime_when": ("when/where downtime happens", "ช่วงเวลาและเครื่องที่หยุด"), "downtime_effect": ("what-if: less downtime", "what-if: ลดการหยุดเครื่อง"),
    "oer_what_if": ("what-if: OER change", "what-if: OER เปลี่ยน"), "energy_why": ("energy use per tonne", "การใช้พลังงานต่อตัน"),
    "trucks_waiting": ("truck queue now", "คิวรถตอนนี้"), "daily_summary": ("daily summary", "สรุปประจำวัน"), "prioritize": ("prioritised issues", "จัดลำดับปัญหา"),
    "exec_brief": ("executive brief", "สรุปผู้บริหาร"), "doc_search": ("sample-document lookup", "ค้นเอกสารตัวอย่าง"),
    "supplier_trace": ("supplier trace of a CPO lot", "ย้อนรอยซัพพลายเออร์ของล็อต"), "forecast": ("a forecast request", "คำขอพยากรณ์"),
}  # fmt: skip


def label(intent: str, lang: str) -> str:
    en, th = INTENT_LABELS.get(intent, (intent, intent))
    return th if lang == "th" else en


def interpreted_as(intent: str, lang: str) -> str:
    return _L(lang, f"Interpreted as: {label(intent, lang)}.", f"ตีความว่า: {label(intent, lang)}")


def clarify(options: list[str], lang: str) -> Composition:
    a, b = (label(o, lang) for o in options[:2])
    return Composition(_L(lang, f"I am not sure what you are asking, so I will not guess. Did you mean (1) {a} or (2) {b}? Please rephrase or pick one.",
                          f"ไม่แน่ใจว่าต้องการถามเรื่องใด จึงจะไม่เดาคำตอบ หมายถึง (1) {a} หรือ (2) {b} กรุณาพิมพ์ใหม่หรือเลือกหนึ่งข้อ"),
                       [CAPABILITIES[lang][0], CAPABILITIES[lang][1]], uncertainty="ambiguous_question")  # fmt: skip


def forecast(R: dict[str, ToolResult], lang: str) -> Composition:
    e = R.get("get_energy_summary")
    if _ok(e) and "get_oer_trend" not in R:
        mae, bmae = e.fact("ml_energy_forecast_mae"), e.fact("ml_energy_forecast_mae_baseline")
        kw = e.data["kpis"].get("kwh_per_t_ffb", {})
        head = _L(lang, "I do not produce a reliable forecast: the energy forecast model in this demo does not beat its naive baseline"
                        + (f" (hourly MAE {f(mae)} vs {f(bmae)} kWh/h, held-out, synthetic data)" if mae is not None and bmae is not None else "") + ". ",
                  "ผู้ช่วยไม่ให้ค่าพยากรณ์ที่เชื่อถือได้ เพราะโมเดลพยากรณ์พลังงานในเดโมนี้ยังไม่ดีกว่า baseline แบบง่าย"
                  + (f" (MAE รายชั่วโมง {f(mae)} เทียบ {f(bmae)} kWh/ชม. ข้อมูลทดสอบสังเคราะห์)" if mae is not None and bmae is not None else "") + " ")  # fmt: skip
        body = _L(lang, f"Measured instead: electricity {f(kw.get('value'))} kWh/t so far today vs {f(kw.get('previous'))} kWh/t in the previous period.",
                  f"ค่าที่วัดได้: ไฟฟ้า {f(kw.get('value'))} kWh/ตัน วันนี้ เทียบกับ {f(kw.get('previous'))} kWh/ตัน ช่วงก่อนหน้า")
        return Composition(head + body, [_L(lang, "Why did energy per tonne rise?", "ทำไมพลังงานต่อตันสูงขึ้น")], uncertainty="no_forecast")
    t = R.get("get_oer_trend")
    if not _ok(t):
        return Composition(_L(lang, "I do not produce a reliable forecast, and no measured OER is available at the demo clock.",
                              "ผู้ช่วยไม่ให้ค่าพยากรณ์ที่เชื่อถือได้ และไม่มีค่า OER ที่วัดได้ ณ เวลาเดโม"), uncertainty="no_forecast")  # fmt: skip
    mae, bmae = t.fact("ml_oer_forecast_mae"), t.fact("ml_oer_forecast_mae_baseline")
    head = _L(lang, "I do not produce a reliable forecast: the OER forecast models in this demo do not beat a naive baseline"
                    + (f" (hourly MAE {f(mae, 3)} vs {f(bmae, 3)} pp, held-out, synthetic data)" if mae is not None and bmae is not None else "") + ". ",
              "ผู้ช่วยไม่ให้ค่าพยากรณ์ที่เชื่อถือได้ เพราะโมเดลพยากรณ์ OER ในเดโมนี้ยังไม่ดีกว่า baseline แบบง่าย"
              + (f" (MAE รายชั่วโมง {f(mae, 3)} เทียบ {f(bmae, 3)} จุด ข้อมูลทดสอบสังเคราะห์)" if mae is not None and bmae is not None else "") + " ")  # fmt: skip
    oer, exp, lo, hi = t.fact("oer_today"), t.fact("expected_oer_today"), t.fact("band_low_today"), t.fact("band_high_today")
    days = [x for x in t.data.get("daily", []) if x["oer_pct"] is not None][-7:]
    series = ", ".join(f"{x['date'][5:]} {f(x['oer_pct'])}%" for x in days)
    body = _L(lang, f"Measured instead: OER so far today {f(oer)}%, expected (trailing 28-day) {f(exp)}%"
                    + (f", normal range {f(lo)}-{f(hi)}% (expected +/- 2 s.d. of daily OER)" if lo is not None and hi is not None else "") + f". Recent days: {series}.",
              f"ค่าที่วัดได้: OER วันนี้ถึงตอนนี้ {f(oer)}% ค่าคาดหมาย (เฉลี่ย 28 วัน) {f(exp)}%"
              + (f" ช่วงปกติ {f(lo)}-{f(hi)}% (ค่าคาดหมาย +/- 2 s.d. ของ OER รายวัน)" if lo is not None and hi is not None else "") + f" วันล่าสุด: {series}")  # fmt: skip
    return Composition(head + body, [_L(lang, "Why did OER drop today?", "ทำไม OER วันนี้ลดลง")], uncertainty="no_forecast")


@dataclass
class Composition:
    text: str
    followups: list[str] = field(default_factory=list)
    uncertainty: str | None = None
    refused: bool = False
    refusal_reason: str | None = None


def f(v: float | None, n: int = 2) -> str:
    if v is None:
        return "n/a"
    if n == 0:
        return f"{v:,.0f}"
    return f"{v:,.{n}f}"


def _L(lang: str, en: str, th: str) -> str:
    return th if lang == "th" else en


def _ok(r: ToolResult | None) -> bool:
    return r is not None and r.status == "ok"


# ------------------------------------------------------------------ per-intent composers
def oer_value(R: dict[str, ToolResult], lang: str) -> Composition:
    p = R.get("get_production_summary")
    if not p or p.status != "ok":
        return Composition(_L(lang, "No processed FFB is recorded for that day up to the demo clock, so OER cannot be computed.",
                              "ยังไม่มีข้อมูลการหีบปาล์มของวันดังกล่าวจนถึงเวลาเดโม จึงคำนวณ OER ไม่ได้"), uncertainty="no_data")  # fmt: skip
    k = p.data["kpis"]
    d = p.data["business_date"]

    def g(key: str, what: str = "value") -> float | None:
        return (k.get(key) or {}).get(what)

    oer, prev = g("oer_pct"), g("oer_pct", "previous")
    txt = _L(lang,
             f"OER on {d} (complete hours up to the demo clock): {f(oer)}% (previous day, same span: {f(prev)}%). "
             f"FFB processed {f(g('ffb_processed_t'), 1)} t, CPO {f(g('cpo_t'), 1)} t, KER {f(g('ker_pct'))}%, "
             f"throughput {f(g('throughput_tph'), 1)} t/h, downtime {f(g('downtime_h'), 1)} h.",
             f"OER วันที่ {d} (ชั่วโมงที่ครบแล้วจนถึงเวลาเดโม): {f(oer)}% (วันก่อนหน้าช่วงเวลาเดียวกัน {f(prev)}%) "
             f"หีบ FFB {f(g('ffb_processed_t'), 1)} ตัน ได้ CPO {f(g('cpo_t'), 1)} ตัน KER {f(g('ker_pct'))}% "
             f"อัตราการหีบ {f(g('throughput_tph'), 1)} ตัน/ชม. หยุดเครื่อง {f(g('downtime_h'), 1)} ชม.")  # fmt: skip
    t = R.get("get_oer_trend")
    if _ok(t) and t.data.get("daily"):
        days = t.data["daily"][-7:]
        series = ", ".join(f"{x['date'][5:]} {f(x['oer_pct'])}%" for x in days if x["oer_pct"] is not None)
        txt += _L(lang, f" Daily OER: {series}.", f" OER รายวัน: {series}")
    return Composition(txt, [_L(lang, "Why did OER change?", "ทำไม OER เปลี่ยนไป"), _L(lang, "OER yesterday", "OER เมื่อวาน")])


def oer_why(R: dict[str, ToolResult], lang: str) -> Composition:
    t = R.get("get_oer_trend")
    if not _ok(t):
        return oer_value(R, lang)
    parts = []
    gap = t.fact("r1_gap_pp")
    if gap is not None:
        parts.append(_L(lang,
            f"OER so far today is {f(t.fact('r1_oer_today'))}%, {f(gap)} pp below the trailing 28-day OER of {f(t.fact('r1_oer_reference'))}% "
            f"(normal range {f(t.fact('r1_normal_low'))}-{f(t.fact('r1_normal_high'))}% = 28-day OER +/- 2 s.d. of daily OER).",
            f"OER วันนี้ถึงตอนนี้ {f(t.fact('r1_oer_today'))}% ต่ำกว่า OER เฉลี่ย 28 วันย้อนหลัง {f(t.fact('r1_oer_reference'))}% อยู่ {f(gap)} จุด "
            f"(ช่วงปกติ {f(t.fact('r1_normal_low'))}-{f(t.fact('r1_normal_high'))}% = ค่าเฉลี่ย 28 วัน +/- 2 s.d. ของ OER รายวัน)"))  # fmt: skip
        if t.data["factors"]:
            fl = "; ".join(f"{x['label']} {f(x['observed'])} {x['unit']} vs {f(x['reference_mean'])} {x['unit']}" for x in t.data["factors"][:6])
            parts.append(_L(lang, f"{CAUSAL_EN.capitalize()}: {fl} (today vs mean of the reference days; each deviates by more than 2 s.d.).",
                            f"{CAUSAL_TH}: {fl} (วันนี้เทียบกับค่าเฉลี่ยของวันอ้างอิง แต่ละตัวเบี่ยงเกิน 2 s.d.)"))  # fmt: skip
        else:
            parts.append(_L(lang, "No single process signal deviates by more than 2 s.d.; lab samples and FFB mix should be checked.",
                            "ไม่มีสัญญาณกระบวนการใดเบี่ยงเกิน 2 s.d. ควรตรวจตัวอย่างแล็บและสัดส่วนผลปาล์ม"))  # fmt: skip
    else:
        oer, exp, g2 = t.fact("oer_today"), t.fact("expected_oer_today"), t.fact("oer_gap_pp")
        if oer is None:
            return Composition(_L(lang, "No processed hours yet today, so there is no OER to explain.", "วันนี้ยังไม่มีชั่วโมงที่หีบปาล์ม จึงยังไม่มี OER ให้อธิบาย"),
                               uncertainty="no_data")  # fmt: skip
        parts.append(_L(lang,
            f"OER so far today is {f(oer)}% vs the expected (trailing 28-day) {f(exp)}%, a difference of {f(g2)} pp. That is within the 0.3 pp "
            "threshold the insight rule uses, so the data does not show a significant OER drop today.",
            f"OER วันนี้ถึงตอนนี้ {f(oer)}% เทียบกับค่าคาดหมาย (เฉลี่ย 28 วัน) {f(exp)}% ต่างกัน {f(g2)} จุด ซึ่งอยู่ในเกณฑ์ 0.3 จุดของกฎ insight "
            "ข้อมูลจึงไม่แสดงว่า OER ลดลงอย่างมีนัยสำคัญวันนี้"))  # fmt: skip
        t.add("threshold_pp", "Insight-rule OER gap threshold", 0.3, "pp")
    al = R.get("get_active_alerts")
    if _ok(al):
        prod = [a for a in al.data["alerts"] if a["module"] == "production"][:2]
        if prod:
            parts.append(_L(lang, "Related active production alerts (advisory, need verification): " + "; ".join(f"{a['code']} {a['title']}" for a in prod) + ".",
                            "การแจ้งเตือนฝ่ายผลิตที่เกี่ยวข้อง (เป็นคำแนะนำ ต้องตรวจสอบ): " + "; ".join(f"{a['code']} {a['title']}" for a in prod)))  # fmt: skip
    mae, bmae = t.fact("ml_oer_forecast_mae"), t.fact("ml_oer_forecast_mae_baseline")
    if mae is not None and bmae is not None:
        parts.append(_L(lang, f"The ML OER forecast (regression model) does not beat its naive baseline (MAE {f(mae, 3)} vs {f(bmae, 3)} pp on held-out synthetic data), "
                              "so no model attribution is used as a reason.",
                        f"โมเดลพยากรณ์ OER (regression) ยังไม่ดีกว่า baseline แบบง่าย (MAE {f(mae, 3)} เทียบ {f(bmae, 3)} จุด บนข้อมูลทดสอบสังเคราะห์) "
                        "จึงไม่ใช้ผลอธิบายของโมเดลเป็นเหตุผล"))  # fmt: skip
    else:
        parts.append(_L(lang, "No ML model attribution is used as a reason.", "ไม่ใช้ผลอธิบายของโมเดล ML เป็นเหตุผล"))
    return Composition(" ".join(parts), [_L(lang, "Which machine should I inspect first?", "ควรตรวจเครื่องไหนก่อน"),
                                         _L(lang, "What if OER improves by 0.5 pp?", "ถ้า OER เพิ่ม 0.5 จุด")],
                       uncertainty=_L(lang, "Factors are statistical associations from synthetic data; confirm with lab samples and on-site checks.",
                                      "ปัจจัยเป็นความสัมพันธ์เชิงสถิติจากข้อมูลสังเคราะห์ ต้องยืนยันด้วยผลแล็บและการตรวจหน้างาน"))  # fmt: skip


def _equip_line(e: dict, lang: str) -> str:
    sens = "; ".join(f"{s['sensor_code']} {f(s['observed'])} {s['unit']} ({s['limit_kind']} limit {f(s['limit'])} {s['unit']}"
                     + (f", ISO zone {s['iso_zone']}" if s.get("iso_zone") else "") + ")" for s in e["breached_sensors"])  # fmt: skip
    trend = "; ".join(f"{t['sensor_code']} rising {f(t['slope_per_day'], 3)} {t['unit']}/day" for t in e["rising_trends"][:2])
    base = _L(lang, f"{e['code']} ({e['name']}): state {e['state']}, risk index {f(e['risk_index'], 1)}/100",
              f"{e['code']} ({e['name']}): สถานะ {e['state']} ดัชนีความเสี่ยง {f(e['risk_index'], 1)}/100")
    if sens:
        base += _L(lang, f"; sensor evidence: {sens}", f"; หลักฐานจากเซ็นเซอร์: {sens}")
    if trend:
        base += f"; {trend}"
    if e.get("anomaly_score") is not None:
        base += _L(lang, f"; ML anomaly score {f(e['anomaly_score'], 3)}", f"; คะแนนความผิดปกติ ML {f(e['anomaly_score'], 3)}")
    return base


def ml_note(h: ToolResult, lang: str) -> str:
    """Describe the ML anomaly detector with its MEASURED limits (read from the model registry facts)."""
    p, r = h.fact("ml_equipment_anomaly_precision"), h.fact("ml_equipment_anomaly_recall")
    if p is None or r is None:
        return _L(lang, "The risk index is a relative ranking, not a failure probability.", "ดัชนีความเสี่ยงเป็นการจัดอันดับเชิงเปรียบเทียบ ไม่ใช่ความน่าจะเป็นของการเสีย")
    return _L(lang,
              f"The ML anomaly score comes from an anomaly detector (held-out period on synthetic data: precision {f(p)}, recall {f(r)}); "
              "it is advisory. The risk index is a relative ranking, not a failure probability.",
              f"คะแนนความผิดปกติมาจากโมเดลตรวจจับความผิดปกติ (ช่วงทดสอบบนข้อมูลสังเคราะห์: precision {f(p)}, recall {f(r)}) เป็นเพียงคำแนะนำ "
              "ดัชนีความเสี่ยงเป็นการจัดอันดับเชิงเปรียบเทียบ ไม่ใช่ความน่าจะเป็นของการเสีย")  # fmt: skip


def inspect_first(R: dict[str, ToolResult], lang: str) -> Composition:
    h = R.get("get_equipment_health")
    if not _ok(h) or not h.data["equipment"]:
        return Composition(_L(lang, "No equipment assessment is available at the demo clock.", "ไม่มีผลประเมินเครื่องจักร ณ เวลาเดโม"), uncertainty="no_data")
    eqs = h.data["equipment"]
    top = eqs[0]
    lines = [_L(lang, f"Inspect first: {top['code']}.", f"ควรตรวจก่อน: {top['code']}"), _equip_line(top, lang) + "."]
    others = [e for e in eqs[1:4]]
    if others:
        lines.append(_L(lang, "Next by risk index: ", "ลำดับถัดไปตามดัชนีความเสี่ยง: ")
                     + "; ".join(f"{e['code']} {e['state']} {f(e['risk_index'], 1)}" for e in others) + ".")  # fmt: skip
    if top["state"] in ("critical", "warning"):
        lines.append(_L(lang, f"Advisory: a qualified engineer should inspect {top['code']} before continued use (see the sample Equipment Inspection Procedure). "
                              f"A work order is created by an authorised person in the Work Orders screen ({WO_SCREEN}); the copilot does not create it.",
                        f"คำแนะนำ: ให้วิศวกรที่มีคุณสมบัติตรวจ {top['code']} ก่อนใช้งานต่อ (ดูเอกสารตัวอย่างขั้นตอนการตรวจเครื่องจักร) "
                        f"การเปิดใบสั่งงานทำโดยผู้มีสิทธิ์ที่หน้าจอ Work Orders ({WO_SCREEN}) ผู้ช่วยไม่สร้างให้"))  # fmt: skip
    lines.append(ml_note(h, lang))
    return Composition(" ".join(lines), [_L(lang, f"What is the health of {top['code']}?", f"สถานะของ {top['code']}"),
                                         _L(lang, "What if a 4 hour breakdown happens?", "ถ้าเครื่องหยุด 4 ชั่วโมงเสียหายเท่าไร")])  # fmt: skip


def equipment_status(R: dict[str, ToolResult], lang: str) -> Composition:
    h = R.get("get_equipment_health")
    if not h or h.status != "ok" or not h.data["equipment"]:
        msg = h.message if h else ""
        return Composition(_L(lang, f"No assessment available for that equipment. {msg}", f"ไม่มีผลประเมินของเครื่องนี้ {msg}"), uncertainty="no_data")
    e = h.data["equipment"][0]
    txt = _equip_line(e, lang) + "."
    if h.data.get("rank"):
        txt += _L(lang, f" Rank {h.data['rank']} by risk index.", f" อยู่อันดับ {h.data['rank']} ตามดัชนีความเสี่ยง")
    if e["open_alerts"]:
        txt += _L(lang, " Open alerts: ", " การแจ้งเตือนที่เปิดอยู่: ") + "; ".join(f"{a['code']} ({a['severity']})" for a in e["open_alerts"]) + "."
    txt += " " + ml_note(h, lang)
    return Composition(txt, [_L(lang, "Which machine should I inspect first?", "ควรตรวจเครื่องไหนก่อน")])


def downtime_when(R: dict[str, ToolResult], lang: str) -> Composition:
    d = R.get("get_downtime_analysis")
    if not _ok(d):
        return Composition(_L(lang, "No downtime is recorded in that period.", "ไม่มีการหยุดเครื่องในช่วงดังกล่าว"), uncertainty="no_data")
    x = d.data
    n = int(d.fact("period_days") or 30)
    hrs = "; ".join(f"{h['label']} ({f(h['downtime_h'])} h)" for h in x["top_hours"])
    eq = "; ".join(f"{e['key']} {f(e['downtime_h'])} h ({e['events']} events)" for e in x["top_equipment"][:3])
    ca = "; ".join(f"{c['label']} {f(c['downtime_h'])} h" for c in x["by_cause"][:3])
    txt = _L(lang,
             f"Over the last {n} days: plant downtime {f(x.get('plant_downtime_h'))} h (hours the mill was stopped), plant availability {f(x['availability_pct'])}%. "
             f"Equipment maintenance-event downtime (sum of event durations, includes planned work, can overlap; not the same as plant downtime): "
             f"{f(x['total_downtime_h'])} h. By hour of day: {hrs}. Top equipment: {eq}. By cause: {ca}.",
             f"ช่วง {n} วันที่ผ่านมา: เวลาหยุดของโรงงาน {f(x.get('plant_downtime_h'))} ชม. ความพร้อมใช้งานของโรงงาน {f(x['availability_pct'])}% "
             f"เวลาหยุดจากเหตุการณ์ซ่อมบำรุงเครื่องจักร (ผลรวมระยะเวลา รวมงานตามแผน อาจซ้อนกัน ไม่เท่ากับเวลาหยุดของโรงงาน): {f(x['total_downtime_h'])} ชม. "
             f"ตามช่วงเวลา: {hrs} เครื่องที่หยุดมาก: {eq} ตามสาเหตุ: {ca}")  # fmt: skip
    return Composition(txt, [_L(lang, "What if we cut downtime by 2 hours?", "ถ้าลด downtime 2 ชั่วโมงจะได้อะไร")])


def downtime_effect(R: dict[str, ToolResult], lang: str) -> Composition:
    s = R.get("run_business_scenario")
    if not _ok(s):
        return Composition(_L(lang, "The downtime what-if could not be calculated.", "คำนวณ what-if ของ downtime ไม่ได้"), uncertainty="no_data")
    x = s.data
    h = s.fact("downtime_hours")
    pl = s.fact("planned_stop_total_thb")
    d = R.get("get_downtime_analysis")
    pct = s.fact("cut_pct")
    if pct is not None and _ok(d):
        first = _L(lang, f"Interpreting the cut as {f(pct, 0)}% of the last {f(d.fact('period_days'), 0)} days' plant downtime ({f(d.fact('plant_downtime_h'))} h; plant downtime = "
                         f"hours the mill was stopped, the same definition as the Executive KPI, not the sum of maintenance events) = {f(h)} h. ",
                   f"ตีความการลดเป็น {f(pct, 0)}% ของเวลาหยุดของโรงงานใน {f(d.fact('period_days'), 0)} วันที่ผ่านมา ({f(d.fact('plant_downtime_h'))} ชม.; เวลาหยุดของโรงงาน = "
                   f"ชั่วโมงที่โรงงานหยุด นิยามเดียวกับ KPI ผู้บริหาร ไม่ใช่ผลรวมเหตุการณ์ซ่อมบำรุง) = {f(h)} ชม. ")  # fmt: skip
    elif s.fact("default_hours_used") is not None:
        first = _L(lang, f"No amount was given, so this uses a default of {f(h, 1)} h of unplanned downtime (give an amount, e.g. 'cut downtime by N hours' or 'by N%'). ",
                   f"ไม่ได้ระบุปริมาณ จึงใช้ค่าเริ่มต้น {f(h, 1)} ชม. ของการหยุดเครื่องที่ไม่ได้วางแผน (ระบุปริมาณได้ เช่น 'ลด downtime N ชั่วโมง' หรือ 'N เปอร์เซ็นต์') ")  # fmt: skip
    else:
        first = ""
    txt = first + _L(lang,
             f"What-if (not a forecast): avoiding {f(h)} h of unplanned downtime"
             + (f" on {x['equipment_code']}" if x.get("equipment_code") else "")
             + f" avoids about {f(x['lost_ffb_processing_t'])} t of lost FFB processing = {f(x['lost_cpo_opportunity_t'])} t CPO, "
             f"{f(x['lost_value_thb'], 0)} THB at the illustrative price, plus {f(x['maintenance_cost_thb'], 0)} THB repair cost "
             f"(total {f(x['total_impact_thb'], 0)} THB)."
             + (f" If the same stop were planned into low-intake hours the impact would be {f(pl, 0)} THB." if pl is not None else ""),
             f"What-if (ไม่ใช่การพยากรณ์): หากลดการหยุดเครื่องที่ไม่ได้วางแผน {f(h)} ชม."
             + (f" ของ {x['equipment_code']}" if x.get("equipment_code") else "")
             + f" จะเลี่ยงการสูญเสียการหีบ FFB ประมาณ {f(x['lost_ffb_processing_t'])} ตัน = CPO {f(x['lost_cpo_opportunity_t'])} ตัน "
             f"มูลค่า {f(x['lost_value_thb'], 0)} บาท (ราคาสมมติ) และค่าซ่อม {f(x['maintenance_cost_thb'], 0)} บาท (รวม {f(x['total_impact_thb'], 0)} บาท)"
             + (f" หากเป็นการหยุดตามแผนในช่วงที่วัตถุดิบน้อย ผลกระทบจะเป็น {f(pl, 0)} บาท" if pl is not None else ""))  # fmt: skip
    return Composition(txt, [_L(lang, "When is downtime highest?", "downtime สูงสุดช่วงเวลาใด")],
                       uncertainty=_L(lang, x.get("notice") or "", "เป็นการประมาณบนข้อมูลสังเคราะห์ด้วยสมมติฐานที่ปรับได้ ไม่ใช่ตัวเลขการเงินจริง"))


def oer_what_if(R: dict[str, ToolResult], lang: str) -> Composition:
    s = R.get("run_business_scenario")
    if not _ok(s):
        return Composition(_L(lang, "The production what-if could not be calculated.", "คำนวณ what-if การผลิตไม่ได้"), uncertainty="no_data")
    dlt = s.data["delta"]
    days = int(s.fact("days") or 30)
    base = s.fact("baseline_oer_pct")
    new = s.fact("input_oer_pct")
    txt = _L(lang,
             f"What-if over {days} days (calculation, not a forecast): OER {f(base)}% -> {f(new)}% with the trailing-30-day intake and hours gives "
             f"{f((dlt.get('cpo_t') or {}).get('value'))} t more CPO, about {f((dlt.get('cpo_revenue_thb') or {}).get('value'), 0)} THB at the illustrative CPO price.",
             f"What-if {days} วัน (การคำนวณ ไม่ใช่การพยากรณ์): OER {f(base)}% -> {f(new)}% ด้วยปริมาณรับเข้าและชั่วโมงหีบเฉลี่ย 30 วัน ได้ CPO เพิ่ม "
             f"{f((dlt.get('cpo_t') or {}).get('value'))} ตัน มูลค่าประมาณ {f((dlt.get('cpo_revenue_thb') or {}).get('value'), 0)} บาท (ราคาสมมติ)")  # fmt: skip
    return Composition(txt, [_L(lang, "Why did OER drop today?", "ทำไม OER วันนี้ลดลง")],
                       uncertainty=_L(lang, "Illustrative calculation on synthetic data with adjustable assumptions.", "เป็นการคำนวณประกอบบนข้อมูลสังเคราะห์"))


def energy_why(R: dict[str, ToolResult], lang: str) -> Composition:
    e = R.get("get_energy_summary")
    if not _ok(e):
        return Composition(_L(lang, "No energy data at the demo clock.", "ไม่มีข้อมูลพลังงาน ณ เวลาเดโม"), uncertainty="no_data")
    k = e.data["kpis"]
    kw = k.get("kwh_per_t_ffb", {})
    idle = k.get("idle_kwh", {})
    parts = [_L(lang,
                f"Electricity per tonne FFB: {f(kw.get('value'))} kWh/t vs {f(kw.get('previous'))} kWh/t in the previous period; "
                f"total {f((k.get('electricity_kwh') or {}).get('value'), 0)} kWh; idle consumption {f(idle.get('value'), 0)} kWh (previous {f(idle.get('previous'), 0)} kWh); "
                f"steam {f((k.get('steam_t_per_t_ffb') or {}).get('value'))} t/t.",
                f"ไฟฟ้าต่อตัน FFB: {f(kw.get('value'))} kWh/ตัน เทียบกับ {f(kw.get('previous'))} kWh/ตัน ช่วงก่อนหน้า; "
                f"รวม {f((k.get('electricity_kwh') or {}).get('value'), 0)} kWh; การใช้ไฟขณะเดินเปล่า {f(idle.get('value'), 0)} kWh (ก่อนหน้า {f(idle.get('previous'), 0)} kWh); "
                f"ไอน้ำ {f((k.get('steam_t_per_t_ffb') or {}).get('value'))} ตัน/ตัน")]  # fmt: skip
    if e.data["abnormal_days"]:
        a = e.data["abnormal_days"][-1]
        i = len(e.data["abnormal_days"]) - 1
        parts.append(_L(lang,
                        f"Abnormal day {a['date']}: {f(a['actual_kwh'], 0)} kWh vs {f(a['expected_kwh'], 0)} kWh expected for the same production "
                        f"(+{f(e.fact(f'abn{i}_excess_pct'), 1)}%, z = {f(a['z_score'])}).",
                        f"วันผิดปกติ {a['date']}: {f(a['actual_kwh'], 0)} kWh เทียบกับที่คาด {f(a['expected_kwh'], 0)} kWh สำหรับปริมาณการผลิตเดียวกัน "
                        f"(+{f(e.fact(f'abn{i}_excess_pct'), 1)}%, z = {f(a['z_score'])})"))  # fmt: skip
    else:
        parts.append(_L(lang, "No day in the window is abnormal against the production-adjusted baseline, so the data does not show an unexplained energy rise.",
                        "ไม่มีวันใดผิดปกติเมื่อเทียบกับ baseline ที่ปรับตามการผลิต ข้อมูลจึงไม่แสดงการใช้พลังงานสูงขึ้นโดยไม่มีคำอธิบาย"))  # fmt: skip
    st = e.data["by_stage"][:3]
    if st:
        parts.append(_L(lang, "Largest consumers: ", "หน่วยที่ใช้ไฟมากที่สุด: ") + "; ".join(f"{s['label']} {f(s['share_pct'], 1)}%" for s in st) + ".")
    parts.append(_L(lang, f"{CAUSAL_EN.capitalize()}: lower throughput spreads the fixed/idle load over fewer tonnes; higher idle kWh adds directly.",
                    f"{CAUSAL_TH}: การหีบน้อยลงทำให้โหลดคงที่/เดินเปล่าถูกเฉลี่ยบนตันที่น้อยลง และการเดินเปล่ามากขึ้นเพิ่มการใช้ไฟโดยตรง"))  # fmt: skip
    return Composition(" ".join(parts), [_L(lang, "Give me a daily summary", "สรุปวันนี้")])


def trucks_waiting(R: dict[str, ToolResult], lang: str) -> Composition:
    lg = R.get("get_logistics_summary")
    if not _ok(lg):
        return Composition(_L(lang, "No logistics data at the demo clock.", "ไม่มีข้อมูลโลจิสติกส์ ณ เวลาเดโม"), uncertainty="no_data")
    x = lg.data
    k = x["today_kpis"]
    aw = (k.get("avg_wait_min") or {}).get("value")
    txt = _L(lang,
             f"At the demo clock {f(x['trucks_waiting'], 0)} trucks are waiting for the weighbridge and {f(x['trucks_unloading'], 0)} are unloading"
             + (f"; the longest current wait is {f(x['max_wait_min'], 1)} min" if x.get("max_wait_min") is not None else "")
             + f". Mean wait-to-weigh today: {f(aw, 1)} min.",
             f"ณ เวลาเดโม มีรถรอชั่ง {f(x['trucks_waiting'], 0)} คัน กำลังขนถ่าย {f(x['trucks_unloading'], 0)} คัน"
             + (f" รอนานสุดตอนนี้ {f(x['max_wait_min'], 1)} นาที" if x.get("max_wait_min") is not None else "")
             + f" เวลารอชั่งเฉลี่ยวันนี้ {f(aw, 1)} นาที")  # fmt: skip
    return Composition(txt, [_L(lang, "Prioritise the plant issues", "จัดลำดับปัญหาในโรงงาน")])


def prioritize(R: dict[str, ToolResult], lang: str) -> Composition:
    al = R.get("get_active_alerts")
    if not _ok(al):
        return Composition(_L(lang, "No alert data available.", "ไม่มีข้อมูลการแจ้งเตือน"), uncertainty="no_data")
    fs = al.data["findings"]
    lines = []
    if fs:
        lines.append(_L(lang, f"{f(al.fact('findings_total'), 0)} findings, highest priority first:", f"พบ {f(al.fact('findings_total'), 0)} ประเด็น เรียงตามความสำคัญ:"))
        for i, x in enumerate(fs[:5]):
            lines.append(f"{i + 1}) [{x['severity']}] {x['headline']} -> {x['suggested_team']}.")
    else:
        lines.append(_L(lang, "No KPI deviates beyond its threshold and no high/critical alert is active.", "ไม่มี KPI ใดเกินเกณฑ์และไม่มีการแจ้งเตือนระดับสูง/วิกฤต"))
    lines.append(_L(lang, f"Active alerts: {f(al.fact('active_alerts_total'), 0)}.", f"การแจ้งเตือนที่ยังเปิดอยู่: {f(al.fact('active_alerts_total'), 0)}"))
    lines.append(_L(lang, "Decisions stay with people; alerts are advisory and need on-site verification.", "การตัดสินใจเป็นของคน การแจ้งเตือนเป็นคำแนะนำที่ต้องตรวจสอบหน้างาน"))
    return Composition(" ".join(lines), [_L(lang, "Which machine should I inspect first?", "ควรตรวจเครื่องไหนก่อน")])


def daily_summary(R: dict[str, ToolResult], lang: str) -> Composition:
    parts = [oer_value(R, lang).text]
    if _ok(R.get("get_active_alerts")):
        al = R["get_active_alerts"]
        fs = al.data["findings"]
        parts.append(_L(lang, f"Active alerts: {f(al.fact('active_alerts_total'), 0)}.", f"การแจ้งเตือนที่เปิดอยู่: {f(al.fact('active_alerts_total'), 0)}"))
        if fs:
            parts.append(_L(lang, f"Top finding: {fs[0]['headline']}.", f"ประเด็นสำคัญสุด: {fs[0]['headline']}"))
    if _ok(R.get("get_energy_summary")):
        kw = R["get_energy_summary"].data["kpis"].get("kwh_per_t_ffb", {})
        parts.append(_L(lang, f"Electricity {f(kw.get('value'))} kWh/t.", f"ไฟฟ้า {f(kw.get('value'))} kWh/ตัน"))
    if _ok(R.get("get_logistics_summary")):
        parts.append(_L(lang, f"Trucks waiting now: {f(R['get_logistics_summary'].data['trucks_waiting'], 0)}.",
                        f"รถรอชั่งตอนนี้: {f(R['get_logistics_summary'].data['trucks_waiting'], 0)} คัน"))  # fmt: skip
    return Composition(" ".join(parts), [_L(lang, "Prioritise the plant issues", "จัดลำดับปัญหาในโรงงาน"), _L(lang, "Why did OER drop today?", "ทำไม OER วันนี้ลดลง")])


def exec_brief(R: dict[str, ToolResult], lang: str) -> Composition:
    c = daily_summary(R, lang)
    h = R.get("get_equipment_health")
    extra = ""
    if _ok(h) and h.data["equipment"]:
        e = h.data["equipment"][0]
        extra = _L(lang, f" Highest equipment risk: {e['code']} ({e['state']}, risk index {f(e['risk_index'], 1)}/100, a relative ranking).",
                   f" ความเสี่ยงเครื่องจักรสูงสุด: {e['code']} ({e['state']} ดัชนีความเสี่ยง {f(e['risk_index'], 1)}/100 เป็นการจัดอันดับเชิงเปรียบเทียบ)")  # fmt: skip
    head = _L(lang, "Executive brief (synthetic demo data): ", "สรุปสำหรับผู้บริหาร (ข้อมูลเดโมสังเคราะห์): ")
    tail = _L(lang, " Decision for the meeting: confirm which team verifies the top finding today.", " ประเด็นตัดสินใจ: ยืนยันทีมที่จะตรวจสอบประเด็นสำคัญสุดวันนี้")
    return Composition(head + c.text + extra + tail, c.followups)


def doc_search(R: dict[str, ToolResult], lang: str) -> Composition:
    s = R.get("search_demo_documents")
    if not s or s.status != "ok":
        return Composition(_L(lang, "No sample document covers that question.", "ไม่มีเอกสารตัวอย่างที่ตอบคำถามนี้"), uncertainty="no_data")
    h = s.data["hits"][0]
    others = ", ".join(f"{x['title']} > {x['heading']}" for x in s.data["hits"][1:])
    txt = _L(lang, f"From the sample document \"{h['title']}\" (section \"{h['heading']}\"): {h['snippet']}",
             f"จากเอกสารตัวอย่าง \"{h['title']}\" (หัวข้อ \"{h['heading']}\"): {h['snippet']}")
    if others:
        txt += _L(lang, f" See also: {others}.", f" ดูเพิ่มเติม: {others}")
    txt += _L(lang, " (Sample document written for this demo, not a company procedure.)", " (เอกสารตัวอย่างสำหรับเดโม ไม่ใช่เอกสารของบริษัทจริง)")
    return Composition(txt, [_L(lang, "Which machine should I inspect first?", "ควรตรวจเครื่องไหนก่อน")])


def supplier_trace(R: dict[str, ToolResult], lang: str) -> Composition:
    s = R.get("get_supplier_trace")
    if not _ok(s):
        return Composition(_L(lang, "No CPO lot found at the demo clock.", "ไม่พบล็อต CPO ณ เวลาเดโม"), uncertainty="no_data")
    lot = s.data["lot"]
    top = "; ".join(f"{x['supplier_code']} {f(x['share_pct'])}%" for x in s.data["top_suppliers"])
    txt = _L(lang, f"Lot {lot['code']} ({f(s.fact('lot_quantity_t'))} t, {f(s.fact('supplier_count'), 0)} suppliers, mass-balance method): top shares {top}.",
             f"ล็อต {lot['code']} ({f(s.fact('lot_quantity_t'))} ตัน ซัพพลายเออร์ {f(s.fact('supplier_count'), 0)} ราย วิธี mass balance): สัดส่วนสูงสุด {top}")
    return Composition(txt, [], uncertainty=_L(lang, "Mass-balance shares, not physical segregation.", "เป็นสัดส่วนแบบ mass balance ไม่ใช่การแยกทางกายภาพ"))


COMPOSERS = {
    "forecast": forecast,
    "oer_value": oer_value, "oer_why": oer_why, "inspect_first": inspect_first, "equipment_status": equipment_status,
    "downtime_when": downtime_when, "downtime_effect": downtime_effect, "oer_what_if": oer_what_if, "energy_why": energy_why,
    "trucks_waiting": trucks_waiting, "prioritize": prioritize, "daily_summary": daily_summary, "exec_brief": exec_brief,
    "doc_search": doc_search, "supplier_trace": supplier_trace,
}  # fmt: skip


def no_data(lang: str, topic: str | None = None) -> Composition:
    caps = "; ".join(CAPABILITIES[lang][:6])
    return Composition(
        _L(lang, f"No data available in this demo for that{(' (' + topic + ')') if topic else ''}. The demo database holds synthetic mill operations only "
                 f"(production, equipment sensors, maintenance, logistics, energy, traceability) - no financial ledgers, invoices, fuel inventories or real company data. "
                 f"I will not estimate it. I can answer, for example: {caps}.",
           f"ไม่มีข้อมูลนี้ในเดโม{(' (' + topic + ')') if topic else ''} ฐานข้อมูลเดโมมีเฉพาะข้อมูลสังเคราะห์ของโรงงาน (การผลิต เซ็นเซอร์ ซ่อมบำรุง โลจิสติกส์ พลังงาน การตรวจย้อนกลับ) "
           f"ไม่มีบัญชีการเงิน ใบแจ้งหนี้ คลังน้ำมัน หรือข้อมูลบริษัทจริง จะไม่ประมาณขึ้นเอง ตัวอย่างคำถามที่ตอบได้: {caps}"),
        CAPABILITIES[lang][:3], uncertainty="no_data", refused=True, refusal_reason="no_data")  # fmt: skip


def help_text(lang: str, unknown: bool = False) -> Composition:
    caps = "; ".join(CAPABILITIES[lang])
    head = (_L(lang, "I could not match that question to the demo data I can query, so I will not guess. ", "ไม่สามารถจับคู่คำถามกับข้อมูลเดโมที่เข้าถึงได้ จึงจะไม่เดาคำตอบ ")
            if unknown else "")  # fmt: skip
    return Composition(head + _L(lang, f"I answer read-only questions from the synthetic demo data and sample documents, e.g.: {caps}.",
                                 f"ผู้ช่วยตอบคำถามแบบอ่านอย่างเดียวจากข้อมูลเดโมสังเคราะห์และเอกสารตัวอย่าง เช่น: {caps}"),
                       CAPABILITIES[lang][:3], uncertainty="unmatched_question" if unknown else None)  # fmt: skip


def refusal(lang: str, kind: str, detail: str | None = None) -> Composition:
    msgs = {
        "control": (f"I cannot do that. The copilot is read-only and advisory: it never controls equipment (start/stop, setpoints, valves) and never creates, "
                    f"approves or changes records. An authorised person does this in the plant's own systems; work orders are created and approved in the Work Orders "
                    f"screen ({WO_SCREEN}) with human confirmation. I can show the data behind the decision (health, alerts, what-if).",
                    f"ทำให้ไม่ได้ ผู้ช่วยทำงานแบบอ่านอย่างเดียวและให้คำแนะนำเท่านั้น ไม่ควบคุมเครื่องจักร (เปิด/ปิด ค่าตั้ง วาล์ว) และไม่สร้าง อนุมัติ หรือแก้ไขข้อมูล "
                    f"ผู้มีสิทธิ์ต้องทำในระบบของโรงงาน ใบสั่งงานสร้างและอนุมัติที่หน้าจอ Work Orders ({WO_SCREEN}) โดยมีการยืนยันจากคน ผู้ช่วยแสดงข้อมูลประกอบการตัดสินใจได้"),
        "injection": ("I treat instructions inside messages, documents or data as data and will not follow them. Please ask a question about the demo data.",
                      "ข้อความที่เป็นคำสั่งในข้อความ เอกสาร หรือข้อมูลจะถูกถือเป็นข้อมูลและจะไม่ทำตาม กรุณาถามคำถามเกี่ยวกับข้อมูลเดโม"),
        "escalation": ("Roles are selected outside the chat (simulated viewpoint) and cannot be changed or escalated by a message. I answer with the permissions of your current role.",
                       "บทบาทเลือกนอกแชต (มุมมองจำลอง) และเปลี่ยนหรือเพิ่มสิทธิ์ผ่านข้อความไม่ได้ ผู้ช่วยตอบตามสิทธิ์ของบทบาทปัจจุบัน"),
        "sql": ("I do not run SQL or free-form queries. I only use a fixed set of read-only analytics tools.",
                "ผู้ช่วยไม่รัน SQL หรือคำสั่งค้นแบบอิสระ ใช้เฉพาะเครื่องมือวิเคราะห์แบบอ่านอย่างเดียวที่กำหนดไว้"),
        "tool_denied": ("Your current role is not allowed to use the tool needed for this question, so I cannot answer it. {d}",
                        "บทบาทปัจจุบันไม่มีสิทธิ์ใช้เครื่องมือที่จำเป็นสำหรับคำถามนี้ จึงตอบไม่ได้ {d}"),
        "accusation": ("I will not name or accuse anyone. The data shows material flows and unusual readings, not intent: a review flag means "
                       "'unusual, needs review' and is never evidence of wrongdoing. I can show neutral facts instead - truck waiting times, weighbridge "
                       "statistics, or (if your role allows) the mass-balance supplier shares of a lot - and weighbridge review flags are listed in the "
                       "Logistics screen for a person to check with the supplier.",
                       "ผู้ช่วยจะไม่ระบุชื่อหรือกล่าวหาผู้ใด ข้อมูลแสดงการไหลของวัตถุดิบและค่าที่ผิดปกติ ไม่ได้แสดงเจตนา ธงให้ตรวจสอบหมายถึง 'ผิดปกติ ควรตรวจสอบ' "
                       "และไม่ใช่หลักฐานของการกระทำผิด ผู้ช่วยแสดงข้อเท็จจริงที่เป็นกลางได้ เช่น เวลารอของรถ สถิติตาชั่ง หรือสัดส่วนซัพพลายเออร์ในล็อต (ตามสิทธิ์) "
                       "และรายการธงตรวจสอบตาชั่งอยู่ในหน้าจอ Logistics ให้เจ้าหน้าที่ตรวจสอบกับซัพพลายเออร์"),
        "rate_limited": ("Too many questions in a short time for this session. Please wait a minute.", "ถามถี่เกินไปสำหรับเซสชันนี้ กรุณารอสักครู่"),
    }  # fmt: skip
    en, th = msgs[kind]
    txt = _L(lang, en, th).replace("{d}", detail or "")
    return Composition(txt.strip(), CAPABILITIES[lang][:3], refused=True, refusal_reason=kind)
