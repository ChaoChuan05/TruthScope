# TruthScope

TruthScope is an evidence-first verification prototype for Malaysian public-interest claims. Its
FastAPI backend retrieves public evidence, runs distinct Gonka-hosted models, audits consensus for
bias indicators, and returns traceable sources and deterministic scores.

Truth Score measures support from collected evidence. It is not a guarantee of objective truth or
political neutrality.

## Repository

```text
backend/                    FastAPI, LangGraph workflow, integrations, and tests
docs/setup.md               Teammate setup guide for Python, uv, pip, and Docker
docs/api.md                 HTTP contract and examples
docs/architecture.md        Verification workflow and trust boundaries
frontend/                   Static authenticated web client
frontend/README.md          Frontend, Supabase, and Google OAuth setup
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

Full setup, troubleshooting, and live-test commands: [backend setup](docs/setup.md).

## Frontend quick start

```bash
cp frontend/config.example.js frontend/config.js
cd frontend
python3 -m http.server 5500 --bind 127.0.0.1
```

Add browser-safe Supabase URL and publishable/legacy `anon` key to `frontend/config.js`. Never put
backend `SUPABASE_KEY` or another secret in frontend code. Google OAuth also needs
`http://127.0.0.1:5500/` in Supabase Site URL and Redirect URLs. Full instructions:
[frontend setup](frontend/README.md).

## Documentation

- [Backend overview](backend/README.md)
- [Setup and local development](docs/setup.md)
- [API contract](docs/api.md)
- [Verification architecture](docs/architecture.md)
- [Frontend and Google OAuth](frontend/README.md)

## Current boundaries

- Gonka Router performs every production AI inference.
- Brave Search is optional but required for evidence retrieval from text claims.
- When `SUPABASE_URL` and `SUPABASE_KEY` are configured, the default backend stores verification
  results through Supabase RPCs. Without them, it uses process-memory persistence.
- Google OAuth is handled by the frontend and Supabase; the backend validates Supabase Bearer tokens
  and derives the trusted user ID before accessing private verification records.
