from __future__ import annotations
from abc import ABC, abstractmethod


class SecretsProvider(ABC):
    @abstractmethod
    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        ...

    @abstractmethod
    def decrypt(self, ciphertext: bytes, iv: bytes) -> str:
        ...

    def get_key_hint(self, plaintext: str) -> str:
        return f"...{plaintext[-4:]}" if len(plaintext) >= 4 else plaintext
