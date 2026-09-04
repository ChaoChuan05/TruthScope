# TruthScope system architecture

This document is source of truth for current repository architecture, runtime workflows, trust
boundaries, model roles, scoring, persistence, and failure behavior.

## 1. Architecture goals

TruthScope is designed to:

- preserve source provenance and model-request traceability;
- apply same evidence standard regardless of political identity;
- expose disagreement and uncertainty instead of hiding them;
- keep final scoring deterministic and reviewable;
- isolate external providers behind typed adapters;
- reject untrusted model output before it enters workflow state;
- retain useful partial results when one provider stage fails; and
- remain understandable and demoable as a hackathon modular monolith.

TruthScope does not guarantee objective truth, political neutrality, source correctness, or model
correctness. It helps users inspect evidence and limitations.

## 2. System context

~~~mermaid
flowchart LR
    User[Authenticated user]
    Browser[Static frontend]
    Google[Google OAuth]
    Auth[Supabase Auth]
    Database[(Supabase Postgres)]
    API[FastAPI backend]
    Graph[LangGraph verification workflow]
    Gonka[Gonka Router]
    Brave[Brave Search API]
    Web[Public web pages]

    User --> Browser
    Browser --> Google
    Google --> Auth
    Auth --> Browser
    Browser -->|Bearer token + claim| API
    Browser -->|RLS-protected profile and history summaries| Database
    API -->|validate access token| Auth
    API --> Graph
    Graph -->|all AI inference| Gonka
    Graph -->|search query| Brave
    Brave -->|candidate URLs| Graph
    Graph -->|SSRF-safe fetch| Web
    API -->|service-only RPC persistence| Database
~~~

### Runtime units

| Unit | Responsibility |
|---|---|
| Static frontend | OAuth, API calls, estimated progress, results, history |
| FastAPI | HTTP validation, authentication dependency, CORS, service lifecycle, public errors |
| VerificationService | IDs, initial state, graph execution, persistence |
| LangGraph | Typed stages, routing, partial-state accumulation, bounded neutrality retry |
| Gonka adapter | Anthropic-compatible Messages API, task policies, request metadata |
| Retrieval adapters | Brave candidate search, public-page fetching, evidence conversion |
| Scoring service | Pure evidence and confidence calculation |
| Supabase Auth | Google session and backend token validation |
| Supabase Postgres | Profiles, user-owned history, normalized records, full result document |

## 3. Repository ownership

~~~text
backend/
  app/api/             HTTP boundary
  app/services/        Application lifecycle and deterministic scoring
  app/agents/          LangGraph state, nodes, routes
  app/integrations/    Gonka, retrieval, Supabase boundaries
  app/schemas/         Pydantic domain and API contracts
  app/prompts/         Versioned production prompts
  tests/               Unit and integration tests

frontend/
  index.html           Application structure
  script.js            Auth, API, rendering, progress, history
  style.css            Responsive themes and states
  login-wave.js        Decorative login animation

supabase/migrations/   Teammate-owned database schema, RLS, triggers, and RPCs
docs/                  Architecture, API, and setup source of truth
~~~

Backend consumes Supabase through Auth and RPC/client boundaries. Database owner remains responsible
for reviewing and applying migrations.

## 4. Backend layers

~~~text
API routes
  depend on
Application services
  depend on
Agent graph + domain schemas
  depend on
Integration interfaces and deterministic services
~~~

Rules:

- Routes parse HTTP and call services; they do not contain prompts or scores.
- VerificationService coordinates graph and repository; it does not depend on FastAPI requests.
- Agent nodes receive typed state and return partial updates.
- Gonka response shapes, Brave payloads, and Supabase payloads stay inside integration modules.
- Agent nodes never persist directly.
- Deterministic scoring never calls an LLM.

## 5. Authentication workflow

~~~mermaid
sequenceDiagram
    actor User
    participant UI as Frontend
    participant Google
    participant SA as Supabase Auth
    participant API as FastAPI
    participant DB as Supabase

    User->>UI: Select Continue with Google
    UI->>SA: signInWithOAuth(google, redirectTo)
    SA->>Google: OAuth authorization
    Google-->>SA: Provider callback
    SA-->>UI: Redirect with Supabase session
    UI->>SA: Read or refresh session
    UI->>API: Request with Bearer access token
    API->>SA: GET /auth/v1/user
    SA-->>API: Trusted user ID
    API->>API: Enforce result ownership
    API-->>UI: User-owned response
    UI->>DB: Read profile/history under RLS
    DB-->>UI: Current user's rows only
~~~

Frontend visibility controls are UX, not authorization. Backend independently validates token.
Supabase RLS independently restricts browser-readable rows.

