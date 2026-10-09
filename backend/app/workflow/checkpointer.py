"""LangGraph checkpoint persistence using SQLite.

Provides async context managers for SQLite-backed checkpoint storage.
Supports workflow state persistence, recovery, and resumption.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator


@asynccontextmanager
async def checkpoint_saver(db_path: str | None = None) -> AsyncIterator[Any]:
    """Provide an async SQLite checkpointer for workflow persistence.

    Args:
        db_path: Path to SQLite database file. Defaults to
                 ./data/workflow_checkpoints.db

    Yields:
        An AsyncSqliteSaver instance for use with LangGraph workflows.
    """
    if db_path is None:
        db_path = os.environ.get("WORKFLOW_CHECKPOINT_DB", "./data/workflow_checkpoints.db")

    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    async with AsyncSqliteSaver.from_conn_string(db_path) as saver:
        yield saver


async def get_checkpoint_saver(db_path: str | None = None) -> Any:
    """Get an async SQLite checkpointer for workflow persistence.

    This is a convenience function that creates a checkpointer
    without using the context manager. The caller is responsible
    for closing the underlying connection.
    """
    if db_path is None:
        db_path = os.environ.get("WORKFLOW_CHECKPOINT_DB", "./data/workflow_checkpoints.db")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    import aiosqlite
    from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

    conn = await aiosqlite.connect(db_path)
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver


async def compile_with_checkpoint(
    graph: Any,
    db_path: str | None = None,
) -> Any:
    """Compile a LangGraph workflow with SQLite checkpoint persistence.

    Args:
        graph: A LangGraph StateGraph to compile.
        db_path: Path to SQLite database file.

    Returns:
        A compiled workflow with checkpoint persistence.
    """
    # Create checkpointer using the helper function
    saver = await get_checkpoint_saver(db_path)
    return graph.compile(checkpointer=saver)