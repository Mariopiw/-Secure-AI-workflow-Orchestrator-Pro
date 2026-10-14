from app.schemas import WorkflowCreate
from app.services.workflows import canonical_request_hash


def test_same_request_has_same_hash():
    a = WorkflowCreate(case_reference="CASE-1", description="A sufficiently long workflow description")
    b = WorkflowCreate(case_reference="CASE-1", description="A sufficiently long workflow description")
    assert canonical_request_hash(a) == canonical_request_hash(b)


def test_changed_request_has_different_hash():
    a = WorkflowCreate(case_reference="CASE-1", description="A sufficiently long workflow description")
    b = WorkflowCreate(case_reference="CASE-1", description="A changed sufficiently long workflow description")
    assert canonical_request_hash(a) != canonical_request_hash(b)
