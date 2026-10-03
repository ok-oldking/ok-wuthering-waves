"""Completion-mark persistence for the map overlay interaction feature.

Stores the set of completed ``location.id`` / ``Path_Node.position_id`` values in
a dedicated SQLite database (``assets/stitched/map_marks.db``). Only completed
ids are stored, one row per id.

This module is intentionally free of Qt / game runtime dependencies so it can be
tested on a development machine against a temporary SQLite file.

Validates: Requirements 3.1, 3.2, 3.3, 3.6, 3.7, 3.8, 6.4, 6.5
"""

import sqlite3


class MapMarksDB:
    """Read/write API for the completion-marks database.

    The backing table stores only completed ids, each at most once::

        CREATE TABLE IF NOT EXISTS completed_marks (
            location_id TEXT PRIMARY KEY
        );
    """

    def __init__(self, db_path: str):
        """Open/create the marks DB and ensure the schema exists.

        Uses ``PRAGMA journal_mode=WAL`` to stay consistent with
        ``map_items.db`` (see ``MapItemOverlay``).

        线程安全说明（关键 bug 修复，问题3）：连接通常在任务线程首次 ``_ensure_marks``
        时创建，而 ``add`` / ``remove`` 由 GUI 线程的右键处理调用（跨线程复用同一连接）。
        sqlite 默认 ``check_same_thread=True`` 会禁止跨线程复用连接并抛
        ``sqlite3.ProgrammingError``（``sqlite3.Error`` 子类），导致写入被回滚、标记
        无法持久化，重启后点位仍显示未完成。这里显式传入 ``check_same_thread=False``
        允许跨线程复用同一连接。SQLite 默认编译为 serialized 线程模式，对本模块这种
        低频读写是安全的。``self._conn`` 属性保持不变（失败回滚单测会替换 ``db._conn``）。
        """
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS completed_marks (location_id TEXT PRIMARY KEY)"
        )
        self._conn.commit()

    def load_completed(self) -> set:
        """Return the set of all completed ids (Requirement 3.6)."""
        cursor = self._conn.execute("SELECT location_id FROM completed_marks")
        return {row[0] for row in cursor.fetchall()}

    def add(self, location_id: str) -> None:
        """Mark ``location_id`` as completed.

        Idempotent: repeating the call does not create duplicate rows
        (Requirements 3.1, 3.2).
        """
        self._conn.execute(
            "INSERT OR IGNORE INTO completed_marks(location_id) VALUES (?)",
            (location_id,),
        )
        self._conn.commit()

    def remove(self, location_id: str) -> None:
        """Remove the completion mark for ``location_id`` (Requirement 3.3)."""
        self._conn.execute(
            "DELETE FROM completed_marks WHERE location_id = ?",
            (location_id,),
        )
        self._conn.commit()

    def is_completed(self, location_id: str) -> bool:
        """Return whether ``location_id`` currently has a completion mark."""
        cursor = self._conn.execute(
            "SELECT 1 FROM completed_marks WHERE location_id = ? LIMIT 1",
            (location_id,),
        )
        return cursor.fetchone() is not None

    def close(self) -> None:
        """Close the underlying database connection."""
        self._conn.close()


def load_completed_or_empty(db) -> set:
    """Failure-safe load of the completed set.

    On a successful read this returns ``db.load_completed()``. If reading the
    marks database fails for any reason (missing/corrupt DB, locked file, broken
    connection), the caller must be able to keep rendering with an empty
    completed set rather than crashing. This helper encapsulates that contract
    so the controller can treat a read failure as "no marks yet".

    Note: opening the database (``MapMarksDB(db_path)``) may itself raise; the
    caller wraps construction in the same way (see Requirement 3.7).

    Validates: Requirements 3.7
    """
    try:
        return db.load_completed()
    except Exception:
        return set()


def reconcile_completed(in_memory, db) -> set:
    """Reconcile an in-memory completed set to the database's persisted records.

    After an optimistic in-memory update (add/remove) whose ``MapMarksDB.add`` /
    ``MapMarksDB.remove`` write subsequently fails, the in-memory completed set
    can diverge from what is actually persisted. This helper returns the
    authoritative completed set so the caller can roll its in-memory state back
    to match the DB's existing records.

    If the database itself cannot be read during reconciliation, the previous
    ``in_memory`` set is returned unchanged (a copy) so the caller never loses
    state or crashes while attempting to recover from a write failure.

    Validates: Requirements 3.8, 6.5
    """
    try:
        return db.load_completed()
    except Exception:
        return set(in_memory)
