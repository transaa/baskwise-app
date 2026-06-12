"""Cross-store product matching for common staples.

The hard problem in receipt comparison: Walmart calls it "GREAT VALUE MILK 1GAL"
and Kroger calls it "2% MILK GALLON" — same product, different text. The real
solution is matching on UPC. Until UPCs are present on every line, this curated
"staples" matcher canonicalizes the most common grocery items so they line up
across stores. Anything that doesn't match falls back to token-based matching.
"""

from __future__ import annotations

# (canonical display name, canonical key, keyword phrases). Checked top to bottom;
# put more specific phrases first so "orange juice" beats "orange".
STAPLES: list[tuple[str, str, tuple[str, ...]]] = [
    ("Orange Juice", "orange_juice", ("orange juice", "oj ")),
    ("Frozen Pizza", "frozen_pizza", ("frozen pizza", "pizza")),
    ("Paper Towels", "paper_towels", ("paper towel",)),
    ("Dish Soap", "dish_soap", ("dish soap", "dish liquid")),
    ("Chicken Breast", "chicken_breast", ("chicken breast", "chkn breast")),
    ("Cheddar Cheese", "cheddar_cheese", ("cheddar",)),
    ("Large Eggs", "large_eggs", ("large egg", "egg")),
    ("White Bread", "white_bread", ("white bread", "bread")),
    ("Milk", "milk", ("milk",)),
    ("Coffee", "coffee", ("coffee",)),
    ("Bananas", "bananas", ("banana",)),
    ("Spinach", "spinach", ("spinach",)),
    ("Romaine Lettuce", "romaine_lettuce", ("romaine", "lettuce")),
    ("Tomatoes", "tomatoes", ("tomato",)),
    ("Honey", "honey", ("honey",)),
    ("Rice", "rice", ("rice",)),
]


def match_staple(raw_name: str) -> tuple[str, str] | None:
    """Return (canonical_name, canonical_key) if the item is a known staple."""
    text = raw_name.lower()
    for name, key, phrases in STAPLES:
        for phrase in phrases:
            if phrase in text:
                return name, key
    return None
