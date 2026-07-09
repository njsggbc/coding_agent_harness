import os
import tempfile
import docker
import git
from harness.core.task import TaskConfig, TaskStatus
from harness.core.agent_loop import AgentLoop, LoopResult
from harness.adapters.openai import OpenAIAdapter
from harness.tools.registry import ToolRegistry
from harness.tools.files import ReadFileTool, WriteFileTool, EditFileTool
from harness.tools.shell import RunShellTool
from harness.tools.search import SearchContentTool, SearchFilesTool
from harness.tools.git import GitDiffTool, GitLogTool, ListDirTool
from harness.sandbox.docker import DockerSandbox
from harness.sandbox.guard import CommandGuard
from harness.observer.base import Observer
from harness.storage.db import TaskStore
from harness.storage.files import FileStore


class TaskManager:
    def __init__(
        self,
        task_store: TaskStore,
        file_store: FileStore,
        observer: Observer,
        data_dir: str,
        api_key: str = None,
    ):
        self.task_store = task_store
        self.file_store = file_store
        self.observer = observer
        self.data_dir = data_dir
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")

    async def run(self, task: TaskConfig, task_file: str) -> LoopResult:
        self.task_store.create(task, task_file)
        self.task_store.update_status(task.id, TaskStatus.RUNNING)

        sandbox = None
        container_id = None
        repo_dir = None

        try:
            docker_client = docker.from_env()
            sandbox = DockerSandbox(docker_client)

            repo_dir = tempfile.mkdtemp(prefix="harness_repo_")
            git.Repo.clone_from(task.repo, repo_dir, branch=task.branch)

            container_id = await sandbox.create(
                image=task.environment.image,
                workdir=task.sandbox.workdir,
                repo_path=repo_dir,
            )

            if task.environment.setup_commands:
                await sandbox.setup(container_id, task.environment.setup_commands)

            adapter = OpenAIAdapter(
                model=task.agent.model,
                api_key=self.api_key,
                temperature=task.agent.temperature,
            )

            tools = ToolRegistry()
            tools.register(ReadFileTool())
            tools.register(WriteFileTool())
            tools.register(EditFileTool())
            tools.register(RunShellTool())
            tools.register(SearchContentTool())
            tools.register(SearchFilesTool())
            tools.register(GitDiffTool())
            tools.register(GitLogTool())
            tools.register(ListDirTool())

            guard = CommandGuard(blocked_patterns=task.sandbox.blocked_commands)

            loop = AgentLoop(
                adapter=adapter,
                tools=tools,
                sandbox=sandbox,
                guard=guard,
                observer=self.observer,
                config=task.agent,
                container_id=container_id,
            )

            result = await loop.run(task)

            self.task_store.update_result(
                task.id,
                turns=result.turns,
                tokens_used=result.tokens_used,
                error=result.error,
            )
            self.task_store.update_status(
                task.id,
                TaskStatus.DONE if result.status == "done" else TaskStatus.FAILED,
            )

            self.file_store.save_messages(task.id, result.messages)
            self.file_store.save_tool_calls(task.id, result.tool_calls)
            self.file_store.save_diff(task.id, result.diff)

            return result

        except Exception as e:
            self.task_store.update_result(task.id, turns=0, tokens_used=0, error=str(e))
            self.task_store.update_status(task.id, TaskStatus.FAILED)
            return LoopResult(
                status="failed",
                diff="",
                turns=0,
                tokens_used=0,
                messages=[],
                tool_calls=[],
                error=str(e),
            )
        finally:
            if sandbox and container_id:
                try:
                    await sandbox.stop(container_id)
                except Exception:
                    pass
            if repo_dir:
                import shutil
                shutil.rmtree(repo_dir, ignore_errors=True)

    def cancel(self, task_id: str):
        self.task_store.update_status(task_id, TaskStatus.CANCELLED)

    def get_status(self, task_id: str):
        return self.task_store.get(task_id)

    def list_all(self, status: str = None):
        return self.task_store.list_all(status=status)