import json
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session
from fastapi import Depends

from app.core.config import settings
from app.core.security import verify_webhook_signature
from app.db import get_db
from app.models import InboundWebhook

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/provider")
async def inbound_webhook(
    request: Request,
    x_webhook_timestamp: str = Header(..., alias="X-Webhook-Timestamp"),
    x_webhook_signature: str = Header(..., alias="X-Webhook-Signature"),
    x_event_id: str = Header(..., alias="X-Event-Id"),
    x_provider: str = Header("demo-provider", alias="X-Provider"),
    db: Session = Depends(get_db),
):
    raw = await request.body()
    try:
        timestamp = int(x_webhook_timestamp)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid webhook timestamp")
    now = int(datetime.now(timezone.utc).timestamp())
    if abs(now - timestamp) > settings.webhook_replay_window_seconds:
        raise HTTPException(status_code=401, detail="Webhook timestamp outside replay window")
    if not verify_webhook_signature(x_webhook_timestamp, raw, x_webhook_signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    existing = db.scalar(
        select(InboundWebhook).where(
            InboundWebhook.provider == x_provider,
            InboundWebhook.external_event_id == x_event_id,
        )
    )
    if existing:
        return {"accepted": True, "duplicate": True, "event_id": x_event_id}
    db.add(InboundWebhook(provider=x_provider, external_event_id=x_event_id, payload=payload))
    db.commit()
    return {"accepted": True, "duplicate": False, "event_id": x_event_id}


@router.post("/demo-partner")
async def demo_partner(request: Request):
    raw = await request.body()
    timestamp = request.headers.get("X-Webhook-Timestamp", "")
    signature = request.headers.get("X-Webhook-Signature", "")
    event_id = request.headers.get("Idempotency-Key", "")
    if not event_id or not verify_webhook_signature(timestamp, raw, signature):
        raise HTTPException(status_code=401, detail="Invalid signed webhook")
    return {"received": True, "event_id": event_id}
