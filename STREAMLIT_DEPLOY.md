# Deploying the baskwise app to Streamlit Community Cloud (free)

This puts the **app** (the Streamlit dashboard) online for free. It's separate
from baskwise.com (the landing page, already live on Netlify).

Unlike the landing page, the app can't be "drag-and-dropped" — it's a running
Python program, so it needs to live in a **GitHub repository**, which Streamlit
then runs. The one new thing you'll need is a free GitHub account. No coding or
command line required — everything below is done in the browser.

---

## What gets uploaded

Upload these (they're all in `C:\Users\LoveT\Downloads\reg15`):

```
app.py                 ← the app
pricewise/             ← the app's code (whole folder)
sample_receipts/       ← demo data the app loads on first run (whole folder)
requirements.txt       ← Python packages to install
packages.txt           ← system package (Tesseract, for photo OCR)
.streamlit/            ← optional theme (skip if dotfolders are fiddly to upload)
```

**Do NOT upload:**
- `pricewise.db` — this is generated automatically; committing it causes stale data
- `.claude/`, `landing/` — not part of the app (landing is the separate website)

---

## Step 1 — Create a GitHub account + repository

1. Go to <https://github.com> → **Sign up** (free) if you don't have an account.
2. Click the **+** (top-right) → **New repository**.
3. Name it `baskwise-app`, leave it **Public**, click **Create repository**.

## Step 2 — Upload the app files (no git needed)

1. On the new empty repo page, click **“uploading an existing file”** (the link
   in the middle), or **Add file → Upload files**.
2. Open File Explorer at `C:\Users\LoveT\Downloads\reg15`.
3. **Drag in** `app.py`, `requirements.txt`, `packages.txt`, and the
   **`pricewise`** and **`sample_receipts`** folders (you can drag folders;
   GitHub keeps their structure).
4. Scroll down, click **Commit changes**.

> The `.streamlit` theme folder is optional. If you want it, after the upload
> click **Add file → Create new file**, type `.streamlit/config.toml` as the
> name (the `/` makes the folder), paste the contents of your local
> `.streamlit/config.toml`, and commit. Skip this if it's a hassle — the app
> looks fine without it.

## Step 3 — Deploy on Streamlit Community Cloud

1. Go to <https://share.streamlit.io> → **Sign in with GitHub** (authorize it).
2. Click **Create app → Deploy a public app from GitHub**.
3. Fill in:
   - **Repository:** `your-username/baskwise-app`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. (Optional) Click **Advanced** and set the app URL to `baskwise` so it becomes
   `baskwise.streamlit.app`.
5. Click **Deploy**. First build takes ~2–5 min (it installs the packages,
   including Tesseract for OCR). When it finishes, your app is live. 🎉

## Step 4 — (Optional) Point baskwise.app at it

Streamlit's free tier doesn't support custom domains directly, so the simplest
route is a redirect:

1. GoDaddy → **baskwise.app → DNS → Forwarding**.
2. Forward `baskwise.app` → `https://baskwise.streamlit.app` (permanent / 301).

When you outgrow the free tier and want baskwise.app to serve the app *directly*
(with HTTPS, no redirect), move the app to **Render** or **Google Cloud Run** —
both let you CNAME the bare domain. I can help with that migration.

---

## Good to know

- **Photo OCR works on the cloud** because `packages.txt` installs Tesseract; the
  app auto-finds it on the server's PATH.
- **The database is temporary.** Streamlit Cloud has an ephemeral disk, so the
  app re-creates and re-seeds `pricewise.db` on each restart. Perfect for a demo.
  The moment you have real users, switch to a free hosted Postgres
  (**Supabase** or **Neon**) so data persists — that's a code change I can make.
- **Updating the app later:** edit a file on GitHub (or re-upload) → Streamlit
  auto-redeploys within a minute.
- **It sleeps when idle.** Free apps spin down after inactivity; the first visit
  after a nap takes ~30s to wake. Normal for free hosting.

## Quick troubleshooting

| Symptom | Fix |
|---|---|
| Build fails on a package | Check `requirements.txt` uploaded correctly |
| "No module named pricewise" | The `pricewise` folder didn't upload — re-upload it whole |
| App loads but no data | `sample_receipts/` folder is missing — re-upload it |
| Photo OCR says unavailable | `packages.txt` (with `tesseract-ocr`) didn't upload |
