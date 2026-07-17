from uuid import UUID, uuid4

from pydantic import BaseModel, Field, SecretBytes, SecretStr


class EncryptedBrowserSession(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    provider: str = "luma"
    ciphertext: SecretBytes = Field(repr=False)
    key_id: str | None = None


class RuntimeSecretBundle(BaseModel):
    database_url: SecretStr | None = Field(default=None, repr=False)
    session_encryption_key: SecretStr | None = Field(default=None, repr=False)
    agentmail_api_key: SecretStr | None = Field(default=None, repr=False)
    nexla_api_key: SecretStr | None = Field(default=None, repr=False)
    zero_api_key: SecretStr | None = Field(default=None, repr=False)
