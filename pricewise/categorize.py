"""Lightweight, dependency-free product categorizer.

Keyword-based mapping into a tidy grocery/household taxonomy. This is deliberately
simple and transparent; in a production system you'd back this with the open
barcode datasets (Open Food Facts category trees) and/or an ML classifier.
"""

from __future__ import annotations

# Order matters: earlier categories win on the first keyword hit. Non-food
# categories and strong-signal words (juice, coffee) are checked BEFORE the
# broad produce/meat lists, because single words like "orange" (orange juice)
# or "ground" (coffee ground) otherwise collide with the wrong category.
TAXONOMY: list[tuple[str, tuple[str, ...]]] = [
    ("Personal Care", (
        "shampoo", "conditioner", "toothpaste", "toothbrush", "deodorant",
        "razor", "lotion", "vitamin", "medicine", "bandage", "floss",
        "sunscreen", "makeup",
    )),
    ("Baby", (
        "diaper", "formula", "baby food", "baby wipe",
    )),
    ("Pet", (
        "dog food", "cat food", "litter", "kibble", "pet treat",
    )),
    ("Household", (
        "paper towel", "toilet", "tissue", "detergent", "dish soap", "soap",
        "cleaner", "bleach", "trash", "foil", "sponge", "dish", "laundry",
        "napkin", "battery", "bulb", "ziploc", "garbage",
    )),
    ("Beverages", (
        "juice", "soda", "cola", "coffee", "tea", "beer", "wine", "lemonade",
        "sparkling", "energy drink", "gatorade", "pepsi", "coke", "water",
    )),
    ("Frozen", (
        "frozen", "ice cream", "pizza", "frz", "popsicle", "waffle",
    )),
    ("Meat & Seafood", (
        "chicken", "beef", "pork", "bacon", "sausage", "turkey", "ham",
        "salmon", "tuna", "shrimp", "fish", "steak", "ground beef", "ribs",
    )),
    ("Dairy & Eggs", (
        "milk", "cheese", "yogurt", "butter", "egg", "cream", "sour crm",
        "cottage", "half & half", "creamer", "cheddar",
    )),
    ("Bakery", (
        "bread", "bagel", "bun", "tortilla", "muffin", "cake",
        "donut", "croissant", "pastry", "baguette", "dinner roll",
    )),
    ("Produce", (
        "banana", "apple", "lettuce", "romaine", "tomato", "onion", "potato",
        "carrot", "spinach", "broccoli", "pepper", "avocado", "grape", "berr",
        "lemon", "lime", "orange", "cucumber", "celery", "mushroom", "garlic",
        "salad",
    )),
    ("Snacks & Candy", (
        "chip", "crisp", "pringles", "cracker", "cookie", "candy", "chocolate",
        "popcorn", "pretzel", "nuts", "granola", "snack",
    )),
    ("Pantry", (
        "rice", "pasta", "flour", "sugar", "oil", "cereal", "soup", "sauce",
        "bean", "canned", "peanut butter", "nutella", "jelly", "jam", "honey",
        "spice", "salt", "ketchup", "mustard", "mayo", "noodle", "oats",
    )),
]

DEFAULT_CATEGORY = "Other"


def categorize(name: str) -> str:
    """Return the best-guess category for a (normalized or raw) item name."""
    text = name.lower()
    for category, keywords in TAXONOMY:
        for kw in keywords:
            if kw in text:
                return category
    return DEFAULT_CATEGORY


def all_categories() -> list[str]:
    return [c for c, _ in TAXONOMY] + [DEFAULT_CATEGORY]
