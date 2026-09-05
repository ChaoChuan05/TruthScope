# TruthScope setup and local development

This guide configures backend, frontend, Supabase, Google OAuth, automated tests, and one live
verification from a fresh clone.

Run repository commands from project root unless section says <code>cd backend</code> or
<code>cd frontend</code>.

## 1. Prerequisites

Required:

- Git
- Python 3.12, 3.13, or 3.14
- modern browser
- Supabase project for login and protected routes
- Google OAuth Web application
- Gonka Router API key for live AI calls
- Brave Search API key for live text-claim evidence retrieval

Optional:

- Docker Engine with Docker Compose v2 for the complete containerized stack

Python 3.13 is recommended and matches Docker image.

Check tools:

~~~bash
git --version
python3 --version
~~~

Windows may use <code>py -3.13</code> instead of <code>python3</code>.

## 2. Clone and enter repository

~~~bash
git clone https://github.com/ChaoChuan05/TruthScope.git
cd TruthScope
~~~

If repository already exists, start from its root. Backend <code>.env.example</code> is inside
<code>backend/</code>, not root.

## 3. Create Python environment

Choose uv or standard venv/pip. Do not mix both inside same environment.

### Option A: uv

Install uv through official installer or existing Python:

~~~bash
python3 -m pip install uv
~~~

Then:

~~~bash
cd backend
uv sync --extra dev
~~~

uv creates <code>backend/.venv</code>. Activation is optional; use <code>uv run</code> before
commands.

### Option B: venv and pip on Linux/macOS

~~~bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
~~~

Exit later with:

~~~bash
deactivate
~~~

### Option C: venv and pip on Windows PowerShell

~~~powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
~~~

If PowerShell blocks activation:

~~~powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
~~~

Dependency files:

- <code>pyproject.toml</code>: canonical project requirements;
- <code>uv.lock</code>: complete locked uv graph;
- <code>requirements.txt</code>: pip runtime ranges;
- <code>requirements-dev.txt</code>: pip runtime and development ranges.

## 4. Configure backend environment

From <code>backend/</code>:

Linux/macOS:

~~~bash
cp .env.example .env
~~~

Windows PowerShell:

~~~powershell
Copy-Item .env.example .env
~~~

Minimum useful local configuration:

~~~dotenv
GONKA_API_KEY=your_gonka_key
BRAVE_SEARCH_API_KEY=your_brave_key
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_backend_secret_key
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
~~~

Use backend-only Supabase secret or legacy <code>service_role</code> key for
<code>SUPABASE_KEY</code>. Never expose it to frontend.

### Environment reference

