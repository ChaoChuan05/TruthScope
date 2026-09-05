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
    Providers[Google / GitHub OAuth]
    Auth[Supabase Auth]
    Database[(Supabase Postgres)]
    API[FastAPI backend]
    Graph[LangGraph verification workflow]
    Gonka[Gonka Router]
    Brave[Brave Search API]
    Web[Public web pages]

    User --> Browser
    Browser --> Providers
    Providers --> Auth
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
| Static frontend | OAuth, job submission/polling, estimated progress, results, history |
| FastAPI | HTTP validation, authentication dependency, CORS, service lifecycle, public errors |
| VerificationService | IDs, initial state, graph execution, persistence |
| VerificationJobService | Process-local job ownership, background execution, polling snapshots |
| LangGraph | Typed stages, routing, partial-state accumulation, bounded neutrality retry |
| Gonka adapter | Anthropic-compatible Messages API, task policies, request metadata |
| Retrieval adapters | Brave candidate/news search, public-page fetching, evidence conversion |
| Scoring service | Pure evidence and confidence calculation |
| Supabase Auth | Google/GitHub sessions and backend token validation |
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
  i18n.js              English, Malay, and Chinese UI dictionaries
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
    participant Provider as Google or GitHub
    participant SA as Supabase Auth
    participant API as FastAPI
    participant DB as Supabase

    User->>UI: Select Google or GitHub
    UI->>SA: signInWithOAuth(provider, redirectTo)
    SA->>Provider: OAuth authorization
    Provider-->>SA: Provider callback
    SA-->>UI: Redirect with Supabase session
    UI->>SA: Read or refresh session
    UI->>UI: Require current Terms acceptance
    User->>UI: Scroll, confirm, and accept or sign out
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
Terms acceptance is versioned per user in browser local storage. It gates frontend features but is
not a cross-device, server-enforced compliance record.

Default application requires both <code>SUPABASE_URL</code> and <code>SUPABASE_KEY</code> to create
Supabase Auth client. Without them, health and automated fake-boundary tests work, but protected
HTTP routes cannot authenticate.

## 6. Verification workflow

The recommended browser path creates an authenticated in-memory job, then polls it. The background
task runs the same service and graph after the initiating HTTP request returns. The legacy
<code>POST /verifications</code> remains synchronous for scripts and compatibility.

~~~mermaid
flowchart TD
    Start([Background job or synchronous POST])
    Prepare[Input preparation]
    IsURL{URL input?}
    Fetch[Resolve and fetch public page]
    FetchOK{Fetch succeeded?}
    Extract[Claim extraction]
    Claims{Claims available?}
    Plan[Direct query and retrieval]
    Normalize[Evidence normalization]
    Evidence{Evidence available?}
    Context[Deterministic context flags]
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

Default <code>GONKA_REDUCED_CALLS=true</code> uses one deterministic direct query per claim and
deterministic missing-date context flags. A normal successful run therefore makes five Gonka tasks:
claim extraction, verifier A, verifier B, consensus judge, and bias audit. Setting it to
<code>false</code> restores model-based evidence planning and context analysis for seven normal
tasks. Provider retries, schema repair, and a flagged-audit correction can add bounded attempts.

### Stage contracts

| Stage | Input | Output | Failure behavior |
|---|---|---|---|
| Input preparation | Text or URL | Analysis text/document | Failed URL produces failed result |
| Claim extraction | Untrusted text | Up to 10 uniquely identified claims | No claim produces failed result |
| Evidence planning | Claims | One direct query per claim by default | Retain valid user URL evidence |
| Retrieval | Candidate URLs | Fetched evidence | Never use search snippets |
| Normalization | Evidence | Safe, linked, globally bounded evidence | Remove invalid/excess records |
| Context analysis | Claims/evidence | Deterministic context flags by default | Continue with verifier review |
| Verifier A/B | Same evidence | Exactly one claim-linked analysis per claim | One schema repair; preserve successful peer |
| Consensus judge | Valid analyses | Comparison and rationale | No hidden judge fallback |
| Bias audit | Judge/evidence | Semantically consistent audit status | One schema repair; unavailable never means passed |
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

For text input, claim extraction and query construction can run without Brave key, but null retrieval produces
no evidence and final status becomes <code>inconclusive</code>. Brave Search is required for current
live text-to-web evidence path.

## 7. Graph state and validation

### Output language

<code>VerificationRequest.outputLanguage</code> flows through service state to every Gonka node.
Supported values: <code>en</code>, <code>ms</code>, and <code>zh-CN</code>; default: English. Each node
appends shared <code>outputLanguage.md</code> contract to task prompt and includes language code in
model payload. Existing inference calls handle output language: no translation API, extra model
call, or database migration.

Only user-facing generated prose changes language. JSON keys, enum values, model/request IDs,
evidence IDs, URLs, original claims, direct quotations, evidence excerpts, names, dates, numbers,
and units remain stable. <code>VerificationResult.outputLanguage</code> records report language in
existing raw result document. Older stored results parse as English.

