# Task 4 Report: Sandbox Layer

## Status: DONE_WITH_CONCERNS

## TDD Evidence

### RED Phase - Guard Tests (Step 3)
```
pytest tests/sandbox/test_guard.py -v
ERROR collecting tests/sandbox/test_guard.py - ModuleNotFoundError: No module named 'harness.sandbox.guard'
```
guard.py did not exist yet — expected RED.

### GREEN Phase - Guard Tests (Step 5)
```
tests/sandbox/test_guard.py::test_guard_allows_safe_command PASSED
tests/sandbox/test_guard.py::test_guard_blocks_dangerous_command PASSED
tests/sandbox/test_guard.py::test_guard_blocks_dangerous_command_in_subcommand PASSED
tests/sandbox/test_guard.py::test_guard_ignores_non_shell_tools PASSED
tests/sandbox/test_guard.py::test_guard_with_empty_blocked_list PASSED
5 passed in 0.02s
```

### RED Phase - Docker Tests (Step 7)
```
ERROR collecting tests/sandbox/test_docker.py - ModuleNotFoundError: No module named 'harness.sandbox.docker'
```
docker.py did not exist yet — expected RED.

### GREEN Phase - Docker Tests (Step 9)
```
tests/sandbox/test_docker.py::test_create_and_stop_container SKIPPED
tests/sandbox/test_docker.py::test_exec_command SKIPPED
tests/sandbox/test_docker.py::test_read_write_file SKIPPED
tests/sandbox/test_docker.py::test_setup_commands SKIPPED
4 skipped (Docker not available on this Windows machine)
```
All 4 docker tests skip gracefully when Docker is unavailable. The skip logic works correctly.

### Final Run (All Sandbox Tests)
```
tests/sandbox/test_guard.py - 5 passed
tests/sandbox/test_docker.py - 4 skipped
5 passed, 4 skipped in 0.06s
```

## Commit
```
0711776 feat: add sandbox layer with Docker, Guard, and abstract interface
5 files changed, 237 insertions(+)
  create mode 100644 harness/sandbox/docker.py
  create mode 100644 harness/sandbox/guard.py
  create mode 100644 tests/sandbox/test_docker.py
  create mode 100644 tests/sandbox/test_guard.py
```

## Files Created/Modified
- `harness/sandbox/base.py` — ExecResult dataclass + Sandbox ABC (overwrote empty placeholder)
- `harness/sandbox/guard.py` — CommandGuard with GuardBlockedError
- `harness/sandbox/docker.py` — DockerSandbox implementation
- `tests/sandbox/test_guard.py` — 5 guard tests
- `tests/sandbox/test_docker.py` — 4 docker tests

## Concerns

### Docker write_file escape issue
The `write_file` method in `harness/sandbox/docker.py:44` uses a heredoc approach:
```python
escaped = content.replace("'", "'\\''")
result = await self.exec(container_id, f"cat > '{path}' << 'EOF'\n{escaped}\nEOF")
```

**Issue**: If the file content contains `EOF` on its own line, the heredoc terminates early, producing a truncated/corrupted file. This is a data integrity bug.

**Recommended fix**: Use base64 encoding for safe content transfer:
```python
import base64
encoded = base64.b64encode(content.encode()).decode()
result = await self.exec(container_id, f"echo '{encoded}' | base64 -d > '{path}'")
```

Alternatively, use `docker cp` or write a small Python script in the container to handle file writes, which would avoid shell escaping issues entirely.

### Docker not available for testing
The 4 Docker integration tests could not be run on this Windows machine because Docker Desktop is not installed/configured. The tests correctly skip with `pytest.skip("Docker not available")`. These should be verified on a machine with Docker before merging.

---

## Review Fixes Applied

### Critical
1. **write_file heredoc EOF injection** — replaced with base64 encoding: `echo <base64> | base64 -d > <path>`
2. **read_file path injection** — replaced `cat '{path}'` with `cat {shlex.quote(path)}`
3. **write_file path injection** — replaced `'{path}'` with `shlex.quote(path)`

### Important
4. **exec stderr always empty** — added `demux=True` to `exec_run` and properly extract stderr from the result tuple
5. **Unused import** — removed `from docker.models.containers import Container`
6. **setup ignores exit codes** — now raises `RuntimeError` with stdout/stderr when a setup command fails

### Final Test Run
```
tests/sandbox/test_guard.py - 5 passed
tests/sandbox/test_docker.py - 4 skipped
5 passed, 4 skipped in 0.06s
```

### Fix Commit
```
fix: address Task 4 review findings
```