"""Streamlit invoice processing demo. NO PAYMENTS are initiated."""
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
from invoice_ai.core import recommend
from invoice_ai.extract import ai_extract, demo_extract, read_document

ROOT = Path(__file__).parent
st.set_page_config(page_title="Invoice AI — Demo", page_icon="🧾", layout="wide")
st.title("🧾 Invoice AI — Processing & Payment Recommendations")
st.caption("Demonstration only · Fictional sample data · Never initiates payments")

if "invoices" not in st.session_state:
    st.session_state.invoices = json.loads((ROOT / "sample_data" / "invoices.json").read_text())
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

upload_tab, review_tab = st.tabs(["📥 Upload invoice", "📊 Review & schedule"])
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
                st.session_state.invoices.append({"vendor": vendor, "invoice_number": number, "amount": amount,
                                                  "due_date": due, "department": dept, "approved": False,
                                                  "bank_details_changed": changed})
                st.success("Added to review queue. Not approved for payment.")
                del st.session_state["extracted"]
    st.info("Try uploading sample_data/invoices/sample_invoice.txt to test the extraction flow.")

with review_tab:
    st.subheader("Invoice queue")
    st.caption("For demonstration, you can toggle approvals below. In production, approvals require authentication, roles, and an audit log.")
    edited = st.data_editor(pd.DataFrame(st.session_state.invoices), hide_index=True, num_rows="fixed", key="invoice_editor",
                            column_config={"approved": st.column_config.CheckboxColumn("Human approved"),
                                           "bank_details_changed": st.column_config.CheckboxColumn("Bank details changed")})
    if st.button("Apply edits and refresh recommendations"):
        st.session_state.invoices = edited.to_dict(orient="records")
        st.rerun()
    results = recommend(st.session_state.invoices, company, today=date.today())
    data = pd.DataFrame(results)
    a, b, c = st.columns(3)
    a.metric("Invoices", len(data))
    b.metric("Schedule suggestions", (data["status"] == "SCHEDULE SUGGESTED").sum())
    c.metric("Require review", (data["status"] != "SCHEDULE SUGGESTED").sum())
    st.dataframe(data[["invoice_number", "vendor", "amount", "due_date", "department", "status", "recommended_date", "reason"]], hide_index=True, use_container_width=True)
    st.download_button("Download recommendation CSV", data.to_csv(index=False).encode(),
                       "recommendations.csv", "text/csv")
    st.warning("These are recommendations, not payment instructions. No transaction is submitted. Review all invoice terms and cash-flow assumptions.")
