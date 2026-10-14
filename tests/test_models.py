from app.models import WorkflowStatus


def test_reconciliation_state_exists():
    assert WorkflowStatus.NEEDS_RECONCILIATION.value == "NEEDS_RECONCILIATION"
