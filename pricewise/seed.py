"""Seed the database from the bundled sample receipts.

Lets the dashboard show real charts on first run with zero setup.
"""

from __future__ import annotations

import os

from . import db
from .parser import parse_receipt

SAMPLE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sample_receipts")


def seed_from_samples(db_path: str = db.DB_PATH, sample_dir: str = SAMPLE_DIR) -> int:
    """Parse every .txt in sample_dir and insert. Returns count of receipts added."""
    if not os.path.isdir(sample_dir):
        return 0

    added = 0
    with db.session(db_path) as conn:
        for fname in sorted(os.listdir(sample_dir)):
            if not fname.lower().endswith(".txt"):
                continue
            path = os.path.join(sample_dir, fname)
            with open(path, "r", encoding="utf-8") as fh:
                text = fh.read()
            parsed = parse_receipt(text)
            if not parsed.items:
                continue
            db.insert_receipt(
                conn,
                store=parsed.store,
                purchased_on=parsed.purchased_on,
                total=parsed.total if parsed.total is not None else parsed.computed_total,
                source_file=fname,
                items=[vars(it) for it in parsed.items],
                city=parsed.city,
                state=parsed.state,
                zip=parsed.zip,
            )
            added += 1
    return added


def seed_example_watches(db_path: str = db.DB_PATH) -> None:
    """Add a couple of demo price watches (one that triggers, one that doesn't)."""
    with db.session(db_path) as conn:
        if db.list_watches(conn):
            return
        db.add_watch(conn, norm_key="milk", label="Milk", threshold=3.00)
        db.add_watch(conn, norm_key="coffee", label="Coffee", threshold=6.00)


def ensure_seeded(db_path: str = db.DB_PATH) -> int:
    db.init_db(db_path)
    if db.is_empty(db_path):
        n = seed_from_samples(db_path)
        seed_example_watches(db_path)
        return n
    return 0


if __name__ == "__main__":
    db.reset_db()
    n = seed_from_samples()
    print(f"Seeded {n} receipts from {SAMPLE_DIR}")
