from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from harness.sandbox.base import Sandbox


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        ...

    @abstractmethod
    async def execute(self, args: dict, sandbox: Sandbox, container_id: str) -> ToolResult:
        ...


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_schema(self) -> list[dict]:
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas