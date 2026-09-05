# TruthScope

TruthScope is an evidence-first AI claim-verification platform built for Malaysian political and
public-interest information. It gathers public evidence, compares multiple AI analyses, preserves
model disagreements, and shows users how each result was produced.

TruthScope does not ask users to blindly trust an AI-generated true-or-false label. It presents
sources, dates, evidence quality, limitations, confidence, model metadata, and Gonka Request IDs so
users can inspect the result themselves.

## Problem Statement

Political and public-interest claims spread quickly through speeches, news articles, social media,
forwarded messages, and screenshots. Verifying one claim manually can require users to:

- locate original sources among repeated reporting;
- distinguish primary evidence from commentary;
- check dates, quotation context, statistics, units, and omitted qualifiers;
- compare supporting and contradicting evidence;
- identify uncertainty or disagreement between AI models; and
- determine whether an AI answer is evidence-based or merely confident.

Political identity, party affiliation, race, religion, office, and popularity must not become
shortcuts for credibility. TruthScope evaluates evidence provenance and context while treating an
inconclusive result as valid when available evidence is insufficient or mixed.

## Project Description

TruthScope runs an auditable multi-stage verification workflow:

1. Accept a text claim or public URL.
2. Extract atomic, independently checkable claims.
3. Generate neutral evidence searches and retrieve public sources.
4. Check dates, quotations, statistics, and missing context.
5. Ask two verifier roles using different Gonka-hosted models to assess the same evidence.
6. Use a separate consensus model to preserve agreement and disagreement.
7. Audit final decision language for defined political-bias indicators.
8. Calculate deterministic Evidence Support and confidence scores.
9. Store user-owned results and display private verification history.

Main capabilities:

- Google and GitHub OAuth through Supabase Auth;
- Brave Search evidence discovery with SSRF-safe public-page retrieval;
- resumable verification jobs that continue when browser refreshes;
- transparent evidence, model comparison, limitations, and request metadata;
- responsive dark and light themes; and
- container-ready deployment on AWS EC2 with optional Cloudflare Quick Tunnels.

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript, Supabase JS |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| Agent workflow | LangGraph |
| AI inference | Gonka Router with multiple hosted models |
| Evidence search | Brave Search API and public web sources |
| Authentication | Supabase Auth with Google and GitHub OAuth |
| Persistence | Supabase Postgres and Row Level Security |
| Deployment | Docker, Nginx, AWS ECR, AWS EC2, Cloudflare Quick Tunnels |
| Testing | Pytest, Ruff, mypy, HTTPX |

## Blockchain Technology Used

TruthScope uses blockchain-backed AI infrastructure indirectly through the Gonka ecosystem. Gonka
is a decentralized AI network with its own Layer 1 coordination and settlement layer. According to
Gonka's architecture, LLM computation happens off-chain while transactions and cryptographic
artifacts used for inference validation are recorded on-chain.

TruthScope accesses this infrastructure through the Gonka Router API. The application records the
requested model, served model, latency, provider metadata, and Gonka Request ID returned for each AI
stage.

TruthScope does **not** currently:

- operate a Gonka validator, host, wallet, or chain node;
- submit blockchain transactions directly;
- deploy or call an application-owned smart contract; or
- treat a Gonka Request ID as a transaction hash or proof that a verdict is correct.

References:

