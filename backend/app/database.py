"""Database wiring.

A single async SQLAlchemy engine + session for application tables.

The LangGraph checkpoint saver is intentionally NOT configured here; it is
wired in a later milestone once orchestration is implemented. The
``get_checkpoint_saver`` helper below is retained (lazily) for that future use.
"""

from __future__ import annotations

from pathlib import Path
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def _ensure_sqlite_dir(database_url: str) -> None:
    """Create the parent directory for a SQLite database file, if any.

    aiosqlite refuses to open a database whose directory does not exist. The
    default path is absolute (see ``app.config``), so without this the first
    run in a fresh checkout fails with "unable to open database file".
    """
    if not database_url.startswith("sqlite"):
        return
    # Use SQLAlchemy's own URL parser so the database component is extracted
    # consistently with how the engine opens the file.
    from sqlalchemy.engine.url import make_url

    file_part = make_url(database_url).database or ""
    if not file_part or not file_part.startswith("/"):
        # Relative path — leave it to the process CWD as documented.
        return
    parent = Path(file_part).parent
    if parent and not parent.exists():
        parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_dir(settings.database_url)

engine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=10,
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency yielding a request-scoped async session."""
    async with AsyncSessionLocal() as asession:
        yield asession


# ---------------------------------------------------------------------------
# Reserved for the future LangGraph checkpoint saver (orchestration milestone).
# ---------------------------------------------------------------------------
def _checkpoint_dsn() -> str:
    """Return the checkpoint DSN, forcing the checkpoint search_path.

    langgraph-checkpoint-postgres's PostgresSaver.setup() creates its tables in
    whatever search_path the connection uses. We keep the application tables in
    `public` and the checkpoint tables in `checkpoint` so neither migration
    can clobber the other.
    """
    dsn = settings.checkpoint_dsn
    if not dsn:
        return dsn
    if "search_path" not in dsn:
        sep = "&" if "?" in dsn else "?"
        dsn = f"{dsn}{sep}options=search_path%3Dcheckpoint"
    return dsn


def get_checkpoint_saver():
    """Build a PostgresSaver bound to the checkpoint schema.

    Reserved for the orchestration milestone. Milestone 1 never calls this.
    """
    import psycopg  # local import: only needed when a Postgres checkpoint DSN is set
    from langgraph.checkpoint.postgres import PostgresSaver

    conn = psycopg.connect(_checkpoint_dsn(), autocommit=False)
    saver = PostgresSaver(conn)
    saver.setup()  # idempotent: creates checkpoint tables if absent
    return saver