import os
import pytest
from core.secrets.encrypted import EncryptedSecretsProvider


@pytest.fixture
def secrets_provider():
    master_key = os.urandom(32).hex()
    return EncryptedSecretsProvider(master_key=master_key)


def test_encrypt_decrypt_roundtrip(secrets_provider):
    original = "sk-ant-api03-test-key-12345"
    encrypted, iv = secrets_provider.encrypt(original)
    decrypted = secrets_provider.decrypt(encrypted, iv)
    assert decrypted == original


def test_different_ivs_per_encryption(secrets_provider):
    key = "sk-ant-api03-test-key-12345"
    _, iv1 = secrets_provider.encrypt(key)
    _, iv2 = secrets_provider.encrypt(key)
    assert iv1 != iv2


def test_key_hint(secrets_provider):
    hint = secrets_provider.get_key_hint("sk-ant-api03-test-key-12345")
    assert hint == "...2345"


def test_decrypt_with_wrong_key():
    provider1 = EncryptedSecretsProvider(master_key=os.urandom(32).hex())
    provider2 = EncryptedSecretsProvider(master_key=os.urandom(32).hex())
    encrypted, iv = provider1.encrypt("secret")
    with pytest.raises(Exception):
        provider2.decrypt(encrypted, iv)
