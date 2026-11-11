"""Read-only Gmail invoice discovery for a local, single-user demo.

Only PDF/TXT attachments are downloaded. No messages are altered or sent.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
MAX_ATTACHMENT_BYTES = 8 * 1024 * 1024
DEFAULT_QUERY = "has:attachment {filename:pdf filename:txt} newer_than:90d"


@dataclass(frozen=True)
class InvoiceAttachment:
    message_id: str
    attachment_key: str
    filename: str
    sender: str
    subject: str
    content: bytes


def decode_body(data: str) -> bytes:
    if not isinstance(data, str):
        raise ValueError("Invalid attachment data")
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def iter_attachment_parts(payload: dict):
    """Yield nested MIME parts with acceptable invoice attachment names."""
    stack = [payload]
    while stack:
        part = stack.pop()
        stack.extend(reversed(part.get("parts") or []))
        name = part.get("filename", "")
        if name and Path(name).suffix.lower() in {".pdf", ".txt"}:
            yield part


def get_gmail_service(credentials_path: Path, token_path: Path, interactive: bool = False):
    """Use OAuth desktop app flow; only open browser if explicitly requested."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    if creds and not creds.valid and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(token_path, creds.to_json())
    if not creds or not creds.valid:
        if not interactive:
            raise RuntimeError("Gmail not connected. Click Connect Gmail first.")
        if not credentials_path.is_file():
            raise FileNotFoundError(
                f"Missing {credentials_path.name}. Download a Desktop OAuth client JSON from Google Cloud and save it here."
            )
        flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
        creds = flow.run_local_server(port=0, open_browser=True)
        _save_token(token_path, creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def _save_token(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def scan_invoices(service, query: str = DEFAULT_QUERY, max_messages: int = 25) -> list[InvoiceAttachment]:
    """Fetch PDF/TXT attachments from matching messages (limited for safety)."""
    max_messages = max(1, min(int(max_messages), 100))
    response = service.users().messages().list(userId="me", q=query, maxResults=max_messages).execute()
    found = []
    for item in response.get("messages", []):
        mid = item["id"]
        message = service.users().messages().get(userId="me", id=mid, format="full").execute()
        headers = {h.get("name", "").lower(): h.get("value", "") for h in message.get("payload", {}).get("headers", [])}
        for part in iter_attachment_parts(message.get("payload", {})):
            body = part.get("body") or {}
            if body.get("size", 0) > MAX_ATTACHMENT_BYTES:
                continue
            attachment_id = body.get("attachmentId")
            data = body.get("data")
            if attachment_id:
                remote = service.users().messages().attachments().get(
                    userId="me", messageId=mid, id=attachment_id
                ).execute()
                if remote.get("size", 0) > MAX_ATTACHMENT_BYTES:
                    continue
                data = remote.get("data")
            if not data:
                continue
            raw = decode_body(data)
            if len(raw) > MAX_ATTACHMENT_BYTES:
                continue
            part_key = attachment_id or part.get("partId") or part["filename"]
            found.append(InvoiceAttachment(
                message_id=mid,
                attachment_key=f"{mid}:{part_key}",
                filename=Path(part["filename"]).name,
                sender=headers.get("from", ""),
                subject=headers.get("subject", ""),
                content=raw,
            ))
    return found
