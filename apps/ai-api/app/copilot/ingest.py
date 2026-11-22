"""`python -m app.copilot.ingest [--kb-dir PATH]` - (re)index data/kb/*.md into kb_documents / kb_chunks (idempotent)."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings
from app.copilot.kb import KB_DIR, ingest
from app.db.session import get_sessionmaker


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kb-dir", type=Path, default=KB_DIR)
    a = ap.parse_args()
    db = get_sessionmaker(get_settings().database_url)()
    try:
        print("ingest:", ingest(db, a.kb_dir))
    finally:
        db.close()


if __name__ == "__main__":
    main()
