from __future__ import annotations

import base64
import json
import os
from dataclasses import dataclass
from typing import Any

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class SessionDecryptionError(ValueError):
    """Raised when encrypted storage state cannot be decrypted."""


@dataclass(frozen=True)
class SessionCrypto:
    key: bytes
    version: int = 1

    def __post_init__(self) -> None:
        if len(self.key) != 32:
            raise ValueError("AES-256-GCM requires a 32-byte key")

    @classmethod
    def from_base64(cls, value: str) -> "SessionCrypto":
        return cls(base64.b64decode(value))

    @classmethod
    def generate(cls) -> "SessionCrypto":
        return cls(os.urandom(32))

    def encrypt_storage_state(self, storage_state: dict[str, Any]) -> dict[str, Any]:
        plaintext = json.dumps(storage_state, sort_keys=True, separators=(",", ":")).encode()
        nonce = os.urandom(12)
        ciphertext = AESGCM(self.key).encrypt(nonce, plaintext, None)
        return {
            "version": self.version,
            "algorithm": "AES-256-GCM",
            "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
        }

    def decrypt_storage_state(self, payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("version") != self.version or payload.get("algorithm") != "AES-256-GCM":
            raise SessionDecryptionError("Unsupported encrypted session payload")
        try:
            nonce = base64.b64decode(payload["nonce"])
            ciphertext = base64.b64decode(payload["ciphertext"])
            plaintext = AESGCM(self.key).decrypt(nonce, ciphertext, None)
            decoded = json.loads(plaintext.decode())
        except (InvalidTag, KeyError, ValueError, json.JSONDecodeError) as exc:
            raise SessionDecryptionError("Unable to decrypt session payload") from exc
        if not isinstance(decoded, dict):
            raise SessionDecryptionError("Session payload did not contain a storage-state object")
        return decoded

