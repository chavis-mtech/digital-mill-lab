"""Thin wrapper: build the synthetic dataset (same as `make seed` / `python -m app.seed`).

Usage (repo root):  apps/ai-api/.venv/bin/python scripts/seed/seed.py [--seed N] [--db-url URL] [--days N] [--if-empty]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/ai-api"))

from app.seed.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
