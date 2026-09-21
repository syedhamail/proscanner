# Pro Scanner — Full Website

A Flask website around your original Pro Scanner strategy engine, with accounts,
email verification, Google/GitHub login, Paddle-billed plans with usage limits,
a user dashboard, and a hidden admin panel — all backed by PostgreSQL.

## Pages
- `/` — Home
- `/about` — About Us
- `/signals` — The Pro Scanner tool (your original strategy, unchanged)
- `/pricing` — Basic / Advanced / Premium plans, paid via Paddle
- `/dashboard` — Logged-in user's account, plan, usage, password change, logout
- `/login`, `/signup` — Email+password or Google/GitHub
- `/verify-email/<token>` — Email verification link target
- `/terms`, `/privacy`
- `/admin` — Hidden admin panel (not linked anywhere; see below)

## Project structure
```
proscanner/
├── app.py                  # Routes, auth, OAuth, Paddle, admin, scan gating
├── plans.py                  # Plan limits + scan-quota logic
├── scanner_engine.py          # Your original scanning strategy — logic untouched
├── models.py                   # SQLAlchemy User model (PostgreSQL)
├── requirements.txt
├── Dockerfile                   # Recommended for Northflank
├── Procfile
├── .env.example
├── templates/
└── static/
```

## How the plans work
| Plan     | Price       | Limit                          |
|----------|-------------|---------------------------------|
| Basic    | $3 / 7 days | 25 scans per rolling 7 days     |
| Advanced | $10 / month | 100 scans per rolling 30 days   |
| Premium  | $100 / year | Unlimited scans for 365 days    |

- If a logged-out user clicks **Run Scan** on `/signals`, they're sent to `/login`
  (then back to `/signals` once they log in).
- If a logged-in user with no plan clicks **Run Scan**, they're sent to `/pricing`.
- If a user hits their plan's limit (or their Premium year has ended), clicking
  **Run Scan** sends them to `/pricing` again.
- All of this is enforced **server-side** in `/api/scan` (see `plans.py`), not just
  in the UI — so it can't be bypassed by editing the page.

## Running locally

```bash
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # fill in what you can — see below
python app.py
```

Visit `http://localhost:5000`. Without `DATABASE_URL`, it falls back to a local
SQLite file so you can test signup/login/dashboard without Postgres.

**Local dev shortcut:** if `RESEND_API_KEY` isn't set, verification emails aren't
actually sent — the verification link is printed to your terminal instead, so you
can still test the full signup → verify → dashboard flow locally.

## Setting up each integration

### 1. PostgreSQL (Northflank)
Add Northflank's free Postgres add-on, copy the connection string into
`DATABASE_URL`. On first boot the app runs `db.create_all()` and creates the
`users` table automatically.

