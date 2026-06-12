"""Receipt text -> structured data.

Real-world receipts vary wildly, so this parser is heuristic but practical:
it pulls the store, the date, and line items (name, qty, unit price, line total)
out of plain text. The same parser handles pasted text and OCR'd image text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .categorize import categorize
from .products import match_staple

# --- name normalization ----------------------------------------------------

_ABBREV = {
    "wht": "white", "wht.": "white", "chkn": "chicken", "chk": "chicken",
    "org": "organic", "orgnc": "organic", "gr": "ground", "grnd": "ground",
    "lb": "", "lbs": "", "ea": "", "pk": "pack", "ct": "count",
    "choc": "chocolate", "crm": "cream", "shrp": "sharp", "ched": "cheddar",
    "yog": "yogurt", "ban": "banana", "bnls": "boneless", "sknls": "skinless",
}

_NOISE = re.compile(r"[^a-z0-9 &]")


def normalize_name(raw: str) -> tuple[str, str]:
    """Return (display_name, norm_key).

    display_name is title-cased and human friendly; norm_key is a canonical
    lowercase key used to match the same product across different receipts.
    """
    text = raw.lower().strip()
    text = _NOISE.sub(" ", text)
    tokens = []
    for tok in text.split():
        tok = _ABBREV.get(tok, tok)
        if tok:
            tokens.append(tok)
    norm_key = " ".join(sorted(set(tokens))) if tokens else raw.lower().strip()
    display = " ".join(tokens).title() if tokens else raw.strip()
    return display, norm_key


# --- line / header parsing -------------------------------------------------

KNOWN_STORES = [
    "Walmart", "Target", "Costco", "Kroger", "Safeway", "Aldi", "Publix",
    "Whole Foods", "Trader Joe's", "Albertsons", "Meijer", "Wegmans",
    "Sam's Club", "H-E-B", "Food Lion", "Giant", "Sprouts",
]

_DATE_PATTERNS = [
    (re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b"), ("m", "d", "y")),
    (re.compile(r"\b(\d{1,2})-(\d{1,2})-(\d{2,4})\b"), ("m", "d", "y")),
]

# A trailing price, optionally negative/with currency, e.g. "3.49", "$3.49", "3.49-"
_PRICE_RE = re.compile(r"\$?\s*(-?\d+\.\d{2})-?\s*$")
# Quantity prefixes like "2 ", "2x", "2 @ 1.50"
_QTY_AT_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*@\s*(\d+\.\d{2})\b")
_QTY_PREFIX_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*[xX]?\s+(?=[A-Za-z])")
_UPC_RE = re.compile(r"\b(\d{12,13})\b")

_SKIP_WORDS = (
    "subtotal", "sub total", "total", "tax", "cash", "change", "debit",
    "credit", "card", "balance", "tend", "visa", "mastercard", "amex",
    "auth", "ref", "account", "approval", "thank", "savings", "loyalty",
    "member", "items sold", "qty", "store #", "tel", "phone", "www",
    "http", "receipt", "cashier", "register", "lane", "order",
)


@dataclass
class ParsedItem:
    raw_text: str
    name: str
    norm_key: str
    category: str
    qty: float
    unit_price: float | None
    line_total: float
    upc: str | None = None


@dataclass
class ParsedReceipt:
    store: str
    purchased_on: str  # ISO date or "" if unknown
    total: float | None
    city: str = ""
    state: str = ""
    zip: str = ""
    time: str = ""  # HH:MM (24h) if a purchase time is on the receipt
    subtotal: float | None = None
    tax: float | None = None
    items: list[ParsedItem] = field(default_factory=list)

    @property
    def computed_total(self) -> float:
        return round(sum(i.line_total for i in self.items), 2)

    @property
    def has_date(self) -> bool:
        return bool(self.purchased_on)


# Purchase time: "14:32", "2:32 PM", "02:32:11 pm". Colon distinguishes it from
# prices (which use a dot). Captured for accuracy/ordering when present.
_TIME_RE = re.compile(
    r"\b(\d{1,2}):(\d{2})(?::\d{2})?\s*([AaPp][Mm])?\b"
)


def _detect_time(text: str) -> str:
    """Return purchase time as HH:MM (24h), or '' if none found."""
    for m in _TIME_RE.finditer(text):
        hh, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3)
        if mm > 59:
            continue
        if ap:
            ap = ap.lower()
            if hh < 1 or hh > 12:
                continue
            if ap == "pm" and hh != 12:
                hh += 12
            elif ap == "am" and hh == 12:
                hh = 0
        if 0 <= hh <= 23:
            return f"{hh:02d}:{mm:02d}"
    return ""


def _detect_store(lines: list[str]) -> str:
    head = " ".join(lines[:6]).lower()
    for store in KNOWN_STORES:
        if store.lower() in head:
            return store
    # Fall back to the first non-empty, non-numeric line.
    for ln in lines:
        s = ln.strip()
        if s and not any(ch.isdigit() for ch in s) and len(s) > 2:
            return s.title()
    return "Unknown Store"


def _detect_date(text: str) -> str:
    for rx, order in _DATE_PATTERNS:
        m = rx.search(text)
        if not m:
            continue
        parts = dict(zip(order, m.groups()))
        y, mo, d = parts["y"], parts["m"], parts["d"]
        if len(y) == 2:
            y = "20" + y
        try:
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        except ValueError:
            continue
    return ""


# "Dallas, TX 75201"  /  "Austin TX 78701"  /  a bare 5-digit ZIP
_CITY_STATE_ZIP_RE = re.compile(
    r"([A-Za-z][A-Za-z .'-]+?)[,\s]+([A-Z]{2})\b\s*(\d{5})?(?:-\d{4})?"
)
_ZIP_RE = re.compile(r"\b(\d{5})(?:-\d{4})?\b")


def _detect_location(lines: list[str]) -> tuple[str, str, str]:
    """Return (city, state, zip) from the receipt header, best-effort."""
    head = lines[:8]
    for ln in head:
        m = _CITY_STATE_ZIP_RE.search(ln)
        if m:
            city = m.group(1).strip(" .,'-").title()
            state = m.group(2).upper()
            zipc = m.group(3) or ""
            if not zipc:
                z = _ZIP_RE.search(ln)
                zipc = z.group(1) if z else ""
            # Guard against matching store-name words as a city.
            if 1 < len(city) <= 25:
                return city, state, zipc
    # Fall back to a bare ZIP anywhere in the header.
    for ln in head:
        z = _ZIP_RE.search(ln)
        if z:
            return "", "", z.group(1)
    return "", "", ""


def _is_skippable(line: str) -> bool:
    """Skip totals/payment/footer lines — matching WHOLE tokens, not substrings.

    Substring matching wrongly flagged real items: "tel" inside "nutella",
    "card" inside "cardamom", "tend" inside "tenders". Single-word skip terms
    must match a whole token; multi-word / punctuated terms fall back to substring.
    """
    low = line.lower()
    tokens = set(re.findall(r"[a-z#]+", low))
    for w in _SKIP_WORDS:
        if " " in w or "#" in w:
            if w in low:
                return True
        elif w in tokens:
            return True
    return False


def parse_receipt(text: str) -> ParsedReceipt:
    raw_lines = [ln.rstrip() for ln in text.splitlines()]
    lines = [ln for ln in raw_lines if ln.strip()]

    store = _detect_store(lines)
    date = _detect_date(text)
    time = _detect_time(text)
    city, state, zipc = _detect_location(lines)

    declared_total: float | None = None
    subtotal: float | None = None
    tax: float | None = None
    items: list[ParsedItem] = []

    for ln in lines:
        low = ln.lower()
        low_ns = low.replace(" ", "")
        price_match = _PRICE_RE.search(ln)

        # Capture subtotal / tax / total separately (don't treat as items) —
        # these power the totals-reconciliation accuracy check.
        if price_match:
            try:
                val = float(price_match.group(1))
            except ValueError:
                val = None
            if val is not None:
                if "subtotal" in low_ns:
                    subtotal = val
                    continue
                if re.search(r"\btax\b", low):
                    tax = val
                    continue
                if "total" in low_ns:
                    declared_total = val
                    continue

        if _is_skippable(ln) or not price_match:
            continue

        line_total = float(price_match.group(1))
        if line_total <= 0:
            continue  # skip coupons / negative adjustments for the demo

        body = ln[: price_match.start()].strip()

        # Pull a UPC out of the line if present, then strip it from the name.
        upc = None
        upc_m = _UPC_RE.search(body)
        if upc_m:
            upc = upc_m.group(1)
            body = (body[: upc_m.start()] + body[upc_m.end():]).strip()

        qty = 1.0
        unit_price: float | None = None

        at_m = _QTY_AT_RE.match(body)
        if at_m:
            qty = float(at_m.group(1))
            unit_price = float(at_m.group(2))
            body = body[at_m.end():].strip()
        else:
            pre_m = _QTY_PREFIX_RE.match(body)
            if pre_m:
                qty = float(pre_m.group(1))
                body = body[pre_m.end():].strip()

        if not body or not re.search(r"[A-Za-z]", body):
            continue  # no real item name

        if unit_price is None:
            unit_price = round(line_total / qty, 2) if qty else line_total

        display, norm_key = normalize_name(body)
        # Canonicalize common staples so the same product lines up across stores.
        staple = match_staple(body)
        if staple:
            display, norm_key = staple
        # Categorize from the normalized/canonical name (abbreviations expanded),
        # so "CHKN BREAST" and "CHICKEN BREAST" land in the same category.
        items.append(
            ParsedItem(
                raw_text=ln.strip(),
                name=display,
                norm_key=norm_key,
                category=categorize(display),
                qty=qty,
                unit_price=unit_price,
                line_total=line_total,
                upc=upc,
            )
        )

    return ParsedReceipt(
        store=store,
        purchased_on=date,
        total=declared_total,
        city=city,
        state=state,
        zip=zipc,
        time=time,
        subtotal=subtotal,
        tax=tax,
        items=items,
    )
