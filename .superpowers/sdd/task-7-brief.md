### Task 7: Tool System

**Files:**
- Create: `harness/tools/registry.py`
- Create: `harness/tools/files.py`
- Create: `harness/tools/shell.py`
- Create: `harness/tools/search.py`
- Create: `harness/tools/git.py`
- Test: `tests/tools/test_registry.py`
- Test: `tests/tools/test_tools.py`

**Interfaces:**
- Consumes: `Sandbox` from `harness.sandbox.base`, `CommandGuard` from `harness.sandbox.guard`
- Produces:
  - `ToolResult` dataclass: `success: bool`, `output: str`, `error: Optional[str]`
  - `Tool` ABC: `name: str`, `description: str`, `parameters: dict`, `async execute(args: dict, sandbox: Sandbox) -> ToolResult`
  - `ToolRegistry` class: `register(tool: Tool)`, `get(name: str) -> Tool`, `get_all() -> list[Tool]`, `to_openai_schema() -> list[dict]`
  - Built-in tools: `ReadFileTool`, `WriteFileTool`, `EditFileTool`, `RunShellTool`, `SearchContentTool`, `SearchFilesTool`, `GitDiffTool`, `GitLogTool`, `ListDirTool`

- [ ] **Step 1: Write registry.py**

```python
# harness/tools/registry.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from harness.sandbox.base import Sandbox


@dataclass
class ToolResult:
    success: bool
    output: str
    error: Optional[str] = None


class Tool(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        ...

    @property
    @abstractmethod
    def parameters(self) -> dict:
        ...

    @abstractmethod
    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        ...


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool):
        self._tools[tool.name] = tool

    def unregister(self, name: str):
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def get_all(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_schema(self) -> list[dict]:
        schemas = []
        for tool in self._tools.values():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                },
            })
        return schemas
```

- [ ] **Step 2: Write failing registry test**

```python
# tests/tools/test_registry.py
import pytest
from harness.tools.registry import Tool, ToolResult, ToolRegistry
from harness.sandbox.base import Sandbox


class FakeTool(Tool):
    name = "fake_tool"
    description = "A fake tool for testing"
    parameters = {
        "type": "object",
        "properties": {"arg1": {"type": "string"}},
        "required": ["arg1"],
    }

    async def execute(self, args, sandbox):
        return ToolResult(success=True, output=f"got {args['arg1']}")


def test_register_and_get_tool():
    registry = ToolRegistry()
    tool = FakeTool()
    registry.register(tool)

    assert registry.get("fake_tool") is tool
    assert registry.get("nonexistent") is None


def test_get_all_tools():
    registry = ToolRegistry()
    registry.register(FakeTool())

    tools = registry.get_all()
    assert len(tools) == 1
    assert tools[0].name == "fake_tool"


def test_unregister_tool():
    registry = ToolRegistry()
    registry.register(FakeTool())
    registry.unregister("fake_tool")

    assert registry.get("fake_tool") is None


def test_to_openai_schema():
    registry = ToolRegistry()
    registry.register(FakeTool())

    schemas = registry.to_openai_schema()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "fake_tool"
    assert "parameters" in schemas[0]["function"]
```

- [ ] **Step 3: Run registry test to verify it passes**

```bash
pytest tests/tools/test_registry.py -v
```

Expected: PASS

- [ ] **Step 4: Write failing tools test**

```python
# tests/tools/test_tools.py
import pytest
import os
from harness.tools.files import ReadFileTool, WriteFileTool, EditFileTool
from harness.tools.shell import RunShellTool
from harness.tools.search import SearchContentTool, SearchFilesTool
from harness.tools.git import GitDiffTool, GitLogTool, ListDirTool
from harness.tools.registry import ToolResult


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

    result = await tool.execute({"path": "/ws/test.py"}, sandbox)
    assert result.success
    assert "print('hello')" in result.output


@pytest.mark.asyncio
async def test_read_file_with_offset_limit():
    sandbox = FakeSandbox()
    sandbox.files["/ws/test.py"] = "line1\nline2\nline3\nline4\n"
    tool = ReadFileTool()

    result = await tool.execute({"path": "/ws/test.py", "offset": 2, "limit": 2}, sandbox)
    assert result.success
    assert "line2" in result.output
    assert "line3" in result.output
    assert "line4" not in result.output


@pytest.mark.asyncio
async def test_write_file():
    sandbox = FakeSandbox()
    tool = WriteFileTool()

    result = await tool.execute({"path": "/ws/new.py", "content": "x = 1"}, sandbox)
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
    )
    assert not result.success


@pytest.mark.asyncio
async def test_run_shell():
    sandbox = FakeSandbox()
    tool = RunShellTool()

    result = await tool.execute({"command": "ls -la"}, sandbox)
    assert result.success
    assert "ls -la" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_search_content():
    sandbox = FakeSandbox()
    tool = SearchContentTool()

    result = await tool.execute({"pattern": "TODO", "path": "/ws"}, sandbox)
    assert result.success
    assert "grep" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_search_files():
    sandbox = FakeSandbox()
    tool = SearchFilesTool()

    result = await tool.execute({"pattern": "*.py", "path": "/ws"}, sandbox)
    assert result.success
    assert "find" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_git_diff():
    sandbox = FakeSandbox()
    tool = GitDiffTool()

    result = await tool.execute({}, sandbox)
    assert result.success
    assert "git diff" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_git_log():
    sandbox = FakeSandbox()
    tool = GitLogTool()

    result = await tool.execute({"count": 5}, sandbox)
    assert result.success
    assert "git log" in sandbox.commands[0]


@pytest.mark.asyncio
async def test_list_dir():
    sandbox = FakeSandbox()
    tool = ListDirTool()

    result = await tool.execute({"path": "/ws"}, sandbox)
    assert result.success
    assert "ls" in sandbox.commands[0]
```