- [Gonka architecture](https://gonka.ai/architecture/)
- [Gonka developer quickstart](https://gonka.ai/docs/developer/quickstart/)

## Smart Contract Addresses — Testnet

| Network | Contract | Address |
|---|---|---|
| Testnet | TruthScope application contract | Not deployed / not applicable |

No testnet smart-contract address exists in the current codebase. Blockchain functionality is
provided through the Gonka inference infrastructure rather than a TruthScope-owned EVM contract.
An address must only be added here after a real contract is deployed and verified; never insert a
placeholder address into a submission.

## Repository Structure

~~~text
backend/    FastAPI, LangGraph workflow, integrations, schemas, services, and tests
frontend/   Static multilingual web client, OAuth, results, history, and terms
supabase/   Teammate-owned SQL migrations for profiles and verification persistence
docs/       Architecture, API, setup, and deployment documentation
~~~

## Setup and Installation

### 1. Prerequisites

- Git
- Python 3.12, 3.13, or 3.14
- `uv` or `pip`
- modern web browser
- Supabase project
- Gonka Router API key
- Brave Search API key for live text-claim evidence retrieval
- Docker and Docker Compose v2, optional

### 2. Clone repository

~~~bash
git clone https://github.com/ChaoChuan05/TruthScope.git
cd TruthScope
~~~

### 3. Configure and install backend

~~~bash
cd backend
cp .env.example .env
uv sync --extra dev
~~~

If `uv` is unavailable:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
~~~

Add real values to `backend/.env`:

~~~dotenv
GONKA_API_KEY=YOUR_GONKA_KEY
BRAVE_SEARCH_API_KEY=YOUR_BRAVE_KEY
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
SUPABASE_KEY=YOUR_BACKEND_SECRET_OR_SERVICE_ROLE_KEY
CORS_ALLOWED_ORIGINS=http://127.0.0.1:5500
~~~

Never commit `.env`, provider secrets, OAuth client secrets, or private keys.

### 4. Run backend

From `backend/`:

~~~bash
uv run uvicorn app.main:app --reload
~~~

With activated virtual environment:

~~~bash
uvicorn app.main:app --reload
~~~

Verify health:

~~~bash
curl -sS http://127.0.0.1:8000/api/v1/health
~~~

### 5. Configure and run frontend

From repository root:

~~~bash
cp frontend/config.example.js frontend/config.js
~~~

Set public browser values in `frontend/config.js`:

~~~javascript
window.TRUTHSCOPE_CONFIG = Object.freeze({
  API_BASE_URL: "http://127.0.0.1:8000/api/v1",
  OAUTH_REDIRECT_URL: "http://127.0.0.1:5500/",
  SUPABASE_URL: "https://YOUR_PROJECT_REF.supabase.co",
  SUPABASE_PUBLISHABLE_KEY: "YOUR_PUBLIC_PUBLISHABLE_OR_ANON_KEY",
});
~~~

Start static frontend:

~~~bash
cd frontend
python3 -m http.server 5500 --bind 127.0.0.1
~~~

Open <http://127.0.0.1:5500/>. Configure the same frontend URL under Supabase Authentication URL
Configuration. Google and GitHub OAuth apps must use the Supabase callback shown on their provider
pages.

### 6. Run automated checks

From `backend/`:

~~~bash
uv run ruff format --check app tests
uv run ruff check app tests
uv run mypy app
uv run pytest -q
~~~

### 7. Run with Docker

From repository root:

~~~bash
cp compose.env.example compose.env
cp backend/.env.example backend/.env
docker compose --env-file compose.env up --build
~~~

Then open <http://127.0.0.1:8080/> and test backend health at
<http://127.0.0.1:8000/api/v1/health>.

Complete setup, Supabase migration order, OAuth configuration, AWS deployment, and troubleshooting
are documented under [Documentation](#documentation).

## Documentation

- [Complete local setup](docs/setup.md)
- [System architecture and workflows](docs/architecture.md)
- [HTTP API contract](docs/api.md)
- [Containers and AWS deployment](docs/deployment.md)
- [AWS EC2 deployment journal — Part 1](docs/deployment/deployment-part-1.md)
- [Public HTTPS Quick Tunnel runbook — Part 2](docs/deployment/deployment-part-2-quick-tunnels.md)
- [Backend codebase](backend/README.md)
- [Frontend codebase](frontend/README.md)

## Responsible-Use Notice

Evidence Support describes support within evidence collected for one run. It is not a probability
of objective truth. AI output may be incomplete, outdated, or wrong. Users should inspect original
sources and must not rely solely on TruthScope for critical decisions.

## Project Status

TruthScope is a hackathon prototype. It prioritizes transparent evidence, reproducible inference
metadata, bounded failure handling, and understandable architecture over production scale.
