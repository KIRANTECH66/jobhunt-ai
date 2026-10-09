"""LangGraph checkpoint persistence using SQLite.

Provides a context manager for SQLite-backed checkpoint storage.
Supports workflow state persistence, recovery, and resumption.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


@contextmanager
def checkpoint_saver(db_path: str | None = None) -> Iterator[Any]:
    """Provide a SQLite checkpointer for workflow persistence.

    Args:
        db_path: Path to SQLite database file. Defaults to
                 ./data/workflow_checkpoints.db

    Yields:
        A SqliteSaver instance for use with LangGraph workflows.
    """
    if db_path is None:
        db_path = os.environ.get("WORKFLOW_CHECKPOINT_DB", "./data/workflow_checkpoints.db")

    # Ensure parent directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from langgraph.checkpoint.sqlite import SqliteSaver

    with SqliteSaver.from_conn_string(db_path) as saver:
        yield saver


def get_checkpoint_saver(db_path: str | None = None) -> Any:
    """Get a SQLite checkpointer for workflow persistence.

    This is a convenience function that creates a checkpointer
    without using the context manager. The caller is responsible
    for closing the underlying connection.
    """
    if db_path is None:
        db_path = os.environ.get("WORKFLOW_CHECKPOINT_DB", "./data/workflow_checkpoints.db")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from langgraph.checkpoint.sqlite import SqliteSaver

    return SqliteSaver.from_conn_string(db_path)


def compile_with_checkpoint(
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
    if db_path is None:
        db_path = os.environ.get("WORKFLOW_CHECKPOINT_DB", "./data/workflow_checkpoints.db")

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    from langgraph.checkpoint.sqlite import SqliteSaver

    saver = SqliteSaver.from_conn_string(db_path)
    return graph.compile(checkpointer=saver)