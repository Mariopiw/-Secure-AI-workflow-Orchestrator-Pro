from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import current_user, require_roles
from app.db import get_db
from app.metrics import WORKFLOWS_CREATED
from app.models import Approval, Decision, ExecutionRecord, User, UserRole, Workflow, WorkflowEvent, WorkflowStatus
from app.schemas import ApprovalRequest, EventOut, ReconcileRequest, RetryRequest, WorkflowCreate, WorkflowOut
from app.services.workflows import canonical_request_hash, create_or_get_workflow, record_event, save_approval, transition
from app.tasks import execute_approved_workflow, start_workflow

router = APIRouter(prefix="/workflows", tags=["workflows"])


def _workflow_for_user(db: Session, user: User, public_id: str, lock: bool = False) -> Workflow:
    stmt = select(Workflow).where(
        Workflow.tenant_id == user.tenant_id,
        Workflow.public_id == public_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    workflow = db.scalar(stmt)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return workflow


@router.post("", response_model=WorkflowOut, status_code=status.HTTP_202_ACCEPTED)
def create_workflow(
    payload: WorkflowCreate,
    response: Response,
    idempotency_key: str = Header(..., alias="Idempotency-Key", min_length=8, max_length=200),
    user: User = Depends(require_roles(UserRole.SUBMITTER, UserRole.APPROVER, UserRole.OPERATOR)),
    db: Session = Depends(get_db),
):
    try:
        workflow, duplicate = create_or_get_workflow(
            db,
            tenant_id=user.tenant_id,
            created_by=user.id,
            payload=payload,
            idempotency_key=idempotency_key,
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc))
    except IntegrityError:
        db.rollback()
        workflow = db.scalar(
            select(Workflow).where(
                Workflow.tenant_id == user.tenant_id,
                Workflow.idempotency_key == idempotency_key,
            )
        )
        if not workflow:
            raise
        if workflow.request_hash != canonical_request_hash(payload):
            raise HTTPException(status_code=409, detail="Idempotency-Key already used with a different request body")
        duplicate = True

    response.headers["X-Idempotent-Replay"] = "true" if duplicate else "false"
    if not duplicate:
        WORKFLOWS_CREATED.labels(tenant=user.tenant_id).inc()
        start_workflow.delay(user.tenant_id, workflow.public_id)
    return workflow


@router.get("/{public_id}", response_model=WorkflowOut)
def get_workflow(public_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    return _workflow_for_user(db, user, public_id)


@router.get("/{public_id}/events", response_model=list[EventOut])
def workflow_events(public_id: str, user: User = Depends(current_user), db: Session = Depends(get_db)):
    workflow = _workflow_for_user(db, user, public_id)
    stmt = (
        select(WorkflowEvent)
        .where(WorkflowEvent.workflow_id == workflow.id, WorkflowEvent.tenant_id == user.tenant_id)
        .order_by(WorkflowEvent.created_at)
    )
    return list(db.scalars(stmt).all())


@router.post("/{public_id}/decision", response_model=WorkflowOut)
def decide_workflow(
    public_id: str,
    payload: ApprovalRequest,
    user: User = Depends(require_roles(UserRole.APPROVER)),
    db: Session = Depends(get_db),
):
    workflow = _workflow_for_user(db, user, public_id, lock=True)
    if workflow.status != WorkflowStatus.WAITING_APPROVAL:
        raise HTTPException(status_code=409, detail=f"Workflow is {workflow.status.value}")
    if settings.four_eyes_required and workflow.created_by == user.id:
        raise HTTPException(status_code=409, detail="Four-eyes rule: creator cannot approve own workflow")
    if db.scalar(select(Approval).where(Approval.workflow_id == workflow.id)):
        raise HTTPException(status_code=409, detail="Decision already recorded")

    decision = Decision(payload.decision)
    save_approval(
        db,
        workflow=workflow,
        actor_id=user.id,
        decision=decision,
        comment=payload.comment,
    )
    if decision == Decision.APPROVE:
        transition(db, workflow, WorkflowStatus.APPROVED, actor=f"user:{user.id}", detail={"comment": payload.comment})
    else:
        transition(db, workflow, WorkflowStatus.REJECTED, actor=f"user:{user.id}", detail={"comment": payload.comment})
    db.commit()

    if decision == Decision.APPROVE:
        execute_approved_workflow.delay(user.tenant_id, workflow.public_id)
    return workflow


@router.post("/{public_id}/retry", response_model=WorkflowOut)
def retry_workflow(
    public_id: str,
    payload: RetryRequest,
    user: User = Depends(require_roles(UserRole.OPERATOR)),
    db: Session = Depends(get_db),
):
    workflow = _workflow_for_user(db, user, public_id, lock=True)
    if workflow.status != WorkflowStatus.FAILED:
        raise HTTPException(status_code=409, detail="Only FAILED workflows can be safely retried")
    record_event(db, workflow, "manual_retry_requested", f"user:{user.id}", {"comment": payload.comment})
    db.commit()
    start_workflow.delay(user.tenant_id, workflow.public_id)
    return workflow


@router.post("/{public_id}/reconcile", response_model=WorkflowOut)
def reconcile_workflow(
    public_id: str,
    payload: ReconcileRequest,
    user: User = Depends(require_roles(UserRole.OPERATOR)),
    db: Session = Depends(get_db),
):
    workflow = _workflow_for_user(db, user, public_id, lock=True)
    if workflow.status != WorkflowStatus.NEEDS_RECONCILIATION:
        raise HTTPException(status_code=409, detail="Workflow does not require reconciliation")

    execution = db.scalar(select(ExecutionRecord).where(ExecutionRecord.workflow_id == workflow.id))
    record_event(
        db,
        workflow,
        "operator_reconciliation",
        f"user:{user.id}",
        {"action": payload.action, "comment": payload.comment, "execution_record_exists": bool(execution)},
    )

    if payload.action == "MARK_COMPLETED":
        if not execution:
            raise HTTPException(status_code=409, detail="Cannot mark completed without durable execution evidence")
        transition(db, workflow, WorkflowStatus.COMPLETED, actor=f"user:{user.id}")
        from app.services.workflows import create_outbox_event
        create_outbox_event(db, workflow, "workflow.completed")
        db.commit()
        return workflow

    # RETRY_EXECUTION is allowed because the demo business effect is idempotent.
    # The task will transition NEEDS_RECONCILIATION -> EXECUTING under a row lock.
    db.commit()
    execute_approved_workflow.delay(user.tenant_id, workflow.public_id)
    return workflow
