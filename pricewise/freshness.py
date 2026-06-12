"""Price freshness — how current is a community price?

A receipt records a real price, but it's "what the last shopper paid," not a
guaranteed live shelf price. Rather than pretend prices are real-time, baskwise
is honest about each price's age and flags stale ones. Freshness improves as
more people shop and report — the crowdsourced flywheel.
"""

from __future__ import annotations

import pandas as pd

FRESH_DAYS = 14      # within two weeks: trust it
AGING_DAYS = 45      # within ~6 weeks: probably close
# older than AGING_DAYS: flag as stale / may have changed


def age_days(when, now: pd.Timestamp | None = None) -> int | None:
    """Whole days since `when`. None if the date is missing."""
    if when is None or pd.isna(when):
        return None
    now = now if now is not None else pd.Timestamp.now()
    return max(0, (now.normalize() - pd.Timestamp(when).normalize()).days)


def freshness_tier(days: int | None) -> str:
    if days is None:
        return "unknown"
    if days <= FRESH_DAYS:
        return "fresh"
    if days <= AGING_DAYS:
        return "aging"
    return "stale"


_BADGE = {"fresh": "🟢 fresh", "aging": "🟡 aging", "stale": "🔴 stale", "unknown": "❔"}


def badge(days: int | None) -> str:
    return _BADGE[freshness_tier(days)]


def _ago(days: int | None) -> str:
    if days is None:
        return "date unknown"
    if days == 0:
        return "today"
    if days == 1:
        return "1 day ago"
    return f"{days} days ago"


def label(when, now: pd.Timestamp | None = None) -> str:
    """Human freshness label, e.g. '🟢 fresh · 2 days ago'."""
    d = age_days(when, now)
    return f"{badge(d)} · {_ago(d)}"


def is_stale(when, now: pd.Timestamp | None = None) -> bool:
    return freshness_tier(age_days(when, now)) == "stale"
