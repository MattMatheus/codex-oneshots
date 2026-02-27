from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class UserRecord:
    id: str
    name: str
    created_at: str


@dataclass
class SessionRecord:
    id: str
    user_id: str
    started_at: str
    ended_at: str | None
    source_ref: str | None


@dataclass
class ThrowRecord:
    id: int
    user_id: str
    session_id: str
    ts: str
    x_norm: float
    y_norm: float
    confidence: float


class DartBoardStore:
    def __init__(self, db_path: str = "dartboard.db") -> None:
        self.db_path = Path(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    source_ref TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(id)
                );

                CREATE TABLE IF NOT EXISTS throws (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    x_norm REAL NOT NULL,
                    y_norm REAL NOT NULL,
                    confidence REAL NOT NULL,
                    FOREIGN KEY(user_id) REFERENCES users(id),
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );

                CREATE INDEX IF NOT EXISTS idx_throws_user ON throws(user_id);
                CREATE INDEX IF NOT EXISTS idx_throws_session ON throws(session_id);
                """
            )

    @staticmethod
    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_user(self, user_id: str, name: str) -> UserRecord:
        with self._lock, self._connect() as conn:
            created_at = self._now_iso()
            conn.execute(
                "INSERT INTO users (id, name, created_at) VALUES (?, ?, ?)",
                (user_id, name, created_at),
            )
            return UserRecord(id=user_id, name=name, created_at=created_at)

    def get_user(self, user_id: str) -> UserRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row is None:
                return None
            return UserRecord(id=row["id"], name=row["name"], created_at=row["created_at"])

    def create_session(self, session_id: str, user_id: str, source_ref: str | None) -> SessionRecord:
        with self._lock, self._connect() as conn:
            started_at = self._now_iso()
            conn.execute(
                "INSERT INTO sessions (id, user_id, started_at, ended_at, source_ref) VALUES (?, ?, ?, ?, ?)",
                (session_id, user_id, started_at, None, source_ref),
            )
            return SessionRecord(
                id=session_id,
                user_id=user_id,
                started_at=started_at,
                ended_at=None,
                source_ref=source_ref,
            )

    def get_session(self, session_id: str) -> SessionRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None:
                return None
            return SessionRecord(
                id=row["id"],
                user_id=row["user_id"],
                started_at=row["started_at"],
                ended_at=row["ended_at"],
                source_ref=row["source_ref"],
            )

    def add_throw(
        self,
        user_id: str,
        session_id: str,
        x_norm: float,
        y_norm: float,
        confidence: float,
    ) -> ThrowRecord:
        with self._lock, self._connect() as conn:
            ts = self._now_iso()
            cursor = conn.execute(
                """
                INSERT INTO throws (user_id, session_id, ts, x_norm, y_norm, confidence)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (user_id, session_id, ts, x_norm, y_norm, confidence),
            )
            throw_id = int(cursor.lastrowid)
            return ThrowRecord(
                id=throw_id,
                user_id=user_id,
                session_id=session_id,
                ts=ts,
                x_norm=x_norm,
                y_norm=y_norm,
                confidence=confidence,
            )

    def list_throws_for_user(self, user_id: str) -> list[ThrowRecord]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, user_id, session_id, ts, x_norm, y_norm, confidence
                FROM throws
                WHERE user_id = ?
                ORDER BY id ASC
                """,
                (user_id,),
            ).fetchall()
            return [
                ThrowRecord(
                    id=row["id"],
                    user_id=row["user_id"],
                    session_id=row["session_id"],
                    ts=row["ts"],
                    x_norm=row["x_norm"],
                    y_norm=row["y_norm"],
                    confidence=row["confidence"],
                )
                for row in rows
            ]

    def clear_throws_for_user(self, user_id: str) -> int:
        """Delete all throws for a user. Returns the number of rows deleted."""
        with self._lock, self._connect() as conn:
            cursor = conn.execute("DELETE FROM throws WHERE user_id = ?", (user_id,))
            return cursor.rowcount
