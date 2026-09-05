# TruthScope frontend

Static browser client for Google/GitHub OAuth, authenticated verification, transparent result rendering,
and private history. No build step or frontend framework is required.

System-level data flow and verification workflow live in
[docs/architecture.md](../docs/architecture.md). This README focuses on frontend code.

## Codebase

~~~text
index.html          Active application markup and accessible result regions
style.css           Responsive dark/light themes and component states
script.js           Auth, API calls, progress, rendering, history, and interactions
i18n.js             English, Bahasa Melayu, and Simplified Chinese UI dictionaries
terms.js            Versioned English, Bahasa Melayu, and Simplified Chinese terms
terms.html          Public Terms and Conditions page
terms-page.js       Safe DOM renderer for the public terms page
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
4. <code>i18n.js</code>
5. <code>terms.js</code>
6. <code>script.js</code>

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
backend <code>SUPABASE_KEY</code>, a <code>service_role</code> key, Google/GitHub client secrets,
Gonka key, or Brave Search key in <code>frontend/</code>.

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

## Google and GitHub OAuth configuration

Supabase Dashboard:

1. Open **Authentication > URL Configuration**.
2. Set local **Site URL** to <code>http://127.0.0.1:5500/</code>.
3. Add same value to **Redirect URLs**.
4. Enable Google and GitHub under **Authentication > Providers** and configure both providers.

Google Auth Platform Web application:

- Authorized JavaScript origin:
  <code>http://127.0.0.1:5500</code>
- Authorized redirect URI:
  <code>https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback</code>

Supabase receives provider callback, creates session, then returns browser to
<code>OAUTH_REDIRECT_URL</code>. Scheme, hostname, port, and trailing path must match configured
values. Plain <code>localhost</code> and <code>127.0.0.1</code> are different origins.

GitHub OAuth App:

- Homepage URL: frontend origin, such as <code>http://127.0.0.1:5500/</code>
- Authorization callback URL:
  <code>https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback</code>

Supabase handles both provider callbacks. Provider client secrets stay in Supabase/GitHub/Google
configuration and never enter frontend files.

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
- Google and GitHub OAuth sessions persist and refresh through Supabase JS.
- Backend calls include <code>Authorization: Bearer &lt;access-token&gt;</code>.
- One automatic session refresh occurs after first backend <code>401</code>.
- Text and public URL claims share one verification form.
- Signed-in users receive three current Malaysian news suggestions from the authenticated backend
  topic endpoint. The browser caches them in per-user <code>sessionStorage</code>, so it makes one
  topic request per user per tab session; safe examples remain available when Brave is unavailable.
- Input type detection, character count, keyboard shortcut, and clear action improve claim entry.
- Expandable progress panel polls a resumable backend job and shows elapsed time plus explicitly
  estimated stages. Per-user job ID/start time persist locally, so refresh resumes tracking. Users
  may stop browser-side waiting without stopping backend processing.
- Confirmed Gonka tasks, served models, latencies, request IDs, evidence count, and failures
  replace estimates after response.
- Results prioritize limitations, verdict explanation, grouped evidence, and per-claim analysis.
  Model cards, audit summaries, and request IDs remain available in collapsed technical details.
- Evidence displays verifier-assessed stance, source type, quality summary, claim mapping, excerpts,
  and source-specific limitations.
- Source links allow only HTTP and HTTPS and open with <code>noopener noreferrer</code>.
- History reads every authenticated user-owned summary page in 500-row API batches, renders all
  loaded rows, and supports local search/verdict filtering.
- Current history records load canonical full result through backend ownership check.
- Legacy records without external verification ID fall back to stored
  <code>verification_runs.raw_result</code>.
- Dark/light preference persists in local storage.
- Header language selector switches static and generated UI labels between English, Bahasa
  Melayu, and Simplified Chinese, including while a verification job runs. Preference persists in
  local storage; a running job keeps the output language selected when it was submitted.
- New verification requests send <code>outputLanguage</code> as <code>en</code>, <code>ms</code>, or
  <code>zh-CN</code>. Existing Gonka stages generate user-facing prose in that language without a
  separate translation API. Source titles, quotations, excerpts, IDs, and enum values stay intact.
- Changing UI language does not rewrite prose inside an already saved report. Run a new
  verification in selected language to generate that report language.
- After OAuth, each user must scroll through and accept the current Terms and Conditions version
  before verification or private history becomes available. Declining signs the user out. The
  acceptance record is stored per user in browser local storage, so another browser/device asks
  again. Change `TRUTHSCOPE_TERMS.version` when updated terms require fresh acceptance.
- Footer links the standalone `terms.html` document. Both consent gate and full document support
  English, Bahasa Melayu, and Simplified Chinese.

In-flight stage names remain estimates because polling exposes job state, not per-node events.
Completed output supplies confirmed model/request metadata. Job recovery survives a page refresh,
not a backend restart, because the hackathon job registry is process-local.

## Supabase browser access

Frontend reads:

- <code>profiles</code> for display name and avatar;
- <code>verification_runs</code> for current user's history summaries; and
- <code>raw_result</code> only for legacy rows lacking backend verification ID.

Supabase Row Level Security must restrict these reads to authenticated owner. Hiding controls is
only UX; backend and RLS remain authorization boundaries.

## Manual smoke test

1. Open application and switch light/dark themes. Switch English, Bahasa Melayu, and 中文; reload
   and confirm language preference persists.
2. Sign in separately with Google and GitHub; confirm both return to app and show account name.
3. Confirm Terms cannot be accepted until their scroll area reaches the end and the acceptance
   checkbox is selected. Confirm decline signs out, acceptance unlocks the app, and the same
   user/browser is not prompted again for the current version.
4. Confirm current topic chips load after sign-in, survive a reload without another topic request,
   and populate the claim box when selected.
5. Submit <code>Malaysia reported a population of 34.1 million in 2024.</code> in each selected
   language. Confirm response <code>outputLanguage</code> and generated summaries match selection.
6. Confirm input type changes between Text claim and Public URL; test Clear and
   <code>Ctrl/Command + Enter</code>.
7. Expand/collapse the activity panel and change UI language while a request runs. Refresh the
   page and confirm polling resumes for the same job. Confirm Stop waiting aborts only the browser
   wait and explains that processing may still appear in History.
8. Confirm final result shows prominent limitations, evidence support score explanation, grouped
   evidence, claim breakdown, and model comparison.
9. Expand How this was verified and confirm model, audit, and request metadata remain available.
10. Search and filter History, confirm every saved row appears, and reopen a saved result.
11. Repeat key checks at mobile width and in both themes.
12. Sign out and confirm Verify, results, and History become unavailable.

Use <code>oauth-test.html</code> when isolating Supabase redirect or session problems.

## Related documentation

- [System architecture and workflow](../docs/architecture.md)
- [Complete setup and troubleshooting](../docs/setup.md)
- [Containers and AWS deployment](../docs/deployment.md)
- [Backend API contract](../docs/api.md)
- [Backend codebase](../backend/README.md)
