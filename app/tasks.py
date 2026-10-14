import logging
from datetime import datetime, timedelta, timezone

import httpx
from celery import shared_task
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.db import SessionLocal
from app.metrics import WEBHOOK_DELIVERIES, WORKFLOW_FAILURES
from app.models import (
    DeadLetter,
    DeliveryStatus,
    ExecutionRecord,
    OutboxEvent,
    WebhookDelivery,
    Workflow,
    WorkflowStatus,
)
from app.services.ai import RetryableAIError, review_risk
from app.services.webhooks import PermanentWebhookError, RetryableWebhookError, deliver_signed_webhook
from app.services.workflows import create_outbox_event, record_event, transition

logger = logging.getLogger(__name__)


def _locked_workflow(db, tenant_id: str, public_id: str) -> Workflow:
    workflow = db.scalar(
        select(Workflow)
        .where(Workflow.tenant_id == tenant_id, Workflow.public_id == public_id)
        .with_for_update()
    )
    if not workflow:
        raise ValueError("Workflow not found")
    return workflow


@shared_task(name="app.tasks.start_workflow", bind=True, max_retries=5)
def start_workflow(self, tenant_id: str, public_id: str):
    db = SessionLocal()
    try:
        workflow = _locked_workflow(db, tenant_id, public_id)
        if workflow.status not in {WorkflowStatus.RECEIVED, WorkflowStatus.FAILED, WorkflowStatus.AI_REVIEW}:
            return
        workflow.attempt_count += 1
        workflow.last_error = None

        if workflow.status in {WorkflowStatus.RECEIVED, WorkflowStatus.FAILED}:
            transition(db, workflow, WorkflowStatus.VALIDATING, actor="worker")
            if len(workflow.description.strip()) < 10:
                raise ValueError("Description too short")
            transition(db, workflow, WorkflowStatus.AI_REVIEW, actor="worker")
            db.commit()

        # A transient AI failure may retry while the durable state is AI_REVIEW.
        score, reason = review_risk(workflow.description)

        workflow = _locked_workflow(db, tenant_id, public_id)
        if workflow.status != WorkflowStatus.AI_REVIEW:
            return
        workflow.risk_score = score
        workflow.ai_reason = reason
        transition(
            db,
            workflow,
            WorkflowStatus.WAITING_APPROVAL,
            actor="worker",
            detail={"risk_score": score},
        )
        db.commit()
        logger.info("workflow_waiting_approval", extra={"workflow_id": public_id, "tenant_id": tenant_id, "task_id": self.request.id})
    except RetryableAIError as exc:
        db.rollback()
        countdown = min(2 ** self.request.retries, 60)
        raise self.retry(exc=exc, countdown=countdown)
    except Exception as exc:
        db.rollback()
        workflow = db.scalar(
            select(Workflow).where(Workflow.tenant_id == tenant_id, Workflow.public_id == public_id)
        )
        if workflow and workflow.status not in {WorkflowStatus.COMPLETED, WorkflowStatus.REJECTED}:
            workflow.last_error = str(exc)[:2000]
            old = workflow.status
            workflow.status = WorkflowStatus.FAILED
            workflow.version += 1
            record_event(db, workflow, "workflow_failed", "worker", {"from": old.value, "error": workflow.last_error})
            db.add(DeadLetter(tenant_id=tenant_id, kind="workflow_start", object_id=public_id, reason=workflow.last_error, payload={"task_id": self.request.id}))
            db.commit()
            WORKFLOW_FAILURES.labels(stage="start").inc()
        raise
    finally:
        db.close()


