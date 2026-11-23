# Secure AI Workflow Orchestrator Pro

![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/Database-PostgreSQL-4169E1?logo=postgresql&logoColor=white)
![Security](https://img.shields.io/badge/Decision-Human%20Approval-168A67)
[![CI](https://github.com/Mariopiw/-Secure-AI-workflow-Orchestrator-Pro/actions/workflows/ci.yml/badge.svg)](https://github.com/Mariopiw/-Secure-AI-workflow-Orchestrator-Pro/actions/workflows/ci.yml)

A **security-focused, event-driven workflow orchestration reference implementation** for regulated or high-impact business processes. It combines FastAPI, PostgreSQL, Celery/Redis, optional AI-assisted triage, durable state management and explicit human approval boundaries.

**Design rule:** An LLM may recommend a classification, but it **never becomes the authority for workflow authorization or durable business state**.

## Architecture

~~~mermaid
flowchart LR
  U["Submitter / Approver / Operator"] --> A["FastAPI + JWT / RBAC"]
  A --> DB[("PostgreSQL")]
  A --> Q["Redis broker"]
  Q --> W["Celery workers"]
  W --> AI["Mock or Ollama triage"]
  W --> DB
  DB --> O["Transactional outbox"]
  O --> H["HMAC-signed webhook delivery"]
  W --> R["Reconciliation / dead letters"]
~~~

## Engineering capabilities

| Domain | Implemented design |
|---|---|
| Authorization | Role-separated submission, approval and recovery controls |
| Workflow state | Explicit state machine with human approval before execution |
| Idempotency | Idempotency keys and unique effect identifiers |
| Async execution | Redis-backed Celery workers and scheduled tasks |
| AI integration | Mock-first triage with optional local Ollama |
| Reliability | Transactional outbox, bounded retry policy, reconciliation |
| Security | Signed webhooks, access tokens, password hashing |
| Observability | Logging and Prometheus-compatible metrics hooks |
| Data persistence | PostgreSQL, SQLAlchemy and Alembic migrations |

**Delivery semantics:** The system does **not** promise exactly-once distributed execution. It instead uses idempotency and reconciliation to handle retry and uncertainty. See [ARCHITECTURE.md](ARCHITECTURE.md).

## Run locally using Docker Compose

Requirements: Docker with Compose, available local ports, and enough memory for PostgreSQL, Redis and workers.

~~~bash
git clone https://github.com/Mariopiw/-Secure-AI-workflow-Orchestrator-Pro.git
cd -Secure-AI-workflow-Orchestrator-Pro

cp .env.example .env
openssl rand -hex 32

# Edit .env before starting:
# - JWT_SECRET and WEBHOOK_SIGNING_SECRET
# - Bootstrap user passwords
# - Database passwords; keep .env out of Git
# Start in deterministic mock AI mode first
docker compose up --build
~~~

API documentation: **http://localhost:8000/docs**

Example workflow: acquire a token using <code>POST /auth/token</code>; submit via <code>POST /workflows</code> with an <code>Idempotency-Key</code>; allow background validation/triage; approve using a **separate approver identity** via <code>POST /workflows/{id}/decision</code>; inspect status and reconciliation as needed.

The repository includes a smoke test in <code>scripts/smoke_test.py</code>. **Use only disposable seeded demo accounts and data**; read the script and environment first. The Docker Compose stack uses demonstration database credentials and is **not hardened for public exposure**.

## Unit tests and linting

Python **3.12+**:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev]'
pytest -q
ruff check .
~~~

Tests cover AI triage behavior, state transitions, idempotency and persistence models. Treat the live [CI page](https://github.com/Mariopiw/-Secure-AI-workflow-Orchestrator-Pro/actions) as the source for current test status; no production deployment or audit certification is claimed.

## Security boundaries

- **AI is advisory:** approval is a deterministic role-controlled transition.
- **No blind retries:** uncertain external effects move to a reconciliation state.
- **Signed delivery:** outbound webhooks use an event identifier and HMAC signature, but receivers still need verification and deduplication.
- **Secrets:** replace development bootstrap credentials and generated keys before any shared deployment.
- **Private by default:** run in a trusted lab environment. Do not expose the demo stack to the Internet.

## Documentation

[Architecture](ARCHITECTURE.md) · [Security model](SECURITY.md) · [Control mapping](CONTROL_MAPPING.md) · [Interview Q&A](INTERVIEW_QA.md) · [Tests](tests/) · [CI](.github/workflows/ci.yml)

**Scope:** Engineering/reference implementation only; not production certification, legal or regulatory compliance assurance, or a guarantee of secure operation.

No open-source license is declared in this repository.
