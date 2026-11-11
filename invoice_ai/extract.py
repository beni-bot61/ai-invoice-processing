"""Extract invoice fields from plain text or text-based PDFs.

Demo parser intentionally supports simple labeled invoices only. Optional AI
extraction uses a structured-output API and should be verified by a person.
"""
import io
import json
import os
import re
from datetime import datetime


def read_document(filename: str, content: bytes) -> str:
    if filename.lower().endswith(".pdf"):
        from pypdf import PdfReader
        return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(content)).pages)
    if filename.lower().endswith(".txt"):
        return content.decode("utf-8-sig")
    raise ValueError("Only text-based PDF and UTF-8 .txt are supported")


def demo_extract(text: str) -> dict:
    patterns = {
        "invoice_number": r"(?:invoice\s*(?:number|no\.?|#)|invoice\s*id)\s*:\s*(.+)",
        "vendor": r"(?:vendor|supplier)\s*:\s*(.+)",
        "amount": r"(?:total\s*due|amount\s*due|total)\s*:\s*\$?([\d,]+(?:\.\d{1,2})?)",
        "due_date": r"(?:due\s*date|payment\s*due)\s*:\s*(.+)",
        "department": r"department\s*:\s*(.+)",
    }
    found = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        found[key] = match.group(1).strip() if match else ""
    if found["due_date"]:
        for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%B %d, %Y"):
            try:
                found["due_date"] = datetime.strptime(found["due_date"], fmt).date().isoformat()
                break
            except ValueError:
                continue
    found["approved"] = False
    found["bank_details_changed"] = False
    return found


def ai_extract(text: str, model: str | None = None) -> dict:
    """OpenAI Structured Outputs; no account credentials stored in source."""
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("Set OPENAI_API_KEY to enable AI extraction")
    from openai import OpenAI
    schema = {
        "type": "object", "additionalProperties": False,
        "properties": {
            "invoice_number": {"type": "string"},
            "vendor": {"type": "string"},
            "amount": {"type": "string"},
            "due_date": {"type": "string"},
            "department": {"type": "string"},
        },
        "required": ["invoice_number", "vendor", "amount", "due_date", "department"],
    }
    response = OpenAI().responses.create(
        model=model or os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        instructions=("Extract invoice fields from the supplied document. Return amount as a numeric string "
                      "without currency symbols; due_date as YYYY-MM-DD. If a value is not present, "
                      "return an empty string. Never infer approval or bank-detail status."),
        input=text[:30000],
        text={"format": {"type": "json_schema", "name": "invoice_fields", "strict": True, "schema": schema}},
    )
    if not response.output_text:
        raise ValueError("AI returned no extractable fields")
    result = json.loads(response.output_text)
    result["approved"] = False
    result["bank_details_changed"] = False
    return result
