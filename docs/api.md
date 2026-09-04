# TruthScope API contract

Base URL during local development: `http://127.0.0.1:8000/api/v1`.

Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs` while backend runs.

## Create verification

`POST /api/v1/verifications` runs synchronous hackathon flow and returns `201` with full
`VerificationResult`. Response exposes atomic claims, source metadata, supporting and contradicting
evidence assessments, independent model summaries, disagreement, bias status, Gonka request IDs,
scores, warnings, limitations, and timestamps.

Text request:

```json
{
  "input": "Malaysia reported a population of 34.1 million in 2024.",
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

`inputType` may be omitted; backend infers URL versus text. URL input accepts only public HTTP/HTTPS
targets. Loopback, private-network, link-local, and unsafe redirect destinations are rejected.

Workflow is synchronous and provider retries can take several minutes. Clients receive no live
node events from this endpoint, so any in-flight stage display must be labelled estimated. Final
`inferenceRecords` provide confirmed task, model, latency, and request metadata. HTTP `201` means
result record was created, not that every model completed. Always inspect response `status`:

- `complete`: critical workflow stages completed.
- `inconclusive`: the workflow finished, but available evidence was insufficient for a conclusion.
- `degraded`: partial result exists, but one or more model, retrieval, audit, or persistence stages
  failed.
- `failed`: workflow stopped before meaningful verification output.

`mixed_or_inconclusive` is valid and must not be treated as an application error.

## Read verification

`GET /api/v1/verifications/{verificationId}` returns the stored result. The caller must provide
`Authorization: Bearer <Supabase access token>`. The backend validates the token and only returns a
record owned by the authenticated user.

When Supabase is configured, records are stored through the Supabase RPC gateway. Without Supabase
configuration, the development fallback uses process memory and records disappear after restart.

## Read evidence

`GET /api/v1/verifications/{verificationId}/evidence` returns traceable evidence pack.

Each evidence record keeps URL, title, publisher when known, retrieval time, publication date when
known, excerpts, claim links, stance, quality metrics, and limitations. Publication and retrieval
times remain separate.

## Health

`GET /api/v1/health` reports process health plus `gonkaConfigured`, `searchConfigured`, and
`persistenceBackend`. Key fields expose presence only. The default service reports `external` when
Supabase is configured and `memory` when the in-memory fallback is active. The endpoint never
returns credentials or provider internals.

```json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "external"
}
```

## Authentication

Verification endpoints require a Supabase access token:

```http
Authorization: Bearer <access-token>
```

The backend validates it through Supabase Auth and uses the verified Supabase user ID for ownership
checks. `GET /api/v1/health` remains public.

Browser requests are accepted only from explicit `CORS_ALLOWED_ORIGINS`. Default development
origins are `http://127.0.0.1:5500` and `http://localhost:5500`; wildcard origins are rejected.


## Errors

Expected public errors use:

```json
{
  "error": {
    "code": "VERIFICATION_NOT_FOUND",
    "message": "Verification was not found.",
    "requestId": null,
    "retryable": false
  }
}
```

Common HTTP responses:

- `201`: verification record created; inspect workflow `status`.
- `401`: Supabase Bearer token is missing, invalid, or expired.
- `403`: authenticated caller does not own the requested verification record.
- `404`: verification ID was not found.
- `422`: request failed schema, size, URL, or safety validation.

Provider-stage failures normally appear inside `VerificationResult.errors` rather than becoming raw
HTTP provider errors. Public responses never include API keys, stack traces, hidden chain-of-thought,
or raw provider exceptions.

## Response interpretation

- `score.truthScore`: evidence-weighted support from 0 to 100, not probability of objective truth.
- `score.confidenceScore`: quality, coverage, consistency, context, and model-agreement measure.
- `agentAnalyses`: validated outputs from distinct verifier models.
- `judgeResult`: consensus result; absent when no valid verifier input or judge failure occurs.
- `biasAudit`: political-neutrality indicator audit; `unavailable` is not equivalent to passed.
- `inferenceRecords`: safe model, request ID, latency, token usage, and fallback metadata.
- `gonkaRequestIds`: provider request receipts returned by Gonka.
- `warnings`, `limitations`, `errors`: partial-failure and uncertainty disclosures clients must show.
