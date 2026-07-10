import json
import os
from pathlib import Path


class FileStore:
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        self.tasks_dir = self.data_dir / "tasks"

    def _task_dir(self, task_id: str) -> Path:
        d = self.tasks_dir / task_id
        d.mkdir(parents=True, exist_ok=True)
        return d

    def save_messages(self, task_id: str, messages: list[dict]):
        path = self._task_dir(task_id) / "messages.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")

    def load_messages(self, task_id: str) -> list[dict]:
        path = self._task_dir(task_id) / "messages.jsonl"
        if not path.exists():
            return []
        messages = []
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(json.loads(line))
        return messages

    def save_tool_calls(self, task_id: str, calls: list[dict]):
        path = self._task_dir(task_id) / "tool_calls.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for call in calls:
                f.write(json.dumps(call, ensure_ascii=False) + "\n")

    def save_diff(self, task_id: str, diff: str):
        path = self._task_dir(task_id) / "diff.patch"
        with open(path, "w", encoding="utf-8") as f:
            f.write(diff)

    def load_diff(self, task_id: str) -> str:
        path = self._task_dir(task_id) / "diff.patch"
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def save_agent_log(self, task_id: str, events: list[dict]):
        path = self._task_dir(task_id) / "agent.log"
        with open(path, "w", encoding="utf-8") as f:
            for event in events:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")