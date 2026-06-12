"""ZIP code -> city/state resolver.

Lets any user set their location by typing their ZIP — the app fills in the
city and state automatically. Uses the free Zippopotam.us API (no key), with a
small offline fallback so the demo works without connectivity.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

_ENDPOINT = "https://api.zippopotam.us/us/{zip}"
_USER_AGENT = "baskwise/0.1 (zip lookup; hello@baskwise.app)"

# Offline fallback for the demo ZIPs (and resilience if the API is down).
_FALLBACK: dict[str, tuple[str, str]] = {
    "75201": ("Dallas", "TX"),
    "75204": ("Dallas", "TX"),
    "78701": ("Austin", "TX"),
    "78205": ("San Antonio", "TX"),
}


def clean_zip(value: str) -> str:
    """Keep only the first 5 digits of an entered ZIP."""
    return "".join(c for c in (value or "") if c.isdigit())[:5]


def zip_to_place(zip_code: str, timeout: float = 6.0) -> tuple[str, str] | None:
    """Return (city, state_abbrev) for a US ZIP, or None if not found.

    Never raises — degrades to the offline fallback on any network error.
    """
    z = clean_zip(zip_code)
    if len(z) != 5:
        return None
    try:
        req = urllib.request.Request(
            _ENDPOINT.format(zip=z), headers={"User-Agent": _USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        places = data.get("places") or []
        if places:
            city = (places[0].get("place name") or "").strip()
            state = (places[0].get("state abbreviation") or "").strip()
            if city and state:
                return city, state
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        pass
    return _FALLBACK.get(z)
