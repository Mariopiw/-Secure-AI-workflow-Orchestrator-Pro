# Secure AI Workflow Orchestrator

A reference workflow platform combining an API, background processing, AI-assisted risk triage, and human authorization.

## Key features

- FastAPI, PostgreSQL, Redis, and Celery
- Idempotent workflow submission and role-separated approval
- AI risk recommendations without autonomous approval
- Transactional outbox, signed webhooks, retries, and reconciliation
- Logging, metrics, and automated tests

## Quick start

Requires Docker Compose. Configure secrets and replace demo credentials before startup.

```bash
cp .env.example .env
openssl rand -hex 32
# Edit .env and set strong secrets and passwords
docker compose up --build
```

API documentation: http://localhost:8000/docs

Use `POST /auth/token` to authenticate, `POST /workflows` to submit, and `POST /workflows/{id}/decision` with a separate approver account.

## Tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check .
```

**Scope:** Portfolio/reference implementation, not a claim of production certification. See `ARCHITECTURE.md` and `SECURITY.md` for design and limitations.
