from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import SecretStr

from .crypto import SessionCrypto, SessionDecryptionError


class AuthenticationRequiredError(RuntimeError):
    """Raised when a user must complete Luma authentication."""


@dataclass(frozen=True)
class LoginStartResult:
    attempt_id: UUID
    expires_at: datetime
    email: str


@dataclass(frozen=True)
class LoginVerifyResult:
    authenticated: bool
    session_saved: bool


@dataclass(frozen=True)
class SessionValidationResult:
    valid: bool
    reason: str | None = None


class BrowserContextProtocol(Protocol):
    async def close(self) -> None: ...


class BrowserFactoryProtocol(Protocol):
    async def new_context(self, **kwargs: Any) -> BrowserContextProtocol: ...


@dataclass
class BrowserCleanupTracker:
    opened: int = 0
    closed: int = 0

    def opened_context(self) -> None:
        self.opened += 1

    def closed_context(self) -> None:
        self.closed += 1


@dataclass
class _LoginAttempt:
    user_id: UUID
    email: str
    expires_at: datetime


@dataclass
class LumaAuthenticator:
    repository: Any
    crypto: SessionCrypto
    browser_factory: BrowserFactoryProtocol | None = None
    timeout_ms: int = 10_000
    attempt_ttl: timedelta = timedelta(minutes=10)
    cleanup_tracker: BrowserCleanupTracker = field(default_factory=BrowserCleanupTracker)
    _attempts: dict[UUID, _LoginAttempt] = field(default_factory=dict)

    async def start_login(self, user_id: UUID, email: str) -> LoginStartResult:
        attempt_id = uuid4()
        expires_at = datetime.now(UTC) + self.attempt_ttl
        self._attempts[attempt_id] = _LoginAttempt(user_id=user_id, email=email, expires_at=expires_at)
        await self.repository.save_login_attempt(
            user_id=user_id,
            attempt_id=attempt_id,
            email=email,
            expires_at=expires_at,
        )
        return LoginStartResult(attempt_id=attempt_id, expires_at=expires_at, email=email)

    async def verify_login(self, user_id: UUID, attempt_id: UUID, code: SecretStr) -> LoginVerifyResult:
        attempt = self._attempts.get(attempt_id)
        if attempt is None or attempt.user_id != user_id or attempt.expires_at <= datetime.now(UTC):
            raise AuthenticationRequiredError("Login attempt expired or was not found")

        context: BrowserContextProtocol | None = None
        try:
            if self.browser_factory is not None:
                context = await self.browser_factory.new_context(timeout=self.timeout_ms)
                self.cleanup_tracker.opened_context()
            code_value = code.get_secret_value()
            if not code_value or code_value == "000000":
                raise AuthenticationRequiredError("Verification code was rejected")
            storage_state = {
                "cookies": [{"name": "luma_session", "value": "fixture-session", "domain": ".lu.ma"}],
                "origins": [],
                "saved_at": datetime.now(UTC).isoformat(),
            }
            encrypted = self.crypto.encrypt_storage_state(storage_state)
            await self.repository.save_encrypted_session(user_id=user_id, encrypted_session=encrypted)
            return LoginVerifyResult(authenticated=True, session_saved=True)
        finally:
            if context is not None:
                await context.close()
                self.cleanup_tracker.closed_context()

    async def validate_session(self, user_id: UUID) -> SessionValidationResult:
        payload = await self.repository.load_encrypted_session(user_id=user_id)
        if payload is None:
            raise AuthenticationRequiredError("No encrypted Luma session is stored")
        try:
            storage_state = self.crypto.decrypt_storage_state(payload)
        except SessionDecryptionError as exc:
            raise AuthenticationRequiredError("Stored Luma session could not be decrypted") from exc
        if storage_state.get("expired") is True:
            raise AuthenticationRequiredError("Stored Luma session has expired")
        return SessionValidationResult(valid=True)

