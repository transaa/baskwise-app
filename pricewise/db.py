"""SQLite storage layer for PriceWise.

Schema is intentionally small and factual: receipts and their line items.
Raw UPCs, prices, store, and date are facts (not copyrightable), which is what
makes the crowdsourced price database both legal and valuable.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from typing import Iterable, Iterator

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pricewise.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS receipts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    store        TEXT NOT NULL,
    city         TEXT,
    state        TEXT,
    zip          TEXT,
    purchased_on TEXT NOT NULL,          -- ISO date (YYYY-MM-DD)
    total        REAL,
    source_file  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    receipt_id  INTEGER NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    raw_text    TEXT NOT NULL,
    name        TEXT NOT NULL,           -- normalized display name
    norm_key    TEXT NOT NULL,           -- canonical key for matching across receipts
    category    TEXT NOT NULL,
    upc         TEXT,
    qty         REAL NOT NULL DEFAULT 1,
    unit_price  REAL,
    line_total  REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_items_normkey ON items(norm_key);
CREATE INDEX IF NOT EXISTS idx_items_category ON items(category);
CREATE INDEX IF NOT EXISTS idx_receipts_store ON receipts(store);

CREATE TABLE IF NOT EXISTS watches (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    norm_key   TEXT NOT NULL,
    label      TEXT NOT NULL,          -- human-friendly product name
    threshold  REAL NOT NULL,          -- alert when cheapest nearby <= this
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(norm_key)
);
"""


def add_watch(conn: sqlite3.Connection, *, norm_key: str, label: str, threshold: float) -> None:
    """Add or update a price watch for a product."""
    conn.execute(
        "INSERT INTO watches (norm_key, label, threshold) VALUES (?, ?, ?) "
        "ON CONFLICT(norm_key) DO UPDATE SET threshold=excluded.threshold, "
        "label=excluded.label",
        (norm_key, label, threshold),
    )


def list_watches(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT id, norm_key, label, threshold FROM watches ORDER BY label"
    ).fetchall()
    return [dict(r) for r in rows]


def delete_watch(conn: sqlite3.Connection, watch_id: int) -> None:
    conn.execute("DELETE FROM watches WHERE id = ?", (watch_id,))


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def session(db_path: str = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def insert_receipt(
    conn: sqlite3.Connection,
    *,
    store: str,
    purchased_on: str,
    total: float | None,
    source_file: str | None,
    items: Iterable[dict],
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
) -> int:
    """Insert one receipt and its line items. Returns the new receipt id."""
    cur = conn.execute(
        "INSERT INTO receipts (store, city, state, zip, purchased_on, total, source_file) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (store, city, state, zip, purchased_on, total, source_file),
    )
    receipt_id = int(cur.lastrowid)
    for it in items:
        conn.execute(
            "INSERT INTO items "
            "(receipt_id, raw_text, name, norm_key, category, upc, qty, unit_price, line_total) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                receipt_id,
                it["raw_text"],
                it["name"],
                it["norm_key"],
                it["category"],
                it.get("upc"),
                it.get("qty", 1),
                it.get("unit_price"),
                it["line_total"],
            ),
        )
    return receipt_id


def is_empty(db_path: str = DB_PATH) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM receipts").fetchone()
        return row["n"] == 0


def reset_db(db_path: str = DB_PATH) -> None:
    with get_connection(db_path) as conn:
        conn.executescript("DROP TABLE IF EXISTS items; DROP TABLE IF EXISTS receipts;")
        conn.commit()
    init_db(db_path)
