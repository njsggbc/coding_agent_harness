### Task 8: Context Builder

**Files:**
- Create: `harness/core/context.py`
- Test: `tests/core/test_context.py`

**Interfaces:**
- Consumes: `Sandbox` from `harness.sandbox.base`
- Produces: `build_context(sandbox: Sandbox, task: TaskConfig) -> str` async function

- [ ] **Step 1: Write failing test**

```python
# tests/core/test_context.py
import pytest
from harness.core.context import build_context
from harness.core.task import TaskConfig, EnvironmentConfig, AgentConfig, SandboxConfig
from harness.sandbox.base import ExecResult


class FakeContextSandbox:
    async def exec(self, container_id, command, workdir=None):
        if "find" in command and "-type f" in command:
            return ExecResult(exit_code=0, stdout="src/main.py\nsrc/utils.py\ntests/test_main.py\n", stderr="")
        if "git log" in command:
            return ExecResult(exit_code=0, stdout="abc1234 Fix login bug\ndef5678 Add feature X\n", stderr="")
        if "tree" in command:
            return ExecResult(exit_code=0, stdout="src/\n  main.py\n  utils.py\ntests/\n  test_main.py\n", stderr="")
        return ExecResult(exit_code=0, stdout="", stderr="")


@pytest.mark.asyncio
async def test_build_context_includes_repo_summary():
    task = TaskConfig(
        id="bug-001",
        name="test",
        description="Fix the login bug in auth module",
        repo="https://github.com/test/repo",
        branch="main",
        environment=EnvironmentConfig(image="python:3.11", setup_commands=[]),
        agent=AgentConfig(model="gpt-4o", max_turns=10, temperature=0.0),
        sandbox=SandboxConfig(workdir="/ws", timeout=300, blocked_commands=[]),
    )

    sandbox = FakeContextSandbox()
    context = await build_context(sandbox, task)

    assert "Fix the login bug in auth module" in context
    assert "src/main.py" in context
    assert "src/utils.py" in context
    assert "abc1234" in context
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/core/test_context.py -v
```

Expected: FAIL

- [ ] **Step 3: Write context.py**

```python
# harness/core/context.py
from harness.core.task import TaskConfig
from harness.sandbox.base import Sandbox


async def build_context(sandbox: Sandbox, task: TaskConfig) -> str:
    parts = []

    result = await sandbox.exec("", f"find . -type f -not -path './.git/*' | head -100")
    file_list = result.stdout.strip()

    result = await sandbox.exec("", "git log --oneline -5")
    recent_commits = result.stdout.strip()

    parts.append("## Repository Structure")
    parts.append("```")
    if file_list:
        parts.append(file_list)
    else:
        parts.append("(empty repository)")
    parts.append("```")

    if recent_commits:
        parts.append("\n## Recent Commits")
        parts.append("```")
        parts.append(recent_commits)
        parts.append("```")

    parts.append(f"\n## Task")
    parts.append(f"**Title:** {task.name}")
    parts.append(f"**Description:** {task.description}")
    parts.append(f"**Repository:** {task.repo}")
    parts.append(f"**Branch:** {task.branch}")

    return "\n".join(parts)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/core/test_context.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add harness/core/context.py tests/core/test_context.py
git commit -m "feat: add repository context builder for agent prompts"
```

---

