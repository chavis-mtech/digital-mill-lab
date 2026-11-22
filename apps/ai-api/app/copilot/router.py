"""Deterministic intent router + slot extraction (DML-076). No API key, no network.

Two signals, combined:
  1. rule patterns (TH + EN keywords) -> a strong vote for an intent;
  2. TF-IDF character 2-4 grams (char_wb) over a labelled exemplar set (TH + EN) -> cosine to each exemplar; the best
     exemplar's intent and score. Character n-grams tolerate typos ("oee dropp", "trucs waitng") and Thai without spaces.
Decision: a rule match wins when it is unambiguous; otherwise the nearest exemplar if cosine >= MIN_SIM, else `unknown`.
The exemplar set IS the router's training data (see docs/ai/model-cards/copilot-router.md).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from datetime import date
from functools import lru_cache
from typing import Any

MIN_SIM = 0.32

# intent -> exemplar questions (training data for the nearest-neighbour router)
EXEMPLARS: dict[str, list[str]] = {
    "oer_why": [
        "why did OER drop today", "why is the oil extraction rate low", "what caused the OER decrease", "OER is down, why",
        "reason for low OER today", "explain the OER drop", "possible causes of the OER decline", "what are the possible causes",
        "ทำไม OER วันนี้ลดลง", "ทำไมอัตราการสกัดน้ำมันต่ำ", "สาเหตุที่ OER ตก", "OER ลดลงเพราะอะไร", "สาเหตุที่เป็นไปได้ของ OER ต่ำ",
    ],
    "oer_value": [
        "what is the OER today", "current oil extraction rate", "how much CPO did we produce today", "show OER and KER",
        "OER yesterday", "production today", "how much FFB was processed", "what was the OER on", "OER trend last 7 days",
        "OER วันนี้เท่าไหร่", "ผลิต CPO ได้เท่าไร", "อัตราการสกัดน้ำมันวันนี้", "วันนี้หีบปาล์มไปกี่ตัน", "แนวโน้ม OER สัปดาห์นี้",
    ],
    "inspect_first": [
        "which machine should I inspect first", "which equipment is most at risk", "what equipment needs attention",
        "which asset should maintenance check first", "highest risk equipment", "any machine with abnormal vibration",
        "เครื่องจักรไหนควรตรวจก่อน", "อุปกรณ์ไหนเสี่ยงที่สุด", "ควรตรวจเครื่องไหนก่อน", "เครื่องไหนสั่นผิดปกติ",
    ],
    "equipment_status": [
        "what is the health of PRS-03", "status of the boiler BLR-01", "is press 3 ok", "show the condition of DIG-02",
        "สถานะของ PRS-03", "เครื่อง PRS-03 เป็นอย่างไร", "สุขภาพเครื่อง BLR-01",
    ],
    "downtime_when": [
        "when is downtime highest", "what time of day do we have the most downtime", "which equipment causes most downtime",
        "downtime analysis", "show plant availability", "หยุดเครื่องบ่อยช่วงไหน", "downtime สูงสุดช่วงเวลาใด", "เครื่องหยุดมากที่สุดเวลาไหน",
    ],
    "downtime_effect": [
        "what if we cut downtime by 2 hours", "effect of reducing downtime", "how much do we gain if downtime drops",
        "value of one hour less downtime", "impact of a 4 hour breakdown", "ถ้าลด downtime 2 ชั่วโมงจะได้อะไร", "ผลของการลดเวลาหยุดเครื่อง",
        "ถ้าเครื่องหยุด 3 ชั่วโมงเสียหายเท่าไร",
    ],
    "oer_what_if": [
        "what if OER increases by 0.5 pp", "impact of raising OER 0.3 points", "what if OER improves", "how much CPO from +0.5% OER",
        "ถ้า OER เพิ่ม 0.5 จุด", "ถ้าเพิ่ม OER จะได้ CPO เท่าไร",
    ],
    "energy_why": [
        "why did energy per tonne rise", "why is kWh per ton high", "energy consumption is up why", "electricity use today",
        "energy summary", "steam per tonne", "ทำไมพลังงานต่อตันสูงขึ้น", "ทำไมใช้ไฟฟ้าต่อตันเพิ่ม", "การใช้พลังงานวันนี้",
    ],
    "trucks_waiting": [
        "how many trucks are waiting", "truck queue now", "weighbridge queue length", "how long are trucks waiting",
        "logistics status", "รถบรรทุกรอกี่คัน", "คิวรถตอนนี้", "รถรอชั่งนานแค่ไหน", "มีรถรอคิวเท่าไร",
    ],
    "daily_summary": [
        "give me a daily summary", "summarise today", "what happened today", "daily report", "shift summary",
        "สรุปประจำวัน", "สรุปวันนี้", "วันนี้เกิดอะไรขึ้นบ้าง", "รายงานประจำวัน",
    ],
    "prioritize": [
        "prioritise the plant issues", "what should we fix first", "rank today's problems", "what is abnormal today",
        "active alerts", "show open alerts", "จัดลำดับปัญหาในโรงงาน", "ควรแก้ปัญหาอะไรก่อน", "วันนี้มีอะไรผิดปกติ", "การแจ้งเตือนที่ยังเปิดอยู่",
    ],
    "exec_brief": [
        "prepare a brief for the executive meeting", "executive summary", "brief for management", "what should the MD know",
        "สรุปสำหรับประชุมผู้บริหาร", "สรุปให้ผู้บริหาร", "บรีฟผู้บริหาร",
    ],
    "doc_search": [
        "how is OER defined", "what does the inspection procedure say", "how do I inspect a screw press", "what is sterilization",
        "explain the clarification stage", "what is KER", "what is the maintenance checklist for bearings", "definition of availability",
        "OER คืออะไร", "ขั้นตอนการตรวจเครื่องหีบ", "การนึ่งปาล์มคืออะไร", "นิยามของ KER", "เช็กลิสต์บำรุงรักษาแบริ่ง",
    ],
    "supplier_trace": [
        "trace the suppliers of the latest CPO lot", "which suppliers are in lot", "supplier traceability", "where did this CPO come from",
        "ย้อนรอยซัพพลายเออร์ของล็อต CPO", "CPO ล็อตนี้มาจากสวนไหน",
    ],
    "help": ["what can you do", "help", "hello", "hi", "สวัสดี", "ช่วยอะไรได้บ้าง", "คุณทำอะไรได้"],
}

# second batch (2026-11-22, after the orchestrator review). Written without looking at the held-out set 2 in evaluate.py.
_MORE: dict[str, list[str]] = {
    "oer_value": ["oil extraction so far", "show me today's yield", "CPO output since the start of the day", "how is the yield looking",
                  "tonnes of crude palm oil produced", "kernel extraction today", "ปริมาณ CPO ที่ผลิตได้", "ผลผลิตน้ำมันวันนี้"],
    "oer_why": ["what is dragging the yield down", "why is extraction below normal", "explain the low oil yield", "what's hurting OER",
                "reasons the extraction rate fell", "ทำไมผลผลิตน้ำมันต่ำกว่าปกติ", "อะไรทำให้อัตราการสกัดลดลง"],
    "inspect_first": ["which equipment is in the worst shape", "any equipment in alarm", "which asset needs a technician", "เครื่องไหนมีอาการผิดปกติ"],
    "equipment_status": ["condition of press 2", "is BLR-01 running normally", "health check for DIG-03", "how is the thresher THR-01 doing",
                         "เครื่อง BLR-01 ปกติไหม"],
    "downtime_when": ["longest stops this month", "stoppage pattern by hour",
                      "เครื่องไหนหยุดนานที่สุด", "ช่วงเวลาที่หยุดเครื่องมากที่สุด"],
    "downtime_effect": ["value of fewer breakdowns", "cost of a 5 hour stop", "what is an hour of downtime worth",
                        "ถ้าเครื่องหยุดน้อยลงจะได้อะไร"],
    "oer_what_if": ["gain from improving extraction by 0.2 points", "what does a higher OER mean in tonnes", "ถ้าอัตราการสกัดเพิ่มขึ้นจะได้เท่าไร"],
    "energy_why": ["power consumption per ton is high", "why so many kWh", "energy intensity today"],
    "trucks_waiting": ["is the weighbridge busy", "how long is the queue at reception", "delivery queue status",
                       "รถขนปาล์มต่อคิวกี่คัน", "หน้าลานรับผลปาล์มมีรถรอไหม"],
    "daily_summary": ["overview of today", "how did the mill do today", "today's recap", "what's the situation at the plant"],
    "prioritize": ["what's most urgent", "top issues now", "which problem first", "biggest problems in the plant right now", "เรื่องเร่งด่วนตอนนี้"],
    "exec_brief": ["talking points for leadership", "summary for the board meeting", "briefing for senior management", "ประเด็นสำหรับผู้บริหาร"],
    "doc_search": ["what does the KPI guide say", "explain the threshing step", "what is in the data dictionary",
                   "อธิบายขั้นตอนการนวดปาล์ม"],
    "supplier_trace": ["which suppliers fed this lot", "origin of the CPO in storage", "supplier shares of the lot", "ล็อตนี้มาจากซัพพลายเออร์ไหนบ้าง"],
    "forecast": ["predict next week's output", "forecast the extraction rate", "expected energy use next week",
                 "คาดการณ์ OER สัปดาห์หน้า"],
}
for _k, _v in _MORE.items():
    EXEMPLARS.setdefault(_k, []).extend(_v)

_FORECAST_WORDS = (
    r"\b(tomorrow|next (week|month|shift|day|year)|forecast|predict|prediction|will (the )?\w+ be|going to be|expect(ed)? next)\b|"
    r"(พรุ่งนี้|สัปดาห์หน้า|เดือนหน้า|พยากรณ์|คาดการณ์|ทำนาย)"
)
_FORECAST_SUBJECT = (
    r"\b(oer|ker|oil|extraction|output|cpo|ffb|production|throughput|yield|energy|kwh|downtime|stoppages?|trucks?|queue|mill|plant)\b|"
    r"(อัตราการสกัด|น้ำมัน|ผลผลิต|พลังงาน|ไฟฟ้า|หยุดเครื่อง|รถ|คิว|การผลิต|โรงงาน|ผลปาล์ม|ปาล์ม)"
)

RULES: list[tuple[str, str]] = [
    (r"\b(no data|cost of goods|cogs|invoices?|payroll|salar(y|ies)|tanker|fuel inventory|share price|stock price|profit|revenue last|customer orders?|"
     r"weather|petroleum|port|terminal|employee names?|quarter|q[1-4]|competitors?|rubber|exchange rate|inflation|commodity|news|lawsuits?|court|allegations?|scandals?|investigations?|audit (results?|findings?|outcomes?)|legal matters?)\b|(ข่าว|คดี|ฟ้องร้อง|ข้อกล่าวหา|ผลการตรวจประเมิน|ผลตรวจประเมิน|ราคายาง|ใบแจ้งหนี้|ต้นทุนขาย|เงินเดือน|น้ำมันเชื้อเพลิงคงคลัง|ราคาหุ้น|กำไร|ยอดขายจริง|"
     r"พยากรณ์อากาศ|ท่าเรือ|ชื่อพนักงาน|ไตรมาส|คู่แข่ง)|real (company|p\.?c\.?)|actual p\.?c\.?|p\.?c\.? group('s)? (real|actual)", "no_data"),
    (r"(defin|นิยาม|คืออะไร|หมายถึง|procedure|ขั้นตอน|checklist|เช็กลิสต์|how (do|should) (i|we) (inspect|check)|sample document|data dictionary|dictionary|พจนานุกรมข้อมูล|เอกสาร|"
     r"what (is|are) (a |the )?(oer|ker)\b(?!.{0,30}(today|now|yesterday|on|for|วันนี้)))", "doc_search"),
    (r"(what if|ถ้า|หาก|suppose|scenario).{0,40}(oer|อัตราการสกัด)", "oer_what_if"),
    (r"(what if|ถ้า|หาก|cut|reduc|ลด|less|fewer|gain|effect|impact|ผล|worth|น้อยลง).{0,40}(downtime|หยุดเครื่อง|breakdown|เวลาหยุด|stoppages?|stops?\b)|"
     r"(downtime|stoppages?|หยุดเครื่อง).{0,30}(น้อยลง|less|fewer|cut|reduc)|\d+\s*-?\s*(hour|ชั่วโมง)s? (stop|breakdown)", "downtime_effect"),
    # A forecast question needs a subject the demo actually measures; "next year's rubber price" is a no-data question.
    (r"^(?=.*(?:" + _FORECAST_SUBJECT + r"))(?=.*(?:" + _FORECAST_WORDS + r"))", "forecast"),
    (r"(when|what time|hour|ช่วงไหน|เวลาไหน|เวลาใด|which equipment|availability|analysis|สูงสุด|most).{0,40}(downtime|หยุดเครื่อง|หยุดมาก)|(downtime|หยุดเครื่อง).{0,30}(highest|most|สูงสุด|มากที่สุด|ช่วงไหน|เวลาไหน)", "downtime_when"),
    (r"(why|ทำไม|เพราะ|cause|reason|สาเหตุ|explain).{0,40}(oer|oil extraction|อัตราการสกัด)|(oer|อัตราการสกัด).{0,40}(why|ทำไม|เพราะอะไร|สาเหตุ|drop|dropp|ตก|ลดลง|low|down|decline)", "oer_why"),
    (r"(why|ทำไม|เพราะ|cause|สาเหตุ).{0,40}(energy|kwh|electric|พลังงาน|ไฟฟ้า|steam|ไอน้ำ)|(energy|kwh|พลังงาน|ไฟฟ้า).{0,30}(rise|rose|up|high|สูง|เพิ่ม)", "energy_why"),
    (r"(truck|trucs|lorr|รถ|queue|คิว|weighbridge|ชั่ง)", "trucks_waiting"),
    (r"(inspect|ตรวจ|check|attention|risk|เสี่ยง|vibration|สั่น).{0,40}(first|ก่อน|most|ที่สุด|machine|equipment|เครื่อง|asset)|(which|ไหน).{0,20}(machine|equipment|เครื่อง)", "inspect_first"),
    (r"(executive|management|md\b|ผู้บริหาร|board|meeting|ประชุม)", "exec_brief"),
    (r"(prioriti|rank|fix first|แก้.{0,10}ก่อน|จัดลำดับ|abnormal|ผิดปกติ|alerts?\b|แจ้งเตือน)", "prioritize"),
    (r"(daily|summary|summar|สรุป|report|รายงาน|what happened|เกิดอะไร)", "daily_summary"),
    (r"(supplier|ซัพพลายเออร์|trace|ย้อนรอย|lot\b|ล็อต)", "supplier_trace"),
    (r"(what is (a |the )?(sterili|clarif|thresh|digest|kernel recovery|mass balance|availability|kpi|pome|efb|dobi|ffa)(?!.{0,30}(today|now|yesterday|วันนี้|ตอนนี้)))", "doc_search"),
    (r"(energy|kwh|electric|พลังงาน|ไฟฟ้า|steam per|ไอน้ำ)", "energy_why"),
    (r"(oer|ker|cpo|ffb|production|ผลิต|หีบ|อัตราการสกัด|throughput)", "oer_value"),
]


def _n(t: str) -> str:
    # same NFKC as safety.normalise(): it decomposes Thai SARA AM, so patterns/exemplars must be normalised identically
    return unicodedata.normalize("NFKC", t)


_RULES = [(re.compile(_n(p), re.IGNORECASE), i) for p, i in RULES]

EQUIP_RE = re.compile(r"\b([A-Za-z]{2,5}(?:-[A-Za-z]{2,5})?-\d{2})\b")
NUM_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")
TOOL_NAME_RE = re.compile(r"\b(get_[a-z_]+|run_[a-z_]+|search_[a-z_]+|draft_[a-z_]+|execute_[a-z_]+|sql_[a-z_]+|[a-z]+_tool)\b")


@dataclass
class Route:
    intent: str
    confidence: float
    method: str  # rule | tfidf | followup | explicit_tool | none
    slots: dict[str, Any] = field(default_factory=dict)
    exemplar: str | None = None


@lru_cache(maxsize=1)
def _model():
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

    labels, texts = [], []
    for intent, qs in EXEMPLARS.items():
        for q in qs:
            labels.append(intent)
            texts.append(_n(q).lower())
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
    mat = vec.fit_transform(texts)
    return vec, mat, labels, texts


def nearest(text: str) -> tuple[str, float, str]:
    from sklearn.metrics.pairwise import cosine_similarity  # noqa: PLC0415

    vec, mat, labels, texts = _model()
    sims = cosine_similarity(vec.transform([_n(text).lower()]), mat).ravel()
    i = int(sims.argmax())
    return labels[i], float(sims[i]), texts[i]


def extract_slots(text: str, as_of_date: date | None = None) -> dict[str, Any]:
    text = _n(text)
    t = text.lower()
    slots: dict[str, Any] = {}
    m = EQUIP_RE.search(text)
    if m:
        slots["equipment_code"] = m.group(1).upper()
    else:
        pm = re.search(r"\b(press|เครื่องหีบ|เครื่องอัด)\s*(?:no\.?\s*)?(\d)\b", t)
        if pm:
            slots["equipment_code"] = f"PRS-{int(pm.group(2)):02d}"
    if re.search(r"yesterday|เมื่อวาน", t):
        slots["day"] = "yesterday"
    elif re.search(r"today|วันนี้|now|ตอนนี้", t):
        slots["day"] = "today"
    dm = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", t)
    if dm:
        slots["day"] = dm.group(1)
    if re.search(r"(last|past)\s*30\s*days|this month|เดือนนี้|30 วัน|month", t):
        slots["period"] = "30d"
    elif re.search(r"(last|past)\s*7\s*days|this week|สัปดาห์|7 วัน|week", t):
        slots["period"] = "7d"
    # numbers for what-ifs: hours / pp
    hm = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(hours?|hrs?|h\b|ชั่วโมง|ชม)", t)
    if hm:
        slots["hours"] = float(hm.group(1))
    pc = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(%|percent\b|per cent\b|เปอร์เซ็นต์|เปอร์เซนต์)", t) or re.search(r"ร้อยละ\s*(\d+(?:\.\d+)?)()", t)
    if pc:
        slots["pct"] = abs(float(pc.group(1)))
    pm2 = re.search(r"([-+]?\d+(?:\.\d+)?)\s*(pp|percentage points?|points?|จุด|%(?!\s*(of|fewer|less|more)))", t)
    if pm2:
        slots["pp"] = float(pm2.group(1))
        if re.search(r"(drop|decreas|fall|lower|ลด)", t) and slots["pp"] > 0:
            slots["pp"] = -slots["pp"]
    lm = re.search(r"\b(CPO-\d{8}-T\d)\b", text.upper())
    if lm:
        slots["lot_code"] = lm.group(1)
    tm = TOOL_NAME_RE.findall(t)
    if tm:
        slots["tool_names"] = sorted(set(tm))
    if re.search(r"planned|แผน", t):
        slots["planned"] = True
    return slots


FOLLOWUP_RE = re.compile(_n(
    # NOTE: a bare trailing "?" is NOT a follow-up cue: "Which machine should I inspect first?" is a new question
    # (regression found by the web-verifier e2e: it repeated the previous OER answer).
    r"^(and|what about|how about|แล้ว|และ|ส่วน)\b|^(why|ทำไม|เพราะอะไร|สาเหตุ(ล่ะ)?|explain|more|อธิบาย|รายละเอียด)\??$|(ล่ะ\??$)"), re.IGNORECASE
)
WHY_RE = re.compile(_n(r"^(why|ทำไม|เพราะอะไร|สาเหตุ|explain|อธิบาย)"), re.IGNORECASE)


WEAK_RULES = {"daily_summary", "prioritize", "exec_brief", "inspect_first", "supplier_trace", "oer_value", "energy_why"}
CLARIFY_LOW, ANSWER_SIM, MIN_MARGIN = 0.30, 0.45, 0.06


def ranked(text: str) -> list[tuple[str, float, str]]:
    """Best cosine per intent, descending: [(intent, sim, exemplar)]."""
    from sklearn.metrics.pairwise import cosine_similarity  # noqa: PLC0415

    vec, mat, labels, texts = _model()
    sims = cosine_similarity(vec.transform([_n(text).lower()]), mat).ravel()
    best: dict[str, tuple[float, str]] = {}
    for i, lab in enumerate(labels):
        if lab not in best or sims[i] > best[lab][0]:
            best[lab] = (float(sims[i]), texts[i])
    return sorted(((k, v[0], v[1]) for k, v in best.items()), key=lambda x: -x[1])


def _eq(intent: str, slots: dict) -> str:
    return "equipment_status" if intent == "inspect_first" and slots.get("equipment_code") else intent


def route(text: str, previous: dict[str, Any] | None = None) -> Route:
    """Decision (see module docstring): strong rule -> answer; weak rule -> answer only if the TF-IDF ranking does not clearly
    prefer another intent; TF-IDF only -> answer when sim >= ANSWER_SIM and margin >= MIN_MARGIN, clarify (top-2) in the grey
    zone, `unknown` below CLARIFY_LOW. A wrong-but-plausible answer is worse than a clarification question."""
    text = _n(text)
    slots = extract_slots(text)
    if slots.get("tool_names"):
        return Route("explicit_tool", 1.0, "explicit_tool", slots)
    hits = [intent for rx, intent in _RULES if rx.search(text)]
    rk = ranked(text)
    (nn_intent, sim, ex), (second, sim2, _) = rk[0], rk[1]
    margin = sim - sim2
    short = len(text.strip()) <= 40
    need = MIN_MARGIN if len(text.split()) > 2 or re.search(r"[฀-๿]", text) else 0.15  # one- or two-word English queries are inherently ambiguous
    # A question that routes confidently on its own (a keyword rule, or a clear nearest exemplar) is a NEW question,
    # never a follow-up, even when it is short or ends with "?".
    standalone = bool(hits) or (sim >= ANSWER_SIM and margin >= need)
    cue = bool(FOLLOWUP_RE.search(text.strip()))
    # multi-turn follow-ups ("why?", "and yesterday?", "what about PRS-01?")
    if previous and previous.get("intent") and short and ((cue and not hits) or (not cue and not standalone)):
        prev = previous["intent"]
        if WHY_RE.search(_n(text.strip())):
            nxt = {"oer_value": "oer_why", "energy_why": "energy_why", "inspect_first": "equipment_status", "equipment_status": "equipment_status"}.get(prev, prev)
        else:
            nxt = "equipment_status" if (slots.get("equipment_code") and prev in ("inspect_first", "equipment_status")) else prev
        merged = {**(previous.get("slots") or {}), **slots}
        return Route(nxt, 0.7, "followup", merged)
    if hits:
        intent = hits[0]
        if intent not in WEAK_RULES or nn_intent == intent or sim < ANSWER_SIM:
            return Route(_eq(intent, slots), 0.9, "rule", slots, ex)
        # weak keyword rule contradicted by a confident nearest exemplar -> ask
        return Route("clarify", round(sim, 3), "clarify", {**slots, "options": [_eq(intent, slots), _eq(nn_intent, slots)]}, ex)
    if sim >= ANSWER_SIM and margin >= need:
        return Route(_eq(nn_intent, slots), round(sim, 3), "tfidf", slots, ex)
    if sim >= CLARIFY_LOW:
        opts = [_eq(nn_intent, slots), _eq(second, slots)]
        if opts[0] == opts[1] or second in ("help",):
            return Route(opts[0], round(sim, 3), "tfidf", slots, ex)
        return Route("clarify", round(sim, 3), "clarify", {**slots, "options": opts}, ex)
    if slots.get("equipment_code"):
        return Route("equipment_status", 0.5, "rule", slots)
    return Route("unknown", round(sim, 3), "none", slots, ex)
