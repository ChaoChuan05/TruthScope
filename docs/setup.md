# Backend setup and local development

This guide starts from a fresh clone. Run backend commands inside the `backend` directory because
`.env.example`, `pyproject.toml`, and application imports live there.

## Prerequisites

- Git
- Python 3.12, 3.13, or 3.14; Python 3.13 is recommended and matches the Docker image
- Gonka Router API key for live AI verification
- Brave Search API key for evidence retrieval from text claims
- Supabase project URL and backend-only secret key for OAuth token validation and persistent storage

Confirm Python:

```bash
python --version
```

On Linux/macOS, command may be `python3`. On Windows, use `py -3.13` when `python` does not select
supported version.

## Option A: uv setup

`uv` is primary project workflow because `uv.lock` pins full dependency graph.

Install `uv` using its official instructions or through existing Python:

```bash
python -m pip install uv
```

Then:

```bash
cd backend
uv sync --extra dev
```

`uv` creates `backend/.venv` automatically. Commands do not require manual activation:

```bash
uv run pytest
uv run uvicorn app.main:app --reload
```

## Option B: standard venv and pip

`requirements.txt` installs runtime dependencies. `requirements-dev.txt` installs runtime plus test,
lint, and type-check tools. Their direct ranges mirror canonical `pyproject.toml` declarations.

### Linux or macOS

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

If `venv` is unavailable on Linux, install your distribution's Python venv package first. Exit
environment later with `deactivate`.

### Windows PowerShell

```powershell
cd backend
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

If PowerShell blocks activation, allow scripts only for current terminal, then retry:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Exit environment later with `deactivate`.

## Environment configuration

Create local file from backend directory:

Linux/macOS:

```bash
cp .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set:

```dotenv
GONKA_API_KEY=your_gonka_key
BRAVE_SEARCH_API_KEY=your_brave_key
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_KEY=your_backend_secret_key
```

Never commit `.env`, paste keys into logs, or share `result.json` without reviewing it. `.gitignore`
already excludes `.env` and root `result.json`.

### Environment variables

| Variable | Required | Default / purpose |
|---|---:|---|
| `GONKA_API_KEY` | Live AI | Authenticates Gonka Router calls |
| `BRAVE_SEARCH_API_KEY` | Text search | Retrieves candidate public sources |
| `SUPABASE_URL`, `SUPABASE_KEY` | Supabase Auth/persistence | Validates Bearer tokens and enables RPC storage; omit both for memory fallback |
| `GONKA_BASE_URL` | No | `https://api.gonkarouter.io` |
| `GONKA_ORCHESTRATOR_MODEL` | No | MiniMax claim, planning, and context tasks |
| `GONKA_MODEL_A` | No | Kimi verifier |
| `GONKA_MODEL_B` | No | MiniMax verifier |
| `GONKA_JUDGE_MODEL` | No | DeepSeek consensus judge |
| `GONKA_BIAS_AUDITOR_MODEL` | No | MiniMax bias auditor |
| `GONKA_PARALLEL_VERIFIERS` | No | `false`; sequential is safer for provider capacity |
| `GONKA_VERIFIER_TIMEOUT_SECONDS` | No | `120` |
| `GONKA_VERIFIER_MAX_RETRIES` | No | `1` |
| `GONKA_JUDGE_TIMEOUT_SECONDS` | No | `75` |
| `GONKA_JUDGE_MAX_RETRIES` | No | `1` |
| `GONKA_AUDIT_TIMEOUT_SECONDS` | No | `60` |
| `GONKA_AUDIT_MAX_RETRIES` | No | `1` |
| `MAX_INPUT_CHARS` | No | `5000` |
| `MAX_EVIDENCE_PER_CLAIM` | No | `12` |

See `.env.example` for complete list and exact model IDs.

## Run backend

With activated venv:

```bash
uvicorn app.main:app --reload
```

With uv:

```bash
uv run uvicorn app.main:app --reload
```

Open:

- Health: <http://127.0.0.1:8000/api/v1/health>
- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>

Expected health response:

```json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "external"
}
```

With both Supabase values configured, the default service reports `persistenceBackend: "external"`.
If both values are omitted, the backend uses the in-memory fallback and reports
`persistenceBackend: "memory"`.

## Run automated checks

No real API keys are required; tests mock external boundaries.

With uv:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy app
uv run pytest
```

With activated venv:

```bash
ruff format --check .
ruff check .
mypy app
pytest
```

## Live verification test

Start backend in one terminal. From repository root in another terminal:

```bash
curl -sS --max-time 360 \
  -o result.json \
  -w 'HTTP %{http_code}\n' \
  -X POST http://127.0.0.1:8000/api/v1/verifications \
  -H 'Content-Type: application/json' \
  -d '{
    "input": "Malaysia reported a population of 34.1 million in 2024.",
    "inputType": "text"
  }'
```

HTTP `201` means verification record was created. It does not guarantee every external model
succeeded. Inspect workflow status:

```bash
python - <<'PY'
import json

with open("result.json", encoding="utf-8") as file:
    data = json.load(file)

print("verification ID:", data["verificationId"])
print("status:", data["status"])
print("claims:", len(data["claims"]))
print("evidence:", len(data["evidence"]))
print("analyses:", len(data["agentAnalyses"]))
print("judge:", data["judgeResult"] is not None)
print("bias audit:", (data["biasAudit"] or {}).get("status"))
print("score:", data["score"])
print("errors:", data["errors"])

for record in data["inferenceRecords"]:
    print(record["taskName"], record["requestedModel"], record["servedModel"])
PY
```

Successful full flow normally reports `completed`. `degraded` means record remains usable but one or
more external stages failed. `failed` means workflow stopped before meaningful verification output.

## Docker

Docker runs production dependencies only:

```bash
cd backend
docker build -t truthscope-backend .
docker run --rm --env-file .env -p 8000:8000 truthscope-backend
```

Do not bake `.env` into image or commit it.

## Troubleshooting

### `cp: cannot stat '.env.example'`

Command ran from repository root. Change into backend first:

```bash
cd backend
cp .env.example .env
```

### `uv: command not found`

Restart terminal after installing uv, run `python -m uv`, or use standard venv/pip path above.

### `422 Unprocessable Content`

Request JSON or `inputType` is invalid. Use raw URL/text inside JSON; do not paste Markdown links such
as `[https://example.com](https://example.com)`.

### `result.json` not found

Create it with curl `-o result.json`, then run inspection command from same directory.

### `status: degraded` with `VERIFIER_FAILED`

Check backend logs. `ReadTimeout` without HTTP status means provider did not answer before configured
timeout. App retries once and preserves partial results. A persistent failure requires provider
recovery or another account-available distinct model.

### Health reports configuration `false`

Restart backend after editing `.env`. Confirm `.env` is inside `backend`, not repository root. Do not
print secret values while diagnosing.

### Reset local environment

Deactivate environment, remove only `backend/.venv`, then repeat selected setup path. Never remove
repository root or `.env` unless intentionally recreating local credentials.
