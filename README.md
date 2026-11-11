# Invoice AI — Accounts Payable Demo

A **runnable, local-first demo** of AI-assisted invoice processing. The app accepts text PDFs/TXT invoices, extracts fields, checks duplicates and budgets, and recommends payment dates while maintaining a projected minimum cash reserve. It **never sends money**.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue) ![Demo](https://img.shields.io/badge/Payments-disabled-orange)

## Quick start

```bash
python -m venv .venv
# macOS / Linux:
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Open the local URL shown by Streamlit, typically `http://localhost:8501`.

1. In **Review & schedule**, inspect fictional sample invoices and recommendations.
2. In **Upload invoice**, upload `sample_data/invoices/sample_invoice.txt` and select **Local demo parser (free)**.
3. Verify extracted fields and add to the queue. New invoices receive a unique internal `invoice_id` and always start unapproved.
4. In the review tab, check **Human approved** for an invoice, then click **Apply edits and refresh recommendations**.
5. Change cash and reserve in the sidebar; watch the recommendation statuses change.

## Connect Gmail (local Windows / VS Code)

The **📧 Gmail import** tab can fetch PDF/TXT invoice attachments from a Gmail account. The app uses **read-only OAuth** (`gmail.readonly`), does not send or modify email, and **never initiates payments**. Imports require you to scan and explicitly confirm; there is no unattended inbox monitoring yet.

1. Open [Google Cloud Console](https://console.cloud.google.com/), create or choose a project, and enable **Gmail API** under **APIs & Services → Library**.
2. Configure **Google Auth Platform → Branding / Audience** (the OAuth consent screen). For a personal demo, use **External** and **Testing**, and add your own Gmail address under **Test users**. Google may display an unverified-app warning for a development app; confirm you trust your own OAuth project before proceeding.
3. Under **Google Auth Platform → Clients**, create an **OAuth Client ID** with application type **Desktop app**. Download its JSON file and rename it **`gmail_credentials.json`**.
4. Put `gmail_credentials.json` beside `app.py` (at the project root), **not** inside `invoice_ai/`. Do **not** commit that file to GitHub.
5. Install dependencies and run from the *outer* project folder:

   ```powershell
   py -m pip install -r requirements.txt
   py -m streamlit run app.py
   ```

6. Open **📧 Gmail import → Connect Gmail**. The Google sign-in window should open in your browser. Grant **read-only** Gmail access. Sign in on the same computer running Streamlit; this desktop OAuth flow is **not appropriate for shared/public cloud hosting**.
7. Set a Gmail query (default: `has:attachment {filename:pdf filename:txt} newer_than:90d`), select Local parser or OpenAI extraction, and click **Scan Gmail attachments**.
8. Inspect the extracted information, choose attachments to import, and click **Import selected invoices (unapproved)**. Go to **Review & schedule** to correct errors and authorize routine review actions. Every Gmail invoice is initially **unapproved**.

**Local storage and security:** OAuth tokens go into `.gmail_token.json` and imported invoice records go into `.local_data/gmail_imports.sqlite3`; both are ignored by Git. These local demo files are not encrypted. Protect your computer and never use confidential financial records without permission. Imported Gmail records persist across app restarts and are not reimported on subsequent scans (idempotence is based on Gmail message + attachment IDs). Manual/sample invoice records still live in Streamlit session memory. To disconnect locally, use the tab's **Disconnect** button; you may also revoke the app under your Google Account's third-party connections. You can remove the local database to clear Gmail import history **only if you intentionally want to erase it**.

**Supported formats:** text-based PDFs and UTF-8 TXT attachments, up to 8 MB each. Scanned/image-only PDFs require OCR (not yet implemented). AI extraction sends extracted invoice text to OpenAI only when you select OpenAI mode and configure `OPENAI_API_KEY`; otherwise the local parser stays on your computer. This is a **single-user local prototype** with no production-grade access control, encryption, or accountant audit log.

## Optional genuine AI extraction

The default mode uses a **regex demo parser**, not AI. To use an actual model for more flexible invoice extraction:

```bash
export OPENAI_API_KEY="your-key-here"  # Windows PowerShell: $env:OPENAI_API_KEY="..."
# optional: export OPENAI_MODEL="gpt-4o-mini"
streamlit run app.py
```

Select **OpenAI extraction** in the Upload tab. The app submits invoice **text** (up to 30,000 characters) to an API with a structured JSON schema; it does not submit raw PDF images. This uses API credits and sends document content to an external provider, so **do not upload confidential financial documents without organizational authorization**. The LLM never sets payment approval.

## Repository layout

```text
app.py                        Streamlit UI
invoice_ai/core.py            Validation and deterministic scheduling
invoice_ai/extract.py         PDF text reading, regex parser, optional LLM extraction
invoice_ai/gmail_integration.py Read-only OAuth Gmail discovery and attachment retrieval
invoice_ai/storage.py         Local SQLite persistence for Gmail imports
sample_data/company.json      Fictional balances, budgets, projected cash events
sample_data/invoices.json     Fictional invoices for the dashboard
sample_data/invoices/         Try-it-yourself invoice text
 tests/                       Unit tests (pytest)
```

## Invoice identifiers and duplicate checks

- **`invoice_id`**: Generated internally as `inv_<random UUID>` for every new record. It is not editable in the dashboard, and is included in CSV exports. Existing sample/legacy records without IDs are automatically backfilled when loaded. Duplicate internal IDs are repaired.
- **`invoice_number`**: Supplier-provided number extracted from the document. It may be the same for two *different* vendors. A missing invoice number is sent for review, not invented.
- **Duplicate check**: Flags a potential duplicate only when the **same normalized vendor name and vendor invoice number** appear more than once. Case and repeated spaces are ignored, but vendor aliases are **not** resolved. This flags possible duplicates; it does not automatically delete or pay anything.

**Demo persistence limitation:** The invoice queue, including generated IDs, lives in Streamlit session state. Restarting/resetting the session reloads fictional samples with freshly generated IDs. A production service must generate IDs once and store them in a persistent database with a uniqueness constraint, then use those IDs in audit logs and payment references.

## What the engine decides

* Duplicates and incomplete/malformed records -> **REVIEW**.
* Unapproved invoices -> **APPROVAL NEEDED**.
* Expenses exceeding a department's remaining budget -> **BUDGET REVIEW**.
* Vendor bank detail changes -> **SECURITY REVIEW**.
* Past-due invoices -> **OVERDUE** (human attention).
* Cash shortages relative to reserve -> **CASH REVIEW**.
* Otherwise -> **SCHEDULE SUGGESTED** for the contractual due date.

The algorithm uses dated inflows/outflows provided in `company.json`; it conservatively tests projected cash for every day through each proposed due date. It accounts for already scheduled demo invoices and decrements remaining departmental budgets. It does **not** infer vendor credibility, calculate penalties, negotiate terms, use unapproved invoices as cash commitments, or move funds.

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Limitations and next steps

This is an educational demo, **not** production accounting software. The sample has fictional approval toggles and no authentication, persistent database, audit log, real bank integration, or financial controls. The local parser only recognizes clearly labeled invoice text; image-only PDFs need an OCR service. The system does not check exchange rates, payment terms other than due dates, purchase orders, receipt of goods, bank verification, or tax treatment.

For production: add SSO + role-based approvals, append-only approval audit logs, transactional accounting ledger, vendor verification, idempotent ingestion, purchase-order matching, OCR, real-time balances, cash forecast confidence, an approval workflow, and encryption. A payment release should require a separate explicitly authorized service and appropriate dual controls.
