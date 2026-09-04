# TruthScope HTTP API

Current API version: <code>v1</code>

Local base URL:

~~~text
http://127.0.0.1:8000/api/v1
~~~

Running backend publishes:

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

Generated OpenAPI is authoritative for field-level validation. This document explains usage and
semantics.

## Authentication

Every verification route requires a Supabase user access token:

~~~http
Authorization: Bearer <access-token>
~~~

Backend validates token through Supabase Auth and derives trusted user ID. Request bodies cannot
select another owner.

Only health route is public.

## Endpoints

| Method | Path | Auth | Purpose |
|---|---|---:|---|
| GET | <code>/health</code> | No | Process and integration configuration health |
| POST | <code>/verifications</code> | Yes | Run and save one verification |
| GET | <code>/verifications/{verificationId}</code> | Yes | Read owner-accessible full result |
| GET | <code>/verifications/{verificationId}/evidence</code> | Yes | Read evidence pack |

## Create verification

~~~http
POST /api/v1/verifications
Content-Type: application/json
Authorization: Bearer <access-token>
~~~

Text request:

~~~json
{
  "input": "Malaysia reported a population of 34.1 million in 2024.",
  "inputType": "text"
}
~~~

URL request:

~~~json
{
  "input": "https://example.com/public-claim-page",
  "inputType": "url"
}
~~~

<code>inputType</code> may be omitted. Backend infers <code>url</code> when input has URL scheme and
network location; otherwise it uses <code>text</code>.

Validation:

- input must contain 1–5,000 non-whitespace characters;
- request accepts no unknown fields;
- input type is <code>text</code> or <code>url</code>;
- URL type accepts only HTTP or HTTPS;
- URL cannot include username or password;
- obvious local, private, loopback, link-local, reserved, and metadata targets are rejected;
- DNS and redirects are checked again during fetching.

Frontend currently limits interactive input to 800 characters, while backend contract permits
5,000.

### Synchronous behavior

Endpoint runs complete LangGraph workflow and persistence attempt before returning. Provider retries
can take several minutes. No polling resource, server-sent event, or WebSocket progress stream
exists.

Frontend progress must be labelled estimated until final response arrives. Final
<code>inferenceRecords</code> provide confirmed task, model, latency, and request metadata.

### Response

Successful HTTP transport returns <code>201 Created</code> with <code>VerificationResult</code>,
including when workflow status is inconclusive, degraded, or failed.

Abbreviated example:

~~~json
{
  "verificationId": "uuid",
  "requestId": "uuid",
  "originalInput": "Malaysia reported a population of 34.1 million in 2024.",
  "inputType": "text",
  "normalizedText": "Malaysia's population was estimated at 34.1 million in 2024.",
  "claims": [],
  "evidence": [],
  "agentAnalyses": [],
  "judgeResult": null,
  "biasAudit": null,
  "score": null,
  "verdict": "mixed_or_inconclusive",
  "modelDisagreement": false,
  "inferenceRecords": [],
  "gonkaRequestIds": [],
  "warnings": [],
  "limitations": [],
  "errors": [],
  "promptVersion": "truthscope-prompts-v2",
  "status": "inconclusive",
  "createdAt": "2026-09-04T08:00:00Z",
  "completedAt": "2026-09-04T08:01:00Z"
}
~~~

Actual populated output exposes complete structured records.

### Workflow status

| Status | Meaning |
|---|---|
| <code>complete</code> | Claims, evidence, judge, and audit completed without errors |
| <code>inconclusive</code> | Claims exist, but no traceable evidence remains |
| <code>degraded</code> | Partial result exists, but provider, judge, audit, or persistence failed |
| <code>failed</code> | Workflow stopped before a verifiable claim was available |

Always inspect <code>status</code>; HTTP 201 alone does not mean every external stage succeeded.

### Verdict

Possible verdicts:

- <code>strongly_contradicted</code>
- <code>mostly_contradicted</code>
- <code>mixed_or_inconclusive</code>
- <code>mostly_supported</code>
- <code>strongly_supported</code>

<code>mixed_or_inconclusive</code> is valid and is not an application error.

### Core response fields

| Field | Meaning |
|---|---|
| <code>claims</code> | Atomic typed claims with original/normalized text and qualifiers |
| <code>evidence</code> | Source provenance, excerpts, claim links, stance, quality, limitations |
| <code>agentAnalyses</code> | Validated independent verifier outputs |
| <code>judgeResult</code> | Agreements, disagreements, relied evidence, and concise rationale |
| <code>biasAudit</code> | <code>passed</code>, <code>flagged</code>, or <code>unavailable</code> |
| <code>score</code> | Deterministic Truth Score, confidence, coverage, agreement, formula version |
| <code>verdict</code> | Deterministic final verdict |
| <code>modelDisagreement</code> | Material judge disagreement or low model agreement |
| <code>inferenceRecords</code> | Task, models, latency, usage, safe provider metadata |
| <code>gonkaRequestIds</code> | Deduplicated Gonka request receipt IDs |
| <code>warnings</code> | Non-fatal caveats |
| <code>limitations</code> | Interpretation boundaries |
| <code>errors</code> | Structured workflow-stage failures |

