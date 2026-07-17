from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Status = Literal[
    "completed",
    "needs_input",
    "queued",
    "auth_required",
    "timeout",
    "error",
]


class ToolResponse(BaseModel):
    ok: bool = True
    status: Status = "completed"
    data: dict[str, Any] = Field(default_factory=dict)
    job_id: str | None = None
    next_action: dict[str, Any] | None = None
    message: str = ""
