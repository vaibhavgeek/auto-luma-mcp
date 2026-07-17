from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import AnyUrl, BaseModel, Field, SecretStr

from lumabot_shared.enums import JobType, ToolStatus
from lumabot_shared.models.users import utc_now


class Job(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    job_type: JobType
    status: ToolStatus = ToolStatus.QUEUED
    user_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    priority: int = Field(default=0, ge=0, le=100)
    idempotency_key: str | None = None
    attempts: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, ge=1)
    locked_by: str | None = None
    locked_at: datetime | None = None
    lease_expires_at: datetime | None = None
    scheduled_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)


class Notification(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    channel: str
    subject: str | None = None
    body: str
    provider: str | None = None
    sender_inbox_id: SecretStr | None = Field(default=None, repr=False)
    provider_message_id: str | None = None
    provider_thread_id: str | None = None
    provider_status: str | None = None
    idempotency_key: str
    status: ToolStatus = ToolStatus.QUEUED
    created_at: datetime = Field(default_factory=utc_now)
    sent_at: datetime | None = None


class ExternalAction(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    action_type: str
    status: ToolStatus = ToolStatus.QUEUED
    provider: str
    external_id: str | None = None
    target_url: AnyUrl | None = None
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
