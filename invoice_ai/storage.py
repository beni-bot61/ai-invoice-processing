"""Lightweight persistence for Gmail-imported invoice records and deduplication."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path


def initialize(db_path: Path):
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("""CREATE TABLE IF NOT EXISTS gmail_invoices (
            attachment_key TEXT PRIMARY KEY,
            invoice_id TEXT NOT NULL UNIQUE,
            payload TEXT NOT NULL
        )""")


def imported_keys(db_path: Path) -> set[str]:
    initialize(db_path)
    with sqlite3.connect(db_path) as db:
        return {row[0] for row in db.execute("SELECT attachment_key FROM gmail_invoices")}


def save_gmail_invoice(db_path: Path, attachment_key: str, invoice: dict) -> bool:
    """Returns False when the attachment has already been imported."""
    initialize(db_path)
    with sqlite3.connect(db_path) as db:
        cursor = db.execute(
            "INSERT OR IGNORE INTO gmail_invoices (attachment_key, invoice_id, payload) VALUES (?, ?, ?)",
            (attachment_key, invoice["invoice_id"], json.dumps(invoice)),
        )
        return cursor.rowcount == 1


def load_gmail_invoices(db_path: Path) -> list[dict]:
    initialize(db_path)
    with sqlite3.connect(db_path) as db:
        return [json.loads(row[0]) for row in db.execute("SELECT payload FROM gmail_invoices ORDER BY rowid")]


def update_gmail_invoice(db_path: Path, invoice: dict) -> None:
    """Preserve review edits for an already imported invoice."""
    initialize(db_path)
    with sqlite3.connect(db_path) as db:
        db.execute("UPDATE gmail_invoices SET payload=? WHERE invoice_id=?", (json.dumps(invoice), invoice["invoice_id"]))
