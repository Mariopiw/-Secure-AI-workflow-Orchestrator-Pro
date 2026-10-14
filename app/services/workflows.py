import hashlib
import json
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.metrics import WORKFLOW_TRANSITIONS
from app.models import (
    Approval,
    Decision,
    OutboxEvent,
    Workflow,
    WorkflowEvent,
    WorkflowStatus,
)
from app.schemas import WorkflowCreate
from app.state_machine import assert_transition


def canonical_request_hash(payload: WorkflowCreate) -> str:
    canonical = json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def record_event(
    db: Session,
    workflow: Workflow,
    event_type: str,
    actor: str = "system",
    detail: dict | None = None,
) -> None:
    db.add(
        WorkflowEvent(
            workflow_id=workflow.id,
            tenant_id=workflow.tenant_id,
            event_type=event_type,
            actor=actor,
            detail=detail or {},
        )
    )


def transition(
    db: Session,
    workflow: Workflow,
    new_status: WorkflowStatus,
    *,
    actor: str = "system",
    detail: dict | None = None,
) -> None:
    assert_transition(workflow.status, new_status)
    old = workflow.status
    workflow.status = new_status
    workflow.version += 1
    WORKFLOW_TRANSITIONS.labels(from_status=old.value, to_status=new_status.value).inc()
    record_event(
        db,
        workflow,
        "status_changed",
        actor,
        {"from": old.value, "to": new_status.value, **(detail or {})},
    )


def create_or_get_workflow(
    db: Session,
    *,
    tenant_id: str,
    created_by: int,
    payload: WorkflowCreate,
    idempotency_key: str,
) -> tuple[Workflow, bool]:
    request_hash = canonical_request_hash(payload)
    existing = db.scalar(
        select(Workflow).where(
            Workflow.tenant_id == tenant_id,
            Workflow.idempotency_key == idempotency_key,
        )
    )
    if existing:
        if existing.request_hash != request_hash:
            raise ValueError("Idempotency-Key already used with a different request body")
        return existing, True

    workflow = Workflow(
        public_id=str(uuid4()),
        tenant_id=tenant_id,
        created_by=created_by,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        case_reference=payload.case_reference,
        description=payload.description,
        input_payload=payload.input_payload,
        callback_url=str(payload.callback_url) if payload.callback_url else None,
    )
    db.add(workflow)
    db.flush()
    record_event(db, workflow, "workflow_created", actor=f"user:{created_by}")
    return workflow, False


def save_approval(
    db: Session,
    *,
    workflow: Workflow,
    actor_id: int,
    decision: Decision,
    comment: str | None,
) -> Approval:
    approval = Approval(
        workflow_id=workflow.id,
        tenant_id=workflow.tenant_id,
        actor_id=actor_id,
        decision=decision,
        comment=comment,
    )
    db.add(approval)
    return approval


def create_outbox_event(db: Session, workflow: Workflow, event_type: str) -> OutboxEvent | None:
    if not workflow.callback_url:
        return None
    event = OutboxEvent(
        workflow_id=workflow.id,
        tenant_id=workflow.tenant_id,
        event_type=event_type,
        payload={
            "event_id": "pending",
            "event_type": event_type,
            "workflow_id": workflow.public_id,
            "status": workflow.status.value,
            "case_reference": workflow.case_reference,
        },
        callback_url=workflow.callback_url,
    )
    db.add(event)
    db.flush()
    event.payload = {**event.payload, "event_id": event.event_id}
    record_event(
        db,
        workflow,
        "outbox_event_created",
        detail={"event_id": event.event_id, "event_type": event_type},
    )
    return event
