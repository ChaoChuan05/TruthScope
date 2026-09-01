# TruthScope

TruthScope is an evidence-first verification prototype for Malaysian public-interest claims. Its
FastAPI backend retrieves public evidence, runs distinct Gonka-hosted models, audits consensus for
bias indicators, and returns traceable sources and deterministic scores.

Truth Score measures support from collected evidence. It is not a guarantee of objective truth or
political neutrality.

## Repository

```text
backend/                    FastAPI, LangGraph workflow, integrations, and tests
backend/docs/setup.md       Teammate setup guide for Python, uv, pip, and Docker
backend/docs/api.md         HTTP contract and examples
backend/docs/architecture.md Verification workflow and trust boundaries
docs/System Design.drawio   Editable system-design diagrams
```

## Quick start

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Windows PowerShell uses `py -3.13`, `.\.venv\Scripts\Activate.ps1`, and
`Copy-Item .env.example .env` instead. Add Gonka and Brave Search keys to `backend/.env`; never
commit that file.

Full setup, troubleshooting, and live-test commands: [backend setup](backend/docs/setup.md).

## Documentation

- [Backend overview](backend/README.md)
- [Setup and local development](backend/docs/setup.md)
- [API contract](backend/docs/api.md)
- [Verification architecture](backend/docs/architecture.md)

## Current boundaries

- Gonka Router performs every production AI inference.
- Brave Search is optional but required for evidence retrieval from text claims.
- Persistence currently uses process memory. Supabase credentials alone do not enable persistence;
  teammate-owned API/schema contract must be wired first.
- OAuth callbacks and production token verification are not implemented.
