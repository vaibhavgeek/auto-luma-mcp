from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    runtime_url: str = "http://127.0.0.1:8080"
    runtime_bearer_token: str | None = None
    request_timeout_seconds: float = 30.0
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> Settings:
        timeout = float(os.getenv("LUMABOT_RUNTIME_TIMEOUT_SECONDS", "5.0"))
        port = int(os.getenv("LUMABOT_MCP_PORT", "8000"))
        return cls(
            runtime_url=os.getenv("LUMABOT_RUNTIME_URL", "http://127.0.0.1:8080"),
            runtime_bearer_token=os.getenv("LUMABOT_RUNTIME_BEARER_TOKEN"),
            request_timeout_seconds=timeout,
            host=os.getenv("LUMABOT_MCP_HOST", "127.0.0.1"),
            port=port,
            log_level=os.getenv("LUMABOT_LOG_LEVEL", "INFO"),
        )
