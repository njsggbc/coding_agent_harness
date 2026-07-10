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
name: "修复登录超时"
description: "修复 session 过期问题"
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


def test_load_task_config(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(SAMPLE_TASK_YAML, encoding="utf-8")

    config = load_task_config(str(task_file))

    assert config.id == "bug-123"
    assert config.name == "修复登录超时"
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
    task_file.write_text(yaml_content, encoding="utf-8")

    config = load_task_config(str(task_file))

    assert config.base_commit is None
    assert config.verification is None


def test_task_status_enum():
    assert TaskStatus.PENDING.value == "pending"
    assert TaskStatus.RUNNING.value == "running"
    assert TaskStatus.DONE.value == "done"
    assert TaskStatus.FAILED.value == "failed"
    assert TaskStatus.CANCELLED.value == "cancelled"


def test_from_yaml_classmethod(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text(SAMPLE_TASK_YAML, encoding="utf-8")

    config = TaskConfig.from_yaml(str(task_file))

    assert config.id == "bug-123"
    assert config.name == "修复登录超时"


def test_load_task_config_file_not_found():
    with pytest.raises(FileNotFoundError, match="Task config file not found"):
        load_task_config("nonexistent.yaml")


def test_load_task_config_invalid_yaml(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text("id: [unclosed\n", encoding="utf-8")

    with pytest.raises(yaml.YAMLError, match="Invalid YAML in task config"):
        load_task_config(str(task_file))


def test_load_task_config_empty_file(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text("", encoding="utf-8")

    with pytest.raises(ValueError, match="Task config file is empty"):
        load_task_config(str(task_file))


def test_load_task_config_not_a_mapping(tmp_path):
    task_file = tmp_path / "task.yaml"
    task_file.write_text("- item1\n- item2\n", encoding="utf-8")

    with pytest.raises(ValueError, match="Task config must be a YAML mapping"):
        load_task_config(str(task_file))


def test_from_dict_missing_required_field():
    with pytest.raises(KeyError, match="Missing required field: 'id'"):
        TaskConfig.from_dict({"name": "test"})


def test_from_dict_missing_nested_section():
    with pytest.raises(KeyError, match="Missing required field: 'environment'"):
        TaskConfig.from_dict({
            "id": "t1",
            "name": "test",
            "description": "desc",
            "repo": "r",
            "branch": "b",
            "agent": {},
            "sandbox": {},
        })


def test_from_dict_missing_nested_field():
    with pytest.raises(KeyError, match="Missing required field: 'agent.model'"):
        TaskConfig.from_dict({
            "id": "t1",
            "name": "test",
            "description": "desc",
            "repo": "r",
            "branch": "b",
            "environment": {"image": "img"},
            "agent": {},
            "sandbox": {"workdir": "/w", "timeout": 30},
        })