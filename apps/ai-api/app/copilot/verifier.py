"""Grounding verifier / unsupported-claim detector (DML-078).

Rule: every numeric claim in the final answer must match a number in the evidence set (tool facts, numbers quoted in
tool text, numbers in cited document snippets, or numbers the user typed), with rounding tolerance. In addition,
definitive causal language ("X caused the drop", "the model shows ...") is flagged: the copilot may only state
possible contributing factors. The SAME verifier checks deterministic and LLM answers; an LLM answer that fails is
discarded (engine.py).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# tokens that contain digits but are identifiers / method constants, not numeric claims
_STRIP = [
    r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?",  # ISO dates / datetimes
    r"\b\d{2}-\d{2}\b(?=\s)",  # MM-DD labels in daily series
    r"\b\d{1,2}:\d{2}(?:-\d{1,2}:\d{2})?\b",  # clock times / hour labels
    r"\b[A-Z]{2,5}(?:-[A-Z]{2,5})*-\d+(?:-[A-Z0-9]+)*\b",  # equipment / sensor / alert / lot codes (PRS-03-VIB-DE, MLA-00093)
    r"\b[A-Z]+\d+\b",  # R1, S16, Q3, T1
    r"\b\d+-day\b|\b\d+ วัน\b(?= ?ย้อนหลัง)|ค่าเฉลี่ย \d+ วัน|เฉลี่ย \d+ วัน",
    r"[+/-]{1,3} ?\d+ s\.d\.|\b\d+ s\.d\.",
    r"/100\b|\b0-100\b|\b0-1\b",
    r"\bISO 10816-3\b",
    r"^\s*\d+\)|(?<=\s)\d+\)",  # list markers
    r"\b(?:sha|SHA)-?256\b",
]
_STRIP_RE = re.compile("|".join(_STRIP), re.MULTILINE)
_NUM_RE = re.compile(r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])")

CAUSAL_PATTERNS = [
    r"\b(the|this|our|an?) (ml |ai )?(model|algorithm|forecast)s? (shows?|proves?|found|says|confirms?|indicates?)\b.{0,80}\b(caus|reason|because|due to|drove|driv)",
    r"\b(was|were|is|are) (directly |clearly )?caused by\b", r"\broot cause (is|was)\b", r"\bproves? that\b",
    r"\bbecause of\b(?!.{0,40}(association|not proven))", r"\bdue to\b(?!.{0,40}(association|not proven))", r"\bdefinitely\b",
    r"สาเหตุ(หลัก)?คือ", r"เกิดจาก(?!.{0,40}(ความสัมพันธ์|ไม่ใช่))", r"โมเดล(แสดง|ยืนยัน|พิสูจน์)ว่า",
]
_CAUSAL = [re.compile(p, re.IGNORECASE) for p in CAUSAL_PATTERNS]


@dataclass
class Verification:
    checked: int = 0
    supported: int = 0
    unsupported: list[str] = field(default_factory=list)
    causal_flags: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unsupported and not self.causal_flags

    def out(self) -> dict:
        return {"ok": self.ok, "numbers_checked": self.checked, "numbers_supported": self.supported,
                "unsupported_numbers": self.unsupported[:20], "causal_flags": self.causal_flags[:5]}  # fmt: skip


def numbers_in(text: str) -> list[str]:
    cleaned = _STRIP_RE.sub(" ", text or "")
    return _NUM_RE.findall(cleaned)


def _parse(tok: str) -> tuple[float, int]:
    t = tok.replace(",", "").lstrip("+")
    dec = len(t.split(".")[1]) if "." in t else 0
    return float(t), dec


def matches(claim: str, values: list[float]) -> bool:
    c, dec = _parse(claim)
    c = abs(c)
    tol = 0.5 * 10 ** (-dec) + 1e-9
    for v in values:
        av = abs(v)
        if abs(av - c) <= tol:
            return True
        if c >= 1000 and av and abs(av - c) / av <= 0.005:  # large currency values rounded for readability
            return True
        if av < 1.0 and abs(av * 100 - c) <= tol:  # share expressed as percent
            return True
    return False


def verify(answer: str, evidence_values: list[float], causal_check: bool = True) -> Verification:
    v = Verification()
    for tok in numbers_in(answer):
        v.checked += 1
        if matches(tok, evidence_values):
            v.supported += 1
        else:
            v.unsupported.append(tok)
    if causal_check:
        for rx in _CAUSAL:
            m = rx.search(answer or "")
            if m:
                v.causal_flags.append(m.group(0)[:80])
    return v


def numbers_from_text(text: str) -> list[float]:
    out = []
    for tok in numbers_in(text):
        try:
            out.append(_parse(tok)[0])
        except ValueError:
            continue
    return out
