"""Auditable invoice validation and payment recommendations (no money movement)."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any


def money(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value).replace(",", "").replace("$", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid money amount: {value}") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Money must be a finite, nonnegative amount")
    return amount


def validate_invoice(invoice: dict, seen: set[tuple[str, str]] | None = None) -> list[str]:
    issues = []
    for field in ("invoice_number", "vendor", "due_date", "amount"):
        if not str(invoice.get(field, "")).strip():
            issues.append(f"Missing {field}")
    try:
        money(invoice.get("amount", ""))
    except ValueError:
        issues.append("Invalid invoice amount")
    try:
        date.fromisoformat(str(invoice.get("due_date", "")))
    except ValueError:
        issues.append("Invalid due date (use YYYY-MM-DD)")
    if seen is not None:
        key = (str(invoice.get("vendor", "")).strip().lower(), str(invoice.get("invoice_number", "")).strip().lower())
        if key in seen:
            issues.append("Possible duplicate: same vendor and invoice number")
        else:
            seen.add(key)
    return issues


def recommend(invoices: list[dict], company: dict, today: date | None = None) -> list[dict]:
    """Conservative rule-based scheduler using day-by-day projected cash.

    Assumptions: no automated transfers, invoices must be approved, inflows are
    entered by user, and scheduling never goes beyond contractual due dates.
    """
    today = today or date.today()
    reserve = money(company["minimum_cash_reserve"])
    initial_cash = money(company["current_cash"])
    budget = {k: money(v) for k, v in company.get("remaining_budgets", {}).items()}
    cash_events = []
    for event in company.get("cash_events", []):
        when = date.fromisoformat(event["date"])
        amount = money(event["amount"])
        if when >= today:
            cash_events.append((when, amount if event["type"] == "inflow" else -amount))

    # An expense remains a commitment whether or not we schedule it today.
    planned: dict[date, Decimal] = {}
    results = []
    seen = set()
    for inv in sorted(invoices, key=lambda i: (str(i.get("due_date", "9999-12-31")), str(i.get("invoice_number", "")))):
        base = dict(inv)
        issues = validate_invoice(inv, seen)
        if issues:
            results.append({**base, "status": "REVIEW", "recommended_date": "", "reason": "; ".join(issues)})
            continue
        amount = money(inv["amount"])
        due = date.fromisoformat(inv["due_date"])
        dept = str(inv.get("department", "General"))
        if not inv.get("approved", False):
            results.append({**base, "status": "APPROVAL NEEDED", "recommended_date": "", "reason": "Invoice requires human approval"})
            continue
        if dept not in budget:
            results.append({**base, "status": "REVIEW", "recommended_date": "", "reason": "No departmental budget available"})
            continue
        if amount > budget[dept]:
            results.append({**base, "status": "BUDGET REVIEW", "recommended_date": "", "reason": "Exceeds remaining department budget"})
            continue
        if inv.get("bank_details_changed", False):
            results.append({**base, "status": "SECURITY REVIEW", "recommended_date": "", "reason": "Vendor banking details changed; independently verify"})
            continue
        if due < today:
            results.append({**base, "status": "OVERDUE", "recommended_date": "", "reason": "Past due; escalate to finance"})
            continue

        # Default to the contractual due date (not an arbitrary 'pay late' date).
        # Check every intervening day to avoid temporarily violating the reserve.
        feasible = True
        for delta in range((due - today).days + 1):
            d = today + timedelta(days=delta)
            balance = initial_cash + sum((a for day, a in cash_events if day <= d), Decimal(0))
            balance -= sum((a for day, a in planned.items() if day <= d), Decimal(0))
            if d >= due:
                balance -= amount
            if balance < reserve:
                feasible = False
                break
        if not feasible:
            results.append({**base, "status": "CASH REVIEW", "recommended_date": "", "reason": "Projected cash would fall below reserve; human action needed before due date"})
            continue
        budget[dept] -= amount
        planned[due] = planned.get(due, Decimal(0)) + amount
        results.append({**base, "status": "SCHEDULE SUGGESTED", "recommended_date": due.isoformat(), "reason": "Approved, within budget, and projected cash stays above reserve through due date"})
    return results
