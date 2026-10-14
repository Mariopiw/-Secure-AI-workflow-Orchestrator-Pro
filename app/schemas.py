from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field

from app.models import WorkflowStatus


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    tenant_id: str
    model_config = {"from_attributes": True}


class WorkflowCreate(BaseModel):
    case_reference: str = Field(min_length=3, max_length=120)
    description: str = Field(min_length=10, max_length=5000)
    input_payload: dict = Field(default_factory=dict)
    callback_url: AnyHttpUrl | None = None


class WorkflowOut(BaseModel):
    public_id: str
    tenant_id: str
    case_reference: str
    description: str
    status: WorkflowStatus
    risk_score: int | None
    ai_reason: str | None
    attempt_count: int
    last_error: str | None
    version: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class ApprovalRequest(BaseModel):
    decision: Literal["APPROVE", "REJECT"]
    comment: str | None = Field(default=None, max_length=1000)


class RetryRequest(BaseModel):
    comment: str | None = Field(default=None, max_length=1000)


class ReconcileRequest(BaseModel):
    action: Literal["MARK_COMPLETED", "RETRY_EXECUTION"]
    comment: str = Field(min_length=3, max_length=1000)


class EventOut(BaseModel):
    event_type: str
    actor: str
    detail: dict
    created_at: datetime
    model_config = {"from_attributes": True}
