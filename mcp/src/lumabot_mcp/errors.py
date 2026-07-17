from __future__ import annotations


class RuntimeErrorBase(Exception):
    """Base class for safe runtime-facing errors."""

    safe_message = "Runtime request failed."


class RuntimeTimeoutError(RuntimeErrorBase):
    safe_message = "Runtime request timed out."


class RuntimeAuthenticationError(RuntimeErrorBase):
    safe_message = "Authentication is required."


class RuntimeAPIError(RuntimeErrorBase):
    def __init__(self, safe_message: str = "Runtime request failed.") -> None:
        super().__init__(safe_message)
        self.safe_message = safe_message

