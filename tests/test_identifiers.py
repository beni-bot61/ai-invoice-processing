from datetime import date

from invoice_ai.core import recommend, validate_invoice
from invoice_ai.identifiers import ensure_invoice_ids, new_invoice_id, supplier_invoice_key

TODAY = date(2026, 11, 10)


def invoice(vendor, number, **extra):
    return {"vendor": vendor, "invoice_number": number, "amount": "100",
            "due_date": "2026-11-13", "department": "IT", "approved": True,
            "bank_details_changed": False, **extra}


def company():
    return {"current_cash": "1000", "minimum_cash_reserve": "100",
            "remaining_budgets": {"IT": "1000"}, "cash_events": []}


def test_internal_ids_unique_and_stable_on_migration():
    records = [invoice("A", "1"), invoice("B", "1"), invoice("A", "2")]
    updated = ensure_invoice_ids(records)
    assert all(record["invoice_id"].startswith("inv_") for record in updated)
    assert len({record["invoice_id"] for record in updated}) == 3
    assert [r["invoice_id"] for r in ensure_invoice_ids(updated)] == [r["invoice_id"] for r in updated]
    assert all("invoice_id" not in r for r in records)


def test_repeated_internal_id_is_replaced():
    updated = ensure_invoice_ids([invoice("A", "1", invoice_id="same"), invoice("B", "1", invoice_id="same")])
    assert updated[0]["invoice_id"] == "same"
    assert updated[1]["invoice_id"] != "same"


def test_supplier_invoice_key_normalizes_spaces_and_case():
    assert supplier_invoice_key(invoice("  ABC   Supplies ", " inv-001 ")) == ("abc supplies", "inv-001")
    assert supplier_invoice_key(invoice("A", "")) is None


def test_same_number_different_vendor_not_duplicate():
    rows = recommend([invoice("A", "INV-001"), invoice("B", "INV-001")], company(), TODAY)
    assert [r["status"] for r in rows] == ["SCHEDULE SUGGESTED", "SCHEDULE SUGGESTED"]


def test_same_vendor_number_detected_even_with_distinct_internal_ids():
    rows = ensure_invoice_ids([invoice("A", "INV-001"), invoice("a", "inv-001")])
    results = recommend(rows, company(), TODAY)
    assert results[1]["status"] == "REVIEW"
    assert "duplicate" in results[1]["reason"].lower()
    assert results[0]["invoice_id"] != results[1]["invoice_id"]


def test_missing_vendor_number_review_without_false_duplicate():
    seen = set()
    a = validate_invoice(invoice("A", ""), seen)
    b = validate_invoice(invoice("A", ""), seen)
    assert "Missing invoice_number" in a
    assert "Missing invoice_number" in b
    assert not any("duplicate" in x.lower() for x in a + b)
