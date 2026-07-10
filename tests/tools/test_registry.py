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