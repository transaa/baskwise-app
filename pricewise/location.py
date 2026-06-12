"""Location helpers for region-aware price comparison.

Proximity is intentionally simple for the prototype: same ZIP is "your area",
same city is "your city", same state is "your region", everything else is "other
regions". A production build would use real geocoding + distance (lat/long, drive
time), but this is enough to demonstrate the crowdsourced, location-aware value:
the cheapest price *you can actually drive to* matters more than the cheapest
price in the country.

"Near you" (drivable) = same ZIP or same city.
"""

from __future__ import annotations

# Proximity tiers, closest first.
AREA = "your area"        # same ZIP code
CITY = "your city"        # same city + state, different ZIP
REGION = "your region"    # same state, different city
ELSEWHERE = "other regions"

TIER_ORDER = {AREA: 0, CITY: 1, REGION: 2, ELSEWHERE: 3}

# Tiers considered close enough to actually shop at.
NEARBY_TIERS = (AREA, CITY)


def _norm(v) -> str:
    return (str(v) if v is not None else "").strip()


def location_label(
    row_zip, row_state, home_zip: str, home_state: str,
    row_city=None, home_city: str = "",
) -> str:
    """Classify a receipt's location relative to the user's home location."""
    rz, rs, rc = _norm(row_zip), _norm(row_state).upper(), _norm(row_city).lower()
    hz, hs, hc = _norm(home_zip), _norm(home_state).upper(), _norm(home_city).lower()

    if hz and rz and rz == hz:
        return AREA
    if hc and rc and rc == hc and hs == rs:
        return CITY
    if hs and rs and rs == hs:
        return REGION
    return ELSEWHERE


def is_nearby(label: str) -> bool:
    return label in NEARBY_TIERS


def place_str(city, state, zipc) -> str:
    """Human-readable 'City, ST 00000' from parts, skipping blanks."""
    city, state, zipc = _norm(city), _norm(state), _norm(zipc)
    left = ", ".join(x for x in [city, state] if x)
    return " ".join(x for x in [left, zipc] if x) or "Unknown location"
