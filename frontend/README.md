# TruthScope frontend

Static browser client for Google OAuth, authenticated verification, transparent result rendering,
and private history. No build step or frontend framework is required.

System-level data flow and verification workflow live in
[docs/architecture.md](../docs/architecture.md). This README focuses on frontend code.

## Codebase

~~~text
index.html          Active application markup and accessible result regions
style.css           Responsive dark/light themes and component states
script.js           Auth, API calls, progress, rendering, history, and interactions
login-wave.js       Decorative login canvas with reduced-motion handling
config.example.js   Safe configuration template committed to Git
config.js           Local browser configuration ignored by Git
oauth-test.html     Standalone Supabase OAuth diagnostic page
auth.js             Legacy standalone helper; not loaded by index.html
~~~

Main application loads scripts in this order:

1. <code>config.js</code>
2. Supabase JavaScript v2 from jsDelivr
3. <code>login-wave.js</code>
4. <code>script.js</code>

Authentication logic used by <code>index.html</code> lives in <code>script.js</code>.

## Browser configuration

From repository root:

~~~bash
cp frontend/config.example.js frontend/config.js
~~~

Edit <code>frontend/config.js</code>:

~~~js
window.TRUTHSCOPE_CONFIG = Object.freeze({
  API_BASE_URL: "http://127.0.0.1:8000/api/v1",
  OAUTH_REDIRECT_URL: "http://127.0.0.1:5500/",
  SUPABASE_URL: "https://YOUR_PROJECT_REF.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "YOUR_PUBLIC_PUBLISHABLE_OR_ANON_KEY",
});
~~~

Only Supabase publishable or legacy <code>anon</code> key belongs in browser code. Never place
backend <code>SUPABASE_KEY</code>, a <code>service_role</code> key, Google client secret, Gonka key,
or Brave Search key in <code>frontend/</code>.

## Run

Start backend in terminal one:

~~~bash
cd backend
uv run uvicorn app.main:app --reload
~~~

Start frontend in terminal two:

~~~bash
cd frontend
python3 -m http.server 5500 --bind 127.0.0.1
~~~

Open <http://127.0.0.1:5500/>. Do not use a <code>file://</code> URL; OAuth needs a stable HTTP
origin.

Backend CORS must contain exact frontend origin:

~~~dotenv
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
~~~

## Google OAuth configuration

Supabase Dashboard:

1. Open **Authentication > URL Configuration**.
2. Set local **Site URL** to <code>http://127.0.0.1:5500/</code>.
3. Add same value to **Redirect URLs**.
4. Enable Google under **Authentication > Providers** and configure Google credentials.

Google Auth Platform Web application:

- Authorized JavaScript origin:
  <code>http://127.0.0.1:5500</code>
- Authorized redirect URI:
  <code>https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback</code>

Supabase receives Google callback, creates session, then returns browser to
<code>OAUTH_REDIRECT_URL</code>. Scheme, hostname, port, and trailing path must match configured
values. Plain <code>localhost</code> and <code>127.0.0.1</code> are different origins.

Complete end-to-end setup: [docs/setup.md](../docs/setup.md).

## Container runtime

The frontend image serves the same static application with rootless Nginx on port 8080. It creates
<code>config.js</code> at startup from <code>API_BASE_URL</code>, <code>OAUTH_REDIRECT_URL</code>,
<code>SUPABASE_URL</code>, and <code>SUPABASE_PUBLISHABLE_KEY</code>. This keeps one image reusable
across local and AWS environments. All four values are visible to browser users and must never be
secrets.

Use root <code>compose.yaml</code> to run the complete stack. See
[docs/deployment.md](../docs/deployment.md) for Docker and AWS ECS steps.

## Implemented behavior

- Signed-out users see login prompt; Verify and History stay hidden.
- Google OAuth session persists and refreshes through Supabase JS.
- Backend calls include <code>Authorization: Bearer &lt;access-token&gt;</code>.
- One automatic session refresh occurs after first backend <code>401</code>.
- Text and public URL claims share one verification form.
- Expandable progress panel shows elapsed time and estimated stages during synchronous request.
- Confirmed Gonka tasks, served models, latencies, request IDs, evidence count, and failures
  replace estimates after response.
- Results render claims, deterministic scores, verifier summaries, judge findings, bias status,
  evidence sources, disagreements, warnings, limitations, and provider errors.
- Source links allow only HTTP and HTTPS and open with <code>noopener noreferrer</code>.
- History reads every authenticated user-owned summary page in 500-row batches.
- Current history records load canonical full result through backend ownership check.
- Legacy records without external verification ID fall back to stored
  <code>verification_runs.raw_result</code>.
- Dark/light preference persists in local storage.

In-flight stage names are estimates because current POST endpoint returns one final synchronous
response, not server-sent progress events.

## Supabase browser access

Frontend reads:

- <code>profiles</code> for display name and avatar;
- <code>verification_runs</code> for current user's history summaries; and
- <code>raw_result</code> only for legacy rows lacking backend verification ID.

Supabase Row Level Security must restrict these reads to authenticated owner. Hiding controls is
only UX; backend and RLS remain authorization boundaries.

## Manual smoke test

1. Open application and switch light/dark themes.
2. Sign in with Google and confirm account name appears.
3. Submit <code>Malaysia reported a population of 34.1 million in 2024.</code>.
4. Expand/collapse activity panel while request runs.
5. Confirm final result shows evidence, two verifiers, judge, bias audit, and request metadata.
6. Refresh History and reopen saved result.
7. Sign out and confirm Verify, results, and History become unavailable.

Use <code>oauth-test.html</code> when isolating Supabase redirect or session problems.

## Related documentation

- [System architecture and workflow](../docs/architecture.md)
- [Complete setup and troubleshooting](../docs/setup.md)
- [Containers and AWS deployment](../docs/deployment.md)
- [Backend API contract](../docs/api.md)
- [Backend codebase](../backend/README.md)