Frontend translates static labels locally from <code>frontend/i18n.js</code> and stores selection in
<code>localStorage</code>. Selector updates UI immediately. New verification is required to generate
report prose in another language, ensuring consensus and bias audit inspect same language user sees.
Versioned Terms content lives in <code>frontend/terms.js</code> and uses the same English, Bahasa
Melayu, and Simplified Chinese selection.

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
Unknown claim IDs or evidence IDs invalidate relevant model stage. Verifiers must return exactly one
analysis per claim, and every cited evidence ID must be linked to that claim. Duplicate claim IDs,
duplicate evidence assessments, and inconsistent bias-audit states are rejected. Model
<code>&lt;think&gt;</code> content and optional JSON fences are removed before validation; hidden
reasoning is not exposed.

Verifier and bias-audit requests prefer the Gonka structured-output tool. Pydantic definitions are
inlined and annotation-only schema fields are removed before transmission for adapter
compatibility. If Gonka rejects a tool request with HTTP 400, the client makes one plain-JSON
compatibility attempt; strict Pydantic and semantic validation still applies. Invalid JSON, schema
violations, semantic violations, missing/ambiguous tool output, and <code>max_tokens</code>
truncation receive at most one targeted repair. Both successful inference receipts remain
traceable. Repair diagnostics contain fixed categories and sanitized paths, never raw model output.
A truncation repair raises the output cap to 4,096 tokens.

## 8. Model architecture

All production AI inference goes through Gonka Router
<code>POST /v1/messages</code>. No direct provider SDK or local fallback model decides results.

Default roles:

| Role | Default model |
|---|---|
| Claim extraction; optional full-mode planning/context | <code>MiniMaxAI/MiniMax-M2.7</code> |
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
- Gonka fallback metadata and stop reason when returned.

Raw <code>outputText</code> remains internal and is excluded from API serialization.

### Provider policies

| Task group | Request timeout | Retries after first attempt | Total stage deadline |
|---|---:|---:|---:|
| Orchestration | 30 seconds | 2 | — |
| Verifiers | 120 seconds | 1 | 180 seconds each |
| Judge | 75 seconds | 1 | — |
| Bias audit | 60 seconds | 1 | 120 seconds |

Transient statuses are 408, 409, 425, 429, 500, 502, 503, and 504. Other transient network failures
use bounded exponential delay up to four seconds. HTTP 429 uses <code>Retry-After</code> when valid,
capped at 60 seconds, or 30 seconds by default. A structured-output HTTP 400 is handled separately
with one tool-free compatibility attempt and does not consume the transient retry budget. Context
analysis uses bounded excerpts and a 1,024-token output cap; failure remains non-blocking.

Verifier and bias-audit stage deadlines include transport retries and the optional schema repair,
preventing the two retry mechanisms from multiplying without a bound. Recoverable attempts log at
INFO; exhausted attempts log at WARNING with application request ID, provider receipt when
available, task, model, timeout, and retry decision.

## 9. Evidence retrieval architecture

Brave integration has two separate trust steps:

1. search query returns candidate URLs;
2. backend independently fetches original public pages.

Search snippets never become evidence. Reduced mode builds one query per claim before network
I/O. Search calls run concurrently. Candidate URLs are selected round-robin across claims;
unclaimed quota and failed fetches are backfilled. Candidate fetches use concurrency limit five and
are deduplicated by URL-derived evidence ID.

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
Normalization applies adapter-independent default limits of 6 records per claim and 8 records
total. The global total includes user-provided URL evidence.

Full evidence remains in graph and API state. Model payloads cap each excerpt:

- optional full-mode context and bias audit: 1,500 characters; and
- verifiers and judge: 2,500 characters.

Truncation is disclosed in model-input limitations.

### Current topic suggestions

Topic suggestions use a separate Brave News Search adapter; they never enter the verification
evidence pack automatically. The authenticated <code>GET /api/v1/trending-topics</code> route makes
one bounded search for recent Malaysian news and turns the first three unique headlines into
optional claim-input suggestions. They are unverified starting points, not evidence or a measured
popularity ranking.

An in-process 15-minute cache and an async lock make concurrent callers share one Brave request.
Provider failures return safe examples cached for five minutes. The frontend then stores the
response in per-user <code>sessionStorage</code>, avoiding another endpoint call for that user in the
same browser-tab session. No topic data or Brave credential is written to Supabase or browser
configuration.

## 10. Deterministic scoring

Formula version: <code>truthscope-evidence-v2</code>.

Each evidence quality weight is:

~~~text
quality = (provenance + directness + date relevance
           + context completeness + corroboration) / 25
~~~

Each directional stance maps into <code>[-1, 1]</code>. Supports is positive, contradicts is
negative, and neutral/unclear is zero. Valid verifier evidence assessments take precedence over
initial neutral retrieval stance.

