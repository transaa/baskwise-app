# 🧺 baskwise

> baskwise.com · baskwise.app

A receipt-powered grocery & household price tracker. Instead of crawling
retailers (hard, blocked, legally gray), **users bring their own receipts** —
turning the data problem into a first-party, fully-legal asset. At scale, those
receipts become a crowdsourced, real-world, local price database that the big
comparison engines can't easily replicate.

(The internal Python package is named `pricewise` from the prototype phase; the
product brand is **baskwise**.)

## What it does

- **Find savings** — a proactive "top savings opportunities near you" panel plus,
  for any receipt, an item-by-item breakdown of which **nearby** store is cheapest,
  your total potential savings, and a "buy these here, those there" shopping plan
  (recommendations are restricted to drivable stores, never out-of-region)
- **Look up by UPC** — enter/scan a barcode, identify the product live via the open
  Open Food Facts database, and see every store + price logged for it, cheapest first
- **Location-aware** — set your home ZIP; comparisons rank by proximity (your area =
  same ZIP, your city, your region = same state) so you see the cheapest price you
  can actually drive to, not just the cheapest in the country
- **Price-drop alerts** — set a target price per product; baskwise flags it when it
  drops to your price at a store near you
- **Personal inflation** — the Overview shows how fast your own staples basket is
  rising over time, with the biggest individual price increases ranked
- **Photo receipts (OCR)** — snap/upload a receipt photo and Tesseract reads it into
  line items (editable before saving)
- **Parse receipts** (pasted text now; photo OCR optional) into clean line items
- **Auto-categorize** every item into a tidy taxonomy (Produce, Dairy, Pantry, …)
- **Match products across stores** so "Great Value Milk 1Gal" and "2% Milk Gallon"
  line up as the same item
- **Track spending** by month, store, and category
- **Watch price history** for any item, across stores, over time
- **Compare baskets** — see which store is actually cheaper for *your* basket

## Quick start

```powershell
# 1. Install dependencies
python -m pip install -r requirements.txt

# 2. Run the dashboard (auto-loads 6 sample receipts on first run)
streamlit run app.py
```

Then open http://localhost:8501.

### Deploying online (free)

See **[STREAMLIT_DEPLOY.md](STREAMLIT_DEPLOY.md)** for step-by-step instructions to
put the app on Streamlit Community Cloud (free). The repo already includes the
needed files: `requirements.txt`, `packages.txt` (installs Tesseract for OCR),
`.gitignore`, and `.streamlit/config.toml` (theme).

### Optional: photo-receipt OCR

Text receipts work out of the box. To read receipt *photos*, also install the
Tesseract binary (the Python packages are already in `requirements.txt`):

- Windows: https://github.com/UB-Mannheim/tesseract/wiki

The app detects whether OCR is available and degrades gracefully if not.

## Project layout

```
app.py                 Streamlit dashboard (Savings / Overview / Prices / Basket / Add)
pricewise/
  db.py                SQLite schema + helpers (receipts, items)
  parser.py            Receipt text -> structured line items
  categorize.py        Keyword taxonomy (Produce, Dairy, Household, …)
  products.py          Cross-store staple matcher (the UPC stand-in for the demo)
  savings.py           Savings engine — receipt vs cheapest nearby + top opportunities
  watches.py           Price-drop watch evaluation (triggered when nearby <= target)
  insights.py          Personal grocery inflation from repeat-purchased staples
  upc.py               UPC -> product resolver (Open Food Facts, offline fallback)
  location.py          Proximity tiers (your area / city / region) for "near you"
  ocr.py               Photo-receipt OCR (Tesseract; auto-locates the binary)
  seed.py              Loads sample_receipts/ + example watches on first run
sample_receipts/       10 receipts (6 stores, 4 TX cities) + sample_receipt.png
landing/               Marketing site for baskwise.com (index.html + DEPLOY.md)
pricewise.db           SQLite database (created on first run)
```

## How this maps to the real product

| Demo (here)                          | Production                                   |
|--------------------------------------|----------------------------------------------|
| Curated staples matcher (`products.py`) | Match on **UPC/GTIN** from receipt barcodes + Open Food Facts |
| 6 sample receipts                    | Real user uploads + photo OCR                |
| SQLite, single user                  | Postgres, multi-user accounts                |
| Latest-price basket compare          | + alerts, coupons, cashback, local stock     |

The software is the easy part; the **data moat** (real shoppers' baskets) is the
defensible asset. This prototype proves the pipeline end to end.

## Legal note

PriceWise stores **facts** users voluntarily share — store, date, item, price,
UPC. Raw facts aren't copyrightable, there's no scraping, and no retailer ToS is
involved. That clean legal footing is the whole point of the receipt-first design.