Default application requires both <code>SUPABASE_URL</code> and <code>SUPABASE_KEY</code> to create
Supabase Auth client. Without them, health and automated fake-boundary tests work, but protected
HTTP routes cannot authenticate.

## 6. Verification workflow

Backend POST is synchronous. One response returns after graph execution and persistence attempt.

~~~mermaid
flowchart TD
    Start([POST /api/v1/verifications])
    Prepare[Input preparation]
    IsURL{URL input?}
    Fetch[Resolve and fetch public page]
    FetchOK{Fetch succeeded?}
    Extract[Claim extraction]
    Claims{Claims available?}
    Plan[Evidence planning and retrieval]
    Normalize[Evidence normalization]
    Evidence{Evidence available?}
    Context[Context analysis]
    A[Verifier A]
    B[Verifier B]
    Judge[Consensus judge]
    Audit[Bias audit]
    Flagged{Audit flagged?}
    RetryJudge[Consensus correction retry]
    RetryAudit[Bias audit retry]
    Score[Deterministic scoring]
    Persist[Repository save]
    Return([VerificationResult])

    Start --> Prepare --> IsURL
    IsURL -->|No| Extract
    IsURL -->|Yes| Fetch --> FetchOK
    FetchOK -->|No| Score
    FetchOK -->|Yes| Extract
    Extract --> Claims
    Claims -->|No| Score
    Claims -->|Yes| Plan --> Normalize --> Evidence
    Evidence -->|No| Score
    Evidence -->|Yes| Context --> A --> B --> Judge --> Audit --> Flagged
    Flagged -->|No| Score
    Flagged -->|Yes, once| RetryJudge --> RetryAudit --> Score
    Score --> Persist --> Return
~~~

Default verifiers run sequentially. With
<code>GONKA_PARALLEL_VERIFIERS=true</code>, context analysis fans out to A and B, then LangGraph
joins both before judge.

### Stage contracts

| Stage | Input | Output | Failure behavior |
|---|---|---|---|
| Input preparation | Text or URL | Analysis text/document | Failed URL produces failed result |
| Claim extraction | Untrusted text | Up to 10 claims | No claim produces failed result |
| Evidence planning | Claims | Neutral queries | Retain valid user URL evidence |
| Retrieval | Candidate URLs | Fetched evidence | Never use search snippets |
| Normalization | Evidence | Safe linked evidence | Remove invalid records |
| Context analysis | Claims/evidence | Context warnings | Continue with explicit error |
| Verifier A/B | Same evidence | Independent analyses | Preserve successful peer |
| Consensus judge | Valid analyses | Comparison and rationale | No hidden judge fallback |
| Bias audit | Judge/evidence | Audit status | Unavailable never means passed |
| Correction retry | Flagged audit | Revised judgment/audit | Run at most once |
| Scoring | Structured state | Final result | No generative fallback |
| Persistence | Result and owner | Stored document | Degrade result on failure |

### URL evidence

For URL input, backend fetches page before claim extraction. Readable page text becomes extraction
input. After claims exist, fetched page becomes <code>user_provided</code> evidence. It remains
explicitly uncorroborated and does not establish claim truth.

If evidence planning or Brave retrieval fails, valid user-provided page may still allow verifier
stages to run.

### Text evidence

For text input, claim extraction and planning can run without Brave key, but null retrieval produces
no evidence and final status becomes <code>inconclusive</code>. Brave Search is required for current
live text-to-web evidence path.

## 7. Graph state and validation

<code>VerificationGraphState</code> is a TypedDict containing:

- request, verification, and user IDs;
- original and normalized input;
- optional fetched source document;
- claims and evidence queries;
- full evidence records;
- context analysis;
- verifier analyses;
- judge and bias-audit results;
- deterministic score and final result;
- inference records and Gonka request IDs;
- warnings, limitations, workflow errors, and prompt version.

Lists produced by parallel branches use additive reducers. Final scoring deduplicates warnings,
limitations, and public Gonka request IDs where needed.

Every external structured result is parsed as one JSON object and validated through Pydantic.
Unknown claim IDs or evidence IDs invalidate relevant model stage. Model <code>&lt;think&gt;</code>
content and optional JSON fences are removed before validation; hidden reasoning is not exposed.

## 8. Model architecture

All production AI inference goes through Gonka Router
<code>POST /v1/messages</code>. No direct provider SDK or local fallback model decides results.

Default roles:

