from pydantic import SecretBytes, SecretStr

from lumabot_shared.fixtures import make_job_seeker
from lumabot_shared.models import AuthSession, Notification
from lumabot_shared.security import EncryptedBrowserSession, RuntimeSecretBundle


def test_browser_session_payload_is_encrypted_bytes_and_redacted() -> None:
    user, _profile = make_job_seeker()
    session = EncryptedBrowserSession(
        user_id=user.id,
        ciphertext=SecretBytes(b"encrypted-cookie-payload"),
    )

    rendered = repr(session)
    assert "encrypted-cookie-payload" not in rendered
    assert "cookie" not in rendered.lower()
    assert session.ciphertext.get_secret_value() == b"encrypted-cookie-payload"


def test_secret_bearing_models_redact_repr() -> None:
    user, _profile = make_job_seeker()
    auth_session = AuthSession(
        user_id=user.id,
        encrypted_browser_session=SecretBytes(b"encrypted-browser-state"),
    )
    notification = Notification(
        user_id=user.id,
        channel="email",
        subject="Demo",
        body="Hello",
        sender_inbox_id=SecretStr("inbox-secret"),
        idempotency_key="notify-demo",
    )
    bundle = RuntimeSecretBundle(
        database_url=SecretStr("postgres://secret"),
        agentmail_api_key=SecretStr("agentmail-secret"),
    )

    rendered = f"{auth_session!r} {notification!r} {bundle!r}"
    assert "encrypted-browser-state" not in rendered
    assert "inbox-secret" not in rendered
    assert "agentmail-secret" not in rendered
    assert "postgres://secret" not in rendered
