"""Receipt quality assessment — guard accuracy before data enters the database.

The strongest automatic accuracy signal for a receipt is **totals
reconciliation**: if the parsed line items add up to the receipt's printed
subtotal (or total minus tax), the OCR + parse are almost certainly correct.
Combined with the date/store/items checks and the OCR engine's own confidence,
this gives each receipt an overall trust grade before it's saved.
"""

from __future__ import annotations

from dataclasses import dataclass

# Absolute dollar tolerance for "the numbers add up" (covers rounding).
_TOL = 0.02


@dataclass
class Check:
    label: str
    ok: bool | None      # True pass, False fail, None = can't determine
    detail: str


def reconcile_totals(parsed) -> Check:
    """Compare the sum of parsed items against the receipt's printed totals."""
    items_sum = parsed.computed_total

    if parsed.subtotal is not None:
        diff = round(items_sum - parsed.subtotal, 2)
        ok = abs(diff) <= _TOL
        return Check(
            "Totals reconcile",
            ok,
            (f"items add up to ${items_sum:.2f} = subtotal ${parsed.subtotal:.2f} ✓"
             if ok else
             f"items sum ${items_sum:.2f} ≠ subtotal ${parsed.subtotal:.2f} "
             f"(off by ${abs(diff):.2f}) — likely a misread, please review"),
        )

    if parsed.total is not None and parsed.tax is not None:
        target = round(parsed.total - parsed.tax, 2)
        diff = round(items_sum - target, 2)
        ok = abs(diff) <= _TOL
        return Check(
            "Totals reconcile",
            ok,
            (f"items ${items_sum:.2f} = total − tax ${target:.2f} ✓" if ok else
             f"items ${items_sum:.2f} ≠ total − tax ${target:.2f} "
             f"(off by ${abs(diff):.2f}) — please review"),
        )

    if parsed.total is not None:
        # Only a tax-inclusive total to compare to — can't match exactly.
        return Check(
            "Totals reconcile", None,
            f"items ${items_sum:.2f} vs printed total ${parsed.total:.2f} "
            "(no subtotal/tax to verify against)",
        )

    return Check("Totals reconcile", None,
                 "no printed total found to check the items against")


def assess(parsed, ocr_confidence: float | None = None) -> dict:
    """Full quality assessment of a parsed receipt -> checks + overall grade."""
    checks: list[Check] = [
        Check("Date present", parsed.has_date,
              parsed.purchased_on + (f" {parsed.time}" if parsed.time else "")
              if parsed.has_date else "missing — required before saving"),
        Check("Store identified", parsed.store != "Unknown Store", parsed.store),
        Check("Items found", bool(parsed.items), f"{len(parsed.items)} item(s)"),
        reconcile_totals(parsed),
    ]
    if ocr_confidence is not None:
        checks.append(Check(
            "OCR confidence",
            ocr_confidence >= 75 if ocr_confidence is not None else None,
            f"{ocr_confidence:.0f}% (engine's own read-accuracy estimate)",
        ))

    # Grade: low if any hard requirement fails or totals clearly don't reconcile.
    hard_fail = (not parsed.has_date) or (not parsed.items)
    recon = next(c for c in checks if c.label == "Totals reconcile")
    low_conf = ocr_confidence is not None and ocr_confidence < 60

    if hard_fail or recon.ok is False or low_conf:
        grade = "low"
    elif recon.ok is True and parsed.store != "Unknown Store":
        grade = "high"
    else:
        grade = "medium"

    return {"checks": checks, "grade": grade, "reconciled": recon.ok}
