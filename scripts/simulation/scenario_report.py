"""Thin wrapper: cross-module scenario chain report (focus vs baseline: sensors -> KPIs -> alerts -> batches/lots).

Usage (repo root):  apps/ai-api/.venv/bin/python scripts/simulation/scenario_report.py [--db-url URL] [--out data/synthetic/scenario_report.json]
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "apps/ai-api"))

from app.seed.report import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
