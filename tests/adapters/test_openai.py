import pytest
import os
from harness.adapters.openai import OpenAIAdapter
from harness.adapters.base import AdapterResponse


@pytest.fixture
def adapter():
    api_key = os.environ.get("OPENAI_API_KEY", "test-key")
    return OpenAIAdapter(model="gpt-4o", api_key=api_key, temperature=0.0)


@pytest.mark.asyncio
async def test_chat_simple_response(adapter):
    if os.environ.get("OPENAI_API_KEY") is None:
        pytest.skip("OPENAI_API_KEY not set")

    messages = [{"role": "user", "content": "Say hello in one word."}]
    tools = []

    response = await adapter.chat(messages, tools)

    assert isinstance(response, AdapterResponse)
    assert response.content is not None
    assert response.finish_reason == "stop"


@pytest.mark.asyncio
async def test_chat_with_tools(adapter):
    if os.environ.get("OPENAI_API_KEY") is None:
        pytest.skip("OPENAI_API_KEY not set")

    messages = [{"role": "user", "content": "What is 2+2?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculator",
                "description": "Calculate a math expression",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "expression": {"type": "string", "description": "Math expression"}
                    },
                    "required": ["expression"],
                },
            },
        }
    ]

    response = await adapter.chat(messages, tools)

    assert isinstance(response, AdapterResponse)
    assert response.usage is not None
    assert response.usage.total_tokens > 0