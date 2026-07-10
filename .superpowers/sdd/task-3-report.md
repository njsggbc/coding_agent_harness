### Task 3 Report: Storage Layer

**Status:** DONE

**Commits:**
- `ae4b31b` feat: add SQLite and file storage layer

**Files created:**
- `harness/storage/db.py` — TaskStore with SQLite backend (TaskStore class)
- `harness/storage/files.py` — FileStore with JSONL/diff file storage (FileStore class)
- `tests/storage/test_db.py` — 5 tests for TaskStore
- `tests/storage/test_files.py` — 4 tests for FileStore

**TDD Evidence:**

**RED phase — test_db.py:**
```
ImportError: cannot import name 'TaskStore' from 'harness.storage.db'
```
**RED phase — test_files.py:**
```
ModuleNotFoundError: No module named 'harness.storage.files'
```

**GREEN phase — full test suite:**
```
21 passed in 0.52s
  - tests/storage/test_db.py: 5 passed
  - tests/storage/test_files.py: 4 passed
  - tests/core/test_task.py: 11 passed
  - tests/test_scaffolding.py: 1 passed
```

**Implementation notes:**
- Used `@contextmanager` for `_get_conn()` to properly close SQLite connections on Windows (prevents file-locking during temp dir cleanup)
- Added explicit `conn.commit()` in the context manager since `sqlite3.Connection.__exit__` is not called when wrapped in a custom context manager

**Test coverage:**
- TaskStore: create, get, update_status, update_result, list_all (with status filter), get nonexistent
- FileStore: save/load messages, save/load diff, save tool_calls, save agent_log