Excluded public fields:

- internal owner user ID;
- raw Gonka output text;
- credentials;
- stack traces;
- hidden chain-of-thought.

### Evidence shape

Each evidence record includes:

~~~json
{
  "evidenceId": "url-stable-id",
  "source": {
    "url": "https://public.example/source",
    "title": "Source title",
    "publisher": "public.example",
    "publicationDate": null,
    "retrievalTimestamp": "2026-09-04T08:00:00Z",
    "sourceType": "unknown"
  },
  "excerpt": "Retrieved source text",
  "claimIds": ["claim-1"],
  "stance": "unclear",
  "stanceStrength": 0,
  "quality": {
    "provenance": 2,
    "directness": 2,
    "dateRelevance": 1,
    "contextCompleteness": 2,
    "corroboration": 0
  },
  "limitations": ["Source limitation"]
}
~~~

Publication date and retrieval timestamp are distinct. Missing publication date remains null rather
than inferred from publisher identity.

### Inference record shape

~~~json
{
  "taskName": "verifierModelA",
  "requestedModel": "moonshotai/Kimi-K2.6",
  "servedModel": "moonshotai/Kimi-K2.6",
  "requestId": "gonka-request-id",
  "providerResponseId": "provider-response-id",
  "latencyMs": 12500,
  "usage": {
    "inputTokens": 1400,
    "outputTokens": 500
  },
  "fallback": null
}
~~~

Request ID may be null when provider omits header. Served model may differ when Gonka reports a
fallback.

### Workflow error shape

~~~json
{
  "code": "VERIFIER_FAILED",
  "stage": "verifierModelA",
  "message": "verifierModelA did not return a valid analysis.",
  "retryable": true
}
~~~

Provider failures normally appear here instead of leaking provider HTTP response.

## Read verification

~~~http
GET /api/v1/verifications/{verificationId}
Authorization: Bearer <access-token>
~~~

Returns <code>200 OK</code> with full <code>VerificationResult</code>.

- Unknown ID returns 404.
- Existing record owned by another user returns 403.
- Unavailable Supabase RPC returns 503.
- In-memory repository records disappear after backend restart.

## Read evidence

~~~http
GET /api/v1/verifications/{verificationId}/evidence
Authorization: Bearer <access-token>
~~~

Returns:

~~~json
{
  "verificationId": "uuid",
  "evidence": []
}
~~~

Ownership and persistence errors match full-result endpoint.

## Health

~~~http
GET /api/v1/health
~~~

Example:

~~~json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "external"
}
~~~

Configuration booleans report presence only. No key value is exposed.

<code>persistenceBackend</code>:

- <code>external</code>: Supabase repository is active;
- <code>memory</code>: process-memory repository is active.

Health <code>ok</code> means FastAPI process responds. It does not test a live Gonka call, Brave
query, Supabase Auth request, or database write.

## Public HTTP errors

~~~json
{
  "error": {
    "code": "AUTHENTICATION_REQUIRED",
    "message": "A valid Supabase access token is required.",
    "requestId": null,
    "retryable": false
  }
}
~~~

| HTTP | Typical meaning |
|---:|---|
| 201 | Verification result produced; inspect body status |
| 200 | Health, full result, or evidence returned |
| 401 | Bearer token missing, invalid, expired, or Supabase Auth unavailable |
| 403 | Authenticated user does not own record |
| 404 | Verification ID not found |
| 422 | Schema, size, input type, or URL validation failed |
| 503 | External persistence unavailable during read |

## CORS

Browser origin must appear exactly in <code>CORS_ALLOWED_ORIGINS</code>. Default:

~~~dotenv
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5500,http://localhost:5500
~~~

Origins cannot contain paths, credentials, queries, fragments, or wildcards. Allowed methods are
GET, POST, and OPTIONS. Bearer authorization is sent as header; CORS credentials mode is disabled.

## curl example

~~~bash
export TRUTHSCOPE_ACCESS_TOKEN='your-supabase-user-access-token'

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

Access tokens are secrets. Do not commit them, paste them into shared logs, or keep them in shell
history longer than needed.

Architecture and score details: [architecture.md](architecture.md). Environment and live testing:
[setup.md](setup.md).
