from __future__ import annotations

import os
from dataclasses import dataclass

from mcp.server.transport_security import TransportSecuritySettings


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str) -> list[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


@dataclass(frozen=True, slots=True)
class Settings:
    runtime_url: str = "http://127.0.0.1:8080"
    runtime_bearer_token: str | None = None
    request_timeout_seconds: float = 30.0
    host: str = "127.0.0.1"
    port: int = 8000
    log_level: str = "INFO"
    enable_dns_rebinding_protection: bool = True
    allowed_hosts: list[str] | None = None
    allowed_origins: list[str] | None = None

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
            enable_dns_rebinding_protection=_env_bool(
                "LUMABOT_MCP_DNS_REBINDING_PROTECTION",
                default=True,
            ),
            allowed_hosts=_env_list("LUMABOT_MCP_ALLOWED_HOSTS"),
            allowed_origins=_env_list("LUMABOT_MCP_ALLOWED_ORIGINS"),
        )

    def transport_security_settings(self) -> TransportSecuritySettings:
        return TransportSecuritySettings(
            enable_dns_rebinding_protection=self.enable_dns_rebinding_protection,
            allowed_hosts=self.allowed_hosts or [],
            allowed_origins=self.allowed_origins or [],
        )
