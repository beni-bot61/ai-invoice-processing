from datetime import date
from invoice_ai.core import money, recommend, validate_invoice

TODAY = date(2026, 11, 10)


def company(cash=50000):
    return {"current_cash": cash, "minimum_cash_reserve": 20000,
            "remaining_budgets": {"IT": 40000}, "cash_events": []}


def invoice(number="1", amount="5000", due="2026-11-13", approved=True):
    return {"vendor": "Vendor A", "invoice_number": number, "amount": amount,
            "due_date": due, "department": "IT", "approved": approved,
            "bank_details_changed": False}


def test_positive_money_validation():
    assert str(money("$1,200.00")) == "1200.00"
    for invalid in ("-4", "NaN", "abc"):
        try:
            money(invalid)
            assert False, "Expected invalid amount"
        except ValueError:
            pass


def test_due_date_recommendation():
    result = recommend([invoice()], company(), TODAY)[0]
    assert result["status"] == "SCHEDULE SUGGESTED"
    assert result["recommended_date"] == "2026-11-13"


def test_no_approval_no_schedule():
    assert recommend([invoice(approved=False)], company(), TODAY)[0]["status"] == "APPROVAL NEEDED"


def test_duplicate_detected():
    results = recommend([invoice(), invoice()], company(), TODAY)
    assert results[1]["status"] == "REVIEW"
    assert "duplicate" in results[1]["reason"].lower()


def test_cash_reserve_never_violated():
    assert recommend([invoice(amount="15000")], company(cash=25000), TODAY)[0]["status"] == "CASH REVIEW"


def test_budget_and_bank_change():
    assert recommend([invoice(amount="41000")], company(), TODAY)[0]["status"] == "BUDGET REVIEW"
    i = invoice()
    i["bank_details_changed"] = True
    assert recommend([i], company(), TODAY)[0]["status"] == "SECURITY REVIEW"


def test_projected_inflow_allows_due_date():
    c = company(cash=25000)
    c["cash_events"] = [{"date": "2026-11-12", "type": "inflow", "amount": 20000}]
    assert recommend([invoice(amount="15000")], c, TODAY)[0]["status"] == "SCHEDULE SUGGESTED"


def test_multiple_bills_respect_shared_cash():
    results = recommend([invoice(number="1", amount="20000"), invoice(number="2", amount="20000", due="2026-11-14")], company(), TODAY)
    assert results[0]["status"] == "SCHEDULE SUGGESTED"
    assert results[1]["status"] == "CASH REVIEW"
