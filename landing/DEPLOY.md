# Deploying the baskwise landing page + pointing your GoDaddy domains

You own **baskwise.com** and **baskwise.app** at GoDaddy. This guide gets the
landing page live on **baskwise.com** and points **baskwise.app** at the app.

There are two separate things to host:

| Domain | Hosts | What it is |
|---|---|---|
| **baskwise.com** | this `landing/` folder (static site) | marketing page |
| **baskwise.app** | the Streamlit app (`app.py`) | the actual product |

---

## Part 1 — Put the landing page online (free, ~10 minutes)

The landing page is a single static file, so any static host works. Easiest is
**Netlify** (no account-juggling, drag-and-drop).

1. Go to <https://app.netlify.com/drop>.
2. Drag the **`landing`** folder onto the page.
3. Netlify instantly gives you a live URL like `random-name-123.netlify.app`.
   Open it — your page is live on the internet.
4. (Optional) In **Site settings → Change site name**, set something like
   `baskwise` so the temp URL is `baskwise.netlify.app`.

> Alternatives if you prefer: **Cloudflare Pages**, **GitHub Pages**, or
> **Vercel** — all free and all work the same way with the DNS steps below.

---

## Part 2 — Point baskwise.com (GoDaddy) at the landing page

Keep the domain registered at GoDaddy; you just change its DNS records.

### A) Tell Netlify about the domain
1. In Netlify: **Site settings → Domain management → Add a domain**.
2. Enter `baskwise.com`, click **Verify → Add domain**.
3. Netlify will show the records you need (they match the values below).

### B) Add the records at GoDaddy
1. Log in to GoDaddy → **My Products → Domains → baskwise.com → DNS**
   (the "Manage DNS" button).
2. **Delete** any default parked **A record** with Host `@` (GoDaddy adds one).
3. **Add an A record** for the bare domain:
   - **Type:** A   **Host:** `@`   **Value:** `75.2.60.5`   **TTL:** default
   - *(75.2.60.5 is Netlify's load balancer. If Netlify shows a different value
     for your site, use theirs.)*
4. **Add a CNAME** for the www version:
   - **Type:** CNAME   **Host:** `www`   **Value:** `baskwise.netlify.app`
     (your Netlify site URL)   **TTL:** default
5. Save.

### C) Wait + turn on HTTPS
- DNS changes take anywhere from a few minutes to a few hours to propagate.
- Once it resolves, Netlify auto-issues a free **HTTPS certificate**
  (Domain management → HTTPS → *Verify / Provision*). Then `https://baskwise.com`
  is live and secure.

> **Simpler-but-weaker option:** GoDaddy → Domain → **Forwarding** can just
> redirect `baskwise.com` → your `.netlify.app` URL. It works in 1 step but the
> address bar may show the netlify URL and HTTPS is flakier. Prefer the DNS
> records above for a real setup.

---

## Part 3 — Point baskwise.app at the actual app

The app (`app.py`) is a Streamlit web app, so it needs a Python host, not a
static host. Easiest free option:

1. Push this project to a **GitHub** repo.
2. Go to <https://share.streamlit.io> (Streamlit Community Cloud), connect the
   repo, set the main file to `app.py`, and deploy. You get a
   `your-app.streamlit.app` URL.
3. Point **baskwise.app** at it in GoDaddy with a **CNAME**:
   - **Host:** `@` (or `www`)   **Value:** the streamlit app hostname.
   - *(Apex CNAMEs aren't always allowed; if GoDaddy rejects Host `@`, use a
     host that supports custom domains directly, e.g. Render, Railway, or Fly.io,
     which give you A/CNAME targets that work on the bare domain.)*

> For a production app you'd typically move off Community Cloud to **Render /
> Railway / Fly.io** (still cheap) for custom-domain + always-on hosting.

---

## Part 4 — Signup form → Netlify Forms (DONE in code)

The form is **already wired for Netlify Forms**. Both signup forms have:
- `name="waitlist"`, `method="POST"`, `data-netlify="true"`
- a hidden `form-name` input (required for no-build / drag-and-drop deploys)
- `netlify-honeypot="bot-field"` for spam protection
- JavaScript that POSTs the signup to Netlify **and** shows the inline
  "You're on the list!" confirmation (no full-page redirect)

**You don't need to change any code.** Just deploy and the captures begin.

### After you (re-)deploy
1. Re-upload the `landing` folder to Netlify (same drag-and-drop as before — this
   pushes the updated form code).
2. In Netlify, open **Forms** (left sidebar). You'll see a form named
   **`waitlist`**. *(It appears after the first real submission on the live site.)*
3. Submit a test email on the **live** `baskwise.com` to confirm it lands there.
4. Optional: **Forms → Settings → Form notifications** → add an email so you get
   pinged on every new signup, and/or **Export to CSV** anytime.

> Note: form capture only works on the **deployed Netlify site**, not the local
> preview (local has no Netlify backend — there it just shows the confirmation and
> keeps a browser-local backup).

> Prefer Formspree instead? Swap the `fetch('/', …)` target for your Formspree
> endpoint; everything else stays the same.

---

## Quick checklist

- [ ] Landing page dropped on Netlify, temp URL works
- [ ] baskwise.com A record `@ → 75.2.60.5` set at GoDaddy
- [ ] baskwise.com CNAME `www → baskwise.netlify.app` set at GoDaddy
- [x] HTTPS provisioned in Netlify (cert issued, valid)
- [x] Signup form wired to Netlify Forms (in code)
- [ ] Re-upload `landing` folder so the Netlify-Forms version is live
- [ ] Confirm a test signup appears in Netlify → Forms → waitlist
- [ ] App deployed; baskwise.app pointed at it
