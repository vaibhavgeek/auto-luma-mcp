from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from bs4 import BeautifulSoup
from pydantic import SecretStr

from lumabot_runtime.browser import AuthenticationRequiredError, LumaAuthenticator, SessionCrypto
from lumabot_runtime.luma.extractors import SELECTORS
from lumabot_runtime.luma.repository import InMemoryLumaRepository

FIXTURES = Path(__file__).parent / "fixtures"


def test_login_selectors_match_sanitized_fixtures() -> None:
    email_soup = BeautifulSoup((FIXTURES / "login-email.html").read_text(), "html.parser")
    code_soup = BeautifulSoup((FIXTURES / "code-page.html").read_text(), "html.parser")
    dashboard_soup = BeautifulSoup((FIXTURES / "authenticated-dashboard.html").read_text(), "html.parser")

    assert email_soup.select_one(SELECTORS["login_email"]) is not None
    assert code_soup.select_one(SELECTORS["login_code"]) is not None
    assert dashboard_soup.select_one(SELECTORS["dashboard"]) is not None


@pytest.mark.asyncio
async def test_session_encryption_round_trip() -> None:
    crypto = SessionCrypto.generate()
    payload = crypto.encrypt_storage_state({"cookies": [{"name": "luma_session", "value": "secret"}], "origins": []})

    assert payload["version"] == 1
    assert payload["algorithm"] == "AES-256-GCM"
    assert "secret" not in str(payload)
    assert crypto.decrypt_storage_state(payload)["cookies"][0]["value"] == "secret"


def test_wrong_key_decryption_failure() -> None:
    payload = SessionCrypto.generate().encrypt_storage_state({"cookies": [{"value": "secret"}]})

    with pytest.raises(Exception, match="Unable to decrypt session payload"):
        SessionCrypto.generate().decrypt_storage_state(payload)


@pytest.mark.asyncio
async def test_code_redaction_on_rejected_code(caplog: pytest.LogCaptureFixture) -> None:
    repository = InMemoryLumaRepository()
    auth = LumaAuthenticator(repository=repository, crypto=SessionCrypto.generate())
    user_id = uuid4()
    started = await auth.start_login(user_id, "person@example.test")

    with pytest.raises(AuthenticationRequiredError, match="Verification code was rejected"):
        await auth.verify_login(user_id, started.attempt_id, SecretStr("000000"))

    assert "000000" not in caplog.text


@pytest.mark.asyncio
async def test_expired_session_requires_authentication() -> None:
    repository = InMemoryLumaRepository()
    crypto = SessionCrypto.generate()
    user_id = uuid4()
    await repository.save_encrypted_session(user_id, crypto.encrypt_storage_state({"expired": True}))
    auth = LumaAuthenticator(repository=repository, crypto=crypto)

    with pytest.raises(AuthenticationRequiredError, match="expired"):
        await auth.validate_session(user_id)


class FakeContext:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBrowserFactory:
    def __init__(self) -> None:
        self.context = FakeContext()

    async def new_context(self, **_: object) -> FakeContext:
        return self.context


@pytest.mark.asyncio
async def test_browser_context_cleanup_after_verify() -> None:
    repository = InMemoryLumaRepository()
    factory = FakeBrowserFactory()
    auth = LumaAuthenticator(repository=repository, crypto=SessionCrypto.generate(), browser_factory=factory)
    user_id = uuid4()
    started = await auth.start_login(user_id, "person@example.test")

    result = await auth.verify_login(user_id, started.attempt_id, SecretStr("123456"))

    assert result.authenticated is True
    assert factory.context.closed is True
    assert auth.cleanup_tracker.opened == 1
    assert auth.cleanup_tracker.closed == 1


@pytest.mark.asyncio
async def test_login_attempt_expiration() -> None:
    repository = InMemoryLumaRepository()
    auth = LumaAuthenticator(repository=repository, crypto=SessionCrypto.generate(), attempt_ttl=timedelta(seconds=-1))
    user_id = uuid4()
    started = await auth.start_login(user_id, "person@example.test")

    with pytest.raises(AuthenticationRequiredError, match="expired"):
        await auth.verify_login(user_id, started.attempt_id, SecretStr("123456"))