| Role | Default model |
|---|---|
| Claim extraction, evidence planning, context | <code>MiniMaxAI/MiniMax-M2.7</code> |
| Verifier A | <code>moonshotai/Kimi-K2.6</code> |
| Verifier B | <code>MiniMaxAI/MiniMax-M2.7</code> |
| Consensus judge | <code>deepseek-ai/DeepSeek-V4-Flash-0731</code> |
| Bias auditor | <code>MiniMaxAI/MiniMax-M2.7</code> |

Verifier A, verifier B, and judge must use three distinct configured IDs. Startup rejects
duplicates. Orchestration and audit roles may reuse a model because they do not count as independent
verifier votes.

Each successful call records:

- task name;
- requested and served model;
- Gonka <code>X-Request-Id</code>;
- provider response ID;
- total latency;
- input/output token counts when returned; and
- Gonka fallback metadata when returned.

Raw <code>outputText</code> remains internal and is excluded from API serialization.

### Provider policies

| Task group | Timeout | Retries after first attempt |
|---|---:|---:|
| Orchestration | 30 seconds | 2 |
| Verifiers | 120 seconds | 1 |
| Judge | 75 seconds | 1 |
| Bias audit | 60 seconds | 1 |

Transient statuses are 408, 409, 425, 429, 500, 502, 503, and 504. Other transient network failures
use bounded exponential delay up to four seconds. HTTP 429 uses <code>Retry-After</code> when valid,
capped at 60 seconds, or 30 seconds by default.

## 9. Evidence retrieval architecture

Brave integration has two separate trust steps:

1. search query returns candidate URLs;
2. backend independently fetches original public pages.

Search snippets never become evidence. Search calls run concurrently. Candidate fetches use
concurrency limit five and are deduplicated by URL-derived evidence ID.

Safe document fetching:

- permits only HTTP and HTTPS;
- rejects embedded URL credentials;
- rejects localhost, <code>.local</code>, private, loopback, link-local, reserved, and metadata
  targets;
- resolves DNS before each request and rejects any non-global address;
- revalidates every redirect destination;
- follows at most three redirects;
- accepts only HTML or plain text;
- reads at most 1 MB;
- keeps at most 12,000 normalized text characters; and
- disables environment proxy inheritance.

Evidence preserves URL, title, publisher hostname when available, publication date when known,
retrieval timestamp, source type, excerpt, claim links, stance, quality dimensions, and limitations.

Full evidence remains in graph and API state. Model payloads cap each excerpt:

- context and verifiers: 4,000 characters;
- judge: 2,500 characters;
- bias audit: 1,500 characters.

Truncation is disclosed in model-input limitations.

## 10. Deterministic scoring

Formula version: <code>truthscope-evidence-v1</code>.

Each evidence quality weight is:

~~~text
quality = (provenance + directness + date relevance
           + context completeness + corroboration) / 25
~~~

Each directional stance maps into <code>[-1, 1]</code>. Supports is positive, contradicts is
negative, and neutral/unclear is zero. Valid verifier evidence assessments take precedence over
initial neutral retrieval stance.

~~~text
support value = sum(quality × signed stance) / sum(directional quality)
Truth Score = 50 + 50 × support value

evidence sufficiency = min(directional evidence count / 2, 1)

Confidence = 100 × evidence sufficiency × (
  0.35 × average evidence quality
  + 0.25 × claim coverage
  + 0.20 × cross-source consistency
  + 0.20 × cross-model agreement
)
~~~

Confidence is reduced when:

- only one verifier analysis exists;
- bias audit is absent, unavailable, or flagged; or
- context analysis detects stale or suspected truncated evidence.

Confidence below 40 forces <code>mixed_or_inconclusive</code>. Otherwise:

| Truth Score | Verdict |
|---:|---|
| 0–19 | <code>strongly_contradicted</code> |
| 20–39 | <code>mostly_contradicted</code> |
| 40–60 | <code>mixed_or_inconclusive</code> |
| 61–80 | <code>mostly_supported</code> |
| 81–100 | <code>strongly_supported</code> |

Judge output informs transparency and disagreement, but final public score and verdict come from
deterministic evidence calculation. Political identity never enters formula.

## 11. Persistence and history

When Supabase is configured:

1. VerificationService runs full graph.
2. Repository maps result into contract-neutral payload.
3. Supabase gateway calls service-only <code>save_verification_result</code> RPC.
4. RPC stores normalized child records and complete <code>raw_result</code>.
5. Backend reads full result through service-only <code>get_verification_result</code> RPC.
6. Repository restores Pydantic result and enforces owner ID.

Database maps API <code>complete</code>, <code>inconclusive</code>, and <code>degraded</code> to
summary status <code>completed</code>; exact API state remains in <code>provider_status</code> and
<code>raw_result</code>.

