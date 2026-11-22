"""Generate docs/architecture/DATABASE_SCHEMA.md from the SQLAlchemy models (`make docs`).

Run: python -m app.db.schema_doc [out_path]
"""

from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import CheckConstraint, UniqueConstraint

import app.models as models
from app.config import REPO_ROOT
from app.db.base import Base

DOMAIN_FILES = ["core", "readings", "production", "logistics", "traceability", "maintenance", "energy", "ai", "platform"]


def _domain_of(table_name: str) -> str:
    for mapper in Base.registry.mappers:
        if mapper.local_table.name == table_name:
            return mapper.class_.__module__.rsplit(".", 1)[-1]
    return "?"


def render() -> str:
    tables = Base.metadata.tables
    out = [
        "# Database Schema",
        "",
        "> **GENERATED** from `apps/ai-api/app/models/**` by `make docs` (`python -m app.db.schema_doc`). Do not edit by hand.",
        "> Portable SQLAlchemy 2.0 models: SQLite (default) and PostgreSQL (via `DATABASE_URL`). Alembic revision `0001` creates the same schema",
        "> (verified by `tests/test_migrations.py`). All timestamps are stored as UTC (`UTCDateTime`).",
        "",
        f"**{len(tables)} tables.** Private (never exposed via API): `{', '.join(sorted(models.PRIVATE_TABLES))}`. "
        f"Session-scoped (ADR-006, `session_id` NULL = seeded baseline): `{', '.join(sorted(models.SESSION_SCOPED_TABLES))}`.",
        "",
    ]
    by_domain: dict[str, list[str]] = {}
    for name in tables:
        by_domain.setdefault(_domain_of(name), []).append(name)
    for domain in DOMAIN_FILES:
        names = sorted(by_domain.get(domain, []))
        if not names:
            continue
        out += [f"## Domain `{domain}` (`app/models/{domain}.py`)", ""]
        for name in names:
            t = tables[name]
            out += [f"### `{name}`", ""]
            cls = next((m.class_ for m in Base.registry.mappers if m.local_table is t), None)
            if cls is not None and cls.__doc__:
                out += [" ".join(cls.__doc__.split()), ""]
            out += ["| Column | Type | Null | Key / FK | Default |", "|---|---|---|---|---|"]
            for c in t.columns:
                keys = []
                if c.primary_key:
                    keys.append("PK")
                for fk in c.foreign_keys:
                    keys.append(f"FK -> `{fk.target_fullname}`")
                if c.unique:
                    keys.append("unique")
                if c.index:
                    keys.append("indexed")
                default = ""
                if c.server_default is not None:
                    default = str(getattr(c.server_default, "arg", ""))
                elif c.default is not None and not callable(getattr(c.default, "arg", None)):
                    default = str(c.default.arg)
                out.append(f"| `{c.name}` | {c.type} | {'yes' if c.nullable else 'no'} | {', '.join(keys)} | {default} |")
            checks = [c for c in t.constraints if isinstance(c, CheckConstraint)]
            uniques = [c for c in t.constraints if isinstance(c, UniqueConstraint)]
            extra_idx = [i for i in t.indexes if len(i.columns) > 1 or i.name and not i.name.startswith(f"ix_{name}_")]
            if uniques:
                out += ["", "Unique: " + "; ".join(f"`({', '.join(col.name for col in u.columns)})`" for u in uniques)]
            if extra_idx:
                out += ["", "Indexes: " + "; ".join(f"`{i.name}({', '.join(col.name for col in i.columns)})`" for i in extra_idx)]
            if checks:
                out += ["", "Checks:"] + [f"- `{c.sqltext}`" for c in checks]
            out.append("")
    return "\n".join(out) + "\n"


def main() -> int:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO_ROOT / "docs/architecture/DATABASE_SCHEMA.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(), encoding="utf-8")
    print(f"wrote {out} ({len(Base.metadata.tables)} tables)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
