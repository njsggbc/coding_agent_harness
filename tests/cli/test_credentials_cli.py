"""Tests for the credentials CLI commands. Separate from test_cli.py
because these require keyring which may not be available in CI."""
import pytest

keyring = pytest.importorskip("keyring", reason="keyring not available")
keyring_backends_fail = pytest.importorskip("keyring.backends.fail", reason="keyring backends not available")
from keyring.backend import KeyringBackend
from click.testing import CliRunner
from harness.cli.main import cli


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


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def mock_keyring(monkeypatch):
    mock = MockKeyring()
    keyring.set_keyring(mock)
    monkeypatch.setattr("keyring.get_keyring", lambda: mock)
    yield mock
    keyring.set_keyring(keyring.backends.fail.Keyring())


class TestCredentialsCLI:
    def test_credentials_help(self, runner):
        result = runner.invoke(cli, ["credentials", "--help"])
        assert result.exit_code == 0
        assert "setup" in result.output
        assert "status" in result.output
        assert "update" in result.output
        assert "clear" in result.output

    def test_credentials_status_empty(self, runner, mock_keyring):
        result = runner.invoke(cli, ["credentials", "status"])
        assert result.exit_code == 0
        assert "No credentials stored" in result.output

    def test_credentials_status_with_keys(self, runner, mock_keyring):
        mock_keyring.set_password("harness/openai", "api_key", "sk-test")
        mock_keyring.set_password("harness/anthropic", "api_key", "sk-ant")
        result = runner.invoke(cli, ["credentials", "status"])
        assert result.exit_code == 0
        assert "harness/openai" in result.output
        assert "harness/anthropic" in result.output

    def test_credentials_setup(self, runner, mock_keyring, monkeypatch):
        inputs = iter(["myservice", "my-key", "my-key"])
        monkeypatch.setattr("click.prompt", lambda *a, **kw: next(inputs))
        result = runner.invoke(cli, ["credentials", "setup"])
        assert result.exit_code == 0
        assert "stored securely" in result.output.lower()
        assert mock_keyring.get_password("myservice", "api_key") == "my-key"

    def test_credentials_update(self, runner, mock_keyring, monkeypatch):
        mock_keyring.set_password("myservice", "api_key", "old-key")
        inputs = iter(["new-key", "new-key"])
        monkeypatch.setattr("click.prompt", lambda *a, **kw: next(inputs))
        result = runner.invoke(cli, ["credentials", "update", "myservice"])
        assert result.exit_code == 0
        assert "updated" in result.output.lower()
        assert mock_keyring.get_password("myservice", "api_key") == "new-key"

    def test_credentials_update_nonexistent(self, runner, mock_keyring, monkeypatch):
        inputs = iter(["new-key", "new-key"])
        monkeypatch.setattr("click.prompt", lambda *a, **kw: next(inputs))
        result = runner.invoke(cli, ["credentials", "update", "nonexistent"])
        assert result.exit_code == 0
        assert "no credential found" in result.output.lower()

    def test_credentials_clear(self, runner, mock_keyring):
        mock_keyring.set_password("myservice", "api_key", "sk-test")
        result = runner.invoke(cli, ["credentials", "clear", "myservice"])
        assert result.exit_code == 0
        assert "removed" in result.output.lower()
        assert mock_keyring.get_password("myservice", "api_key") is None

    def test_credentials_clear_nonexistent(self, runner, mock_keyring):
        result = runner.invoke(cli, ["credentials", "clear", "nonexistent"])
        assert result.exit_code == 0
        assert "no credential found" in result.output.lower()

    def test_credentials_clear_all(self, runner, mock_keyring):
        mock_keyring.set_password("svc_a", "api_key", "key-a")
        mock_keyring.set_password("svc_b", "api_key", "key-b")
        result = runner.invoke(cli, ["credentials", "clear", "--all"], input="y\n")
        assert result.exit_code == 0
        assert "all credentials" in result.output.lower()
        assert mock_keyring.get_password("svc_a", "api_key") is None
        assert mock_keyring.get_password("svc_b", "api_key") is None

    def test_credentials_clear_all_abort(self, runner, mock_keyring):
        mock_keyring.set_password("svc_a", "api_key", "key-a")
        result = runner.invoke(cli, ["credentials", "clear", "--all"], input="n\n")
        assert result.exit_code == 0
        assert "aborted" in result.output.lower()
        assert mock_keyring.get_password("svc_a", "api_key") == "key-a"