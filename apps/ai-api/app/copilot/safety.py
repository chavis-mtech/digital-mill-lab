"""Copilot input/output safety (DML-078).

Everything that is not the system's own code is DATA: the user's message, retrieved sample-document text and
string fields inside tool results. This module detects instruction-like / escalation / SQL / control patterns so
the engine can refuse, and neutralises such text inside retrieved documents and tool results before it reaches the
composer or an (optional) LLM. Pattern matching is a defence layer, not a guarantee: the real guarantees are
structural (tools are read-only, role allow-list enforced server-side, no SQL path exists, every number verified).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

MAX_INPUT_CHARS = 2000  # also enforced by ChatRequest (max_length)
REMOVED = "[removed: instruction-like text]"

# ---------------------------------------------------------------- patterns (EN + TH)
INJECTION_PATTERNS = [
    r"\b(ignore|disregard|forget|override|bypass)\b.{0,40}\b(previous|prior|above|earlier|all|your|the|system)\b.{0,30}\b(instruction|instructions|rules?|prompt|guardrails?|policy|policies)\b",
    r"\bsystem\s*prompt\b", r"\bdeveloper\s*mode\b", r"\bjail\s*break", r"\bDAN\b mode", r"\bdo anything now\b",
    r"\byou are (now|no longer)\b", r"\bpretend (to be|you are)\b", r"\bact as (an? )?(admin|administrator|root|system|developer)\b",
    r"\bnew instructions?\b", r"\breveal (your|the) (prompt|instructions|rules)\b", r"<\|?\s*(system|im_start|assistant)\s*\|?>",
    r"^\s*(system|assistant|developer)\s*:", r"\[\s*(system|inst)\s*\]", r"```\s*system",
    r"(ลืม|เพิกเฉย|ไม่ต้องสนใจ|ข้าม)(คำสั่ง|กฎ|ข้อห้าม)", r"คำสั่งก่อนหน้า", r"ตอนนี้คุณคือ", r"แกล้งทำเป็น", r"system prompt",
]
ESCALATION_PATTERNS = [
    r"\b(make|set|switch|change|give|grant|elevate|upgrade|promote)\b.{0,25}\b(me|my role|role|permission|permissions|access|privilege)s?\b.{0,25}\b(admin|system_admin|administrator|root|superuser|executive|factory_manager|all tools|full access)\b",
    r"\bi am (the |an? )?(admin|administrator|system_admin|root|ceo|md)\b", r"\bas (a |the )?system_admin\b", r"\bx-demo-role\b",
    r"\bauthori[sz]ed by (anthropic|the admin|the owner|management)\b", r"\bpre-?authori[sz]ed\b",
    r"(ให้|เปลี่ยน|ยกระดับ).{0,15}(สิทธิ์|บทบาท).{0,15}(แอดมิน|ผู้ดูแลระบบ|admin)", r"ฉันคือผู้ดูแลระบบ",
]
SQL_PATTERNS = [
    r"\b(select)\b[\s\S]{1,80}\bfrom\b", r"\b(drop|truncate|alter)\s+table\b", r"\bdelete\s+from\b", r"\binsert\s+into\b",
    r"\bupdate\s+\w+\s+set\b", r";\s*--", r"\bunion\s+select\b", r"\b(run|execute|exec)\b.{0,20}\b(sql|query|queries|statement)\b",
    r"\bsqlite_master\b", r"\bpragma\b", r"(รัน|สั่ง|ใช้).{0,10}sql",
]
# control / write actions: the copilot never performs them (SPEC rule 4)
CONTROL_PATTERNS = [
    r"\b(stop|shut ?down|start|restart|trip|switch (on|off)|turn (on|off)|run up|speed up|slow down)\b.{0,30}\b(press|boiler|machine|mill|plant|pump|motor|sterili[sz]er|digester|turbine|line|conveyor|equipment|PRS-\d+|BLR-\d+)\b",
    r"\b(change|adjust|set|increase|decrease|raise|lower|modify|write)\b.{0,30}\b(set ?point|setpoint|valve|steam pressure|temperature set|speed|rpm|plc|scada)\b",
    r"\b(open|close)\b.{0,15}\bvalve\b",
    r"\b(approve|reject|create|raise|close|resolve|cancel|assign|delete|submit|(edit|update|open) (a|an|the|this|that|my|new))\b.{0,30}\b(work ?orders?|wo|alerts?|recommendations?|tickets?|records?|anomal(y|ies))\b",
    r"\b(acknowledge|dismiss)\b.{0,20}\b(alert|alarm|anomaly)\b",
    r"\b(delete|drop|wipe|erase|reset)\b.{0,20}\b(data|database|records?|table|audit)\b",
    # Thai "หยุดเครื่อง" also means "downtime": only an imperative without question / what-if words counts as a control request
    r"^(?!.*(ถ้า|หาก|ลด|น้อยลง|บ่อย|นาน|กี่|เท่าไร|ไหม|ช่วงไหน|เมื่อไร|ทำไม)).*(หยุด|ปิด|เปิด|สตาร์ท|รีสตาร์ท)\s*(เครื่อง|การทำงาน|หม้อไอน้ำ|บอยเลอร์|เครื่องหีบ|เครื่องอัด|โรงงาน|ปั๊ม|มอเตอร์|วาล์ว)",
    r"(เปลี่ยน|ปรับ|ตั้ง)\s*(ค่า)?\s*(setpoint|เซ็ตพอยต์|ค่าตั้ง|อุณหภูมิ|แรงดัน|ความเร็ว|วาล์ว)",
    r"(อนุมัติ|สร้าง|เปิด|ปิด|ลบ|ยกเลิก|มอบหมาย)\s*(ใบสั่งงาน|ใบสั่งซ่อม|work ?order|การแจ้งเตือน|อลาร์ม|ข้อเสนอแนะ)",
    r"ลบ\s*(ข้อมูล|ประวัติ|บันทึก)",
]

# accusation / blame bait (SPEC rule 7: a logistics anomaly is never an accusation of fraud; never accuse individuals)
ACCUSATION_PATTERNS = [
    r"\b(steal(s|ing)?|stole|stolen|theft|thie(f|ves)|fraud(ster|sters|ulent)?|cheat(s|ing|er|ers|ed)?|scam(mer|ming)?|embezzl\w*|corrupt(ion)?|brib(e|es|ery|ing)|"
    r"culprits?|guilty|blame|liars?|lying|dishonest|crook(s|ed)?|smuggl\w*)\b",
    r"\bname (the|that|this) (supplier|driver|person|people|culprit|employee|operator|dealer)\b", r"\bwho (is|was|are) (to blame|responsible for (the )?(loss|theft|missing|shortage))",
    r"(ขโมย|โกง|ทุจริต|ฉ้อโกง|คนผิด|ใครผิด|ตัวการ|ติดสินบน|ยักยอก|หลอกลวง|แอบเอา)",
    # person-blame wording (audit P2). "drivers" is deliberately NOT listed: "which drivers explain the OER drop" is a legitimate question.
    r"\b(operators?|employees?|workers?|staff|technicians?|supervisors?|managers?)\b.{0,50}\b(responsible|fault|blame|negligen\w*|mistake|to blame)\b|"
    r"\b(responsible|fault|blame|negligen\w*|mistake)\b.{0,50}\b(operators?|employees?|workers?|staff|technicians?|supervisors?)\b",
    r"\b(give|tell|show) me (their|his|her|the) names?\b",
    r"(ใคร|พนักงานคนไหน|ผู้ปฏิบัติงานคนไหน|ช่างคนไหน|หัวหน้ากะคนไหน).{0,20}(รับผิดชอบ|ผิดพลาด|ต้นเหตุ|เป็นสาเหตุ|ทำให้)|ขอชื่อ(เขา|พนักงาน|ผู้ปฏิบัติงาน|ช่าง)",
]
_FLAGS = re.IGNORECASE | re.MULTILINE


def _c(pats: list[str]) -> list[re.Pattern]:
    # NFKC on the patterns too: it decomposes Thai SARA AM, exactly as normalise() does to the input
    return [re.compile(unicodedata.normalize("NFKC", p), _FLAGS) for p in pats]


_INJ, _ESC, _SQL, _CTL = _c(INJECTION_PATTERNS), _c(ESCALATION_PATTERNS), _c(SQL_PATTERNS), _c(CONTROL_PATTERNS)
_ACC = _c(ACCUSATION_PATTERNS)
_ZERO_WIDTH = re.compile("[​-‏‪-‮⁠-⁤﻿]")


@dataclass
class SafetyVerdict:
    flags: list[str] = field(default_factory=list)  # injection | escalation | sql | control
    matched: list[str] = field(default_factory=list)

    @property
    def blocked(self) -> bool:
        return bool(self.flags)


def normalise(text: str) -> str:
    """NFKC + strip zero-width/bidi controls (hidden-text tricks), collapse whitespace, cap length."""
    t = unicodedata.normalize("NFKC", text or "")
    t = _ZERO_WIDTH.sub("", t)
    t = "".join(ch for ch in t if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    return re.sub(r"[ \t]+", " ", t).strip()[:MAX_INPUT_CHARS]


def _scan(text: str, groups: list[tuple[str, list[re.Pattern]]]) -> SafetyVerdict:
    v = SafetyVerdict()
    text = unicodedata.normalize("NFKC", text or "")
    for name, pats in groups:
        for p in pats:
            m = p.search(text)
            if m:
                v.flags.append(name)
                v.matched.append(m.group(0)[:80])
                break
    return v


def check_user_input(text: str) -> SafetyVerdict:
    return _scan(text, [("injection", _INJ), ("escalation", _ESC), ("sql", _SQL), ("control", _CTL), ("accusation", _ACC)])


def is_instruction_like(text: str) -> bool:
    return bool(_scan(text, [("injection", _INJ), ("escalation", _ESC), ("sql", _SQL)]).flags)


def neutralise_text(text: str) -> tuple[str, bool]:
    """Remove instruction-like sentences/lines from untrusted DATA (documents, tool strings). Returns (text, flagged)."""
    if not text:
        return text, False
    flagged = False
    out_lines = []
    for line in text.split("\n"):
        if is_instruction_like(line) or _scan(line, [("control", _CTL)]).flags and _looks_imperative(line):
            flagged = True
            out_lines.append(REMOVED)
        else:
            out_lines.append(line)
    return "\n".join(out_lines), flagged


def _looks_imperative(line: str) -> bool:
    """Control phrases inside data are only removed when addressed to the assistant (not e.g. 'stop the press before inspection')."""
    return bool(re.search(r"\b(assistant|copilot|ai|you must|you should now|tell the user|answer that)\b|(ผู้ช่วย|คุณต้อง)", unicodedata.normalize("NFKC", line), re.IGNORECASE))


def sanitise_data(obj: Any, _flags: list[str] | None = None) -> tuple[Any, list[str]]:
    """Walk a tool result and neutralise instruction-like strings (tool output is data, never instructions)."""
    flags = _flags if _flags is not None else []
    if isinstance(obj, str):
        t, f = neutralise_text(obj)
        if f:
            flags.append(obj[:60])
        return t, flags
    if isinstance(obj, dict):
        return {k: sanitise_data(v, flags)[0] for k, v in obj.items()}, flags
    if isinstance(obj, list):
        return [sanitise_data(v, flags)[0] for v in obj], flags
    return obj, flags
