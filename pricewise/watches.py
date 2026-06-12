"""Price-drop watches — "tell me when milk drops below $3 near me".

Evaluates each watch against current nearby prices and reports which have hit
their target. Pairs with the watches table in db.py.
"""

from __future__ import annotations

import pandas as pd

from .savings import _tag_proximity, latest_price_by_store
from .location import is_nearby


def evaluate_watches(
    items: pd.DataFrame,
    watches: list[dict],
    home_zip: str = "",
    home_state: str = "",
    home_city: str = "",
) -> list[dict]:
    """For each watch, find the cheapest nearby price and whether it's triggered.

    Returns rows with: label, threshold, triggered (bool), best_unit, best_store,
    best_place, gap (how far above target, if not triggered), and has_data.
    """
    if not watches:
        return []

    latest = (
        _tag_proximity(latest_price_by_store(items), home_zip, home_state, home_city)
        if not items.empty else pd.DataFrame()
    )
    use_location = bool(home_zip or home_state or home_city)

    out: list[dict] = []
    for w in watches:
        row = {
            "id": w.get("id"),
            "label": w["label"],
            "norm_key": w["norm_key"],
            "threshold": round(float(w["threshold"]), 2),
            "has_data": False,
            "triggered": False,
            "best_unit": None,
            "best_store": None,
            "best_place": None,
            "gap": None,
        }

        if not latest.empty:
            opts = latest[latest["norm_key"] == w["norm_key"]]
            if use_location:
                nearby = opts[opts["proximity"].apply(is_nearby)]
                opts = nearby if not nearby.empty else opts
            if not opts.empty:
                best = opts.loc[opts["unit_price"].idxmin()]
                best_unit = round(float(best["unit_price"]), 2)
                row.update(
                    has_data=True,
                    best_unit=best_unit,
                    best_store=best["store"],
                    best_place=best["place"],
                    triggered=best_unit <= row["threshold"] + 1e-9,
                    gap=round(best_unit - row["threshold"], 2),
                )
        out.append(row)

    # Triggered first, then closest to triggering.
    out.sort(key=lambda r: (not r["triggered"], r["gap"] if r["gap"] is not None else 9e9))
    return out
