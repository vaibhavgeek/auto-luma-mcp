from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, Field, SecretStr

from lumabot_shared.enums import JobType, ToolStatus

T = TypeVar("T")


class NextAction(BaseModel):
    label: str
    action_type: str
    url: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False


class ToolResponse(BaseModel, Generic[T]):
    status: ToolStatus
    data: T | None = None
    message: str | None = None
    next_actions: list[NextAction] = Field(default_factory=list)
    error_code: str | None = None
    correlation_id: str | None = None


class RuntimeJobRequest(BaseModel):
    job_type: JobType
    user_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    priority: int = Field(default=0, ge=0, le=100)


class RuntimeJobResponse(BaseModel):
    job_id: UUID
    status: ToolStatus
    idempotency_key: str | None = None


class InternalRuntimeAuth(BaseModel):
    token: SecretStr = Field(repr=False)


class ClaimJobsRequest(BaseModel):
    worker_id: str
    job_types: list[JobType] | None = None
    limit: int = Field(default=1, ge=1, le=100)
    lease_seconds: int = Field(default=300, ge=30, le=3600)
