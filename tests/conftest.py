import pytest
import tempfile
import os
from pathlib import Path


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def sample_config_yaml():
    return """
defaults:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

storage:
  data_dir: "./data"

docker:
  default_image: "python:3.11"

api:
  openai_api_key: "test-key"

logging:
  level: "INFO"
  file: "harness.log"
"""
