# TruthScope

TruthScope is an evidence-first claim-verification prototype built for Malaysian public-interest
and political information.

## Problem statement

Public claims spread through speeches, news, social media posts, forwarded messages, and
screenshots faster than most people can investigate them. Checking one claim often requires users
to:

- find original sources among repeated or copied reporting;
- distinguish direct records from commentary;
- check dates, quotation context, units, and omitted qualifiers;
- compare sources that support and contradict the claim;
- judge whether an AI answer is evidence-based or merely confident; and
- understand why models disagree.

Political claims add another risk: source identity, party affiliation, office, race, religion, or
popularity can become shortcuts for credibility. A system that produces one unexplained
“true/false” label may hide uncertainty and reproduce those shortcuts.

## Proposed solution

TruthScope helps users investigate a claim instead of asking them to trust one model. It:

1. extracts atomic, verifiable claims;
2. gathers public source pages and preserves provenance;
3. checks date, quotation, and statistical context;
4. asks two distinct Gonka-hosted verifier models to assess the same evidence;
5. uses a third distinct model to compare agreement and disagreement;
6. audits judgment language for political-bias indicators;
7. calculates deterministic evidence and confidence scores; and
8. shows sources, limitations, failures, and Gonka request metadata to the user.

Truth Score measures support from evidence collected for that run. It is not probability of
objective truth. Bias audit detects defined warning signs; it cannot guarantee political
neutrality. Inconclusive is a valid result.

## User experience

Authenticated users can submit text or a public URL, watch an expandable progress panel, inspect
the final evidence pack and model comparison, and reopen private verification history. Progress
stages are labelled estimated while the synchronous backend request is running. Confirmed model,
latency, and request metadata replace those estimates after the backend responds.

Gonka request IDs provide inference traceability. They are not blockchain transactions, proof of
immutability, or proof that a verdict is correct.

## Repository

~~~text
backend/    FastAPI application, LangGraph agents, integrations, schemas, and tests
frontend/   Static browser client, Google OAuth, result rendering, and history
supabase/   Teammate-owned SQL migrations for profiles and verification persistence
docs/       Architecture, workflow, API, and complete setup documentation
~~~

## Documentation

- [System architecture and workflows](docs/architecture.md)
- [Complete local setup](docs/setup.md)
- [Containers and AWS deployment](docs/deployment.md)
- [AWS EC2 deployment journal — Part 1](docs/deployment/deployment-part-1.md)
- [Public HTTPS Quick Tunnel runbook — Part 2](docs/deployment/deployment-part-2-quick-tunnels.md)
- [HTTP API contract](docs/api.md)
- [Backend codebase](backend/README.md)
- [Frontend codebase](frontend/README.md)

## Start here

Follow [docs/setup.md](docs/setup.md) for Python environment creation, dependencies, provider
configuration, Supabase and Google OAuth setup, automated checks, and live end-to-end testing. To
run both services with Docker or prepare AWS ECS, use [docs/deployment.md](docs/deployment.md).

## Project status

TruthScope is a hackathon prototype. It prioritizes transparent evidence, reproducible model
metadata, bounded failure handling, and understandable architecture over production scale.
