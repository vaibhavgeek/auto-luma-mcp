from __future__ import annotations

import contextvars
import logging
import re
import uuid
from collections.abc import Mapping
from typing import Any

from lumabot_mcp.runtime_client import RuntimeClient
from lumabot_mcp.settings import Settings

SECRET_KEYS = re.compile(r"(token|authorization|password|secret|code)", re.IGNORECASE)
REDACTED = "[REDACTED]"


runtime_client_var: contextvars.ContextVar[RuntimeClient] = contextvars.ContextVar(
    "runtime_client"
)
settings_var: contextvars.ContextVar[Settings] = contextvars.ContextVar("settings")


def correlation_id() -> str:
    return str(uuid.uuid4())


def redact_secrets(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if SECRET_KEYS.search(str(key)) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    return value


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def log_tool_call(logger: logging.Logger, tool_name: str, payload: dict[str, Any]) -> None:
    logger.info(
        "tool_call",
        extra={
            "tool_name": tool_name,
            "payload": redact_secrets(payload),
        },
    )

