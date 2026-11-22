"""Thin wrapper: validate the synthetic dataset (same as `python -m app.seed.validate`). Exit 1 on failure.

Usage (repo root):  apps/ai-api/.venv/bin/python scripts/validation/validate_dataset.py [--db-url URL] [--json]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/ai-api"))

from app.seed.validate import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
