from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
import yaml


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class EnvironmentConfig:
    image: str
    setup_commands: list[str] = field(default_factory=list)


@dataclass
class AgentConfig:
    model: str
    max_turns: int
    temperature: float


@dataclass
class SandboxConfig:
    workdir: str
    timeout: int
    blocked_commands: list[str] = field(default_factory=list)


@dataclass
class VerificationConfig:
    commands: list[str] = field(default_factory=list)


@dataclass
class TaskConfig:
    id: str
    name: str
    description: str
    repo: str
    branch: str
    environment: EnvironmentConfig
    agent: AgentConfig
    sandbox: SandboxConfig
    base_commit: Optional[str] = None
    verification: Optional[VerificationConfig] = None

    @classmethod
    def from_dict(cls, data: dict) -> "TaskConfig":
        env = EnvironmentConfig(
            image=data["environment"]["image"],
            setup_commands=data["environment"].get("setup_commands", []),
        )
        agent = AgentConfig(
            model=data["agent"]["model"],
            max_turns=data["agent"]["max_turns"],
            temperature=data["agent"]["temperature"],
        )
        sandbox = SandboxConfig(
            workdir=data["sandbox"]["workdir"],
            timeout=data["sandbox"]["timeout"],
            blocked_commands=data["sandbox"].get("blocked_commands", []),
        )
        verification = None
        if "verification" in data and data["verification"] is not None:
            verification = VerificationConfig(
                commands=data["verification"].get("commands", [])
            )

        return cls(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            repo=data["repo"],
            branch=data["branch"],
            base_commit=data.get("base_commit"),
            environment=env,
            agent=agent,
            sandbox=sandbox,
            verification=verification,
        )


def load_task_config(path: str) -> TaskConfig:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return TaskConfig.from_dict(data)