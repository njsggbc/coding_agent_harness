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
        required_fields = ["id", "name", "description", "repo", "branch", "environment", "agent", "sandbox"]
        for field in required_fields:
            if field not in data:
                raise KeyError(f"Missing required field: '{field}'")

        if not isinstance(data.get("environment"), dict):
            raise KeyError("'environment' section must be a dictionary")
        if not isinstance(data.get("agent"), dict):
            raise KeyError("'agent' section must be a dictionary")
        if not isinstance(data.get("sandbox"), dict):
            raise KeyError("'sandbox' section must be a dictionary")

        env_data = data["environment"]
        if "image" not in env_data:
            raise KeyError("Missing required field: 'environment.image'")

        agent_data = data["agent"]
        for field in ["model", "max_turns", "temperature"]:
            if field not in agent_data:
                raise KeyError(f"Missing required field: 'agent.{field}'")

        sandbox_data = data["sandbox"]
        for field in ["workdir", "timeout"]:
            if field not in sandbox_data:
                raise KeyError(f"Missing required field: 'sandbox.{field}'")

        env = EnvironmentConfig(
            image=env_data["image"],
            setup_commands=env_data.get("setup_commands", []),
        )
        agent = AgentConfig(
            model=agent_data["model"],
            max_turns=agent_data["max_turns"],
            temperature=agent_data["temperature"],
        )
        sandbox = SandboxConfig(
            workdir=sandbox_data["workdir"],
            timeout=sandbox_data["timeout"],
            blocked_commands=sandbox_data.get("blocked_commands", []),
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

    @classmethod
    def from_yaml(cls, path: str) -> "TaskConfig":
        return load_task_config(path)


def load_task_config(path: str) -> TaskConfig:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise FileNotFoundError(f"Task config file not found: {path}")
    except yaml.YAMLError as e:
        raise yaml.YAMLError(f"Invalid YAML in task config: {path}\n{e}")

    if data is None:
        raise ValueError(f"Task config file is empty: {path}")
    if not isinstance(data, dict):
        raise ValueError(f"Task config must be a YAML mapping, got {type(data).__name__}: {path}")

    try:
        return TaskConfig.from_dict(data)
    except KeyError as e:
        raise KeyError(f"Invalid task config in {path}: {e}")