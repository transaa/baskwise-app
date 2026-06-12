"""Spending insights — how fast are your staples getting more expensive?

Uses the shopper's own purchase history to measure real, personal grocery
inflation: for each item bought more than once, compare the first price paid to
the most recent, and roll it up into an overall "staples basket" change.
"""

from __future__ import annotations

import pandas as pd


def staple_inflation(items: pd.DataFrame, min_purchases: int = 2) -> dict:
    """Return personal inflation stats based on repeat-purchased items.

    {
      basket_pct: overall % change of the repeat-bought basket (first -> latest),
      from_date, to_date: span covered,
      first_total, last_total: basket cost then vs now,
      rows: per-item [{item, category, first_unit, last_unit, pct, first_date, last_date}]
            sorted by pct descending (biggest risers first)
    }
    """
    empty = {
        "basket_pct": 0.0, "from_date": None, "to_date": None,
        "first_total": 0.0, "last_total": 0.0, "rows": [],
    }
    if items.empty:
        return empty

    df = items.dropna(subset=["unit_price", "purchased_on"]).copy()
    df = df.sort_values("purchased_on")

    rows: list[dict] = []
    first_total = 0.0
    last_total = 0.0
    dates: list[pd.Timestamp] = []

    for key, grp in df.groupby("norm_key"):
        # Need purchases on at least two distinct dates to measure change.
        if grp["purchased_on"].dt.normalize().nunique() < min_purchases:
            continue
        first = grp.iloc[0]
        last = grp.iloc[-1]
        fu, lu = float(first["unit_price"]), float(last["unit_price"])
        if fu <= 0:
            continue
        pct = (lu - fu) / fu * 100
        first_total += fu
        last_total += lu
        dates.extend([first["purchased_on"], last["purchased_on"]])
        rows.append({
            "item": last["name"],
            "category": last["category"],
            "first_unit": round(fu, 2),
            "last_unit": round(lu, 2),
            "pct": round(pct, 1),
            "first_date": first["purchased_on"].date(),
            "last_date": last["purchased_on"].date(),
        })

    if not rows:
        return empty

    rows.sort(key=lambda r: r["pct"], reverse=True)
    basket_pct = (last_total - first_total) / first_total * 100 if first_total else 0.0
    return {
        "basket_pct": round(basket_pct, 1),
        "from_date": min(dates).date(),
        "to_date": max(dates).date(),
        "first_total": round(first_total, 2),
        "last_total": round(last_total, 2),
        "rows": rows,
    }
