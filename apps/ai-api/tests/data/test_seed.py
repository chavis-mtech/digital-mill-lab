"""Fresh small builds (21 days, ~2 s each): determinism, validation, storage format, CLI flags.

The full 120-day build is covered by test_seed_full.py (opt-in: DML_FULL_SEED_TEST=1, ~15 s) and by `make seed` +
`python -m app.seed.validate` (evidence in docs/status/data-engine.md).
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.db.session import get_engine
from app.models import Alert, InjectedEvent, ScenarioRun, SensorReading, WorkOrder
from app.seed.__main__ import main as seed_main
from app.seed.build import build
from app.seed.validate import validate
from app.seed.writer import FORBIDDEN_TABLES

ANCHOR = date(2026, 11, 20)
DAYS = 21


def _build(path, seed=20261120):
    url = f"sqlite:///{path}"
    summary = build(url, seed=seed, anchor=ANCHOR, days=DAYS, write_manifest=False, log=lambda *_: None)
    return url, summary


@pytest.fixture(scope="module")
def small(tmp_path_factory):
    p = tmp_path_factory.mktemp("seed") / "small.db"
    return _build(p)


def test_same_seed_same_checksum(small, tmp_path):
    _, s1 = small
    _, s2 = _build(tmp_path / "again.db")
    assert s1["checksum_sha256"] == s2["checksum_sha256"]
    assert s1["row_counts"] == s2["row_counts"]


def test_different_seed_different_data(small, tmp_path):
    _, s1 = small
    _, s3 = _build(tmp_path / "other.db", seed=7)
    assert s1["checksum_sha256"] != s3["checksum_sha256"]


def test_validator_passes_on_small_build(small):
    url, _ = small
    rep = validate(get_engine(url), None)
    failed = [f"{c.name}: {c.detail}" for c in rep.checks if not c.ok and c.level == "fail"]
    assert rep.passed, failed


def test_window_scenarios_and_ground_truth(small):
    url, s = small
    eng = get_engine(url)
    with Session(eng) as db:
        codes = set(db.scalars(select(ScenarioRun.code)))
        assert {"TRUCK_QUEUE_CONGESTION", "PRESS_VIBRATION_ANOMALY"} <= codes  # episodes that fit in 21 days
        assert db.scalar(select(func.count()).select_from(InjectedEvent).where(InjectedEvent.scenario_code == "PRESS_VIBRATION_ANOMALY")) >= 1
        assert set(db.scalars(select(Alert.source).distinct())) == {"rule"}
        prs3 = db.scalar(select(func.count()).select_from(WorkOrder).where(WorkOrder.equipment_id == select(text("id")).select_from(text("equipment")).where(text("code = 'PRS-03'")).scalar_subquery()))
        assert prs3 == 0  # the guided tour creates the PRS-03 work order
        last = db.scalar(select(func.max(SensorReading.ts)))
        end = datetime(2026, 11, 20, 17, 0, tzinfo=UTC)  # 2026-11-21 00:00 Asia/Bangkok
        assert last < end
    with eng.connect() as c:
        for t in FORBIDDEN_TABLES:
            assert c.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar() == 0  # noqa: S608


def test_fast_path_timestamps_round_trip_through_sqlalchemy(small):
    """Readings are written with a raw executemany; SQLAlchemy must read them back as the same UTC instants."""
    url, _ = small
    eng = get_engine(url)
    with eng.connect() as c:
        raw = c.execute(text("SELECT ts FROM sensor_readings ORDER BY id LIMIT 1")).scalar()
        raw_wo = c.execute(text("SELECT created_at FROM work_orders ORDER BY id LIMIT 1")).scalar()
    assert len(raw) == len(raw_wo) == 26 and raw[10] == " " and raw[19] == "."  # same text format as Core inserts
    with Session(eng) as db:
        ts = db.scalar(select(SensorReading.ts).order_by(SensorReading.id).limit(1))
    assert ts.tzinfo is not None and ts.isoformat(sep=" ").startswith(raw[:19])


def test_cli_if_empty_skips_populated_db(small, capsys):
    url, _ = small
    assert seed_main(["--db-url", url, "--if-empty", "--no-manifest", "--days", str(DAYS)]) == 0
    assert "nothing to do" in capsys.readouterr().out