Frontend history:

- queries user-owned <code>verification_runs</code> summaries under RLS;
- paginates in 500-row batches until all rows are loaded;
- fetches current full result through protected backend GET; and
- uses direct <code>raw_result</code> only for legacy rows without external verification ID.

In-memory repository supports tests and injected development services. Data disappears after
process restart. Default protected HTTP routes still require configured Supabase Auth.

## 12. Frontend request workflow

1. Supabase session enables Verify and History controls.
2. User submits up to 800 characters through browser form.
3. Frontend sends input to backend with Bearer token.
4. Expandable activity panel starts elapsed timer.
5. UI displays time-based estimated stages because POST exposes no live node events.
6. Backend returns complete <code>VerificationResult</code>.
7. UI replaces estimates with confirmed inference records and failures.
8. UI renders score, claims, models, analysis, evidence, disagreement, and notices.
9. History reloads, then page scrolls to result.

If first API response is 401, frontend requests one Supabase session refresh and retries once. A
second 401 signs out local session.

## 13. Status and failure model

| API status | Meaning |
|---|---|
| <code>complete</code> | Claims, evidence, judge, and audit completed without errors |
| <code>inconclusive</code> | Claims exist but no traceable evidence remains |
| <code>degraded</code> | Useful result exists with provider or persistence failure |
| <code>failed</code> | No claim exists, including failed URL preparation or claim extraction |

Important behavior:

- One verifier failure preserves other analysis and reduces confidence.
- Both verifier failures cause consensus node to return unavailable without Gonka judge call.
- Judge failure leaves <code>judgeResult</code> absent.
- Bias audit without judge returns <code>unavailable</code> without audit call.
- Bias-audit failure never becomes implicit pass.
- Persistence failure returns computed result as degraded with explicit error.
- No-evidence path never invents a source or verdict.
- HTTP 201 means record object was produced, not every provider stage succeeded.

## 14. Security and neutrality boundaries

### Untrusted inputs

User input, URLs, DNS answers, redirects, page text, search results, OAuth tokens, model text, and
database payloads are treated as untrusted.

Controls include:

- strict Pydantic schemas with unknown fields rejected;
- URL and DNS SSRF checks;
- content, size, redirect, and timeout bounds;
- explicit CORS origin allow-list;
- backend token validation and owner enforcement;
- Supabase RLS for browser reads;
- service-only persistence RPCs;
- safe DOM text rendering and HTTP/HTTPS link checks;
- prompts that treat evidence as data, not instructions; and
- evidence-ID validation after every citing model stage.

### Political neutrality

- Party, coalition, ideology, race, religion, office, and popularity never alter source weight.
- Government sources are primary evidence, not automatic truth.
- Opposition sources establish what was stated, not automatic truth or falsehood.
- Media sources are evidence, not final arbiters.
- Equivalent evidence should receive equivalent treatment across political labels.
- Mixed, contradictory, or insufficient evidence stays visible.
- System describes audit indicators; it never claims guaranteed neutrality.

## 15. Deployment shape and constraints

Current container deployment is one rootless Nginx frontend and one non-root FastAPI/Uvicorn
backend. Local Compose adds health checks, read-only filesystems, bounded temporary storage, dropped
Linux capabilities, and privilege-escalation protection. Supabase remains external persistent
storage; containers are disposable.

The AWS deployment shape uses separate ECR images and ECS/Fargate services. The backend health path
is <code>/api/v1/health</code> on port 8000; frontend health is <code>/healthz</code> on port 8080.
Backend secrets are injected at runtime and frontend public configuration is generated at container
startup.

No queue or background worker exists. Verification latency therefore remains inside one HTTP
request and can reach several minutes when Gonka retries. A backend Application Load Balancer must
use an idle timeout longer than the maximum verification request duration.

Sequential verifiers are default because constrained Gonka routes may time out concurrent calls.
Parallel mode can reduce latency only after account capacity testing.

Future real-time progress requires a backend job resource plus polling, server-sent events, or
WebSocket transport. Current frontend intentionally labels progress estimates instead of claiming
live agent telemetry.

## 16. Architecture change checklist

When changing workflow:

- update typed state and node contract;
- review conditional routes and failure status;
- validate all cited claim/evidence IDs;
- preserve inference metadata;
- keep retry count bounded;
- check neutrality and deterministic scoring impact;
- update tests;
- update this document and [api.md](api.md).

Environment and local execution: [setup.md](setup.md). Backend code map:
[backend/README.md](../backend/README.md). Frontend code map:
[frontend/README.md](../frontend/README.md). Container and AWS deployment:
[deployment.md](deployment.md).
