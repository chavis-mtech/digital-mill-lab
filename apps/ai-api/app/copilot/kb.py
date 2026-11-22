"""Sample-document knowledge base: ingest (chunk by heading) + TF-IDF retrieval + citations (DML-073/074).

* Source: data/kb/*.md (newly authored SAMPLE documents, never company documents; README.md is not indexed).
* Chunking: one chunk per `##` / `###` section (heading path kept), long sections split at paragraph boundaries.
* Retrieval: scikit-learn TF-IDF, word 1-2 grams + character 3-5 grams (typo- and Thai-tolerant), cosine, then a small
  lexical rerank (query terms in the heading). No external embedding service.
* Retrieved text is untrusted DATA: instruction-like lines are neutralised before they reach any answer or LLM.
"""

from __future__ import annotations

import hashlib
import re
import threading
from pathlib import Path
from typing import Any
from urllib.parse import quote

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.copilot.safety import neutralise_text
from app.models.platform import KbChunk, KbDocument

KB_DIR = REPO_ROOT / "data" / "kb"
MAX_CHUNK_CHARS = 1800
SAMPLE_NOTICE = "Newly authored sample document for this demo - not a real company document."
_lock = threading.Lock()
STOP = {"how", "is", "are", "the", "a", "an", "what", "does", "do", "of", "to", "in", "on", "for", "and", "or", "say", "says", "should", "we", "i",
        "defined", "define", "definition", "explain", "about", "tell", "me", "with", "by", "be", "this", "that", "which", "when", "why"}
_index: dict[str, Any] = {}


def _front_matter(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end > 0:
            for line in text[3:end].splitlines():
                m = re.match(r"^([a-z_]+):\s*(.*)$", line)
                if m:
                    meta[m.group(1)] = m.group(2).strip().strip('"')
            text = text[end + 4 :].lstrip("\n")
    return meta, text


def chunk_markdown(body: str) -> list[tuple[str | None, str]]:
    chunks: list[tuple[str | None, str]] = []
    h2: str | None = None
    heading: str | None = None
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if not text:
            return
        parts, cur = [], ""
        for para in re.split(r"\n\s*\n", text):
            if cur and len(cur) + len(para) > MAX_CHUNK_CHARS:
                parts.append(cur)
                cur = para
            else:
                cur = (cur + "\n\n" + para) if cur else para
        if cur:
            parts.append(cur)
        for p in parts:
            chunks.append((heading, p.strip()))

    for line in body.splitlines():
        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            flush()
            buf = []
            level, title = len(m.group(1)), m.group(2).strip()
            if level <= 2:
                h2 = title
                heading = title
            else:
                heading = f"{h2} > {title}" if h2 else title
            continue
        buf.append(line)
    flush()
    return chunks


def ingest(db: Session, kb_dir: Path | None = None) -> dict[str, int]:
    """Idempotent: documents are upserted by (slug, lang); their chunks are rebuilt when the body changed."""
    kb_dir = kb_dir or KB_DIR
    docs = chunks = unchanged = 0
    for path in sorted(kb_dir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        raw = path.read_text(encoding="utf-8")
        meta, body = _front_matter(raw)
        slug = path.stem.lower()
        title = meta.get("title") or slug
        version = hashlib.sha256(raw.encode()).hexdigest()[:12]
        doc = db.execute(select(KbDocument).where(KbDocument.slug == slug, KbDocument.lang == "en")).scalar_one_or_none()
        if doc and doc.version == version:
            unchanged += 1
            continue
        if doc is None:
            doc = KbDocument(slug=slug, lang="en")
            db.add(doc)
        doc.title, doc.doc_type, doc.body_md, doc.version = title[:200], (meta.get("doc_type") or "sample")[:32], raw, version
        try:
            doc.source_path = str(path.relative_to(REPO_ROOT))
        except ValueError:
            doc.source_path = path.name
        db.flush()
        db.execute(delete(KbChunk).where(KbChunk.document_id == doc.id))
        for i, (heading, text) in enumerate(chunk_markdown(body)):
            db.add(KbChunk(document_id=doc.id, chunk_index=i, heading=(heading or title)[:200], text=text, token_count=len(text.split())))
            chunks += 1
        docs += 1
    db.commit()
    _index.clear()
    return {"documents_written": docs, "chunks_written": chunks, "documents_unchanged": unchanged}


def ensure_ingested(db: Session) -> None:
    if not db.execute(select(func.count(KbChunk.id))).scalar_one():
        ingest(db)


def _build(db: Session) -> dict[str, Any]:
    from scipy.sparse import hstack  # noqa: PLC0415
    from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: PLC0415

    rows = db.execute(
        select(KbChunk.id, KbChunk.chunk_index, KbChunk.heading, KbChunk.text, KbDocument.slug, KbDocument.title)
        .join(KbDocument, KbDocument.id == KbChunk.document_id)
        .order_by(KbDocument.slug, KbChunk.chunk_index)
    ).all()
    corpus = [f"{r.title}\n{r.heading}\n{r.heading}\n{r.text}" for r in rows]
    wv = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, min_df=1, token_pattern=r"(?u)\b\w\w+\b", stop_words=list(STOP))
    cv = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True, min_df=1)
    wm = wv.fit_transform(corpus) if corpus else None
    cm = cv.fit_transform(corpus) if corpus else None
    return {"rows": rows, "wv": wv, "cv": cv, "wm": wm, "cm": cm, "key": (len(rows), rows[-1].id if rows else 0), "hstack": hstack}