| Variable | Default | Purpose |
|---|---|---|
| <code>APP_ENV</code> | <code>development</code> | Runtime label |
| <code>LOG_LEVEL</code> | <code>INFO</code> | Python logging level |
| <code>CORS_ALLOWED_ORIGINS</code> | Local port 5500 origins | Exact browser origins |
| <code>GONKA_BASE_URL</code> | <code>https://api.gonkarouter.io</code> | Gonka base |
| <code>GONKA_API_KEY</code> | empty | Required for live AI |
| <code>GONKA_ORCHESTRATOR_MODEL</code> | MiniMax M2.7 | Extraction, planning, context |
| <code>GONKA_MODEL_A</code> | Kimi K2.6 | Verifier A |
| <code>GONKA_MODEL_B</code> | MiniMax M2.7 | Verifier B |
| <code>GONKA_JUDGE_MODEL</code> | DeepSeek V4 Flash | Consensus judge |
| <code>GONKA_BIAS_AUDITOR_MODEL</code> | MiniMax M2.7 | Bias auditor |
| <code>GONKA_TIMEOUT_SECONDS</code> | <code>30</code> | Orchestration timeout |
| <code>GONKA_MAX_RETRIES</code> | <code>2</code> | Orchestration retries |
| <code>GONKA_MAX_TOKENS</code> | <code>2048</code> | Maximum output tokens per call |
| <code>GONKA_PARALLEL_VERIFIERS</code> | <code>false</code> | Concurrent verifier opt-in |
| <code>GONKA_REDUCED_CALLS</code> | <code>true</code> | Use deterministic planning/context; five normal Gonka tasks |
| <code>GONKA_VERIFIER_TIMEOUT_SECONDS</code> | <code>120</code> | Verifier timeout |
| <code>GONKA_VERIFIER_MAX_RETRIES</code> | <code>1</code> | Verifier retries |
| <code>GONKA_VERIFIER_STAGE_TIMEOUT_SECONDS</code> | <code>180</code> | Total deadline per verifier, including repair/retries |
| <code>GONKA_JUDGE_TIMEOUT_SECONDS</code> | <code>75</code> | Judge timeout |
| <code>GONKA_JUDGE_MAX_RETRIES</code> | <code>1</code> | Judge retries |
| <code>GONKA_AUDIT_TIMEOUT_SECONDS</code> | <code>60</code> | Audit timeout |
| <code>GONKA_AUDIT_MAX_RETRIES</code> | <code>1</code> | Audit retries |
| <code>GONKA_AUDIT_STAGE_TIMEOUT_SECONDS</code> | <code>120</code> | Total audit deadline, including repair/retries |
| <code>MAX_EVIDENCE_QUERIES_PER_CLAIM</code> | <code>1</code> | Search-query cap per claim |
| <code>MAX_EVIDENCE_PER_CLAIM</code> | <code>6</code> | Retrieval evidence bound |
| <code>MAX_TOTAL_EVIDENCE</code> | <code>8</code> | Total evidence records per verification |
| <code>MAX_INPUT_CHARS</code> | <code>5000</code> | Declared; API schema fixes 5,000 |
| <code>BRAVE_SEARCH_BASE_URL</code> | Brave API | Search base |
| <code>BRAVE_SEARCH_API_KEY</code> | empty | Live text evidence search |
| <code>BRAVE_SEARCH_COUNTRY</code> | <code>MY</code> | Search country |
| <code>BRAVE_SEARCH_LANGUAGE</code> | <code>en</code> | Search language |
| <code>BRAVE_SEARCH_RESULTS_PER_QUERY</code> | <code>3</code> | Candidates per query |
| <code>SUPABASE_URL</code> | empty | Auth and database API |
| <code>SUPABASE_KEY</code> | empty | Backend-only Auth/RPC key |

Verifier A, verifier B, and judge model IDs must be distinct. Application startup fails when they
duplicate.

## 5. Prepare Supabase

Repository contains ordered SQL migrations under <code>supabase/migrations/</code>:

~~~text
20260902010000_create_core_tables.sql
20260902020000_create_profile_trigger.sql
20260902030000_add_rls_policies.sql
20260902040000_gonka_verification_result_schema.sql
20260902050000_save_verification_result.sql
20260902060000_get_verification_result.sql
~~~

Supabase/database owner must review and apply them in order through team's approved Supabase
migration process. They create:

- user profiles linked to <code>auth.users</code>;
- verification summary and normalized detail tables;
- owner-only Row Level Security policies for browser reads;
- profile creation trigger; and
- service-only save/read RPC functions used by backend.

Backend does not apply migrations automatically.

Get values from Supabase project settings:

- project URL for backend and frontend;
- publishable or legacy <code>anon</code> key for frontend;
- backend secret or legacy <code>service_role</code> key for backend.

## 6. Configure Google OAuth

### Supabase Dashboard

1. Open **Authentication > URL Configuration**.
2. Set local Site URL to <code>http://127.0.0.1:5500/</code>.
3. Add <code>http://127.0.0.1:5500/</code> to Redirect URLs.
4. Open **Authentication > Providers > Google**.
5. Enable Google and enter Google client ID and secret.

### Google Auth Platform

Create OAuth client of type **Web application**.

Authorized JavaScript origin:

~~~text
http://127.0.0.1:5500
~~~

Authorized redirect URI:

~~~text
https://YOUR_PROJECT_REF.supabase.co/auth/v1/callback
~~~