@shared_task(name="app.tasks.execute_approved_workflow", bind=True, max_retries=3)
def execute_approved_workflow(self, tenant_id: str, public_id: str):
    db = SessionLocal()
    try:
        workflow = _locked_workflow(db, tenant_id, public_id)
        if workflow.status == WorkflowStatus.COMPLETED:
            return
        if workflow.status not in {WorkflowStatus.APPROVED, WorkflowStatus.NEEDS_RECONCILIATION}:
            return
        transition(db, workflow, WorkflowStatus.EXECUTING, actor="worker")
        db.commit()

        # Demo business effect: a durable execution record with a UNIQUE workflow_id.
        # Re-delivery is safe because the side effect is idempotent.
        workflow = _locked_workflow(db, tenant_id, public_id)
        effect_key = f"workflow:{public_id}:execute:v1"
        existing = db.scalar(select(ExecutionRecord).where(ExecutionRecord.workflow_id == workflow.id))
        if not existing:
            db.add(
                ExecutionRecord(
                    workflow_id=workflow.id,
                    tenant_id=tenant_id,
                    effect_key=effect_key,
                    result={"action": "demo_regulated_action", "ok": True},
                )
            )
            try:
                db.flush()
            except IntegrityError:
                db.rollback()
                workflow = _locked_workflow(db, tenant_id, public_id)

        record_event(db, workflow, "business_action_confirmed", "worker", {"effect_key": effect_key})
        transition(db, workflow, WorkflowStatus.COMPLETED, actor="worker")
        create_outbox_event(db, workflow, "workflow.completed")
        db.commit()
        logger.info("workflow_completed", extra={"workflow_id": public_id, "tenant_id": tenant_id, "task_id": self.request.id})
    except Exception as exc:
        db.rollback()
        workflow = db.scalar(
            select(Workflow).where(Workflow.tenant_id == tenant_id, Workflow.public_id == public_id)
        )
        if workflow and workflow.status == WorkflowStatus.EXECUTING:
            # Do not blindly retry an uncertain external side effect.
            workflow.status = WorkflowStatus.NEEDS_RECONCILIATION
            workflow.last_error = str(exc)[:2000]
            workflow.version += 1
            record_event(db, workflow, "execution_uncertain", "worker", {"error": workflow.last_error})
            db.add(DeadLetter(tenant_id=tenant_id, kind="execution_reconciliation", object_id=public_id, reason=workflow.last_error, payload={"task_id": self.request.id}))
            db.commit()
            WORKFLOW_FAILURES.labels(stage="execution").inc()
        raise
    finally:
        db.close()


@shared_task(name="app.tasks.dispatch_outbox")
def dispatch_outbox():
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=60)
        events = list(
            db.scalars(
                select(OutboxEvent)
                .where(
                    OutboxEvent.delivered_at.is_(None),
                    OutboxEvent.dead_lettered_at.is_(None),
                    ((OutboxEvent.enqueued_at.is_(None)) | (OutboxEvent.enqueued_at < cutoff)),
                )
                .order_by(OutboxEvent.id)
                .limit(50)
                .with_for_update(skip_locked=True)
            ).all()
        )
        jobs = []
        now = datetime.now(timezone.utc)
        for event in events:
            event.enqueued_at = now
            jobs.append(event.id)
        db.commit()
        for event_id in jobs:
            deliver_outbox_event.delay(event_id)
        return {"enqueued": len(jobs)}
    finally:
        db.close()


