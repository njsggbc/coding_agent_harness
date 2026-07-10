import json
import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class MemoryEntry:
    key: str
    value: str
    category: str
    timestamp: str


class MemoryStore:
    def __init__(self, data_dir: str):
        self.memory_dir = Path(data_dir) / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

    def _project_file(self, repo_url: str) -> Path:
        project_hash = hashlib.sha256(repo_url.encode()).hexdigest()[:16]
        return self.memory_dir / f"{project_hash}.json"

    def _load(self, repo_url: str) -> dict[str, MemoryEntry]:
        path = self._project_file(repo_url)
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return {k: MemoryEntry(**v) for k, v in raw.items()}

    def _save(self, repo_url: str, data: dict[str, MemoryEntry]):
        path = self._project_file(repo_url)
        raw = {k: {"key": v.key, "value": v.value, "category": v.category, "timestamp": v.timestamp} for k, v in data.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(raw, f, indent=2)

    def add(self, repo_url: str, key: str, value: str, category: str = "note"):
        data = self._load(repo_url)
        timestamp = datetime.now(timezone.utc).isoformat()
        data[key] = MemoryEntry(key=key, value=value, category=category, timestamp=timestamp)
        self._save(repo_url, data)

    def get(self, repo_url: str, key: str) -> Optional[MemoryEntry]:
        data = self._load(repo_url)
        return data.get(key)

    def get_all(self, repo_url: str) -> list[MemoryEntry]:
        data = self._load(repo_url)
        return list(data.values())

    def remove(self, repo_url: str, key: str):
        data = self._load(repo_url)
        data.pop(key, None)
        self._save(repo_url, data)

    def clear(self, repo_url: str):
        path = self._project_file(repo_url)
        if path.exists():
            path.unlink()

    def list_projects(self) -> list[str]:
        if not self.memory_dir.exists():
            return []
        return [p.stem for p in self.memory_dir.glob("*.json")]

    def to_context_string(self, repo_url: str) -> str:
        entries = self.get_all(repo_url)
        if not entries:
            return ""
        lines = ["## Project Memory", ""]
        for entry in entries:
            lines.append(f"- [{entry.category}] {entry.key}: {entry.value}")
        return "\n".join(lines)