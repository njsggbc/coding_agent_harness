### Task 11: Report Generator — DONE

**Commit:** 567da73

**Files changed:**
- `harness/report/generator.py` — 67 lines (implementation)
- `tests/report/test_generator.py` — 95 lines (5 tests)
- `tests/report/__init__.py` — empty

**TDD:**
- RED: ImportError (ReportGenerator not found) — confirmed
- GREEN: All 5 tests pass + full suite (59 passed, 6 skipped)

**Self-review:**
- `ReportGenerator` consumes `TaskStore` and `FileStore` as specified
- `generate(task_id)` returns full dict with all task fields + diff + messages
- `format_summary` produces human-readable text with diff and error if present
- `format_verbose` extends summary with message conversation
- `format_json` returns indented JSON string
- Raises `ValueError` for nonexistent tasks
- No deviations from the brief