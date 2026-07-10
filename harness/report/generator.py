import json
from harness.storage.db import TaskStore
from harness.storage.files import FileStore


class ReportGenerator:
    def __init__(self, task_store: TaskStore, file_store: FileStore):
        self.task_store = task_store
        self.file_store = file_store

    def generate(self, task_id: str) -> dict:
        record = self.task_store.get(task_id)
        if record is None:
            raise ValueError(f"Task {task_id} not found")

        diff = self.file_store.load_diff(task_id)
        messages = self.file_store.load_messages(task_id)

        return {
            "id": record["id"],
            "name": record["name"],
            "status": record["status"],
            "repo": record["repo"],
            "branch": record["branch"],
            "model": record["model"],
            "created_at": record["created_at"],
            "started_at": record["started_at"],
            "finished_at": record["finished_at"],
            "turns": record["turns"],
            "tokens_used": record["tokens_used"],
            "error": record["error"],
            "diff": diff,
            "messages": messages,
        }

    def format_summary(self, task_id: str) -> str:
        report = self.generate(task_id)
        lines = [
            f"Task: {report['id']} - {report['name']}",
            f"Status: {report['status']}",
            f"Agent: {report['model']}",
            f"Turns: {report['turns']} turns",
            f"Tokens: {report['tokens_used']} tokens",
            f"Repo: {report['repo']} ({report['branch']})",
            "",
        ]
        if report["diff"]:
            lines.append("Diff:")
            lines.append(report["diff"])
        if report["error"]:
            lines.append(f"Error: {report['error']}")
        return "\n".join(lines)

    def format_verbose(self, task_id: str) -> str:
        report = self.generate(task_id)
        text = self.format_summary(task_id)
        text += "\n\n--- Messages ---\n\n"
        for msg in report.get("messages", []):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                text += f"[{role}]: {content[:500]}\n\n"
        return text

    def format_json(self, task_id: str) -> str:
        report = self.generate(task_id)
        return json.dumps(report, ensure_ascii=False, indent=2)