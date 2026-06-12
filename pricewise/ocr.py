"""Photo-receipt OCR.

Turns a receipt photo into text using Tesseract. The Tesseract binary often
isn't on PATH (especially on Windows installs), so we auto-locate it in the
common install dirs. `ocr_available()` lets the UI degrade gracefully.
"""

from __future__ import annotations

import os
import shutil

# Common Tesseract locations to check when it isn't on PATH.
_CANDIDATES = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
    "/opt/homebrew/bin/tesseract",
]


def _locate_binary() -> str | None:
    found = shutil.which("tesseract")
    if found:
        return found
    for path in _CANDIDATES:
        if path and os.path.isfile(path):
            return path
    return None


def _configure() -> str | None:
    """Point pytesseract at the binary if found. Returns the path or None."""
    try:
        import pytesseract
    except Exception:
        return None
    path = _locate_binary()
    if path:
        pytesseract.pytesseract.tesseract_cmd = path
    return path


def ocr_available() -> tuple[bool, str]:
    """Return (available, reason). Reason explains what's missing if not."""
    try:
        import pytesseract  # noqa: F401
        from PIL import Image  # noqa: F401
    except Exception:
        return False, "pytesseract/Pillow not installed (pip install pytesseract Pillow)"

    if not _configure():
        return (
            False,
            "Tesseract binary not found. Install it: "
            "https://github.com/UB-Mannheim/tesseract/wiki",
        )

    try:
        import pytesseract
        pytesseract.get_tesseract_version()
    except Exception as e:
        return False, f"Tesseract found but not runnable: {e}"
    return True, "ready"


# Receipts are a single tall column of text → PSM 4 ("single column of text of
# variable sizes") reads them more accurately than the default.
_OCR_CONFIG = "--psm 4"


def _prep(file_or_bytes):
    """Open + preprocess an image for accurate receipt OCR."""
    import io

    from PIL import Image, ImageOps, ImageFilter

    if isinstance(file_or_bytes, (bytes, bytearray)):
        img = Image.open(io.BytesIO(file_or_bytes))
    else:
        img = Image.open(file_or_bytes)

    img = ImageOps.exif_transpose(img)        # respect phone orientation
    img = img.convert("L")                     # grayscale
    if img.width < 1400:                        # upscale small/low-res photos
        scale = 1400 / img.width
        img = img.resize((1400, int(img.height * scale)))
    img = ImageOps.autocontrast(img)           # normalize lighting
    img = img.filter(ImageFilter.SHARPEN)      # crisp the text edges
    return img


def image_to_text(file_or_bytes) -> str:
    """OCR an image (path, file-like, or bytes) into text. Raises if unavailable."""
    import pytesseract

    _configure()
    return pytesseract.image_to_string(_prep(file_or_bytes), config=_OCR_CONFIG)


def image_to_text_with_confidence(file_or_bytes) -> tuple[str, float | None]:
    """OCR plus a mean word-confidence (0-100), the OCR engine's own accuracy
    estimate. Returns (text, confidence) — confidence is None if unavailable."""
    import pytesseract

    _configure()
    img = _prep(file_or_bytes)
    text = pytesseract.image_to_string(img, config=_OCR_CONFIG)
    try:
        data = pytesseract.image_to_data(
            img, config=_OCR_CONFIG, output_type=pytesseract.Output.DICT
        )
        confs = [float(c) for c in data.get("conf", []) if str(c).strip() not in ("", "-1")]
        confidence = round(sum(confs) / len(confs), 1) if confs else None
    except Exception:
        confidence = None
    return text, confidence
