from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def init_db(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS daily_close (
              instrument_id TEXT NOT NULL,
              d TEXT NOT NULL,
              close REAL NOT NULL,
              PRIMARY KEY (instrument_id, d)
            )
            """
        )
        conn.commit()


def read_series(conn: sqlite3.Connection, instrument_id: str, d0: date, d1: date) -> List[Tuple[date, float]]:
    cur = conn.execute(
        """
        SELECT d, close FROM daily_close
        WHERE instrument_id = ? AND d >= ? AND d <= ?
        ORDER BY d
        """,
        (instrument_id, d0.isoformat(), d1.isoformat()),
    )
    out: List[Tuple[date, float]] = []
    for row in cur.fetchall():
        ds, cl = row
        out.append((date.fromisoformat(ds), float(cl)))
    return out


def upsert_rows(conn: sqlite3.Connection, instrument_id: str, rows: Iterable[Tuple[date, float]]) -> None:
    data = [(instrument_id, d.isoformat(), float(c)) for d, c in rows]
    conn.executemany(
        """
        INSERT INTO daily_close (instrument_id, d, close)
        VALUES (?, ?, ?)
        ON CONFLICT(instrument_id, d) DO UPDATE SET close = excluded.close
        """,
        data,
    )
    conn.commit()


def count_in_range(conn: sqlite3.Connection, instrument_id: str, d0: date, d1: date) -> int:
    cur = conn.execute(
        """
        SELECT COUNT(*) FROM daily_close
        WHERE instrument_id = ? AND d >= ? AND d <= ?
        """,
        (instrument_id, d0.isoformat(), d1.isoformat()),
    )
    return int(cur.fetchone()[0])


def series_to_dict(series: List[Tuple[date, float]]) -> Dict[date, float]:
    return {d: c for d, c in series}
