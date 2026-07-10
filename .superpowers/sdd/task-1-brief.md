### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `config.yaml`
- Create: `harness/__init__.py`
- Create: `harness/core/__init__.py`
- Create: `harness/adapters/__init__.py`
- Create: `harness/tools/__init__.py`
- Create: `harness/sandbox/__init__.py`
- Create: `harness/storage/__init__.py`
- Create: `harness/observer/__init__.py`
- Create: `harness/report/__init__.py`
- Create: `harness/cli/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `tasks/.gitkeep`
- Create: `reports/.gitkeep`
- Create: `data/.gitkeep`
- Create: `.gitignore`

**Interfaces:**
- Consumes: nothing
- Produces: project structure, `pyproject.toml` with all dependencies, `config.yaml` template

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "harness"
version = "0.1.0"
description = "Coding Agent Harness - Bug-fixing agent orchestration framework"
requires-python = ">=3.11"
dependencies = [
    "openai>=1.0.0",
    "docker>=7.0.0",
    "click>=8.1.0",
    "pyyaml>=6.0",
    "gitpython>=3.1.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[project.scripts]
harness = "harness.cli.main:cli"
```

- [ ] **Step 2: Create config.yaml**

```yaml
defaults:
  model: "gpt-4o"
  max_turns: 30
  temperature: 0.0

storage:
  data_dir: "./data"

docker:
  default_image: "python:3.11"

api:
  openai_api_key: "${OPENAI_API_KEY}"

logging:
  level: "INFO"
  file: "harness.log"
```

- [ ] **Step 3: Create conftest.py**

```python
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
```

- [ ] **Step 4: Create all __init__.py files (empty)**

- [ ] **Step 5: Create .gitignore**

```
__pycache__/
*.pyc
data/
.env
*.egg-info/
dist/
build/
```

- [ ] **Step 6: Create .gitkeep files for tasks/, reports/, data/**

- [ ] **Step 7: Install dependencies and verify**

```bash
pip install -e ".[dev]"
```

Expected: all packages install without error

- [ ] **Step 8: Run a smoke test**

```python
# tests/test_scaffolding.py
def test_imports():
    import harness
    from harness.core import task
    from harness.adapters import base
    from harness.tools import registry
    from harness.sandbox import base as sandbox_base
    from harness.storage import db
    from harness.observer import base as observer_base
    from harness.report import generator
    from harness.cli import main
```

```bash
pytest tests/test_scaffolding.py -v
```

Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: scaffold project structure and dependencies"
```

---

