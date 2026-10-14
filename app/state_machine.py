from app.models import WorkflowStatus

ALLOWED_TRANSITIONS = {
    WorkflowStatus.RECEIVED: {WorkflowStatus.VALIDATING, WorkflowStatus.FAILED},
    WorkflowStatus.VALIDATING: {WorkflowStatus.AI_REVIEW, WorkflowStatus.FAILED},
    WorkflowStatus.AI_REVIEW: {WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.FAILED},
    WorkflowStatus.WAITING_APPROVAL: {
        WorkflowStatus.APPROVED,
        WorkflowStatus.REJECTED,
        WorkflowStatus.FAILED,
    },
    WorkflowStatus.APPROVED: {WorkflowStatus.EXECUTING, WorkflowStatus.FAILED},
    WorkflowStatus.EXECUTING: {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.NEEDS_RECONCILIATION,
    },
    WorkflowStatus.FAILED: {WorkflowStatus.VALIDATING},
    WorkflowStatus.NEEDS_RECONCILIATION: {
        WorkflowStatus.EXECUTING,
        WorkflowStatus.COMPLETED,
    },
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.REJECTED: set(),
}


def assert_transition(old: WorkflowStatus, new: WorkflowStatus) -> None:
    if new not in ALLOWED_TRANSITIONS[old]:
        raise ValueError(f"Illegal transition: {old.value} -> {new.value}")
