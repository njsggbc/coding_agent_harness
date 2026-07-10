import sqlite3
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional
from harness.core.task import TaskConfig, TaskStatus


class TaskStore:
    def __init__(self, data_dir: str):
        self.db_path = os.path.join(data_dir, "harness.db")
        os.makedirs(data_dir, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id          TEXT PRIMARY KEY,
                    name        TEXT NOT NULL,
                    status      TEXT NOT NULL DEFAULT 'pending',
                    repo        TEXT NOT NULL,
                    branch      TEXT NOT NULL,
                    model       TEXT NOT NULL,
                    created_at  TEXT NOT NULL,
                    started_at  TEXT,
                    finished_at TEXT,
                    duration_ms INTEGER,
                    turns       INTEGER,
                    tokens_used INTEGER,
                    error       TEXT,
                    task_file   TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tool_calls (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id     TEXT NOT NULL,
                    turn_number INTEGER NOT NULL,
                    tool_name   TEXT NOT NULL,
                    args        TEXT NOT NULL,
                    result      TEXT,
                    duration_ms INTEGER,
                    success     INTEGER NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)

    def create(self, task: TaskConfig, task_file: str) -> str:
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO tasks (id, name, status, repo, branch, model,
                   created_at, task_file)
                   VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)""",
                (task.id, task.name, task.repo, task.branch, task.agent.model, now, task_file),
            )
        return task.id

    def update_status(self, task_id: str, status: TaskStatus):
        now = datetime.now(timezone.utc).isoformat()
        with self._get_conn() as conn:
            if status == TaskStatus.RUNNING:
                conn.execute(
                    "UPDATE tasks SET status = ?, started_at = ? WHERE id = ?",
                    (status.value, now, task_id),
                )
            elif status in (TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED):
                conn.execute(
                    "UPDATE tasks SET status = ?, finished_at = ? WHERE id = ?",
                    (status.value, now, task_id),
                )
            else:
                conn.execute(
                    "UPDATE tasks SET status = ? WHERE id = ?",
                    (status.value, task_id),
                )

    def update_result(self, task_id: str, turns: int, tokens_used: int, error: Optional[str] = None):
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE tasks SET turns = ?, tokens_used = ?, error = ? WHERE id = ?",
                (turns, tokens_used, error, task_id),
            )

    def get(self, task_id: str) -> Optional[dict]:
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return None
            return dict(row)

    def list_all(self, status: Optional[str] = None) -> list[dict]:
        with self._get_conn() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]