# TruthScope backend

Hackathon-ready FastAPI and LangGraph backend for neutral, evidence-first verification of
Malaysian public-interest claims.

Truth Score measures support from collected evidence. It is not probability of objective truth.
Confidence measures evidence quality, coverage, consistency, context, and model agreement. Neither
score guarantees political neutrality.

## Architecture

```text
FastAPI
  -> VerificationService
  -> LangGraph
       URL input preparation (SSRF-safe fetch before AI)
       claim extraction
       evidence planning and optional Brave Search retrieval
       context analysis
       two sequential Gonka verifiers (parallel opt-in)
       consensus judge
       bias audit, with at most one targeted correction
       deterministic scoring
  -> repository contract
       in-memory development adapter
       Supabase REST RPC adapter
```

Every production AI step goes through GonkaRouter. When `GONKA_API_KEY` is missing, requests fail
safely at claim extraction; no local LLM or fabricated verdict replaces Gonka. Gonka integration
uses its documented Anthropic-compatible `POST /v1/messages` API and preserves `X-Request-Id`.

Default model roles:

```text
orchestration: MiniMaxAI/MiniMax-M2.7
verifier A:   moonshotai/Kimi-K2.6
verifier B:   MiniMaxAI/MiniMax-M2.7
judge:        deepseek-ai/DeepSeek-V4-Flash-0731
bias auditor: MiniMaxAI/MiniMax-M2.7
```

Startup validation rejects duplicate verifier/judge model IDs.

Verifiers run sequentially by default because low-capacity Gonka routes may time out both calls when
started together. Set `GONKA_PARALLEL_VERIFIERS=true` only after account capacity testing confirms
concurrent calls are reliable. Sequential mode preserves independent models and partial results.
Role-specific timeout/retry defaults give slow reasoning verifiers up to 120 seconds and one bounded
retry. Judge and bias-audit stages also receive one bounded retry. HTTP 429 responses honor Gonka's
documented 30-60 second backoff window.

URL input is fetched before claim extraction, and fetched page is retained as user-provided evidence.
URL fetching enforces scheme, hostname, DNS, redirect, content-type, timeout, and size checks.
Optional Brave Search retrieves candidates for text and URL claims, then fetches original pages
through same SSRF-safe boundary. Search snippets alone never become evidence. Tests use fixture
evidence. When `SUPABASE_URL` and `SUPABASE_KEY` are configured, the backend validates Supabase
Bearer tokens and stores verification results through service-role-only REST RPC functions defined
in `../supabase/migrations`.

## Setup

Python 3.12-3.14 supported; Python 3.13 recommended. Full Windows, macOS, Linux, pip, uv,
environment-variable, Docker, and troubleshooting instructions live in
[docs/setup.md](docs/setup.md).

Fastest uv setup:

```bash
cd backend
uv sync --extra dev
cp .env.example .env
```

Standard Python setup:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
```

`pyproject.toml` is dependency source of truth. `uv.lock` pins uv installs. `requirements.txt` and
`requirements-dev.txt` mirror direct dependency ranges for conventional pip setup.

Add a GonkaRouter key to `.env`. For web evidence search, also add `BRAVE_SEARCH_API_KEY`. Current
default model IDs follow
<https://gonkarouter.io/docs>; confirm available models for your account before demo use.

Brave Search uses official `GET /res/v1/web/search` API. Create key through
<https://api-dashboard.search.brave.com/>. Keep key only in `.env`.

## Run

```bash
uv run uvicorn app.main:app --reload
```

With activated pip venv, omit `uv run`. OpenAPI UI: <http://127.0.0.1:8000/docs>.

## API

```text
POST /api/v1/verifications
GET  /api/v1/verifications/{verificationId}
GET  /api/v1/verifications/{verificationId}/evidence
GET  /api/v1/health
```

Example request:

```json
{
  "input": "A public-interest claim to verify",
  "inputType": "text"
}
```

URL request:

```json
{
  "input": "https://example.com/public-claim-page",
  "inputType": "url"
}
```

Health response includes `gonkaConfigured`, `searchConfigured`, and `persistenceBackend`. Key fields
report presence only; no credential values are returned. The default service reports
`persistenceBackend: "external"` when Supabase is configured. Without Supabase configuration it uses
the in-memory fallback, whose results disappear after process restart.

Full evidence stays in result state and API responses. Model-stage payloads use bounded excerpts:
4,000 characters for context/verifiers, 2,500 for judge, and 1,500 for bias audit. This reduces
latency and provider timeouts without changing stored evidence or deterministic scoring input.

Verification endpoints require `Authorization: Bearer <Supabase access token>`. The backend validates
the token through Supabase Auth, obtains the trusted user ID, and enforces record ownership. The
health endpoint remains public.

`POST /verifications` is synchronous and may take several minutes during provider retries. HTTP 201
means result record was created; clients must inspect response `status` for `completed`, `degraded`,
or `failed`.

## Validation

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest
```

Tests mock external Gonka, search, and persistence boundaries. Real API keys are not required.

## Documentation

- [Setup and local development](docs/setup.md)
- [HTTP API contract](docs/api.md)
- [Verification architecture](docs/architecture.md)
- [Editable system diagrams](../docs/System%20Design.drawio)

## Known limitations

- Text-claim retrieval is inconclusive when `BRAVE_SEARCH_API_KEY` is absent.
- Search source type and publication date remain unknown unless original page exposes trusted
  structured metadata; current prototype does not infer them from publisher identity.
- Live Gonka behavior needs valid credentials and account-available model IDs.
- A failed distinct verifier remains visible as degraded coverage; one model is never silently
  presented as two independent verifiers.
- Supabase persistence requires the migrations in `../supabase/migrations` and backend-only
  credentials.
- OAuth provider redirects are handled by the frontend and Supabase; the backend validates the
  resulting Supabase access token.
- When Supabase configuration is absent, in-memory fallback results disappear on process restart.
