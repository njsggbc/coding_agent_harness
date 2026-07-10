import os
import pytest
import keyring
import keyring.backends.fail
from keyring.backend import KeyringBackend
from harness.credentials import CredentialManager


class MockKeyring(KeyringBackend):
    priority = 1

    def __init__(self):
        self._store = {}

    def set_password(self, service, username, password):
        self._store[(service, username)] = password

    def get_password(self, service, username):
        return self._store.get((service, username))

    def delete_password(self, service, username):
        self._store.pop((service, username), None)

    def get_credential(self, service, username):
        pwd = self.get_password(service, username)
        if pwd is None:
            return None
        from keyring.credentials import SimpleCredential
        return SimpleCredential(username, pwd)


@pytest.fixture(autouse=True)
def setup_mock_keyring(monkeypatch):
    mock = MockKeyring()
    keyring.set_keyring(mock)
    yield mock
    keyring.set_keyring(keyring.backends.fail.Keyring())


class TestCredentialManager:
    def test_store_and_retrieve(self):
        mgr = CredentialManager()
        mgr.store("test_service", "my-secret-key")
        assert mgr.retrieve("test_service") == "my-secret-key"

    def test_retrieve_nonexistent(self):
        mgr = CredentialManager()
        assert mgr.retrieve("nonexistent") is None

    def test_delete(self):
        mgr = CredentialManager()
        mgr.store("test_service", "my-secret-key")
        mgr.delete("test_service")
        assert mgr.retrieve("test_service") is None

    def test_delete_nonexistent_no_error(self):
        mgr = CredentialManager()
        mgr.delete("nonexistent")

    def test_has_credentials_true(self):
        mgr = CredentialManager()
        mgr.store("test_service", "my-secret-key")
        assert mgr.has_credentials("test_service") is True

    def test_has_credentials_false(self):
        mgr = CredentialManager()
        assert mgr.has_credentials("nonexistent") is False

    def test_list_services_empty(self):
        mgr = CredentialManager()
        assert mgr.list_services() == []

    def test_list_services(self):
        mgr = CredentialManager()
        mgr.store("service_a", "key_a")
        mgr.store("service_b", "key_b")
        assert set(mgr.list_services()) == {"service_a", "service_b"}

    def test_get_api_key_keyring_priority(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mgr = CredentialManager()
        mgr.store("harness/openai", "keyring-key")
        assert mgr.get_api_key() == "keyring-key"

    def test_get_api_key_env_var_fallback(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENAI_API_KEY", "env-key")
        mgr = CredentialManager()
        assert mgr.get_api_key() == "env-key"

    def test_get_api_key_dotenv_fallback(self, monkeypatch, tmp_path):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("OPENAI_API_KEY=dotenv-key")
        mgr = CredentialManager(env_path=str(env_file))
        assert mgr.get_api_key() == "dotenv-key"

    def test_get_api_key_none(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        mgr = CredentialManager(env_path="nonexistent.env")
        assert mgr.get_api_key() is None

    def test_setup_wizard(self, monkeypatch):
        inputs = iter(["myservice", "my-secret-key"])
        monkeypatch.setattr("click.prompt", lambda *a, **kw: next(inputs))
        mgr = CredentialManager()
        mgr.setup_wizard()
        assert mgr.retrieve("myservice") == "my-secret-key"

    def test_setup_wizard_default_service(self, monkeypatch):
        inputs = iter(["", "my-openai-key"])
        monkeypatch.setattr(
            "click.prompt",
            lambda text="", default=None, **kw: default if (val := next(inputs)) == "" else val,
        )
        mgr = CredentialManager()
        mgr.setup_wizard()
        assert mgr.retrieve("harness/openai") == "my-openai-key"