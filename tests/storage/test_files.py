import json
from harness.storage.files import FileStore


def test_save_and_load_messages(temp_dir):
    store = FileStore(str(temp_dir))
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Fix the bug."},
    ]

    store.save_messages("task-001", messages)
    loaded = store.load_messages("task-001")

    assert loaded == messages


def test_save_and_load_diff(temp_dir):
    store = FileStore(str(temp_dir))
    diff = "diff --git a/file.py b/file.py\n+ fixed line"

    store.save_diff("task-001", diff)
    loaded = store.load_diff("task-001")

    assert loaded == diff


def test_save_tool_calls(temp_dir):
    store = FileStore(str(temp_dir))
    calls = [
        {"turn": 1, "tool": "read_file", "args": {"path": "test.py"}, "result": "content"},
        {"turn": 1, "tool": "edit_file", "args": {"path": "test.py"}, "result": "edited"},
    ]

    store.save_tool_calls("task-001", calls)
    task_dir = temp_dir / "tasks" / "task-001"
    assert (task_dir / "tool_calls.jsonl").exists()


def test_save_agent_log(temp_dir):
    store = FileStore(str(temp_dir))
    events = [
        {"type": "turn_start", "turn": 1},
        {"type": "tool_call", "tool": "read_file"},
    ]

    store.save_agent_log("task-001", events)
    task_dir = temp_dir / "tasks" / "task-001"
    assert (task_dir / "agent.log").exists()