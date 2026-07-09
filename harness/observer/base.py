from dataclasses import dataclass, field
from typing import Callable, Any


@dataclass
class TurnStart:
    turn_number: int


@dataclass
class ToolCallStart:
    tool_name: str
    args: dict


@dataclass
class ToolCallEnd:
    tool_name: str
    result: str
    duration: float


@dataclass
class AgentThinking:
    content: str


@dataclass
class LoopError:
    error: str


@dataclass
class LoopComplete:
    status: str
    turns: int
    tokens_used: int


@dataclass
class SandboxEvent:
    message: str


class Observer:
    def __init__(self):
        self._handlers: list[Callable] = []

    def subscribe(self, handler: Callable):
        self._handlers.append(handler)

    def unsubscribe(self, handler: Callable):
        self._handlers.remove(handler)

    def emit(self, event):
        for handler in self._handlers:
            try:
                handler(event)
            except Exception:
                pass