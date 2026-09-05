# TruthScope backend

FastAPI backend for authenticated, evidence-first claim verification. It owns transport validation,
LangGraph execution, Gonka inference, public-source retrieval, deterministic scoring, and
verification persistence through a Supabase boundary.

System design and agent flow live in
[docs/architecture.md](../docs/architecture.md). This README focuses on backend code.

## Responsibilities

- validate text and public URL requests;
- authenticate Supabase Bearer tokens;
- retrieve public source pages through an SSRF-safe boundary;
- run typed, schema-validated Gonka agent stages;
- preserve evidence provenance and Gonka inference metadata;
- calculate deterministic Truth Score and confidence;
- expose verification and evidence APIs;
- persist and retrieve user-owned results; and
- degrade explicitly when providers or storage fail.

Backend does not own browser OAuth UI or Supabase schema decisions. Agent nodes never write
directly to Supabase.

## Codebase

~~~text
app/
├── main.py                     Application factory, middleware, dependencies, lifecycle
├── api/
│   ├── dependencies.py         Bearer authentication and service dependencies
│   └── v1/                     Health, topics, verification, result, and evidence routes
├── agents/
│   ├── graph.py                Compiled LangGraph and conditional routing
│   ├── state.py                Typed shared graph state
│   └── nodes/                  Focused workflow stages
├── core/                       Settings, logging, exceptions, URL security
├── integrations/
│   ├── gonka/                  Gonka Messages API adapter and output mapper
│   ├── retrieval/              Brave Search and safe page fetching
│   └── supabase/               Auth, repository, RPC gateway, and mapping
├── prompts/                    Versioned production prompts and JSON contracts
├── schemas/                    Pydantic request, result, evidence, and agent models
└── services/                   Verification jobs/lifecycle, topics, source logic, scoring
tests/
├── unit/                       Pure logic, validation, security, and adapter tests
└── integration/                API, graph, Gonka, retrieval, and persistence tests
~~~

## Runtime entry points

- ASGI application: <code>app.main:app</code>
- Application factory: <code>app.main.createApp</code>
- API prefix: <code>/api/v1</code>
- Interactive OpenAPI: <http://127.0.0.1:8000/docs>

Protected routes:

~~~text
POST /api/v1/verifications
POST /api/v1/verification-jobs
GET  /api/v1/verification-jobs/{jobId}
GET  /api/v1/verifications/{verificationId}
GET  /api/v1/verifications/{verificationId}/evidence
GET  /api/v1/trending-topics
~~~

Public route:

~~~text
GET /api/v1/health
~~~

Full request, response, status, and error contracts:
[docs/api.md](../docs/api.md).

## Install and run

Python 3.12–3.14 is supported; Python 3.13 is recommended.

~~~bash
uv sync --extra dev
cp .env.example .env
uv run uvicorn app.main:app --reload
~~~

Run these commands inside <code>backend/</code>. Live protected routes require Gonka, Brave Search
for text evidence, and Supabase settings. Complete uv, venv, pip, Windows, Docker, OAuth, and
troubleshooting instructions: [docs/setup.md](../docs/setup.md).

The production container uses Python 3.13, installs only runtime dependencies, runs as a dedicated
non-root user, exposes port 8000, and includes an application health check. Run the complete
frontend/backend stack with root <code>compose.yaml</code>. Container and AWS ECS instructions:
[docs/deployment.md](../docs/deployment.md).

## Configuration sources

- <code>pyproject.toml</code>: canonical direct dependencies and tool settings
- <code>uv.lock</code>: reproducible uv dependency graph
- <code>requirements.txt</code>: pip runtime dependencies
- <code>requirements-dev.txt</code>: pip runtime and development dependencies
- <code>.env.example</code>: documented environment-variable template
- local <code>.env</code>: secrets and machine configuration; never commit

Verifier A, verifier B, and consensus judge model IDs must be distinct. Startup rejects duplicate
IDs. Other model availability depends on Gonka account routing.

The frontend uses the resumable job endpoints. A job continues after page refresh and the browser
stores only its opaque job ID, start time, and submitted language. The job registry is
process-local: run one Uvicorn worker and one backend container. A backend restart loses active job
state; multiple workers require a shared durable job store, which this hackathon deployment does
not include.

<code>GONKA_REDUCED_CALLS=true</code> is the default latency mode. It replaces generative evidence
planning and context analysis with deterministic steps, reducing the normal workflow from seven to
five Gonka tasks while retaining claim extraction, two independent verifiers, consensus judge, and
bias audit.

## Result semantics

Backend uses four workflow statuses:

- <code>complete</code>: critical stages completed;
- <code>inconclusive</code>: no traceable evidence supported meaningful scoring;
- <code>degraded</code>: useful partial output exists, but a provider, audit, or persistence stage
  failed; and
- <code>failed</code>: workflow stopped before a verifiable claim was available.

Truth Score describes collected evidence, not objective truth probability. Confidence describes
evidence quality, claim coverage, consistency, context checks, and model agreement. Final API output
contains concise summaries, never hidden chain-of-thought or raw provider output.

Clients may request <code>outputLanguage</code> as <code>en</code>, <code>ms</code>, or
<code>zh-CN</code>; English is default. Shared language contract reaches every Gonka stage, so
user-facing prose follows selection without separate translation service. Structured keys, enum
values, identifiers, URLs, and original source wording remain stable. Result stores selected
language for history replay; existing stored results without field default to English.

Scoring formula <code>truthscope-evidence-v2</code> calculates claim-specific values, then gives each
claim equal weight. A directional verdict requires two distinct served verifier models for every
claim and a passed bias audit; otherwise verdict stays <code>mixed_or_inconclusive</code>. Verifier
and bias-audit responses prefer forced structured output with one bounded repair. Tool schemas are
normalized for router compatibility; an HTTP 400 tool rejection gets one plain-JSON compatibility
attempt. Total stage deadlines prevent repair and transport retries from multiplying without limit.

## Development checks

External calls are mocked in automated tests; real keys are not required.

~~~bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest
~~~

Focused examples:

~~~bash
uv run pytest tests/unit/test_scoringService.py
uv run pytest tests/integration/test_graph.py
uv run pytest tests/integration/test_api.py
~~~

## Extension rules

- Add HTTP behavior under <code>app/api/</code>, not agent nodes.
- Keep provider shapes inside <code>app/integrations/</code>.
- Validate every model response before adding it to graph state.
- Keep scoring deterministic and outside prompts.
- Preserve unknown, mixed, and failed outcomes instead of manufacturing certainty.
- Update architecture, API, and setup docs when contracts change.

## Related documentation

- [System architecture and workflow](../docs/architecture.md)
- [Setup and local development](../docs/setup.md)
- [Containers and AWS deployment](../docs/deployment.md)
- [HTTP API contract](../docs/api.md)
- [Frontend codebase](../frontend/README.md)
