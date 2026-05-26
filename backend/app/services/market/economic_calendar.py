"""Lightweight economic calendar.

Hardcoded with the recurring high-impact macro events (Fed FOMC, ECB,
NFP, US CPI, EU HICP). Returns the next N events from today.

A future iteration can swap this for tradingeconomics-python or
investpy, but those need keys or aggressive scraping; for the briefing
context we just need 'next 7 days' awareness.
"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class EconEvent:
    name: str
    region: str
    impact: str  # "high" | "medium" | "low"
    weekday: int | None = None  # 0=Mon ... 6=Sun (recurring weekly)
    day_of_month: int | None = None  # for monthly events approx
    cron_month_match: str | None = None  # special handling


# Canonical recurring macro releases (approximate dates — within ±3 days)
RECURRING_EVENTS = [
    EconEvent(name="US Non-Farm Payrolls", region="US", impact="high"),  # 1st Friday
    EconEvent(name="US CPI", region="US", impact="high"),  # ~mid-month
    EconEvent(name="US Core PCE", region="US", impact="high"),  # ~end-month
    EconEvent(name="EU HICP flash estimate", region="EU", impact="high"),  # ~end-month
    EconEvent(name="EU Industrial Production", region="EU", impact="medium"),  # ~mid-month
    EconEvent(name="ECB monetary policy meeting", region="EU", impact="high"),  # ~every 6 weeks
    EconEvent(name="Fed FOMC meeting", region="US", impact="high"),  # ~every 6 weeks
]


def first_weekday_of_month(year: int, month: int, weekday: int) -> date:
    """Return the first occurrence of `weekday` (Mon=0) in `month` of `year`."""
    d = date(year, month, 1)
    offset = (weekday - d.weekday()) % 7
    return d + timedelta(days=offset)


def upcoming_events(today: date | None = None, horizon_days: int = 30) -> list[dict]:
    """Approximate next macro events from `today` within `horizon_days`."""
    today = today or date.today()
    end = today + timedelta(days=horizon_days)
    out: list[dict] = []

    # Walk the date range and find approximate occurrences
    cursor = today
    while cursor <= end:
        y, m, d_day = cursor.year, cursor.month, cursor.day

        # NFP — first Friday of the month
        nfp = first_weekday_of_month(y, m, weekday=4)
        if nfp == cursor:
            out.append({"date": cursor.isoformat(), "name": "US Non-Farm Payrolls", "region": "US", "impact": "high"})

        # US CPI — typically 10th-13th
        if d_day in (10, 11, 12, 13):
            out.append({"date": cursor.isoformat(), "name": "US CPI (mensual)", "region": "US", "impact": "high"})
            cursor += timedelta(days=4)  # skip subsequent matches in same window
            continue

        # EU HICP flash — last 3 working days of month (approx)
        last_day = (date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1) - timedelta(days=1)).day
        if d_day in (last_day - 2, last_day - 1, last_day):
            out.append({"date": cursor.isoformat(), "name": "EU HICP flash", "region": "EU", "impact": "high"})
            cursor += timedelta(days=4)
            continue

        cursor += timedelta(days=1)

    return out[:10]
