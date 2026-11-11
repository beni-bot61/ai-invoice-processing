"""Internal IDs are independent of identifiers assigned by suppliers."""
from __future__ import annotations

from uuid import uuid4


def new_invoice_id() -> str:
    """Create an opaque, collision-resistant internal tracking identifier."""
    return f"inv_{uuid4().hex}"


def ensure_invoice_ids(invoices: list[dict]) -> list[dict]:
    """Backfill missing or repeated internal IDs for legacy and sample records.

    Existing valid unique IDs are retained. Does not modify the input list.
    This is an in-memory migration, not a persistent database migration.
    """
    seen: set[str] = set()
    updated: list[dict] = []
    for invoice in invoices:
        record = dict(invoice)
        internal_id = str(record.get("invoice_id") or "").strip()
        if not internal_id or internal_id in seen:
            internal_id = new_invoice_id()
        record["invoice_id"] = internal_id
        seen.add(internal_id)
        updated.append(record)
    return updated


def supplier_invoice_key(invoice: dict) -> tuple[str, str] | None:
    """Return a vendor-scoped key only when both fields are present."""
    vendor = " ".join(str(invoice.get("vendor") or "").split()).casefold()
    number = " ".join(str(invoice.get("invoice_number") or "").split()).casefold()
    return (vendor, number) if vendor and number else None
