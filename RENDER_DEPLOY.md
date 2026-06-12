# Deploying the baskwise app to Render (free, anonymous, custom domain)

Render serves the app to **anyone with no login** and lets **baskwise.app serve it
directly** (its own HTTPS — no redirect). It deploys from the same GitHub repo
(`transaa/baskwise-app`). The repo already includes everything Render needs:
`Dockerfile` (installs Tesseract for OCR), `render.yaml` (the Blueprint), and
`.dockerignore`.

## Step 1 — Create the service (one-click via Blueprint)

1. Go to <https://render.com> → **Get Started / Sign in with GitHub** → authorize
   Render.
2. Click **New +** → **Blueprint**.
3. Connect / pick the **`baskwise-app`** repository → Render reads `render.yaml`
   and proposes a free web service named **baskwise** → click **Apply**.
4. The first build takes ~5–10 min (it's building the Docker image: installing
   Tesseract + Python packages). Watch the log; it ends with the app live at
   something like **`https://baskwise.onrender.com`**.

> Alternative if Blueprint gives trouble: **New + → Web Service →** pick the repo
> → Render auto-detects the **Dockerfile** → set **Instance Type: Free** →
> **Create Web Service**. Same result.

## Step 2 — Point baskwise.app at it (true custom domain)

1. In the Render service → **Settings → Custom Domains → Add Custom Domain**.
2. Enter **`baskwise.app`** (and optionally `www.baskwise.app`).
3. Render shows the exact DNS records to add. Typically:
   - **apex `baskwise.app`** → an **A record** to a Render IP (Render shows it), or
   - **`www`** → a **CNAME** to `baskwise.onrender.com`.
4. In **GoDaddy → baskwise.app → DNS**, add exactly the record(s) Render shows.
   - If baskwise.app currently uses GoDaddy *forwarding*, remove that first.
5. Back in Render, click **Verify**. Once DNS propagates (minutes–hours), Render
   **auto-issues a free HTTPS certificate**. Then `https://baskwise.app` serves
   the app directly. 🎉

## Make data persistent — connect a free Postgres (Supabase or Neon)

By default the app uses an ephemeral SQLite file that resets on every restart.
To get a **persistent, ever-growing community database**, point it at a free
cloud Postgres. The app auto-switches the moment a `DATABASE_URL` is present —
no code change.

1. Create a free Postgres:
   - **Neon** (<https://neon.tech>) → New Project → copy the **connection string**, or
   - **Supabase** (<https://supabase.com>) → New Project → Settings → Database →
     **Connection string (URI)**. Use the connection string (include the password).
2. In **Render → your `baskwise` service → Environment → Add Environment Variable**:
   - **Key:** `DATABASE_URL`
   - **Value:** the Postgres connection string (e.g. `postgresql://user:pass@host:5432/dbname`)
3. **Save** → Render redeploys. On first boot the app creates the tables and seeds
   the sample data into Postgres; after that, **every receipt persists** across
   restarts and accumulates for all users.

> The app accepts either `postgres://` or `postgresql://` and adjusts
> automatically. Leave `DATABASE_URL` unset to keep using local SQLite in dev.

## Good to know (honest caveats)

- **Free tier sleeps** after ~15 min idle → the first visit then takes ~50s to
  wake. Fine for early users; upgrade to **Starter ($7/mo)** for always-on when
  you launch for real.
- **Anonymous access** — no login wall (the key win over Streamlit Cloud).
- **Data persistence:** without `DATABASE_URL` the DB is ephemeral (resets on
  restart). Set `DATABASE_URL` to a free Postgres (see the section above) and data
  persists and accumulates — the code already supports it, no change needed.
- **Updating the app:** push to GitHub → Render auto-redeploys (autoDeploy is on).

## If a deploy fails

Copy the build log error and send it over. The image is already verified to build
and run locally, so most issues would be Render-config (instance type, branch).
