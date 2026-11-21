"""Appraisal storage. SQLite for the prototype; the table maps 1:1 to Postgres/Supabase."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager

from app.config import settings


@contextmanager
def _conn():
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(settings.data_dir / "secondcharge.db")
    try:
        con.execute("CREATE TABLE IF NOT EXISTS appraisals (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, vin TEXT, data TEXT NOT NULL)")
        yield con
        con.commit()
    finally:
        con.close()


def save(result: dict) -> None:
    with _conn() as con:
        con.execute("INSERT OR REPLACE INTO appraisals (id, created_at, vin, data) VALUES (?, ?, ?, ?)",
                    (result["id"], result["created_at"], result["vehicle"]["vin"], json.dumps(result)))


def get(appraisal_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute("SELECT data FROM appraisals WHERE id = ?", (appraisal_id,)).fetchone()
    return json.loads(row[0]) if row else None


def list_all(limit: int = 200) -> list[dict]:
    with _conn() as con:
        rows = con.execute("SELECT data FROM appraisals ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [json.loads(r[0]) for r in rows]