Google redirects to Supabase callback first. Supabase then redirects to configured frontend URL.

Use exact same scheme, hostname, port, and path. <code>localhost</code> and
<code>127.0.0.1</code> are different origins.

## 7. Configure frontend

Return to repository root, then:

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

<code>frontend/config.js</code> is ignored by Git. It still reaches every browser user, so only
public values belong there.

## 8. Run application

### Terminal one: backend with uv

~~~bash
cd backend
uv run uvicorn app.main:app --reload
~~~

With activated pip venv:

~~~bash
cd backend
uvicorn app.main:app --reload
~~~

### Terminal two: frontend

~~~bash
cd frontend
python3 -m http.server 5500 --bind 127.0.0.1
~~~

Windows may use:

~~~powershell
cd frontend
py -3.13 -m http.server 5500 --bind 127.0.0.1
~~~

Open <http://127.0.0.1:5500/>.

## 9. Check health

~~~bash
curl -sS http://127.0.0.1:8000/api/v1/health
~~~

Expected fully configured shape:

~~~json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "external"
}
~~~

Health reports configuration presence, not successful live calls.

## 10. Test through browser

1. Open frontend.
2. Sign in with Google.
3. Confirm user name and History appear.
4. Enter:

~~~text
Malaysia reported a population of 34.1 million in 2024.
~~~

5. Select **Run Verification**.
6. Watch expandable estimated progress panel.
7. Wait for final result.
8. Confirm:
   - status is complete, inconclusive, degraded, or failed;
   - evidence links open public source pages;
   - two verifier analyses appear on complete run;
   - judge and bias audit appear on complete run;
   - confirmed pipeline records show served model and request ID;
   - History contains saved result.

## 11. Test through curl

Obtain current Supabase user access token from authorized local session. Treat it as secret.

~~~bash
export TRUTHSCOPE_ACCESS_TOKEN='paste-access-token-here'

curl -sS --max-time 360 \
  -o result.json \
  -w 'HTTP %{http_code}\n' \
  -X POST http://127.0.0.1:8000/api/v1/verifications \
  -H "Authorization: Bearer $TRUTHSCOPE_ACCESS_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{
    "input": "Malaysia reported a population of 34.1 million in 2024.",
    "inputType": "text"
  }'
~~~

Inspect safe summary:

~~~bash
python3 - <<'PY'
import json

with open("result.json", encoding="utf-8") as file:
    data = json.load(file)

print("verification ID:", data["verificationId"])
print("status:", data["status"])
print("claims:", len(data["claims"]))
print("evidence:", len(data["evidence"]))
print("analyses:", len(data["agentAnalyses"]))
print("judge:", data["judgeResult"] is not None)
print("bias audit:", (data["biasAudit"] or {}).get("status"))
print("score:", data["score"])
print("errors:", data["errors"])

for record in data["inferenceRecords"]:
    print(
        record["taskName"],
        "| requested:", record["requestedModel"],
        "| served:", record["servedModel"],
        "| request ID:", record["requestId"],
        "| stop reason:", record["stopReason"],
    )
PY
~~~

HTTP 201 means result object was produced. Inspect body <code>status</code>.

## 12. Run automated checks

Tests use fake Gonka, retrieval, Auth, and persistence boundaries. Real keys are not needed.

With uv:

~~~bash
cd backend
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest
~~~

With activated venv:

~~~bash
cd backend
ruff format --check .
ruff check .
mypy app
pytest
~~~

## 13. Run with Docker

The repository includes backend and frontend images plus a two-service Compose stack:

~~~bash
cp compose.env.example compose.env
# Edit compose.env with public frontend values.
docker compose --env-file compose.env up --build -d
docker compose --env-file compose.env ps
~~~

Open <http://127.0.0.1:8080/>. Both images run as non-root users; Compose adds read-only root
filesystems and reduced Linux privileges. Complete configuration, lifecycle, security, and AWS ECS
instructions: [deployment.md](deployment.md).

## 14. Secret and Git checks

Never commit:

