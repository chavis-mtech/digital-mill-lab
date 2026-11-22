"""Engine + session factory. One engine per DATABASE_URL (cached)."""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


def _enable_sqlite_fk(dbapi_connection, _record) -> None:  # noqa: ANN001
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _tune_sqlite_file(dbapi_connection, _record) -> None:  # noqa: ANN001
    """File databases only: WAL lets several API worker processes read while one writes; wait instead of failing on a lock."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=10000")
    cursor.close()


@lru_cache(maxsize=8)
def get_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    kwargs: dict = {"future": True, "pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        # QA-19: sync handlers run in AnyIO's 40-thread pool and each holds one connection; the default QueuePool (5 + 10)
        # made requests beyond 15 in flight wait 30 s and then fail with HTTP 500 under load. Allow one connection per thread.
        if ":memory:" not in url:
            kwargs.update(pool_size=5, max_overflow=35, pool_timeout=60)
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "sqlite":
        event.listen(engine, "connect", _enable_sqlite_fk)
        if ":memory:" not in url and get_settings().sqlite_wal:
            event.listen(engine, "connect", _tune_sqlite_file)
    return engine


@lru_cache(maxsize=8)
def get_sessionmaker(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def get_db(request: Request) -> Iterator[Session]:
    """FastAPI dependency: one session per request, closed afterwards. Handlers commit explicitly.

    Uses the settings bound to the running app (create_app(settings)), so tests can point at their own DB.
    """
    settings = getattr(request.app.state, "settings", None) or get_settings()
    db = get_sessionmaker(settings.database_url)()
    try:
        yield db
    finally:
        db.close()
