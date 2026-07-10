### Task 2: Task Model

**Files:**
- Create: `harness/core/task.py`
- Test: `tests/core/test_task.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `TaskConfig` dataclass
  - `EnvironmentConfig` dataclass
  - `AgentConfig` dataclass
  - `SandboxConfig` dataclass
  - `VerificationConfig` dataclass
  - `TaskStatus` enum: `PENDING = "pending"`, `RUNNING = "running"`, `DONE = "done"`, `FAILED = "failed"`, `CANCELLED = "cancelled"`
  - `load_task_config(path: str) -> TaskConfig` function
  - `TaskConfig.from_yaml(path: str) -> TaskConfig` classmethod

- [ ] **Step 1: Write the failing test**

```python
# tests/core/test_task.py
import pytest
import yaml
from pathlib import Path
from harness.core.task import (
    TaskConfig,
    EnvironmentConfig,
    AgentConfig,
    SandboxConfig,
    VerificationConfig,
    TaskStatus,
    load_task_config,
)


SAMPLE_TASK_YAML = """
id: "bug-123"
name: "淇鐧诲綍瓒呮椂"
description: "淇 session 杩囨湡闂"
repo: "https://github.com/example/repo"
branch: "main"
base_commit: "abc1234"

environment:
  image: "python:3.11"
  setup_commands:
    - "pip install -r requirements.txt"

agent:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

sandbox:
  workdir: "/workspace"
  timeout: 600
  blocked_commands:
    - "rm -rf /"

verification:
  commands:
    - "pytest tests/"
"""


def test_task_config_from_yaml(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(SAMPLE_TASK_YAML)

    config = load_task_config(str(task_file))

    assert config.id == "bug-123"
    assert config.name == "淇鐧诲綍瓒呮椂"
    assert config.repo == "https://github.com/example/repo"
    assert config.branch == "main"
    assert config.base_commit == "abc1234"

    assert config.environment.image == "python:3.11"
    assert config.environment.setup_commands == ["pip install -r requirements.txt"]

    assert config.agent.model == "gpt-4o"
    assert config.agent.max_turns == 30
    assert config.agent.temperature == 0.0

    assert config.sandbox.workdir == "/workspace"
    assert config.sandbox.timeout == 600
    assert config.sandbox.blocked_commands == ["rm -rf /"]

    assert config.verification.commands == ["pytest tests/"]


def test_task_config_without_optional_fields(tmp_path):
    yaml_content = """
id: "bug-456"
name: "simple bug"
description: "simple desc"
repo: "https://github.com/example/repo"
branch: "main"

environment:
  image: "python:3.11"
  setup_commands: []

agent:
  model: "gpt-4o"
  max_turns: 10
  temperature: 0.0

sandbox:
  workdir: "/workspace"
  timeout: 300
  blocked_commands: []
"""
    task_file = tmp_path / "task.yaml"
    task_file.write_text(yaml_content)

    config = load_task_config(str(task_file))

    assert config.base_commit is None
    assert config.verification is None


def test_task_status_enum():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_task.py -v
```

Expected: FAIL with import errors

- [ ] **Step 3: Write implementation**

```python
# harness/core/task.py
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_task.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/core/task.py tests/core/test_task.py
git commit -m "feat: add task config model with YAML loader"
```

---

