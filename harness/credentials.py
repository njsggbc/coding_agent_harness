import os
from typing import Optional

import click
import keyring
from dotenv import load_dotenv

DEFAULT_SERVICE = "harness/openai"


class CredentialManager:
    def __init__(self, env_path: Optional[str] = None):
        self._env_path = env_path or ".env"

    def store(self, service: str, key: str) -> None:
        keyring.set_password(service, "api_key", key)

    def retrieve(self, service: str) -> Optional[str]:
        return keyring.get_password(service, "api_key")

    def delete(self, service: str) -> None:
        try:
            keyring.delete_password(service, "api_key")
        except keyring.errors.PasswordDeleteError:
            pass

    def list_services(self) -> list[str]:
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