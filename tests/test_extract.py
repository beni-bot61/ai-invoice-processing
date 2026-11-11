from pathlib import Path
from invoice_ai.extract import demo_extract, read_document


def test_extract_sample_invoice():
    data = demo_extract(Path("sample_data/invoices/sample_invoice.txt").read_text())
    assert data["vendor"] == "Example Office Goods"
    assert data["amount"] == "700.00"
    assert data["due_date"] == "2026-11-30"
    assert data["approved"] is False


def test_read_txt():
    assert read_document("a.txt", b"hello") == "hello"
