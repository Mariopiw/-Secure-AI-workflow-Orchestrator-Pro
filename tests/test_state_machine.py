import pytest

from app.models import WorkflowStatus
from app.state_machine import assert_transition


def test_waiting_approval_can_be_approved():
    assert_transition(WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.APPROVED)


def test_waiting_approval_cannot_skip_to_completed():
    with pytest.raises(ValueError):
        assert_transition(WorkflowStatus.WAITING_APPROVAL, WorkflowStatus.COMPLETED)


def test_completed_is_terminal():
    with pytest.raises(ValueError):
        assert_transition(WorkflowStatus.COMPLETED, WorkflowStatus.EXECUTING)
