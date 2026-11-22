"""Models import, FK enforcement, physical-sanity check constraints, UTC round-trip."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

import app.models as m
from app.models import PRIVATE_TABLES, SESSION_SCOPED_TABLES


def _plant(s):
    company = m.Company(code="DEMO", name="Demo Palm Oil Co. (fictional)")
    s.add(company)
    s.flush()
    fac = m.Facility(company_id=company.id, code="MILL-A", name="Demo Palm Mill A", capacity_tph=60)
    s.add(fac)
    s.flush()
    stage = m.ProcessStage(facility_id=fac.id, code="PRESSING", name_en="Pressing", name_th="การหีบ", sequence=5)
    s.add(stage)
    s.flush()
    eq = m.Equipment(facility_id=fac.id, process_stage_id=stage.id, code="PRS-02", name="Screw Press 2", equipment_type="screw_press")
    s.add(eq)
    s.flush()
    return company, fac, stage, eq


def test_all_tables_registered():
    names = set(m.Base.metadata.tables)
    assert len(names) == 44
    assert PRIVATE_TABLES <= names
    assert SESSION_SCOPED_TABLES <= names
    for t in SESSION_SCOPED_TABLES:
        assert "session_id" in m.Base.metadata.tables[t].c, t
        assert m.Base.metadata.tables[t].c.session_id.nullable


def test_valid_chain_and_utc_roundtrip(db_session):
    _, _, _, eq = _plant(db_session)
    sensor = m.Sensor(equipment_id=eq.id, code="PRS-02-VIB", name="Vibration DE", sensor_type="vibration", unit="mm/s")
    db_session.add(sensor)
    db_session.flush()
    ts = datetime(2026, 11, 20, 18, 0, tzinfo=timezone(timedelta(hours=7)))
    db_session.add(m.SensorReading(sensor_id=sensor.id, ts=ts, value=4.2))
    db_session.commit()
    db_session.expire_all()
    r = db_session.query(m.SensorReading).one()
    assert r.ts == ts and r.ts.utcoffset() == timedelta(0)


def test_fk_enforced(db_session):
    _plant(db_session)
    db_session.add(m.Equipment(facility_id=1, process_stage_id=999, code="X-1", name="ghost", equipment_type="pump"))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_company_must_be_fictional(db_session):
    db_session.add(m.Company(code="REAL", name="Real Co", is_fictional=False))
    with pytest.raises(IntegrityError):
        db_session.flush()


def _trip(s, fac):
    sup = m.Supplier(code="S1", name="Fictional Supplier 1", supplier_type="dealer")
    s.add(sup)
    s.flush()
    trip = m.TruckTrip(code="T1", facility_id=fac.id, supplier_id=sup.id, plate_masked="XX-0001", arrival_ts=datetime(2026, 11, 20, 1, tzinfo=UTC))
    s.add(trip)
    s.flush()
    return trip


def test_weighbridge_net_must_equal_gross_minus_tare(db_session):
    _, fac, _, _ = _plant(db_session)
    trip = _trip(db_session, fac)
    t0 = datetime(2026, 11, 20, 2, tzinfo=UTC)
    db_session.add(m.WeighbridgeTicket(ticket_no="W1", truck_trip_id=trip.id, bridge_code="B1", weigh_in_ts=t0, gross_kg=20000, tare_kg=8000, net_kg=12000))
    db_session.flush()
    db_session.add(m.WeighbridgeTicket(ticket_no="W2", truck_trip_id=_trip_two(db_session, fac).id, bridge_code="B1", weigh_in_ts=t0, gross_kg=20000, tare_kg=8000, net_kg=13000))
    with pytest.raises(IntegrityError):
        db_session.flush()


def _trip_two(s, fac):
    trip = m.TruckTrip(code="T2", facility_id=fac.id, supplier_id=1, plate_masked="XX-0002", arrival_ts=datetime(2026, 11, 20, 1, tzinfo=UTC))
    s.add(trip)
    s.flush()
    return trip


@pytest.mark.parametrize("oer", [-1, 40])
def test_oer_range_enforced(db_session, oer):
    _, fac, _, _ = _plant(db_session)
    t = datetime(2026, 11, 20, 1, tzinfo=UTC)
    db_session.add(m.ProcessHourly(facility_id=fac.id, ts=t, ffb_processed_t=50, cpo_t=10, oer_pct=oer))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_recommendation_always_advisory(db_session):
    db_session.add(m.AiRecommendation(code="R1", rec_type="inspect_bearing", title="t", rationale="r", advisory=False, created_at=datetime.now(UTC)))
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_batch_input_share_range(db_session):
    db_session.add(m.BatchInput(ffb_batch_id=1, production_batch_id=1, mass_kg=100, mass_share=1.5))
    with pytest.raises(IntegrityError):
        db_session.flush()