### 2. Resend (verification + contact emails)
Create an API key at [resend.com](https://resend.com) → `RESEND_API_KEY`.
Set `CONTACT_TO_EMAIL` to your own inbox.

### 3. Google OAuth
1. [Google Cloud Console](https://console.cloud.google.com/apis/credentials) → Create OAuth Client ID → "Web application".
2. Authorized redirect URI: `https://yourdomain.com/auth/google/callback` (and `http://localhost:5000/auth/google/callback` for local testing).
3. Put the Client ID/Secret into `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`.

### 4. GitHub OAuth
1. [GitHub Developer Settings](https://github.com/settings/developers) → New OAuth App.
2. Authorization callback URL: `https://yourdomain.com/auth/github/callback` (and a second app, or just test on localhost first, for `http://localhost:5000/auth/github/callback`).
3. Put the Client ID/Secret into `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET`.

### 5. Paddle Billing
1. Sign up at [Paddle](https://www.paddle.com) — use **Sandbox** while testing.
2. **Catalog → Prices**: create one price for each plan (Basic $3/7 days, Advanced
   $10/month, Premium $100/year). Copy each Price ID into `PADDLE_BASIC_PRICE_ID`,
   `PADDLE_ADVANCED_PRICE_ID`, `PADDLE_PREMIUM_PRICE_ID`.
3. **Developer Tools → Authentication**: copy your client-side token into
   `PADDLE_CLIENT_TOKEN`. Set `PADDLE_ENV=sandbox` (switch to `production` when live).
4. **Developer Tools → Notifications**: add a webhook destination pointing to
   `https://yourdomain.com/api/paddle-webhook`, subscribe to `transaction.completed`,
   `subscription.created`, `subscription.activated`, `subscription.canceled`, and
   `subscription.paused`. Copy the webhook's secret key into `PADDLE_WEBHOOK_SECRET`.
5. **Important:** Paddle's exact webhook payload shape can change between API
   versions — `app.py`'s `paddle_webhook()` reads `event_type`, `data.custom_data`,
   `data.subscription_id`/`data.id`, and `data.customer_id`. Check this against
   Paddle's current docs after you wire up your account, and adjust the field
   names there if Paddle has changed anything.
6. The checkout flow: `/pricing` opens a Paddle.js overlay with `customData:
   {user_id, plan}`; once Paddle confirms payment, it calls your webhook, which
   is what actually sets `user.plan` in the database. The client-side redirect to
   `/dashboard` happens immediately, but the plan may take a few seconds to show
   up if the webhook is slightly delayed.

### 6. Admin panel
Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` in your environment. Go to
`https://yourdomain.com/admin` — there's no link to it anywhere on the site.
It shows every signed-up user, their plan, and their signup/last-login time in
Pakistan time (Asia/Karachi).

## Deploying on Northflank

1. Push this project to a GitHub repository.
2. Add Northflank's Postgres add-on (free tier) and copy its connection string.
3. Create a new Service in Northflank, connect your repo — it will detect the
   `Dockerfile` automatically.
4. Add every variable from `.env.example` under the service's **Environment** tab.
5. Set the service port to `8080` (matches the `Dockerfile`).
6. Deploy, then go back and set your real domain in Google/GitHub/Paddle's
   redirect URIs and webhook URL once you have it.

## SEO — what's already done vs. what you need to do

### Already built in
- Unique `<title>` and meta description on every public page.
- `rel="canonical"` on every page, built from `SITE_URL` + the page path.
- Open Graph + Twitter Card tags (title, description, image, url) on every page,
  using `static/img/og-image.png` as the default share image.
- JSON-LD structured data: `Organization` + `WebSite` on every page, plus a
  `Product`/`Offer` schema on `/pricing` listing the three real plans and prices
  (no fake ratings or review counts — Google penalizes fabricated structured data).
- `robots.txt` and `sitemap.xml`, served at the actual domain root
  (`https://proscanner.com.pk/robots.txt`, `.../sitemap.xml`) — required, since
  crawlers won't look for them under `/static/`.
- `noindex, nofollow` on account pages (`/login`, `/signup`, `/dashboard`,
  `/verify-email`, `/resend-verification`, `/admin`) — these shouldn't show up in
  Google, only the real content pages should.
- A full favicon/icon set generated from a new logo (magnifying glass + trend
  line): `favicon.ico`, 16/32px PNGs, `apple-touch-icon.png`, Android Chrome
  icons, and `site.webmanifest` — all under `static/img/` and `static/`.

### You need to do this yourself (I can't do these from here)
1. **Set `SITE_URL`** in your environment to `https://proscanner.com.pk` (already
   the default, but confirm it once you deploy — this drives every canonical/OG URL).
2. **`static/seo/sitemap.xml` has the domain hardcoded** (not read from `SITE_URL`,
   since it's a static file) — if you ever change domains, edit that file directly.
3. **Google Search Console** (search.google.com/search-console): add
   `proscanner.com.pk` as a property, verify ownership (DNS TXT record is easiest),
   then submit `https://proscanner.com.pk/sitemap.xml` under Sitemaps. This is the
   actual step that gets your pages into Google — nothing in the code does this
   for you.
4. **Bing Webmaster Tools** (bing.com/webmasters): same idea, so you also show up
   on Bing/Yahoo/DuckDuckGo (which use Bing's index).
5. **Facebook/Twitter share preview**: once live, paste your homepage URL into
   Facebook's Sharing Debugger and Twitter's Card Validator to confirm the
   `og-image.png` preview renders the way you expect (they cache aggressively, so
   use "Scrape Again" if you update the image later).
6. **Replace the generated logo if you want a custom-designed one** — see the
   next section for exactly which files and sizes to replace.
7. **Add a real Twitter/X handle** if you have one: in `templates/base.html`, add
   `<meta name="twitter:site" content="@yourhandle">` next to the other Twitter tags.

## Replacing the logo with your own design
Everything below lives in `static/img/` (and one file in `static/`). If you'd
rather use a professionally designed logo instead of the generated one, replace
these files with the exact same names and sizes — nothing else needs to change:

| File | Size | Used for |
|---|---|---|
| `static/img/logo.svg` | any (vector) | Header logo, footer logo |
| `static/img/favicon.ico` | 16/32/48px multi-size | Classic browser tab icon |
| `static/img/favicon-16x16.png` | 16×16 | Browser tab (small) |
| `static/img/favicon-32x32.png` | 32×32 | Browser tab (retina) |
| `static/img/apple-touch-icon.png` | 180×180 | iOS "Add to Home Screen" |
| `static/img/android-chrome-192x192.png` | 192×192 | Android home screen / PWA |
| `static/img/android-chrome-512x512.png` | 512×512 | Android splash / PWA, also used as the `Organization` logo in structured data |
| `static/img/og-image.png` | 1200×630 (exactly) | Facebook/WhatsApp/LinkedIn/Twitter share preview |

If your new logo doesn't already have a background baked in (transparent PNG),
make sure `favicon.ico`, the Android icons, and the Apple touch icon each have a
solid background fill — iOS and some browsers don't add one automatically and a
transparent icon can look broken.

## Notes
- If you already deployed an earlier version of this project, the `users` table
  now has several new columns (`is_verified`, `plan`, `oauth_provider`, etc.).
  `db.create_all()` won't add columns to an existing table — for a fresh Postgres
  database this isn't an issue, but if you already have data, drop the `users`
  table (or use a migration tool like Flask-Migrate) before redeploying.
- `/signals` and `scanner_engine.py` still mirror your original strategy exactly —
  only the page around it changed.
