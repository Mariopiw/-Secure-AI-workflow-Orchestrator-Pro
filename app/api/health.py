from fastapi import APIRouter, HTTPException
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis import Redis
from sqlalchemy import text
from starlette.responses import Response

from app.core.config import settings
from app.db import SessionLocal

router = APIRouter(tags=["operations"])


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
        Redis.from_url(settings.redis_url).ping()
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Dependency unavailable: {type(exc).__name__}")
    return {"status": "ready"}


@router.get("/metrics", include_in_schema=False)
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
