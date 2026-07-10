# Final Review Fix Report

## Summary

Addressed all 5 Critical and 3 Important issues from the whole-branch final code review.

## Critical Issues Fixed

### 1. container_id not threaded through tool execution chain ✅
**Affected files:** `harness/core/agent_loop.py`, `harness/tools/*.py`, `harness/core/context.py`

**Changes:**
- Added `container_id: str` parameter to `Tool.execute()` abstract method in `harness/tools/registry.py:31`
- Updated all 9 tool implementations (`files.py`, `shell.py`, `search.py`, `git.py`) to accept and use `container_id` instead of hardcoded `""`
- Updated `build_context()` in `harness/core/context.py` to accept `container_id` parameter
- Updated `AgentLoop` to pass `self.container_id` to both `build_context()` and `tool.execute()` calls
- Updated all test fakes and test calls to match new signatures

### 2. No OpenAI API retry/rate-limit handling ✅
**Affected file:** `harness/adapters/openai.py`

**Changes:**
- Added 3 retries with exponential backoff (1s, 2s, 4s)
- Handles `RateLimitError` with `Retry-After` header detection
- Handles `APITimeoutError`, `APIConnectionError` (transient errors)
- Handles `APIStatusError` with status >= 500 (server errors)
- Non-retryable errors (4xx client errors) raised immediately

### 3. Cancel command doesn't actually stop running tasks ✅
**Affected files:** `harness/cli/main.py`, `harness/core/task_manager.py`, `harness/core/agent_loop.py`

**Changes:**
- Added `cancel_event: asyncio.Event` to `AgentLoop` - checked at top of each turn loop
- Added `_cancel_events` dict to `TaskManager` to track running tasks
- `TaskManager.cancel()` now sets the event to signal the running task
- AgentLoop catches `asyncio.CancelledError` and returns a "cancelled" result
- Added SIGINT/SIGTERM + KeyboardInterrupt handling in CLI `run` command
- CLI uses `asyncio.new_event_loop()` + `run_until_complete()` instead of `asyncio.run()` for proper signal handling

### 4. No task total timeout ✅
**Affected file:** `harness/core/task_manager.py`

**Changes:**
- Wrapped `loop.run(task)` with `asyncio.wait_for(..., timeout=task.sandbox.timeout)` at `task_manager.py:88`
- `asyncio.TimeoutError` caught and translated to a failed `LoopResult`

### 5. No tool execution timeout ✅
**Affected file:** `harness/core/agent_loop.py`

**Changes:**
- Added `TOOL_TIMEOUT = 30` constant
- Wrapped `tool.execute()` with `asyncio.wait_for(..., timeout=TOOL_TIMEOUT)`
- `asyncio.TimeoutError` caught and returned as a failed `ToolResult`

## Important Issues Fixed

### 6. setup_commands failure should continue, not raise ✅
**Affected file:** `harness/sandbox/docker.py`

**Changes:**
- `DockerSandbox.setup()` now logs a warning instead of raising `RuntimeError` when a setup command fails
- Added `logging` import and `logger` instance

### 7. Run verification commands after agent loop completes ✅
**Affected file:** `harness/core/task_manager.py`

**Changes:**
- Added `_run_verification()` method to `TaskManager`
- Called after agent loop completes, before updating status
- Iterates over `task.verification.commands`, logs exit code, stdout, and stderr for each
- Verification failures are logged but do not change the task result status

### 8. Add Ctrl+C signal handling for graceful shutdown ✅
**Affected file:** `harness/cli/main.py`

**Changes:**
- Added `signal` import
- CLI `run` command now uses explicit event loop with signal handlers
- On Windows: uses `signal.signal()` handlers
- On Unix: uses `loop.add_signal_handler()` for SIGINT and SIGTERM
- Signal handler calls `manager.cancel(task.id)` to set the cancel event, then cancels the asyncio task
- `asyncio.CancelledError` and `KeyboardInterrupt` caught gracefully

## Test Results

```
69 passed, 6 skipped in 3.34s
```

6 skipped:
- 2 OpenAI adapter tests (require `OPENAI_API_KEY` env var)
- 4 Docker sandbox tests (require Docker daemon)