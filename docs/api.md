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

Workflow is synchronous and provider retries can take several minutes. HTTP `201` means result
record was created, not that every model completed. Always inspect response `status`:

- `completed`: critical workflow stages completed.
- `degraded`: partial result exists, but one or more model, retrieval, audit, or persistence stages
  failed.
- `failed`: workflow stopped before meaningful verification output.

`mixed_or_inconclusive` is valid and must not be treated as an application error.

## Read verification

`GET /api/v1/verifications/{verificationId}` returns stored result. If record has owner, caller must
present same development `X-User-Id`; production must replace header with verified OAuth identity.

Current storage is process memory. Records disappear after backend restart.

## Read evidence

`GET /api/v1/verifications/{verificationId}/evidence` returns traceable evidence pack.

Each evidence record keeps URL, title, publisher when known, retrieval time, publication date when
known, excerpts, claim links, stance, quality metrics, and limitations. Publication and retrieval
times remain separate.

## Health

`GET /api/v1/health` reports process health plus `gonkaConfigured`, `searchConfigured`, and
`persistenceBackend`. Key fields expose presence only. `persistenceBackend` remains `memory` until
teammate-owned Supabase contract is wired. Endpoint never returns credentials or provider internals.

```json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "memory"
}
```

## Development identity

Optional `X-User-Id` associates a record with a development user. Same header is then required to
read it. This is not production authentication and must be replaced with verified OAuth middleware.

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
- `403`: caller does not own requested development record.
- `404`: verification ID not found in current process memory.
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
