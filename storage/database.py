"""
database.py
------------
Thin storage-layer helpers used ONLY by the integration/CLI layer for
things Member 2's Indexer intentionally does not track: run history
(for "last indexing time/duration") and a couple of read-only stats
queries.

Design choice: rather than modifying indexer.Indexer (Member 2's
module), this opens its own short-lived sqlite3 connection to the same
database file and adds one small additional table, `index_runs`. This
keeps Member 2's class untouched while giving Member 4's CLI the data
it needs for the statistics screen.
"""

import sqlite3
import time
from pathlib import Path
from typing import Optional, Dict, Any


def _connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_run_history_table(db_path: str) -> None:
    """Create the index_runs table if it doesn't exist yet."""
    conn = _connect(db_path)
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS index_runs (
                run_id           INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at       REAL NOT NULL,
                duration_seconds REAL NOT NULL,
                files_discovered INTEGER NOT NULL,
                files_indexed    INTEGER NOT NULL,
                files_skipped    INTEGER NOT NULL,
                errors           INTEGER NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def record_index_run(
    db_path: str,
    started_at: float,
    duration_seconds: float,
    files_discovered: int,
    files_indexed: int,
    files_skipped: int,
    errors: int,
) -> None:
    """Persist one indexing run for later display in Index Statistics."""
    ensure_run_history_table(db_path)
    conn = _connect(db_path)
    try:
        conn.execute(
            """INSERT INTO index_runs
               (started_at, duration_seconds, files_discovered,
                files_indexed, files_skipped, errors)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (started_at, duration_seconds, files_discovered,
             files_indexed, files_skipped, errors),
        )
        conn.commit()
    finally:
        conn.close()


def get_last_run(db_path: str) -> Optional[Dict[str, Any]]:
    """Return the most recent index_runs row, or None if never indexed."""
    if not Path(db_path).exists():
        return None
    ensure_run_history_table(db_path)
    conn = _connect(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM index_runs ORDER BY run_id DESC LIMIT 1"
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_unique_term_count(db_path: str) -> int:
    """Number of distinct terms across the whole inverted index."""
    if not Path(db_path).exists():
        return 0
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT COUNT(DISTINCT term) AS c FROM terms").fetchone()
        return row["c"] if row else 0
    except sqlite3.OperationalError:
        # 'terms' table doesn't exist yet (no index built).
        return 0
    finally:
        conn.close()


def get_database_size_bytes(db_path: str) -> int:
    """Size of the SQLite database file on disk, in bytes."""
    path = Path(db_path)
    return path.stat().st_size if path.exists() else 0


def database_exists(db_path: str) -> bool:
    return Path(db_path).exists()
