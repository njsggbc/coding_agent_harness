from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExecResult:
    exit_code: int
    stdout: str
    stderr: str


class Sandbox(ABC):
    @abstractmethod
    async def create(self, image: str, workdir: str, repo_path: str) -> str:
        ...

    @abstractmethod
    async def exec(self, container_id: str, command: str, workdir: Optional[str] = None) -> ExecResult:
        ...

    @abstractmethod
    async def read_file(self, container_id: str, path: str) -> str:
        ...

    @abstractmethod
    async def write_file(self, container_id: str, path: str, content: str):
        ...

    @abstractmethod
    async def setup(self, container_id: str, commands: list[str]):
        ...

    @abstractmethod
    async def stop(self, container_id: str):
        ...