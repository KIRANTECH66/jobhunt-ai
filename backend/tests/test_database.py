"""Tests for database wiring and configuration defaults.

Covers the checkpoint DSN helper and the SQLite path default, including
regression tests for the ``_checkpoint_dsn`` undefined-variable bug and the
CWD-dependent relative SQLite path.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from sqlalchemy.engine.url import make_url

from app import database as database_module
from app.config import settings


def _sqlite_db_path(database_url: str) -> str:
    """Extract the database file component from a SQLite URL."""
    return make_url(database_url).database or ""


# --------------------------------------------------------------------------- #
# Regression: _checkpoint_dsn typo (dn -> dsn)
# --------------------------------------------------------------------------- #


def test_checkpoint_dsn_appends_search_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DSN without search_path gets ?options=search_path%3Dcheckpoint appended."""
    monkeypatch.setattr(
        database_module.settings, "checkpoint_dsn", "postgresql://u:p@db:5432/jobhunt"
    )
    assert (
        database_module._checkpoint_dsn()
        == "postgresql://u:p@db:5432/jobhunt?options=search_path%3Dcheckpoint"
    )


def test_checkpoint_dsn_appends_with_existing_query(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DSN with an existing query string appends with &."""
    monkeypatch.setattr(
        database_module.settings,
        "checkpoint_dsn",
        "postgresql://u:p@db:5432/jobhunt?sslmode=require",
    )
    assert (
        database_module._checkpoint_dsn()
        == "postgresql://u:p@db:5432/jobhunt?sslmode=require&options=search_path%3Dcheckpoint"
    )


def test_checkpoint_dsn_preserves_existing_search_path(monkeypatch: pytest.MonkeyPatch) -> None:
    """A DSN that already sets search_path is returned unchanged."""
    monkeypatch.setattr(
        database_module.settings,
        "checkpoint_dsn",
        "postgresql://u:p@db:5432/jobhunt?options=search_path%3Dcheckpoint",
    )
    assert (
        database_module._checkpoint_dsn()
        == "postgresql://u:p@db:5432/jobhunt?options=search_path%3Dcheckpoint"
    )


def test_checkpoint_dsn_empty_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty checkpoint DSN returns an empty string (no crash)."""
    monkeypatch.setattr(database_module.settings, "checkpoint_dsn", "")
    assert database_module._checkpoint_dsn() == ""


def test_checkpoint_dsn_does_not_use_undefined_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: the helper must not reference an undefined ``dn`` variable.

    This test fails on the original bug (NameError) and passes after the fix.
    """
    monkeypatch.setattr(
        database_module.settings, "checkpoint_dsn", "postgresql://u:p@db:5432/jobhunt"
    )
    # Must not raise NameError.
    result = database_module._checkpoint_dsn()
    assert "search_path" in result


# --------------------------------------------------------------------------- #
# Regression: CWD-independent SQLite default path
# --------------------------------------------------------------------------- #


def test_default_database_url_is_absolute() -> None:
    """The default SQLite URL resolves to an absolute path, not CWD-relative."""
    assert settings.database_url.startswith("sqlite+aiosqlite:///")
    db_path = _sqlite_db_path(settings.database_url)
    assert Path(db_path).is_absolute(), (
        f"Default SQLite path must be absolute; got {db_path!r}"
    )
    # Must live under the backend package's parent (repo root), not under an
    # arbitrary process working directory.
    assert "jobhunt-ai" in str(Path(db_path).resolve())


def test_default_database_url_under_repo_data() -> None:
    """The default path is <repo>/data/jobhunt.db."""
    db_path = _sqlite_db_path(settings.database_url)
    assert Path(db_path).name == "jobhunt.db"
    assert Path(db_path).parent.name == "data"


def test_ensure_sqlite_dir_creates_missing_parents(tmp_path: Path) -> None:
    """_ensure_sqlite_dir creates the parent directory for an absolute path."""
    db_path = tmp_path / "nested" / "deep" / "test.db"
    database_module._ensure_sqlite_dir(f"sqlite+aiosqlite:///{db_path.as_posix()}")
    assert db_path.parent.is_dir()


def test_ensure_sqlite_dir_noop_for_non_sqlite() -> None:
    """_ensure_sqlite_dir does nothing for non-SQLite URLs."""
    # Should not raise.
    database_module._ensure_sqlite_dir("postgresql+asyncpg://u:p@db:5432/jobhunt")


def test_ensure_sqlite_dir_noop_for_relative_path() -> None:
    """_ensure_sqlite_dir leaves relative paths to the process CWD."""
    # Should not raise and should not create ./data.
    database_module._ensure_sqlite_dir("sqlite+aiosqlite:///./data/relative.db")


def test_config_reimport_uses_resolved_default() -> None:
    """Re-importing config yields the same resolved absolute default."""
    reloaded = importlib.import_module("app.config")
    assert reloaded.settings.database_url == settings.database_url
    assert reloaded.settings.database_url.startswith("sqlite+aiosqlite:///")
    db_path = _sqlite_db_path(reloaded.settings.database_url)
    assert Path(db_path).is_absolute()