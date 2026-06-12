# Turn on "Sign in with Google" (user accounts)

The app is **account-ready**. Until you complete the steps below it runs in
**open mode** (one shared journal, no login) — nothing breaks. Once you add the
Google credentials, users can sign in and get their **own private journal**,
while their receipts still feed the shared community price database.

## Step 1 — Create a Google OAuth client (free, ~10–15 min)

1. Go to <https://console.cloud.google.com> → create a project (e.g. "baskwise").
2. **APIs & Services → OAuth consent screen**:
   - User type: **External** → Create
   - App name: **baskwise**, support email: your email
   - Add your email under "Test users" (and "Developer contact")
   - Save. (You can "Publish" later to allow anyone; while in Testing, only
     listed test users can sign in.)
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**:
   - Application type: **Web application**
   - Name: **baskwise web**
   - **Authorized redirect URIs** → add **both**:
     - `https://baskwise.app/oauth2callback`
     - `https://www.baskwise.app/oauth2callback`
   - Create → copy the **Client ID** and **Client secret**

## Step 2 — Add the secrets to Render

Streamlit reads auth config from secrets. On Render, add a **Secret File**:

1. Render → your `baskwise` service → **Environment → Secret Files → Add Secret File**
2. **Filename:** `.streamlit/secrets.toml`
3. **Contents** (fill in your values):

   ```toml
   [auth]
   redirect_uri = "https://baskwise.app/oauth2callback"
   cookie_secret = "PASTE_A_LONG_RANDOM_STRING_HERE"

   [auth.google]
   client_id = "YOUR_GOOGLE_CLIENT_ID"
   client_secret = "YOUR_GOOGLE_CLIENT_SECRET"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
   ```

   - `cookie_secret`: any long random string (e.g. run `python -c "import secrets;print(secrets.token_hex(32))"`).
4. **Save** → Render redeploys.

## Step 3 — Verify

1. Open **baskwise.app** → the sidebar now shows **"🔑 Sign in with Google."**
2. Sign in → it should greet you with **"👤 your@email.com"** and receipts you
   add are saved to **your** journal (Overview/Savings show only yours; UPC
   Lookup, Price History, Basket and the price comparisons still use the shared
   community pool).

## Notes
- **Open mode stays the default** until `[auth]` is present — safe to deploy anytime.
- **Watches/alerts are currently shared** (not yet per-user) — a small follow-up.
- **Apple sign-in** can be added later (needs a paid Apple Developer account); for
  a web app, Google already covers iPhone and Android users.
- Existing/seed receipts have no owner (they stay in the community pool, not in
  any personal journal).
