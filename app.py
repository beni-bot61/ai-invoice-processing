"""Streamlit invoice processing demo. NO PAYMENTS are initiated."""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from invoice_ai.core import recommend
from invoice_ai.extract import ai_extract, demo_extract, read_document
from invoice_ai.identifiers import ensure_invoice_ids, new_invoice_id
from invoice_ai.gmail_integration import DEFAULT_QUERY, get_gmail_service, scan_invoices
from invoice_ai.storage import imported_keys, load_gmail_invoices, save_gmail_invoice, update_gmail_invoice

ROOT = Path(__file__).parent
GMAIL_DB = ROOT / ".local_data" / "gmail_imports.sqlite3"
GMAIL_CREDENTIALS = ROOT / "gmail_credentials.json"
GMAIL_TOKEN = ROOT / ".gmail_token.json"
st.set_page_config(page_title="Invoice AI — Demo", page_icon="🧾", layout="wide")
st.title("🧾 Invoice AI — Processing & Payment Recommendations")
st.caption("Demonstration only · Fictional sample data · Never initiates payments")

if "invoices" not in st.session_state:
    st.session_state.invoices = ensure_invoice_ids(
        json.loads((ROOT / "sample_data" / "invoices.json").read_text())
    ) + load_gmail_invoices(GMAIL_DB)
if "company" not in st.session_state:
    st.session_state.company = json.loads((ROOT / "sample_data" / "company.json").read_text())

with st.sidebar:
    st.header("Company finances")
    company = st.session_state.company
    company["current_cash"] = st.number_input("Current cash ($)", value=float(company["current_cash"]), min_value=0., step=1000.)
    company["minimum_cash_reserve"] = st.number_input("Minimum cash reserve ($)", value=float(company["minimum_cash_reserve"]), min_value=0., step=1000.)
    st.subheader("Remaining department budgets ($)")
    for dept in list(company["remaining_budgets"]):
        company["remaining_budgets"][dept] = st.number_input(dept, min_value=0., value=float(company["remaining_budgets"][dept]), step=1000.)
    st.subheader("Expected cash movements")
    st.caption("Positive inflows and outgoing bills are sample projections; edit sample_data/company.json to change them.")
    st.dataframe(pd.DataFrame(company["cash_events"]), hide_index=True)
    if st.button("Reset to example data"):
        st.session_state.pop("company", None)
        st.session_state.pop("invoices", None)
        st.rerun()

upload_tab, gmail_tab, review_tab = st.tabs(["📥 Upload invoice", "📧 Gmail import", "📊 Review & schedule"])
with upload_tab:
    st.markdown("Upload a **text-based PDF** or a **TXT** invoice. Scanned PDFs require OCR, which is not included in this demo.")
    f = st.file_uploader("Invoice document", type=["pdf", "txt"])
    mode = st.radio("Extraction method", ["Local demo parser (free)", "OpenAI extraction (requires API key)"], horizontal=True)
    if f and st.button("Extract invoice"):
        try:
            raw = read_document(f.name, f.getvalue())
            if not raw.strip():
                st.error("No selectable text found; OCR is needed for scanned files.")
            else:
                extracted = ai_extract(raw) if mode.startswith("OpenAI") else demo_extract(raw)
                st.session_state["extracted"] = extracted
        except Exception as exc:
            st.error(f"Extraction failed: {exc}")
    if "extracted" in st.session_state:
        st.subheader("Verify extracted fields")
        st.caption("The document is untrusted input: review all fields before adding. Approval defaults to false.")
        with st.form("edit_invoice"):
            source = st.session_state["extracted"]
            vendor = st.text_input("Vendor", value=source.get("vendor", ""))
            number = st.text_input("Invoice number", value=source.get("invoice_number", ""))
            amount = st.text_input("Amount (USD)", value=str(source.get("amount", "")))
            due = st.text_input("Due date (YYYY-MM-DD)", value=source.get("due_date", ""))
            dept = st.selectbox("Department", list(company["remaining_budgets"]), index=0)
            changed = st.checkbox("Vendor bank details changed (security review required)")
            if st.form_submit_button("Add to review queue"):
                st.session_state.invoices.append({"invoice_id": new_invoice_id(), "vendor": vendor, "invoice_number": number, "amount": amount,
                                                  "due_date": due, "department": dept, "approved": False,
                                                  "bank_details_changed": changed})
                st.success("Added to review queue. Not approved for payment.")
                del st.session_state["extracted"]
    st.info("Try uploading sample_data/invoices/sample_invoice.txt to test the extraction flow.")

