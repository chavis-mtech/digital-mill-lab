"""CLI: python -m app.seed [--if-empty] [--seed N] [--db-url URL] [--reset] [--days N] [--anchor YYYY-MM-DD] [--no-manifest]

Default behaviour rebuilds the dataset from scratch (drop + create the schema, then load) - this is what `make seed`
runs. `--if-empty` (Docker CMD) only builds when the database has no facility rows. `--reset` is accepted for
explicitness (rebuild is already the default). Fully deterministic: same seed + anchor + days => same checksum.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date

from app.seed.assumptions import DEFAULT_SEED
from app.seed.dburl import seed_db_url


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.seed", description="Build the deterministic synthetic dataset (fictional palm oil mill).")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--db-url", default=None, help="SQLAlchemy URL (default: DATABASE_URL / settings)")
    ap.add_argument("--if-empty", action="store_true", help="only build when the database has no data")
    ap.add_argument("--reset", action="store_true", help="drop + recreate the schema before loading (default behaviour)")
    ap.add_argument("--days", type=int, default=None, help="window length in days (default: settings.dataset_days = 120)")
    ap.add_argument("--anchor", type=date.fromisoformat, default=None, help="last day of the window (default: settings.demo_anchor)")
    ap.add_argument("--no-manifest", action="store_true", help="do not write data/synthetic/MANIFEST.json")
    a = ap.parse_args(argv)
    url = seed_db_url(a.db_url)
    from app.seed.build import build  # imported after the URL is pinned (see dburl.py)

    print(f"seed: target {url}")
    res = build(url, seed=a.seed, anchor=a.anchor, days=a.days, if_empty=a.if_empty, write_manifest=not a.no_manifest)
    if res.get("skipped"):
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
