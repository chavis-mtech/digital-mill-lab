"""Alembic `upgrade head` on a fresh SQLite file == Base.metadata.create_all schema (no drift)."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.db.base import Base

API_DIR = Path(__file__).resolve().parents[1]


def _alembic_cfg(db_path: Path) -> Config:
    cfg = Config(str(API_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(API_DIR / "alembic"))
    cfg.cmd_opts = type("o", (), {"x": [f"db_url=sqlite:///{db_path}"]})()
    return cfg


def _schema(engine):
    insp = inspect(engine)
    out = {}
    for t in sorted(insp.get_table_names()):
        if t == "alembic_version":
            continue
        out[t] = {
            "columns": sorted((c["name"], str(c["type"]), c["nullable"]) for c in insp.get_columns(t)),
            "fks": sorted((tuple(f["constrained_columns"]), f["referred_table"]) for f in insp.get_foreign_keys(t)),
            "indexes": sorted((i["name"], tuple(i["column_names"]), bool(i["unique"])) for i in insp.get_indexes(t)),
            "checks": sorted(c["name"] or "" for c in insp.get_check_constraints(t)),
            "uniques": sorted(tuple(u["column_names"]) for u in insp.get_unique_constraints(t)),
        }
    return out


def test_upgrade_head_matches_create_all(tmp_path):
    mig_db = tmp_path / "migrated.db"
    command.upgrade(_alembic_cfg(mig_db), "head")
    mig_engine = create_engine(f"sqlite:///{mig_db}")

    ca_engine = create_engine(f"sqlite:///{tmp_path / 'create_all.db'}")
    Base.metadata.create_all(ca_engine)

    a, b = _schema(mig_engine), _schema(ca_engine)
    assert set(a) == set(b)
    assert len(a) == len(Base.metadata.tables) == 44
    for table in a:
        assert a[table] == b[table], table

    with mig_engine.connect() as conn:
        diffs = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    assert diffs == []
