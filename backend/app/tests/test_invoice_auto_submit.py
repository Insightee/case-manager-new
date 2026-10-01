from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.invoice_auto_submit_service import billing_month_due_at_close

IST = ZoneInfo("Asia/Kolkata")


def test_billing_month_due_only_at_2359_on_the_last_day():
    assert billing_month_due_at_close(datetime(2026, 9, 30, 23, 59, tzinfo=IST)) == "2026-09"
    assert billing_month_due_at_close(datetime(2026, 9, 30, 23, 58, tzinfo=IST)) is None
    assert billing_month_due_at_close(datetime(2026, 9, 29, 23, 59, tzinfo=IST)) is None
    assert billing_month_due_at_close(datetime(2026, 10, 31, 18, 29, tzinfo=ZoneInfo("UTC"))) == "2026-10"
