from __future__ import annotations
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from core.secrets.base import SecretsProvider


class EncryptedSecretsProvider(SecretsProvider):
    def __init__(self, master_key: str):
        self._key = bytes.fromhex(master_key)
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        iv = os.urandom(12)
        ciphertext = self._aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
        return ciphertext, iv

    def decrypt(self, ciphertext: bytes, iv: bytes) -> str:
        plaintext_bytes = self._aesgcm.decrypt(iv, ciphertext, None)
        return plaintext_bytes.decode("utf-8")
