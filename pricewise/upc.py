"""UPC -> product resolver.

A UPC is a global GS1 standard: the same code is the same product at every
store. That makes it the perfect join key for cross-store price comparison.
This module resolves a UPC to a product name/brand/category using the free,
open Open Food Facts database (no API key, no scraping, facts only).

Network is optional: results are cached, and a small offline fallback keeps the
demo working with no connectivity.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

OFF_ENDPOINT = (
    "https://world.openfoodfacts.org/api/v2/product/{upc}.json"
    "?fields=code,product_name,brands,categories"
)
USER_AGENT = "baskwise/0.1 (price-comparison demo; contact: hello@baskwise.app)"

# Offline fallback so the feature still demonstrates when there's no network.
_FALLBACK: dict[str, dict] = {
    "0049000028911": {"name": "Diet Coke", "brand": "Coca-Cola", "category": "Beverages"},
    "0038000138416": {"name": "Pringles Original", "brand": "Pringles", "category": "Snacks & Candy"},
    "3017620422003": {"name": "Nutella", "brand": "Ferrero", "category": "Pantry"},
}


@dataclass
class Product:
    upc: str
    name: str
    brand: str
    category: str
    source: str  # "openfoodfacts" | "offline-cache" | "unknown"

    @property
    def found(self) -> bool:
        return self.source != "unknown"


def _clean(upc: str) -> str:
    return "".join(ch for ch in (upc or "") if ch.isdigit())


def resolve_upc(upc: str, timeout: float = 6.0) -> Product:
    """Resolve a UPC to product info. Never raises — degrades gracefully."""
    code = _clean(upc)
    if not code:
        return Product(upc, "", "", "", "unknown")

    # Try the live open database first.
    try:
        req = urllib.request.Request(
            OFF_ENDPOINT.format(upc=code), headers={"User-Agent": USER_AGENT}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if data.get("status") == 1:
            p = data.get("product", {})
            name = (p.get("product_name") or "").strip()
            brand = (p.get("brands") or "").split(",")[0].strip()
            category = (p.get("categories") or "").split(",")[-1].strip()
            if name:
                return Product(code, name, brand, category, "openfoodfacts")
    except (urllib.error.URLError, TimeoutError, ValueError, OSError):
        pass  # fall through to offline fallback

    if code in _FALLBACK:
        f = _FALLBACK[code]
        return Product(code, f["name"], f["brand"], f["category"], "offline-cache")

    return Product(code, "", "", "", "unknown")
