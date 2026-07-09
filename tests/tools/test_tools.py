import pytest
import os
from harness.tools.files import ReadFileTool, WriteFileTool, EditFileTool
from harness.tools.shell import RunShellTool
from harness.tools.search import SearchContentTool, SearchFilesTool
from harness.tools.git import GitDiffTool, GitLogTool, ListDirTool
from harness.tools.registry import ToolResult

CID = "test-container"


class FakeSandbox:
    def __init__(self):
        self.files = {}
        self.commands = []

    async def read_file(self, container_id, path):
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    async def write_file(self, container_id, path, content):
        self.files[path] = content

    async def exec(self, container_id, command, workdir=None):
        self.commands.append(command)
        from harness.sandbox.base import ExecResult
        return ExecResult(exit_code=0, stdout="", stderr="")


@pytest.mark.asyncio
async def test_read_file():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "print('hello')"
    tool = ReadFileTool()

    result = await tool.execute({"path": "/ws/test.py"}, sandbox, CID)
    assert result.success
    assert "print('hello')" in result.output


@pytest.mark.asyncio
async def test_read_file_with_offset_limit():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "line1\nline2\nline3\nline4\n"
    tool = ReadFileTool()

    result = await tool.execute({"path": "/ws/test.py", "offset": 2, "limit": 2}, sandbox, CID)
    assert result.success
    assert "line2" in result.output
    assert "line3" in result.output
    assert "line4" not in result.output


@pytest.mark.asyncio
async def test_write_file():
    sandbox = FakeSandbox()
    tool = WriteFileTool()

    result = await tool.execute({"path": "/ws/new.py", "content": "x = 1"}, sandbox, CID)
    assert result.success
    assert sandbox.files["/ws/new.py"] == "x = 1"


@pytest.mark.asyncio
async def test_edit_file():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "old content here"
    tool = EditFileTool()

    result = await tool.execute(
        {"path": "/ws/test.py", "old_str": "old content", "new_str": "new content"},
        sandbox,
        CID,
    )
    assert result.success
    assert sandbox.files["/ws/test.py"] == "new content here"


@pytest.mark.asyncio
async def test_edit_file_not_found():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "different content"
    tool = EditFileTool()

    result = await tool.execute(
        {"path": "/ws/test.py", "old_str": "not in file", "new_str": "replacement"},
        sandbox,
        CID,
    )
    assert not result.success


@pytest.mark.asyncio
async def test_run_shell():
    sandbox = FakeSandbox()
    tool = RunShellTool()

    result = await tool.execute({"command": "ls -la"}, sandbox, CID)
    assert result.success
    assert "ls -la" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_search_content():
    sandbox = FakeSandbox()
    tool = SearchContentTool()

    result = await tool.execute({"pattern": "TODO", "path": "/ws"}, sandbox, CID)
    assert result.success
    assert "grep" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_search_files():
    sandbox = FakeSandbox()
    tool = SearchFilesTool()

    result = await tool.execute({"pattern": "*.py", "path": "/ws"}, sandbox, CID)
    assert result.success
    assert "find" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_git_diff():
    sandbox = FakeSandbox()
    tool = GitDiffTool()

    result = await tool.execute({}, sandbox, CID)
    assert result.success
    assert "git diff" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_git_log():
    sandbox = FakeSandbox()
    tool = GitLogTool()

    result = await tool.execute({"count": 5}, sandbox, CID)
    assert result.success
    assert "git log" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_list_dir():
    sandbox = FakeSandbox()
    tool = ListDirTool()

    result = await tool.execute({"path": "/ws"}, sandbox, CID)
    assert result.success
    assert "ls" in sandbox.commands[0]