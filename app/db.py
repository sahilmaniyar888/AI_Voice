"""Tiny SQLite layer. Synchronous on purpose: every query is a few rows."""
import csv
import os
import random
import sqlite3
import threading
import time
from typing import Any, Optional

from . import config

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS truckers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    city TEXT DEFAULT '',
    truck_type TEXT DEFAULT 'any',
    capacity_tons REAL DEFAULT 0,
    language TEXT DEFAULT 'hindi',
    opted_in INTEGER DEFAULT 1,
    created_at REAL
);
CREATE TABLE IF NOT EXISTS loads (
    id TEXT PRIMARY KEY,
    origin TEXT, destination TEXT, material TEXT,
    weight_tons REAL, truck_type TEXT, pickup_time TEXT,
    target_rate INTEGER, max_rate INTEGER,
    broker_name TEXT, broker_phone TEXT,
    source TEXT DEFAULT 'dashboard',          -- dashboard | voice
    status TEXT DEFAULT 'dispatching',        -- dispatching | quoting | shortlisted | booked
    booked_trucker_id TEXT,
    created_at REAL, first_quote_at REAL, shortlisted_at REAL, booked_at REAL
);
CREATE TABLE IF NOT EXISTS calls (
    id TEXT PRIMARY KEY,
    load_id TEXT, trucker_id TEXT,
    kind TEXT DEFAULT 'quote',                -- quote | confirm | broker_callback
    execution_id TEXT,
    call_status TEXT DEFAULT 'queued',        -- Bolna telephony status
    outcome TEXT DEFAULT 'pending',           -- pending | quoted | declined | no_answer | failed
    available INTEGER,
    quoted_rate INTEGER, final_rate INTEGER,
    truck_location TEXT, eta_hours REAL, truck_number TEXT,
    notes TEXT, transcript TEXT, recording_url TEXT, error TEXT,
    created_at REAL, updated_at REAL
);
CREATE INDEX IF NOT EXISTS idx_calls_exec ON calls(execution_id);
CREATE INDEX IF NOT EXISTS idx_calls_load ON calls(load_id);
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    load_id TEXT, ts REAL, kind TEXT, message TEXT
);
"""


def conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        os.makedirs(os.path.dirname(config.DB_PATH) or ".", exist_ok=True)
        _conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.executescript(SCHEMA)
    return _conn


def q(sql: str, args: tuple = ()) -> list[dict[str, Any]]:
    with _lock:
        cur = conn().execute(sql, args)
        rows = [dict(r) for r in cur.fetchall()]
        conn().commit()
        return rows


def one(sql: str, args: tuple = ()) -> Optional[dict[str, Any]]:
    rows = q(sql, args)
    return rows[0] if rows else None


def insert(table: str, row: dict[str, Any]) -> None:
    cols = ",".join(row.keys())
    marks = ",".join("?" for _ in row)
    q(f"INSERT INTO {table} ({cols}) VALUES ({marks})", tuple(row.values()))


def update(table: str, row_id: str, fields: dict[str, Any]) -> None:
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    q(f"UPDATE {table} SET {sets} WHERE id=?", tuple(fields.values()) + (row_id,))


def new_id(prefix: str, digits: int = 4) -> str:
    # Short, speakable IDs: the voice LLM has to copy these into tool calls.
    while True:
        candidate = f"{prefix}{random.randint(10 ** (digits - 1), 10 ** digits - 1)}"
        table = {"L": "loads", "T": "truckers", "C": "calls"}[prefix]
        if not one(f"SELECT id FROM {table} WHERE id=?", (candidate,)):
            return candidate


def log_event(load_id: str, kind: str, message: str) -> None:
    insert("events", {"load_id": load_id, "ts": time.time(), "kind": kind, "message": message})


def seed_truckers_from_csv(path: str) -> int:
    """Load data/truckers.csv into an empty truckers table. Returns rows added."""
    if one("SELECT id FROM truckers LIMIT 1") or not os.path.exists(path):
        return 0
    added = 0
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not r.get("phone"):
                continue
            insert(
                "truckers",
                {
                    "id": new_id("T", 3),
                    "name": r["name"].strip(),
                    "phone": r["phone"].strip(),
                    "city": r.get("city", "").strip(),
                    "truck_type": (r.get("truck_type") or "any").strip().lower(),
                    "capacity_tons": float(r.get("capacity_tons") or 0),
                    "language": (r.get("language") or "hindi").strip().lower(),
                    "opted_in": int(r.get("opted_in", "1") or 1),
                    "created_at": time.time(),
                },
            )
            added += 1
    return added