- <code>backend/.env</code>;
- <code>frontend/config.js</code>;
- <code>result*.json</code>;
- Supabase backend keys;
- Gonka or Brave keys;
- OAuth client secrets;
- user access tokens.

Verify ignore rules:

~~~bash
git check-ignore -v backend/.env frontend/config.js result.json
git status --short
~~~

<code>.env.example</code> and <code>config.example.js</code> should remain tracked because they
contain placeholders only.

## 15. Troubleshooting

### <code>cp: cannot stat '.env.example'</code>

Command ran from repository root. File is in backend:

~~~bash
cd backend
cp .env.example .env
~~~

### <code>SUPABASE_URL Input should be a valid URL</code>

Use current <code>.env.example</code>. Blank optional Supabase values are normalized to absent.
When enabling Supabase, provide complete <code>https://...supabase.co</code> URL.

### Health says <code>gonkaConfigured: false</code>

Add Gonka key to <code>backend/.env</code>, then restart backend.

### Health says <code>searchConfigured: false</code>

Add Brave Search key to <code>backend/.env</code>, then restart backend. Without it, text claims
normally become inconclusive because no web evidence is retrieved.

### Health says <code>persistenceBackend: memory</code>

Both <code>SUPABASE_URL</code> and <code>SUPABASE_KEY</code> are not configured. Protected routes
also cannot authenticate in default app until Supabase is configured.

### <code>401 AUTHENTICATION_REQUIRED</code>

Bearer token is missing, expired, invalid, or backend Supabase Auth is not configured. Sign in again
and verify frontend/backend use same Supabase project.

### Google redirects to unreachable <code>localhost</code>

Supabase rejected requested redirect and used Site URL fallback. Make frontend address,
<code>OAUTH_REDIRECT_URL</code>, Supabase Site URL, Supabase Redirect URLs, and Google origin agree
exactly.

### Browser reports CORS error

Add exact frontend origin to backend <code>CORS_ALLOWED_ORIGINS</code> and restart backend. Do not
include path or trailing slash.

### <code>422 Unprocessable Content</code>

Send raw text or URL inside valid JSON. Do not send Markdown link such as
<code>[https://example.com](https://example.com)</code>.

### <code>status: degraded</code> with <code>VERIFIER_FAILED</code>

Inspect backend logs and response <code>errors</code>. Gonka model may be unavailable, timed out, or
returned invalid structured data. Verifier and bias-audit stages prefer schema-constrained tool
output and attempt one repair. If Gonka rejects a tool request with HTTP 400, the backend retries
once in plain-JSON mode while keeping the same strict validation. If repair also fails, backend
preserves successful inference receipts, keeps any successful peer analysis, and returns a
conservative degraded result.

### <code>result.json</code> not found

Run curl with <code>-o result.json</code>, then inspect file from same directory.

### Request appears slow

The direct curl endpoint is synchronous, while the frontend starts and polls a resumable in-memory
job. Sequential verifiers, provider timeouts, and bounded retries can still take several minutes.
Frontend progress stages are estimates until the job completes. Each verifier
is capped by <code>GONKA_VERIFIER_STAGE_TIMEOUT_SECONDS</code>; bias audit is capped by
<code>GONKA_AUDIT_STAGE_TIMEOUT_SECONDS</code>. Evidence query and record limits reduce provider
payload. Keep <code>GONKA_REDUCED_CALLS=true</code> for five normal model tasks instead of seven.
Lower deadlines carefully if demo latency matters more than slow-provider recovery.

### History misses records

Confirm migrations and RLS are applied, signed-in user owns rows, and frontend uses same Supabase
project. Frontend paginates all rows in 500-record pages.

### Reset Python environment

Deactivate environment. Remove only <code>backend/.venv</code>, then repeat one environment option.
Do not remove repository root or local secret files unless intentionally recreating them.

## 16. Next documents

- [System architecture and workflows](architecture.md)
- [Containers and AWS deployment](deployment.md)
- [HTTP API contract](api.md)
- [Backend codebase](../backend/README.md)
- [Frontend codebase](../frontend/README.md)
