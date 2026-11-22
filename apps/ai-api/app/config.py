"""Environment-based configuration (pydantic-settings).

Demo vs production separation: DEMO_MODE / APP_ENV switch behaviour; nothing secret has a default.
Relative sqlite paths in DATABASE_URL are resolved from the REPO ROOT so every agent, test and
script points at the same file regardless of the current working directory.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]
API_ROOT = Path(__file__).resolve().parents[1]

PRODUCT_NAME = "Digital Mill Lab"
PRODUCT_TAGLINE = "Intelligent Operations & AI Transformation"


def resolve_database_url(url: str) -> str:
    """Make `sqlite:///relative/path.db` absolute relative to the repo root."""
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////") and ":memory:" not in url:
        rel = url[len(prefix) :]
        path = (REPO_ROOT / rel).resolve()
        if REPO_ROOT.resolve() not in path.parents:
            # Guard: a relative path such as ../../data/x.db must never create files outside the repo.
            raise ValueError(f"relative sqlite path resolves outside the repository: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{path}"
    return url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"),),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: Literal["development", "test", "demo", "production"] = "development"
    demo_mode: bool = True
    version: str = "0.1.0"

    database_url: str = "sqlite:///data/demo.db"

    demo_anchor: date = date(2026, 11, 20)
    dataset_days: int = Field(default=120, ge=7, le=1000)
    mill_timezone: str = "Asia/Bangkok"

    rate_limit_enabled: bool = True
    rate_limit_per_ip_per_minute: int = Field(default=240, ge=1)
    rate_limit_per_session_per_minute: int = Field(default=120, ge=1)
    rate_limit_burst: int = Field(default=40, ge=1)
    trust_proxy_headers: bool = False  # honour X-Forwarded-For only behind a trusted reverse proxy
    # SQLite WAL + busy timeout for file databases. OFF by default: switching to WAL rewrites the database file header, which
    # development and tests must not do to the canonical data/demo.db. The Docker entrypoint turns it on for multi-worker serving.
    sqlite_wal: bool = False
    # POST /demo/reset-all clears EVERY visitor's sandbox. The simulated role header is not authentication, so on a public
    # deployment (APP_ENV=demo|production) it is refused unless ALLOW_RESET_ALL=true; development and tests keep it available.
    allow_reset_all: bool | None = None

    @property
    def reset_all_allowed(self) -> bool:
        return self.allow_reset_all if self.allow_reset_all is not None else self.app_env in ("development", "test")
    # number of trusted proxies that each append to X-Forwarded-For in front of the API (e.g. TLS proxy -> Next.js = 2)
    trusted_proxy_hops: int = Field(default=1, ge=1, le=5)

    llm_provider: str = "none"
    llm_model: str = ""
    llm_api_key: str = ""  # never commit a value; blank = deterministic copilot mode

    max_body_bytes: int = Field(default=256 * 1024, ge=1024)  # request-body cap for JSON endpoints (QA-03); uploads: upload_max_bytes + 1 MiB
    upload_max_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    upload_allowed_types: str = "image/jpeg,image/png,image/webp"

    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    log_level: str = "INFO"

    @field_validator("database_url")
    @classmethod
    def _resolve_db(cls, v: str) -> str:
        return resolve_database_url(v)

    # ---- derived -------------------------------------------------------
    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.mill_timezone)

    @property
    def window_start_date(self) -> date:
        """First business day (mill-local) of the dataset window."""
        return self.demo_anchor - timedelta(days=self.dataset_days - 1)

    @property
    def window_start(self) -> datetime:
        """Inclusive UTC start of the dataset window (mill-local midnight of the first day)."""
        return datetime.combine(self.window_start_date, time.min, tzinfo=self.tz).astimezone(UTC)

    @property
    def window_end(self) -> datetime:
        """Exclusive UTC end of the dataset window (mill-local midnight after the anchor day)."""
        end_local = datetime.combine(self.demo_anchor + timedelta(days=1), time.min, tzinfo=self.tz)
        return end_local.astimezone(UTC)

    @property
    def default_as_of(self) -> datetime:
        """Default demo 'now': 18:00 mill-local on the anchor day (end of day shift)."""
        return datetime.combine(self.demo_anchor, time(18, 0), tzinfo=self.tz).astimezone(UTC)

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]

    @property
    def allowed_upload_types(self) -> set[str]:
        return {t.strip() for t in self.upload_allowed_types.split(",") if t.strip()}

    @property
    def llm_enabled(self) -> bool:
        return self.llm_provider.lower() != "none" and bool(self.llm_api_key or self.llm_provider == "local")


@lru_cache
def get_settings() -> Settings:
    return Settings()
