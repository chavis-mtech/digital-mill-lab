"""Relative SQLite URLs resolve inside the repo and may never escape it."""

import pytest

from app.config import REPO_ROOT, resolve_database_url


def test_relative_url_resolves_inside_repo():
    url = resolve_database_url("sqlite:///data/dev/_pathtest.db")
    assert url.startswith("sqlite:////")
    assert str(REPO_ROOT.resolve()) in url


def test_relative_url_escaping_repo_is_rejected():
    with pytest.raises(ValueError, match="outside the repository"):
        resolve_database_url("sqlite:///../../data/dev/x.db")


def test_absolute_and_memory_urls_untouched():
    assert resolve_database_url("sqlite:///:memory:") == "sqlite:///:memory:"
    assert resolve_database_url("sqlite:////tmp/abs.db") == "sqlite:////tmp/abs.db"