with gmail_tab:
    st.subheader("Import invoices from Gmail")
    st.caption("Local desktop OAuth · Gmail read-only access · Nothing is sent or paid · Review every extracted invoice")
    if not GMAIL_CREDENTIALS.exists():
        st.warning("Setup needed: put your Google Cloud Desktop OAuth file at gmail_credentials.json (see README).")
    st.write("Gmail:", "Connected (local token exists)" if GMAIL_TOKEN.exists() else "Not connected")
    if st.button("Connect Gmail", disabled=not GMAIL_CREDENTIALS.exists()):
        try:
            get_gmail_service(GMAIL_CREDENTIALS, GMAIL_TOKEN, interactive=True)
            st.success("Gmail connected with read-only access.")
        except Exception as exc:
            st.error(f"Gmail connection failed: {exc}")
    query = st.text_input("Gmail search query", value=DEFAULT_QUERY, help="Uses Gmail search operators. Narrow this before scanning confidential mail.")
    max_msgs = st.number_input("Maximum matching emails to scan", min_value=1, max_value=100, value=25)
    gmail_mode = st.radio("Gmail extraction", ["Local demo parser (free)", "OpenAI extraction (requires API key)"], key="gmail_extract_mode")
    if st.button("Scan Gmail attachments"):
        try:
            service = get_gmail_service(GMAIL_CREDENTIALS, GMAIL_TOKEN)
            attachments = scan_invoices(service, query=query, max_messages=int(max_msgs))
            old_keys = imported_keys(GMAIL_DB)
            preview = []
            errors = []
            for attachment in attachments:
                if attachment.attachment_key in old_keys:
                    continue
                try:
                    raw = read_document(attachment.filename, attachment.content)
                    if not raw.strip():
                        raise ValueError("No selectable text (scanned PDF needs OCR)")
                    fields = ai_extract(raw) if gmail_mode.startswith("OpenAI") else demo_extract(raw)
                    preview.append({"attachment_key": attachment.attachment_key,
                                    "filename": attachment.filename, "sender": attachment.sender,
                                    "subject": attachment.subject, "fields": fields})
                except Exception as exc:
                    errors.append(f"{attachment.filename}: {exc}")
            st.session_state.gmail_preview = preview
            st.session_state.gmail_errors = errors
            st.info(f"Found {len(attachments)} supported attachments; {len(preview)} new invoices ready for review.")
        except Exception as exc:
            st.error(f"Gmail scan failed: {exc}")
    for error in st.session_state.get("gmail_errors", []):
        st.warning(error)
    preview = st.session_state.get("gmail_preview", [])
    if preview:
        st.markdown("**Review extracted records before import.** New records are never approved automatically.")
        with st.form("gmail_import_form"):
            selected = []
            for ix, item in enumerate(preview):
                fields = item["fields"]
                label = f'{item["filename"]} — {fields.get("vendor") or "Unknown vendor"} — {fields.get("invoice_number") or "No number"}'
                include = st.checkbox(label, value=True, key=f"gmail_select_{ix}")
                with st.expander(f"Source: {item['sender']} · {item['subject']}"):
                    st.json(fields)
                if include:
                    selected.append(item)
            department = st.selectbox("Assign department to imported invoices", list(company["remaining_budgets"]), key="gmail_dept")
            if st.form_submit_button("Import selected invoices (unapproved)"):
                count = 0
                for item in selected:
                    fields = item["fields"]
                    record = {"invoice_id": new_invoice_id(), "invoice_number": fields.get("invoice_number", ""),
                              "vendor": fields.get("vendor", ""), "amount": fields.get("amount", ""),
                              "due_date": fields.get("due_date", ""), "department": department,
                              "approved": False, "bank_details_changed": False,
                              "source": "gmail", "source_filename": item["filename"]}
                    if save_gmail_invoice(GMAIL_DB, item["attachment_key"], record):
                        st.session_state.invoices.append(record)
                        count += 1
                st.session_state.gmail_preview = []
                st.success(f"Imported {count} invoice(s) for human review.")
    if GMAIL_TOKEN.exists() and st.button("Disconnect Gmail on this computer"):
        GMAIL_TOKEN.unlink()
        st.session_state.pop("gmail_preview", None)
        st.success("Deleted the local Gmail token. Revoke access in your Google account if needed.")

with review_tab:
    st.subheader("Invoice queue")
    st.caption("Internal IDs uniquely identify records in this app. Vendor invoice numbers come from suppliers and may repeat across vendors.")
    st.caption("For demonstration, you can toggle approvals below. In production, approvals require authentication, roles, and an audit log.")
    edited = st.data_editor(
        pd.DataFrame(st.session_state.invoices),
        hide_index=True,
        num_rows="fixed",
        key="invoice_editor",
        disabled=["invoice_id"],
        column_config={
            "invoice_id": st.column_config.TextColumn("Internal ID", help="Generated by our system; not editable"),
            "invoice_number": st.column_config.TextColumn("Vendor invoice number"),
            "approved": st.column_config.CheckboxColumn("Human approved"),
            "bank_details_changed": st.column_config.CheckboxColumn("Bank details changed"),
        },
    )
    if st.button("Apply edits and refresh recommendations"):
        st.session_state.invoices = edited.to_dict(orient="records")
        for record in st.session_state.invoices:
            if record.get("source") == "gmail":
                update_gmail_invoice(GMAIL_DB, record)
        st.rerun()
    results = recommend(st.session_state.invoices, company, today=date.today())
    data = pd.DataFrame(results)
    a, b, c = st.columns(3)
    a.metric("Invoices", len(data))
    b.metric("Schedule suggestions", (data["status"] == "SCHEDULE SUGGESTED").sum())
    c.metric("Require review", (data["status"] != "SCHEDULE SUGGESTED").sum())
    display_cols = ["invoice_id", "invoice_number", "vendor", "amount", "due_date", "department", "status", "recommended_date", "reason"]
    # Soft background colors for the entire row, based on payment recommendation status.
    status_colors = {
        "SCHEDULE SUGGESTED": "#DDF4E5",  # green
        "BUDGET REVIEW": "#FFF0C2",      # yellow
        "SECURITY REVIEW": "#FBDADA",    # red
        "APPROVAL NEEDED": "#DDEBFF",    # blue
        "REVIEW": "#FFF0C2",
        "OVERDUE": "#FBDADA",
        "CASH REVIEW": "#FFF0C2",
    }

    def color_status_row(row):
        background = status_colors.get(row["status"], "#EDEDED")
        return [f"background-color: {background}; color: #17212B" for _ in row]

    styled = data[display_cols].style.apply(color_status_row, axis=1)
    st.dataframe(styled, hide_index=True, width="stretch")

    st.download_button("Download recommendation CSV", data.to_csv(index=False).encode(),
                       "recommendations.csv", "text/csv")
    st.warning("These are recommendations, not payment instructions. No transaction is submitted. Review all invoice terms and cash-flow assumptions.")
