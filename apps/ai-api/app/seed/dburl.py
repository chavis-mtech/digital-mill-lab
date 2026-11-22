"""Target-database resolution shared by the seed and validate CLIs."""

from __future__ import annotations

import os
from pathlib import Path

from app.config import REPO_ROOT


def seed_db_url(cli_url: str | None) -> str:
    """Resolve the target DB. Relative sqlite paths resolve from the repo root (app.config convention); a relative path
    that would escape the repo (e.g. 'sqlite:///../../data/dev/x.db' typed from apps/ai-api) is resolved from the CWD
    instead, so the seed never writes outside the repository."""
    raw = cli_url or os.environ.get("DATABASE_URL")
    prefix = "sqlite:///"
    if raw and raw.startswith(prefix) and not raw.startswith("sqlite:////") and ":memory:" not in raw:
        rel = raw[len(prefix):]
        root = REPO_ROOT.resolve()
        p = (root / rel).resolve()
        if root not in p.parents:
            p = (Path.cwd() / rel).resolve()
            if root not in p.parents:
                raise SystemExit(f"seed: refusing to write outside the repository: {p}")
        p.parent.mkdir(parents=True, exist_ok=True)
        url = f"sqlite:////{str(p).lstrip('/')}"
        os.environ["DATABASE_URL"] = url  # pin it so app.config never re-resolves the relative path
        return url
    if raw:
        os.environ["DATABASE_URL"] = raw
        return raw
    from app.config import get_settings

    return get_settings().database_url