@shared_task(name="app.tasks.deliver_outbox_event", bind=True, max_retries=5)
def deliver_outbox_event(self, outbox_event_id: int):
    db = SessionLocal()
    try:
        event = db.get(OutboxEvent, outbox_event_id)
        if not event or event.delivered_at is not None:
            return
        delivery = db.scalar(select(WebhookDelivery).where(WebhookDelivery.outbox_event_id == event.id))
        if not delivery:
            delivery = WebhookDelivery(
                outbox_event_id=event.id,
                event_id=event.event_id,
                tenant_id=event.tenant_id,
            )
            db.add(delivery)
            db.flush()
        if delivery.status == DeliveryStatus.DELIVERED:
            return
        delivery.status = DeliveryStatus.DELIVERING
        delivery.attempts += 1
        db.commit()

        code = deliver_signed_webhook(event.callback_url, event.event_id, event.payload)

        event = db.get(OutboxEvent, outbox_event_id)
        delivery = db.scalar(select(WebhookDelivery).where(WebhookDelivery.outbox_event_id == event.id))
        now = datetime.now(timezone.utc)
        event.delivered_at = now
        delivery.status = DeliveryStatus.DELIVERED
        delivery.last_status_code = code
        delivery.last_error = None
        delivery.delivered_at = now
        db.commit()
        WEBHOOK_DELIVERIES.labels(result="success").inc()
    except PermanentWebhookError as exc:
        db.rollback()
        event = db.get(OutboxEvent, outbox_event_id)
        if event:
            delivery = db.scalar(select(WebhookDelivery).where(WebhookDelivery.outbox_event_id == event.id))
            event.dead_lettered_at = datetime.now(timezone.utc)
            if delivery:
                delivery.status = DeliveryStatus.FAILED
                delivery.last_error = str(exc)[:2000]
            db.add(DeadLetter(tenant_id=event.tenant_id, kind="webhook", object_id=event.event_id, reason=str(exc)[:2000], payload={"outbox_event_id": event.id}))
            db.commit()
        WEBHOOK_DELIVERIES.labels(result="permanent_failure").inc()
        raise
    except RetryableWebhookError as exc:
        db.rollback()
        event = db.get(OutboxEvent, outbox_event_id)
        delivery = db.scalar(select(WebhookDelivery).where(WebhookDelivery.outbox_event_id == outbox_event_id)) if event is None else db.scalar(select(WebhookDelivery).where(WebhookDelivery.outbox_event_id == event.id))
        if delivery:
            delivery.last_error = str(exc)[:2000]
            delivery.status = DeliveryStatus.PENDING
            db.commit()
        if self.request.retries >= self.max_retries:
            if event:
                delivery = db.scalar(select(WebhookDelivery).where(WebhookDelivery.outbox_event_id == event.id))
                event.dead_lettered_at = datetime.now(timezone.utc)
                if delivery:
                    delivery.status = DeliveryStatus.FAILED
                db.add(DeadLetter(tenant_id=event.tenant_id, kind="webhook", object_id=event.event_id, reason=str(exc)[:2000], payload={"outbox_event_id": event.id}))
                db.commit()
            WEBHOOK_DELIVERIES.labels(result="failed").inc()
            raise
        countdown = min(2 ** self.request.retries, 300)
        raise self.retry(exc=exc, countdown=countdown)
    finally:
        db.close()


@shared_task(name="app.tasks.recover_stuck_workflows")
def recover_stuck_workflows():
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.stuck_after_seconds)
        stuck = list(
            db.scalars(
                select(Workflow).where(
                    Workflow.updated_at < cutoff,
                    Workflow.status.in_([
                        WorkflowStatus.VALIDATING,
                        WorkflowStatus.AI_REVIEW,
                        WorkflowStatus.EXECUTING,
                    ]),
                )
            ).all()
        )
        safe_retries: list[tuple[str, str]] = []
        for workflow in stuck:
            if workflow.status == WorkflowStatus.EXECUTING:
                workflow.status = WorkflowStatus.NEEDS_RECONCILIATION
                workflow.version += 1
                workflow.last_error = "Execution became stale; manual reconciliation required"
                record_event(db, workflow, "stuck_execution_requires_reconciliation", "scheduler")
            else:
                old = workflow.status
                workflow.status = WorkflowStatus.FAILED
                workflow.version += 1
                workflow.last_error = "Stale pre-execution workflow recovered by scheduler"
                record_event(db, workflow, "stuck_workflow_recovered", "scheduler", {"from": old.value})
                if workflow.attempt_count < settings.max_workflow_retries:
                    safe_retries.append((workflow.tenant_id, workflow.public_id))
        db.commit()
        for tenant_id, public_id in safe_retries:
            start_workflow.delay(tenant_id, public_id)
        return {"stuck": len(stuck), "safe_retries": len(safe_retries)}
    finally:
        db.close()