def _get_index(db: Session) -> dict[str, Any]:
    key = db.execute(select(func.count(KbChunk.id), func.max(KbChunk.id))).one()
    k = (key[0], key[1] or 0)
    bind = str(db.get_bind().url)
    with _lock:
        idx = _index.get(bind)
        if idx is None or idx["key"] != k:
            idx = _build(db)
            _index[bind] = idx
    return idx


def ref_for(slug: str, chunk_index: int) -> str:
    return f"kb:{slug}#{chunk_index}"


def url_for(ref: str) -> str:
    return "/api/v1/copilot/sources/" + quote(ref, safe=":")


def _snippet(text: str, terms: set[str], n: int = 320) -> str:
    clean, _ = neutralise_text(text)
    flat = re.sub(r"\s+", " ", clean).strip()
    best, pos = -1, 0
    low = flat.lower()
    for t in terms:
        i = low.find(t)
        if i >= 0 and (best < 0 or i < best):
            best = i
    if best > 0:
        pos = max(0, best - 80)
    s = flat[pos : pos + n]
    return ("..." if pos else "") + s + ("..." if pos + n < len(flat) else "")


def search(db: Session, query: str, k: int = 3, min_score: float = 0.06) -> list[dict[str, Any]]:
    ensure_ingested(db)
    idx = _get_index(db)
    if not idx["rows"]:
        return []
    from sklearn.metrics.pairwise import cosine_similarity  # noqa: PLC0415

    q = query.lower()
    sw = cosine_similarity(idx["wv"].transform([q]), idx["wm"]).ravel()
    sc = cosine_similarity(idx["cv"].transform([q]), idx["cm"]).ravel()
    terms = {t for t in re.findall(r"\w{3,}", q) if t not in STOP}
    idents = set(re.findall(r"\b[a-z]+(?:_[a-z0-9]+)+\b", q))
    scored = []
    thai_summary: set[int] = set()
    for i, r in enumerate(idx["rows"]):
        s = 0.65 * sw[i] + 0.35 * sc[i]
        head = (r.heading or "").lower()
        bonus = sum(0.08 for t in terms if re.search(r"\b" + re.escape(t), head))
        if (r.heading or "").lower().startswith(("limits of this document", "fact tags")):
            s *= 0.6  # boilerplate sections rank below content
        if (r.heading or "").startswith("สรุปภาษาไทย"):
            thai_summary.add(i)
        for ident in idents:
            if ident in r.text.lower():
                s += 0.15  # exact schema identifiers (truck_trip_id, ffb_processed_t) point to the right dictionary section
        scored.append((s + min(bonus, 0.2), i))
    # the Thai summary is a fallback: down-weight it only when an English body section also clears the threshold
    if any(sc_ >= min_score for sc_, i in scored if i not in thai_summary):
        scored = [(sc_ * 0.55 if i in thai_summary else sc_, i) for sc_, i in scored]
    scored.sort(reverse=True)
    hits = []
    for s, i in scored[:k]:
        if s < min_score:
            continue
        r = idx["rows"][i]
        text, flagged = neutralise_text(r.text)
        ref = ref_for(r.slug, r.chunk_index)
        hits.append({"ref": ref, "doc_id": r.slug, "title": r.title, "heading": r.heading, "score": round(float(s), 4),
                     "snippet": _snippet(r.text, terms), "text": text[:1500], "url": url_for(ref), "instruction_like_removed": flagged,
                     "data_kind": "sample_document"})  # fmt: skip
    return hits


def get_chunk(db: Session, ref: str) -> dict[str, Any] | None:
    m = re.match(r"^kb:([a-z0-9-]+)#(\d+)$", ref)
    if not m:
        return None
    ensure_ingested(db)
    row = db.execute(
        select(KbChunk, KbDocument).join(KbDocument, KbDocument.id == KbChunk.document_id)
        .where(KbDocument.slug == m.group(1), KbChunk.chunk_index == int(m.group(2)))
    ).first()  # fmt: skip
    if not row:
        return None
    ch, doc = row
    return {"ref": ref, "document_slug": doc.slug, "document_title": doc.title, "heading": ch.heading, "text": ch.text}
