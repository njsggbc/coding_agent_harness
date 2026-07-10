# Task 8 Report: Context Builder

**Status:** Complete

## Files
- Created: `harness/core/context.py` (34 lines)
- Created: `tests/core/test_context.py` (37 lines)

## Implementation
- `build_context(sandbox: Sandbox, task: TaskConfig) -> str` — async function that builds a Markdown context string for the agent prompt
- Collects: repository file listing (find), recent git commits (git log), and task metadata
- Handles edge case: empty repository (shows "(empty repository)") and no recent commits (omits section)

## Test
- `test_build_context_includes_repo_summary` — uses `FakeContextSandbox` that returns canned responses for find and git log commands
- Verifies task description, file listing, and commit hashes appear in the output

## Verification
```
pytest tests/core/test_context.py -v  # PASSED
pytest -v                              # 47 passed, 6 skipped (all good)
```

## Commit
```
525d5e4 feat: add repository context builder for agent prompts
```

## Self-Review
- [x] Implementation matches task brief exactly
- [x] Test passes
- [x] No regressions in full suite
- [x] Commit message follows conventional format