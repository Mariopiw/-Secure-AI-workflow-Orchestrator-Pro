import json
from datetime import datetime, timezone

import httpx

from app.core.security import webhook_signature


class RetryableWebhookError(RuntimeError):
    pass


class PermanentWebhookError(RuntimeError):
    pass


def deliver_signed_webhook(callback_url: str, event_id: str, payload: dict) -> int:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    timestamp = str(int(datetime.now(timezone.utc).timestamp()))
    signature = webhook_signature(timestamp, raw)
    try:
        response = httpx.post(
            callback_url,
            content=raw,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Timestamp": timestamp,
                "X-Webhook-Signature": signature,
                "Idempotency-Key": event_id,
            },
            timeout=20.0,
        )
    except (httpx.TimeoutException, httpx.ConnectError) as exc:
        raise RetryableWebhookError(str(exc)) from exc

    if response.status_code == 429 or response.status_code >= 500:
        raise RetryableWebhookError(f"remote status {response.status_code}")
    if response.status_code >= 400:
        raise PermanentWebhookError(f"remote status {response.status_code}")
    return response.status_code
