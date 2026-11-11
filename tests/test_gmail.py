from invoice_ai.gmail_integration import decode_body, iter_attachment_parts, scan_invoices
from invoice_ai.storage import imported_keys, load_gmail_invoices, save_gmail_invoice, update_gmail_invoice
import base64


class Call:
    def __init__(self, obj):
        self.obj = obj
    def execute(self):
        return self.obj


class Messages:
    def list(self, **kwargs):
        return Call({"messages": [{"id": "mail1"}]})
    def get(self, **kwargs):
        return Call({"payload": {"headers": [{"name": "Subject", "value": "Invoice"}],
                                 "parts": [{"filename": "invoice.txt", "body": {"attachmentId": "a1", "size": 17}}]}})
    def attachments(self):
        return self
    def get_attachment(self, **kwargs):
        return Call({"data": base64.urlsafe_b64encode(b"Total: $25\n").decode(), "size": 11})


class FakeMessages(Messages):
    def attachments(self):
        return FakeAttachments()


class FakeAttachments:
    def get(self, **kwargs):
        return Call({"data": base64.urlsafe_b64encode(b"Total: $25\n").decode(), "size": 11})


class Service:
    def users(self):
        return self
    def messages(self):
        return FakeMessages()


def test_scan_supported_gmail_attachment():
    items = scan_invoices(Service())
    assert len(items) == 1
    assert items[0].content == b"Total: $25\n"
    assert items[0].attachment_key == "mail1:a1"


def test_nested_mime_parts():
    assert [p["filename"] for p in iter_attachment_parts({"parts": [
        {"parts": [{"filename": "bill.PDF"}, {"filename": "image.png"}]}]})] == ["bill.PDF"]


def test_base64url_decode():
    assert decode_body(base64.urlsafe_b64encode(b"hi").decode().rstrip("=")) == b"hi"


def test_persistent_import_is_idempotent(tmp_path):
    path = tmp_path / "app.sqlite3"
    invoice = {"invoice_id": "inv_1", "vendor": "Test", "approved": False}
    assert save_gmail_invoice(path, "mail1:a1", invoice)
    assert not save_gmail_invoice(path, "mail1:a1", {**invoice, "invoice_id": "inv_2"})
    assert imported_keys(path) == {"mail1:a1"}
    invoice["approved"] = True
    update_gmail_invoice(path, invoice)
    assert load_gmail_invoices(path) == [invoice]
