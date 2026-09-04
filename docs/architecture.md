# Verification architecture

TruthScope is a modular FastAPI monolith. HTTP routes call `VerificationService`; service runs a
typed LangGraph workflow; infrastructure adapters isolate Gonka, retrieval, and persistence. Agent
nodes never write directly to persistence.

## Graph

```text
START
  -> inputPreparation
       URL: SSRF-safe fetch and readable-text extraction
       text: preserve submitted claim
  -> claimExtraction
  -> evidencePlanningAndRetrieval
  -> evidenceNormalization
  -> contextAnalyzer
  -> verifierModelA -> verifierModelB (sequential by default, same evidence pack)
  -> consensusJudge
  -> biasAudit
       flagged: consensusRetry -> biasAuditRetry
       otherwise: deterministicScoring
  -> END
```

Failed URL retrieval and failed extraction routes end in explicit failed results. No-evidence routes
end inconclusive. A fetched user URL is preserved even if evidence planning/search fails. One
verifier may fail while another remains visible. If all verifiers or judge fail, no verifier is
silently promoted to judge. If bias audit fails, status is `unavailable`, never bias-cleared.

Parallel verifier execution is configuration-controlled. Default sequential execution avoids
provider-capacity contention observed on Gonka while preserving distinct model outputs. Accounts
with reliable concurrent capacity may enable `GONKA_PARALLEL_VERIFIERS=true`.
Verifier calls allow 120 seconds and one retry because reasoning models can respond slowly. Judge and
bias-audit calls retain separate bounded policies, so one stage cannot consume another stage's retry
budget. HTTP 429 responses wait 30 seconds by default and honor `Retry-After` up to 60 seconds.

## Retrieval

- User URL is fetched before claim extraction; model sees readable page content, not only URL.
- Fetched page becomes `user_provided` evidence after extracted claim IDs exist.
- Brave Search is optional and used only when `BRAVE_SEARCH_API_KEY` is configured.
- Search results are candidate URLs. Original pages must pass URL/DNS/redirect checks and be fetched
  successfully before they become evidence.
- Search snippets never become evidence.
- Search-selected pages start with conservative unknown-source quality; political/publisher identity
  does not raise credibility.
- Full retrieved excerpts remain in graph/result state. Per-stage model payloads use explicit excerpt
  caps to reduce latency; truncation is disclosed inside model-input limitations.

## Trust boundaries

- User claims, URLs, retrieved pages, and model output are untrusted.
- Pydantic validates each provider output before graph state accepts it.
- Verifier, judge, context, and bias citations must match supplied evidence IDs.
- Retrieved page instructions cannot replace system prompts.
- Gonka response metadata is normalized at integration boundary.
- Agent nodes never write directly to persistence.
- Supabase Auth, REST RPC access, repository mapping, and SQL migrations remain isolated behind
  the Supabase integration boundary.

### Browser frontend

- Supabase JS receives only project URL plus publishable/legacy `anon` key.
- Google OAuth redirects through Supabase Auth. Frontend sends resulting access token as Bearer
  authorization to backend verification endpoints.
- Backend validates token independently; hiding Verify and History controls is UX, not
  authorization.
- History summaries paginate through every authenticated user-owned `verification_runs` row under
  Supabase RLS. Opening a current record uses backend ownership-protected full-result endpoint;
  legacy records fall back to stored `raw_result` when available.
- Backend, model, and source strings render as text. Source links accept only HTTP/HTTPS URLs.
- Gonka Request IDs are trace metadata, not proof of blockchain storage or immutable verdicts.

## Scoring

Formula version: `truthscope-evidence-v1`.

Each evidence stance maps to `[-1, 1]` and receives quality weight equal to mean of five rubric
dimensions: provenance, directness, date relevance, context completeness, and corroboration.

```text
support = weighted signed stance / evidence quality weight
Truth Score = 50 + 50 * support

Confidence = 100 * evidence sufficiency * (
  0.35 * average evidence quality
  + 0.25 * claim coverage
  + 0.20 * cross-source consistency
  + 0.20 * cross-model agreement
)
```

Confidence receives explicit penalties for one-verifier coverage, unavailable/flagged bias audit,
and detected stale or truncated context. Confidence below 40 forces `mixed_or_inconclusive`, so weak
evidence cannot create a strong verdict.

Political identity, party, coalition, race, religion, office, and popularity never enter formula.

## Model roles

```text
orchestration: MiniMaxAI/MiniMax-M2.7
verifier A:   moonshotai/Kimi-K2.6
verifier B:   MiniMaxAI/MiniMax-M2.7
judge:        deepseek-ai/DeepSeek-V4-Flash-0731
bias auditor: MiniMaxAI/MiniMax-M2.7
```

Verifier A, verifier B, and judge must use three distinct model IDs. Startup validation rejects
duplicates. Bias auditor may reuse orchestration model because it audits judge output rather than
serving as another independent verdict vote.

## Failure behavior

- Claim-extraction failure stops workflow with explicit `failed` status.
- Missing evidence yields inconclusive result; system never invents citations.
- One verifier failure preserves other verifier and marks coverage degraded.
- Both verifier failures prevent judge call.
- Judge failure never promotes verifier output to hidden consensus.
- Bias-audit failure produces `unavailable`, never an implicit pass.
- HTTP 429 honors provider delay between 30 and 60 seconds.
- Request timeouts and transient HTTP failures receive only configured bounded retries.
- Persistence failure preserves computed response when possible and reports explicit error.

## Persistence

When `SUPABASE_URL` and `SUPABASE_KEY` are configured, the default service uses the Supabase REST
gateway and reports `persistenceBackend: "external"`. Verification results are saved and retrieved
through service-role-only RPC functions. Bearer tokens are validated through Supabase Auth, and the
repository enforces record ownership before returning private data.

Without Supabase configuration, the backend uses the in-memory fallback and reports
`persistenceBackend: "memory"`. Tables, triggers, RLS policies, and RPC functions are versioned in
`../supabase/migrations`.

## API boundary

Routes validate transport input and call application service. They do not hold prompts, calculate
scores, or call model nodes directly. Full contract and status semantics: [api.md](api.md). Local
environment and test setup: [setup.md](setup.md).
