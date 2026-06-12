"""Storage layer for baskwise.

Backed by SQLAlchemy so a single DATABASE_URL switches between local SQLite
(development) and cloud Postgres (production) with no other code changes:

  • DATABASE_URL unset            -> local SQLite file (pricewise.db)
  • DATABASE_URL=postgresql://... -> persistent Postgres (Supabase / Neon)

Set DATABASE_URL on the host (e.g. Render) to a free Supabase/Neon Postgres to
get a persistent, multi-user, ever-growing community price database. Schema is
small and factual: receipts, their line items, and price watches.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterable, Iterator

from sqlalchemy import (
    Column, Float, ForeignKey, Integer, MetaData, String, Table,
    create_engine, func, select,
)
from sqlalchemy.engine import Connection, Engine

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pricewise.db")

metadata = MetaData()

# Tables are UPPERCASE module constants so they don't collide with the `items`
# function parameter in insert_receipt.
RECEIPTS = Table(
    "receipts", metadata,
    Column("id", Integer, primary_key=True),
    Column("store", String, nullable=False),
    Column("city", String),
    Column("state", String),
    Column("zip", String),
    Column("purchased_on", String, nullable=False),   # ISO date — required
    Column("purchased_time", String),                 # HH:MM if on receipt
    Column("total", Float),
    Column("source_file", String),
    Column("created_at", String),
    Column("user_email", String, index=True),         # owner; NULL = community/seed
)

ITEMS = Table(
    "items", metadata,
    Column("id", Integer, primary_key=True),
    Column("receipt_id", Integer,
           ForeignKey("receipts.id", ondelete="CASCADE"), nullable=False, index=True),
    Column("raw_text", String, nullable=False),
    Column("name", String, nullable=False),
    Column("norm_key", String, nullable=False, index=True),
    Column("category", String, nullable=False, index=True),
    Column("upc", String),
    Column("qty", Float, nullable=False, default=1),
    Column("unit_price", Float),
    Column("line_total", Float, nullable=False),
)

WATCHES = Table(
    "watches", metadata,
    Column("id", Integer, primary_key=True),
    Column("norm_key", String, nullable=False, unique=True),
    Column("label", String, nullable=False),
    Column("threshold", Float, nullable=False),
    Column("created_at", String),
)

_engine: Engine | None = None


def database_url() -> str:
    """Resolve the DB URL: DATABASE_URL if set, else a local SQLite file."""
    url = os.environ.get("DATABASE_URL", "").strip()
    if url:
        # Some hosts hand out the legacy postgres:// scheme; SQLAlchemy wants postgresql://
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url
    return f"sqlite:///{DB_PATH}"


def is_postgres() -> bool:
    return database_url().startswith("postgresql")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), future=True, pool_pre_ping=True)
    return _engine


def get_connection() -> Connection:
    """A fresh SQLAlchemy connection (works as a context manager and with pandas)."""
    return get_engine().connect()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _migrate(engine: Engine) -> None:
    """Add columns that post-date a deployed DB (works on SQLite + Postgres)."""
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    wanted = {"receipts": ["user_email"]}
    with engine.begin() as conn:
        for table, cols in wanted.items():
            if table not in tables:
                continue
            have = {c["name"] for c in insp.get_columns(table)}
            for col in cols:
                if col not in have:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} VARCHAR"))


def init_db(db_path: str = DB_PATH) -> None:
    engine = get_engine()
    metadata.create_all(engine)
    _migrate(engine)


@contextmanager
def session(db_path: str = DB_PATH) -> Iterator[Connection]:
    """Transactional connection — commits on success, rolls back on error."""
    with get_engine().begin() as conn:
        yield conn


def insert_receipt(
    conn: Connection,
    *,
    store: str,
    purchased_on: str,
    total: float | None,
    source_file: str | None,
    items: Iterable[dict],
    city: str | None = None,
    state: str | None = None,
    zip: str | None = None,
    purchased_time: str | None = None,
    user_email: str | None = None,
) -> int:
    """Insert one receipt and its line items. Returns the new receipt id."""
    result = conn.execute(RECEIPTS.insert().values(
        store=store, city=city, state=state, zip=zip,
        purchased_on=purchased_on, purchased_time=purchased_time,
        total=total, source_file=source_file, created_at=_now(),
        user_email=user_email,
    ))
    receipt_id = int(result.inserted_primary_key[0])
    rows = [
        {
            "receipt_id": receipt_id,
            "raw_text": it["raw_text"],
            "name": it["name"],
            "norm_key": it["norm_key"],
            "category": it["category"],
            "upc": it.get("upc"),
            "qty": it.get("qty", 1),
            "unit_price": it.get("unit_price"),
            "line_total": it["line_total"],
        }
        for it in items
    ]
    if rows:
        conn.execute(ITEMS.insert(), rows)
    return receipt_id


def add_watch(conn: Connection, *, norm_key: str, label: str, threshold: float) -> None:
    """Add or update a price watch (dialect-agnostic upsert)."""
    exists = conn.execute(
        select(WATCHES.c.id).where(WATCHES.c.norm_key == norm_key)
    ).first()
    if exists:
        conn.execute(
            WATCHES.update().where(WATCHES.c.norm_key == norm_key)
            .values(label=label, threshold=threshold)
        )
    else:
        conn.execute(WATCHES.insert().values(
            norm_key=norm_key, label=label, threshold=threshold, created_at=_now(),
        ))


def list_watches(conn: Connection) -> list[dict]:
    rows = conn.execute(
        select(WATCHES.c.id, WATCHES.c.norm_key, WATCHES.c.label, WATCHES.c.threshold)
        .order_by(WATCHES.c.label)
    ).mappings().all()
    return [dict(r) for r in rows]


def delete_watch(conn: Connection, watch_id: int) -> None:
    conn.execute(WATCHES.delete().where(WATCHES.c.id == watch_id))


def is_empty(db_path: str = DB_PATH) -> bool:
    with get_engine().connect() as conn:
        n = conn.execute(select(func.count()).select_from(RECEIPTS)).scalar()
        return (n or 0) == 0


def reset_db(db_path: str = DB_PATH) -> None:
    metadata.drop_all(get_engine())
    metadata.create_all(get_engine())
