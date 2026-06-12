"""Savings Finder — the core money-saving engine.

Given one receipt, look at every item the shopper bought and ask: based on the
prices in the database (their own history now; the crowdsourced network later),
which store *near them* is cheapest, and how much could they have saved?

"Near them" matters: recommending a store three cities away isn't actionable.
Comparisons are restricted to drivable stores (same ZIP or same city) when a
home location is provided; otherwise all stores are considered.
"""

from __future__ import annotations

import pandas as pd

from .location import is_nearby, location_label, place_str

_LOC_COLS = ["norm_key", "store", "city", "state", "zip", "unit_price", "purchased_on"]


def latest_price_by_store(items: pd.DataFrame) -> pd.DataFrame:
    """Most recent unit price for each (norm_key, physical store location)."""
    if items.empty:
        return items
    ordered = items.sort_values("purchased_on")
    latest = ordered.groupby(
        ["norm_key", "store", "city", "state", "zip"], as_index=False, dropna=False
    ).tail(1)
    return latest[_LOC_COLS]


def _tag_proximity(df: pd.DataFrame, home_zip, home_state, home_city) -> pd.DataFrame:
    df = df.copy()
    df["proximity"] = df.apply(
        lambda r: location_label(
            r["zip"], r["state"], home_zip, home_state, r["city"], home_city
        ),
        axis=1,
    )
    df["place"] = df.apply(
        lambda r: place_str(r["city"], r["state"], r["zip"]), axis=1
    )
    return df


def analyze_receipt(
    items: pd.DataFrame,
    receipt_id: int,
    home_zip: str = "",
    home_state: str = "",
    home_city: str = "",
) -> dict:
    """Compare one receipt against the cheapest *nearby* price for each item.

    If a home location is given, the cheapest alternative is chosen only among
    drivable stores (same ZIP or city). Items with no nearby alternative keep
    their paid price (no out-of-town recommendation).
    """
    receipt_items = items[items["receipt_id"] == receipt_id]
    if receipt_items.empty:
        return {
            "rows": [], "paid_total": 0.0, "optimized_total": 0.0,
            "savings": 0.0, "by_store": {}, "receipt_store": None,
        }

    latest = _tag_proximity(
        latest_price_by_store(items), home_zip, home_state, home_city
    )
    use_location = bool(home_zip or home_state or home_city)
    receipt_store = receipt_items["store"].iloc[0]

    rows: list[dict] = []
    paid_total = 0.0
    optimized_total = 0.0
    by_store: dict[str, list[str]] = {}

    for _, it in receipt_items.iterrows():
        qty = it["qty"] or 1
        paid_unit = it["unit_price"]
        paid_line = it["line_total"]
        paid_total += paid_line

        options = latest[latest["norm_key"] == it["norm_key"]]
        if use_location:
            nearby = options[options["proximity"].apply(is_nearby)]
            options = nearby if not nearby.empty else options

        best = options.loc[options["unit_price"].idxmin()]
        best_store = best["store"]
        best_unit = float(best["unit_price"])
        best_place = best["place"]

        best_line = round(best_unit * qty, 2)
        # Never recommend paying more than they did (e.g. their store is cheapest).
        if best_line > paid_line:
            best_store, best_unit, best_place = it["store"], round(paid_unit, 2), ""
            best_line = round(paid_line, 2)
        optimized_total += best_line
        item_savings = round(paid_line - best_line, 2)

        rows.append({
            "item": it["name"],
            "category": it["category"],
            "qty": qty,
            "paid_store": it["store"],
            "paid_unit": round(paid_unit, 2),
            "best_store": best_store,
            "best_place": best_place,
            "best_unit": round(best_unit, 2),
            "stores_compared": int(options["store"].nunique()),
            "savings": item_savings,
            "cheaper_elsewhere": item_savings > 0.001,
        })

        by_store.setdefault(best_store, []).append(it["name"])

    paid_total = round(paid_total, 2)
    optimized_total = round(optimized_total, 2)
    return {
        "rows": rows,
        "paid_total": paid_total,
        "optimized_total": optimized_total,
        "savings": round(paid_total - optimized_total, 2),
        "by_store": by_store,
        "receipt_store": receipt_store,
    }


def top_opportunities(
    items: pd.DataFrame,
    home_zip: str = "",
    home_state: str = "",
    home_city: str = "",
    limit: int = 5,
    min_savings: float = 0.05,
    community: pd.DataFrame | None = None,
) -> list[dict]:
    """Across everything the shopper buys, where are they overpaying the most?

    `items` is the shopper's own history (what they pay); `community` is the
    shared price pool used to find the cheapest nearby price (defaults to
    `items` when not provided). Returns the biggest per-unit savings
    opportunities, ranked.
    """
    if items.empty:
        return []

    price_source = community if community is not None else items
    latest = _tag_proximity(
        latest_price_by_store(price_source), home_zip, home_state, home_city
    )
    use_location = bool(home_zip or home_state or home_city)

    # What the shopper most recently paid for each product, and where.
    ordered = items.sort_values("purchased_on")
    mine = ordered.groupby("norm_key", as_index=False).tail(1)

    out: list[dict] = []
    for _, row in mine.iterrows():
        key = row["norm_key"]
        paid_unit = row["unit_price"]
        if paid_unit is None:
            continue

        options = latest[latest["norm_key"] == key]
        if use_location:
            nearby = options[options["proximity"].apply(is_nearby)]
            options = nearby if not nearby.empty else options
        if options.empty:
            continue

        best = options.loc[options["unit_price"].idxmin()]
        savings = round(paid_unit - float(best["unit_price"]), 2)
        if savings < min_savings or best["store"] == row["store"]:
            continue

        out.append({
            "item": row["name"],
            "norm_key": key,
            "category": row["category"],
            "your_store": row["store"],
            "your_unit": round(paid_unit, 2),
            "best_store": best["store"],
            "best_place": best["place"],
            "best_unit": round(float(best["unit_price"]), 2),
            "savings": savings,
        })

    out.sort(key=lambda r: r["savings"], reverse=True)
    return out[:limit]
