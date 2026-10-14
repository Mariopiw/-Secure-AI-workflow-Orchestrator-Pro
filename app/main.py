import logging
from uuid import uuid4

from fastapi import FastAPI, Request

from app.api import auth, health, webhooks, workflows
from app.core.logging import configure_logging, request_id_ctx

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Secure AI Workflow Orchestrator Pro",
    version="0.2.0",
    description=(
        "Production-oriented reference implementation for idempotent, auditable, "
        "human-approved AI workflows with reliable asynchronous execution."
    ),
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid4())
    token = request_id_ctx.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    finally:
        request_id_ctx.reset(token)


app.include_router(auth.router)
app.include_router(workflows.router)
app.include_router(webhooks.router)
app.include_router(health.router)