- [ ] **Step 5: Run test to verify it fails**

```bash
pytest tests/tools/test_tools.py -v
```

Expected: FAIL with import errors

- [ ] **Step 6: Write files.py**

```python
# harness/tools/files.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read the contents of a file. Use offset and limit for large files."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "offset": {"type": "integer", "description": "Line number to start reading from (1-indexed)"},
            "limit": {"type": "integer", "description": "Maximum number of lines to read"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            content = await sandbox.read_file("", args["path"])
            lines = content.split("\n")
            offset = args.get("offset", 1) - 1
            limit = args.get("limit")
            if limit:
                lines = lines[offset:offset + limit]
            else:
                lines = lines[offset:]
            return ToolResult(success=True, output="\n".join(lines))
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write or overwrite a file with the given content."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "content": {"type": "string", "description": "Content to write"},
        },
        "required": ["path", "content"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            await sandbox.write_file("", args["path"], args["content"])
            return ToolResult(success=True, output=f"File written: {args['path']}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class EditFileTool(Tool):
    name = "edit_file"
    description = "Replace exact string in a file. The old_str must match exactly including whitespace."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the file"},
            "old_str": {"type": "string", "description": "Exact string to replace"},
            "new_str": {"type": "string", "description": "Replacement string"},
        },
        "required": ["path", "old_str", "new_str"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            content = await sandbox.read_file("", args["path"])
            old_str = args["old_str"]
            new_str = args["new_str"]

            if old_str not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"old_str not found in {args['path']}",
                )

            count = content.count(old_str)
            if count > 1:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} matches for old_str. Provide more context to make it unique.",
                )

            new_content = content.replace(old_str, new_str, 1)
            await sandbox.write_file("", args["path"], new_content)
            return ToolResult(success=True, output=f"File edited: {args['path']}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 7: Write shell.py**

```python
# harness/tools/shell.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class RunShellTool(Tool):
    name = "run_shell"
    description = "Execute a shell command in the sandbox. Use for running tests, installing packages, etc."
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to execute"},
            "workdir": {"type": "string", "description": "Working directory for the command"},
        },
        "required": ["command"],
    }

    MAX_OUTPUT = 8000

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", args["command"], workdir=args.get("workdir"))
            output = result.stdout
            if len(output) > self.MAX_OUTPUT:
                output = output[:self.MAX_OUTPUT] + "\n... (output truncated)"

            if result.exit_code != 0:
                return ToolResult(
                    success=False,
                    output=output,
                    error=f"Command exited with code {result.exit_code}",
                )

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 8: Write search.py**

```python
# harness/tools/search.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class SearchContentTool(Tool):
    name = "search_content"
    description = "Search for a regex pattern in file contents. Fast grep-like search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Regex pattern to search for"},
            "path": {"type": "string", "description": "Directory or file path to search in"},
            "include": {"type": "string", "description": "File pattern filter, e.g. '*.py'"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            cmd_parts = ["grep", "-rn", "--include", args.get("include", "*")]
            search_path = args.get("path", ".")
            cmd_parts.extend([args["pattern"], search_path])
            result = await sandbox.exec("", " ".join(cmd_parts))
            return ToolResult(success=True, output=result.stdout or "No matches found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Find files matching a glob pattern. Fast file name search."
    parameters = {
        "type": "object",
        "properties": {
            "pattern": {"type": "string", "description": "Glob pattern, e.g. '**/*.py'"},
            "path": {"type": "string", "description": "Directory to search in"},
        },
        "required": ["pattern"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            search_path = args.get("path", ".")
            result = await sandbox.exec("", f"find {search_path} -name '{args['pattern']}' -type f")
            return ToolResult(success=True, output=result.stdout or "No files found")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 9: Write git.py**

```python
# harness/tools/git.py
from harness.tools.registry import Tool, ToolResult
from harness.sandbox.base import Sandbox


class GitDiffTool(Tool):
    name = "git_diff"
    description = "Show the current git diff of all changes made so far."
    parameters = {
        "type": "object",
        "properties": {},
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", "git diff")
            return ToolResult(success=True, output=result.stdout or "No changes")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class GitLogTool(Tool):
    name = "git_log"
    description = "Show recent git commit history."
    parameters = {
        "type": "object",
        "properties": {
            "count": {"type": "integer", "description": "Number of recent commits to show"},
        },
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            count = args.get("count", 10)
            result = await sandbox.exec("", f"git log --oneline -{count}")
            return ToolResult(success=True, output=result.stdout or "No commits")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


class ListDirTool(Tool):
    name = "list_dir"
    description = "List the contents of a directory."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "Absolute path to the directory"},
        },
        "required": ["path"],
    }

    async def execute(self, args: dict, sandbox: Sandbox) -> ToolResult:
        try:
            result = await sandbox.exec("", f"ls -la {args['path']}")
            return ToolResult(success=True, output=result.stdout)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
```

- [ ] **Step 10: Run test to verify it passes**

```bash
pytest tests/tools/test_tools.py -v
```

Expected: PASS

- [ ] **Step 11: Commit**

```bash
git add harness/tools/ tests/tools/
git commit -m "feat: add tool system with registry and 9 built-in tools"
```

---