Scoring first calculates support, quality, consistency, and evidence sufficiency independently for
each claim. Shared evidence assessments are keyed by both claim ID and evidence ID. Claim-level
values are then averaged with equal claim weight, so a claim with many sources cannot drown out an
unresolved or contradicted claim.

~~~text
claim support = sum(quality × claim-specific signed stance) / sum(directional quality)
claim Truth Score = 50 + 50 × claim support
Truth Score = mean(claim Truth Scores)

claim evidence sufficiency = min(claim directional evidence count / 2, 1)
evidence sufficiency = mean(claim evidence sufficiencies)

Confidence = 100 × evidence sufficiency × (
  0.35 × mean claim evidence quality
  + 0.25 × claim coverage
  + 0.20 × mean claim consistency
  + 0.20 × within-claim cross-model agreement
)
~~~

Confidence is reduced when:

- any claim lacks two distinct served verifier models;
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

A directional verdict additionally requires two distinct served verifier models for every claim
and a passed bias audit. If either requirement is missing, the public verdict remains
<code>mixed_or_inconclusive</code>; numeric Truth Score and confidence remain diagnostic.

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
- paginates API reads in 500-row batches, then renders all loaded rows;
- fetches current full result through protected backend GET; and
- uses direct <code>raw_result</code> only for legacy rows without external verification ID.

Normalized model-inference rows use Gonka request identity, not served model name, for uniqueness.
Verifier A and B request distinct models, but provider routing can serve the same model for both;
both independently traceable analyses must remain persistable.

In-memory repository supports tests and injected development services. Data disappears after
process restart. Default protected HTTP routes still require configured Supabase Auth.

## 12. Frontend request workflow

1. Frontend obtains a Supabase session.
2. Current Terms version must be read and accepted before Verify and History controls appear.
3. User submits up to 800 characters through browser form.
4. Frontend starts <code>POST /verification-jobs</code> with Bearer token.
5. Backend returns an opaque job ID and continues work in a background task.
6. Frontend stores job ID/start time under the user ID and polls the protected job route.
7. Refresh restores elapsed tracking and polling from local storage.
8. UI displays time-based estimated stages because polling exposes job state, not node events.
9. Completed job returns <code>VerificationResult</code>; UI replaces estimates with confirmed records.
10. UI renders result and reloads History.

The process-local registry is sufficient for the one-worker hackathon deployment. It survives
browser refresh, not backend restart, and is not shared between workers. Durable production jobs
would require an external queue/store and deployment coordination.

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
backend. Local Compose and AWS EC2 direct-container commands add health checks, read-only
filesystems, bounded temporary storage, dropped Linux capabilities, and privilege-escalation
protection. Supabase remains external persistent storage; containers are disposable.

The completed hackathon deployment stores separate images in private ECR and pulls them onto one
Ubuntu EC2 instance using an ECR pull-only instance role. The backend health path is
<code>/api/v1/health</code> on port 8000; frontend health is <code>/healthz</code> on port 8080.
Backend secrets are injected from an EC2-local protected env file and frontend public configuration
is generated at container startup. See
[Deployment Part 1](deployment/deployment-part-1.md).

The hackathon public test path adds separate Cloudflare Quick Tunnel containers for the frontend
and backend. Each tunnel proxies a random HTTPS `trycloudflare.com` origin to its localhost port.
This removes the need for public EC2 inbound rules on ports 8000 and 8080, but the random origins
must be kept aligned across frontend runtime configuration, backend CORS, Supabase redirect URLs,
and Google/GitHub OAuth settings. Quick Tunnels are temporary and provide no production uptime guarantee.
See [Deployment Part 2](deployment/deployment-part-2-quick-tunnels.md).

The longer-term AWS alternative separates the images into ECS/Fargate services with HTTPS
endpoints and managed secret injection. It must keep exactly one backend task until job state is
moved to a durable shared store.

The browser creates a job through <code>POST /verification-jobs</code>, receives
<code>202 Accepted</code>, and polls <code>GET /verification-jobs/{jobId}</code>. An in-process
<code>asyncio</code> task runs the existing verification service after the submission request
returns. This survives browser refresh and HTTP disconnection, but it is not a durable queue or a
separate worker system. A backend restart loses active job state, and multiple workers cannot see
one another's jobs. The current deployment therefore uses one Uvicorn worker and one backend
container.

The synchronous <code>POST /verifications</code> endpoint remains available for scripts and can
hold one HTTP request for several minutes. A load balancer only needs an extended idle timeout when
that compatibility endpoint is exposed to long-running clients.

Sequential verifiers are default because constrained Gonka routes may time out concurrent calls.
Parallel mode can reduce latency only after account capacity testing.

Polling exposes job-level <code>queued</code>, <code>running</code>, <code>complete</code>, and
<code>failed</code> states, not live node events. The frontend therefore labels its stage timeline
as estimated. True per-node progress would require explicit graph telemetry plus polling fields,
server-sent events, or WebSocket transport.

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
