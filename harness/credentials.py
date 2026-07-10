import os
import logging
from typing import Optional

import click
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

try:
    import keyring
    _KEYRING_AVAILABLE = True
except ImportError:
    keyring = None
    _KEYRING_AVAILABLE = False

DEFAULT_SERVICE = "harness/openai"


class CredentialManager:
    def __init__(self, env_path: Optional[str] = None):
        self._env_path = env_path or ".env"

    def _warn_keyring_unavailable(self):
        if not _KEYRING_AVAILABLE:
            logger.warning("keyring is not available on this platform. Credentials will only work via environment variables or .env files.")

    def store(self, service: str, key: str) -> None:
        if not _KEYRING_AVAILABLE:
            raise RuntimeError("keyring is not available. Use environment variables or .env file instead.")
        keyring.set_password(service, "api_key", key)

    def retrieve(self, service: str) -> Optional[str]:
        if not _KEYRING_AVAILABLE:
            return None
        try:
            return keyring.get_password(service, "api_key")
        except Exception:
            return None

    def delete(self, service: str) -> None:
        if not _KEYRING_AVAILABLE:
            return
        try:
            keyring.delete_password(service, "api_key")
        except Exception:
            pass

    def list_services(self) -> list[str]:
        if not _KEYRING_AVAILABLE:
            return []
        if hasattr(keyring, "get_keyring"):
            backend = keyring.get_keyring()
            if hasattr(backend, "_store"):
                return [s for (s, _) in backend._store.keys()]
        return []

    def has_credentials(self, service: str) -> bool:
        return self.retrieve(service) is not None

    def get_api_key(self) -> Optional[str]:
        key = self.retrieve(DEFAULT_SERVICE)
        if key:
            return key
        key = os.environ.get("OPENAI_API_KEY")
        if key:
            return key
        if os.path.exists(self._env_path):
            load_dotenv(self._env_path, override=True)
            key = os.environ.get("OPENAI_API_KEY")
            if key:
                return key
        return None

    def setup_wizard(self) -> None:
        service = click.prompt(
            "Service name",
            default=DEFAULT_SERVICE,
            show_default=True,
        )
        key = click.prompt(
            "API key",
            hide_input=True,
            confirmation_prompt=True,
        )
        self.store(service, key)
        click.echo(f"Key stored securely for service '{service}'.")