# TruthScope frontend

Static frontend for Supabase Google OAuth, authenticated verification, private history, and complete
backend result rendering.

## 1. Configure browser-safe values

From repository root:

```bash
cp frontend/config.example.js frontend/config.js
```

Edit `frontend/config.js`:

```js
window.TRUTHSCOPE_CONFIG = Object.freeze({
  API_BASE_URL: "http://127.0.0.1:8000/api/v1",
  OAUTH_REDIRECT_URL: "http://127.0.0.1:5500/",
  SUPABASE_URL: "https://YOUR_PROJECT_REF.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "YOUR_PUBLIC_PUBLISHABLE_OR_ANON_KEY",
});
```

Only use Supabase publishable or legacy `anon` key here. Never copy backend `SUPABASE_KEY`, a
`service_role` key, Google client secret, Gonka key, or Brave key into frontend files.

## 2. Configure Google OAuth redirects

In Supabase Dashboard:

1. Open **Authentication > URL Configuration**.
2. Set **Site URL** to `http://127.0.0.1:5500/` for local development.
3. Add `http://127.0.0.1:5500/` to **Redirect URLs**.
4. Open **Authentication > Providers > Google**, enable provider, and add Google client ID/secret.

In Google Auth Platform, create Web application credentials and add:

- Authorized JavaScript origin: `http://127.0.0.1:5500`
- Authorized redirect URI: `https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback`

Google returns to Supabase callback first. Supabase then returns to `OAUTH_REDIRECT_URL`.

If browser ends at plain `localhost` with `ERR_CONNECTION_REFUSED`, requested frontend redirect was
not in Supabase allow-list, so Supabase used its Site URL fallback. Make Site URL, Redirect URLs,
`OAUTH_REDIRECT_URL`, and actual frontend address agree exactly, including scheme and port.

## 3. Run

Start backend in terminal one:

```bash
cd backend
uv run uvicorn app.main:app --reload
```

Start frontend in terminal two:

```bash
cd frontend
python3 -m http.server 5500 --bind 127.0.0.1
```

Open <http://127.0.0.1:5500/>. Do not open `index.html` through a `file://` URL; OAuth needs a web
origin.

Backend `.env` must allow frontend origin:

```dotenv
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
```

## Behavior

- Verify and History controls appear only after authentication.
- Google OAuth session supplies Bearer token required by backend.
- Verification results render backend claims, scores, model summaries, evidence, request IDs,
  disagreements, warnings, limitations, and failures.
- While synchronous verification runs, an expandable activity panel shows elapsed time and clearly
  labelled estimated stages. After response arrives, it replaces estimates with confirmed Gonka
  inference records, served models, latencies, request IDs, retrieval count, and failures.
- History paginates through every authenticated user-owned `verification_runs` row under Supabase
  RLS, including legacy rows without external verification IDs. Selecting a current row fetches
  canonical full result from backend ownership-protected endpoint; legacy rows use stored
  `raw_result` when available.
- Theme toggle persists dark/light preference locally.
