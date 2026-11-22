"""Declarative base + shared column helpers (portable SQLite <-> PostgreSQL)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, MetaData, String, TypeDecorator
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Deterministic constraint names -> identical schema from Alembic and create_all, clean Postgres migrations.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class UTCDateTime(TypeDecorator):
    """Timezone-aware UTC datetimes on every backend.

    SQLite has no tz storage; values are normalised to UTC on write and re-tagged as UTC on read.
    Naive datetimes passed in are assumed to already be UTC.
    """

    impl = DateTime
    cache_ok = True

    def __init__(self, timezone: bool = True) -> None:  # noqa: ARG002 - always tz-aware; arg kept for Alembic rendering
        super().__init__(timezone=True)

    def process_bind_param(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):  # noqa: ANN001
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map = {datetime: UTCDateTime()}


# ---- reusable column factories -------------------------------------------------

DATA_KIND_VALUES = ("synthetic", "synthetic_actual", "forecast", "what_if", "sample_document", "user_input")


def data_kind_column(default: str = "synthetic") -> Mapped[str]:
    """Provenance marker so a fact can never be mistaken for real plant data."""
    return mapped_column(String(32), default=default, server_default=default, nullable=False)


def session_id_column() -> Mapped[str | None]:
    """ADR-006: NULL = seeded shared baseline; uuid string = a visitor's demo session."""
    return mapped_column(String(36), nullable=True, index=True)
