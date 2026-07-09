### Task 5: Adapter Layer

**Files:**
- Create: `harness/adapters/base.py`
- Create: `harness/adapters/openai.py`
- Test: `tests/adapters/test_openai.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `ToolCall` dataclass: `id: str`, `name: str`, `arguments: dict`
  - `TokenUsage` dataclass: `prompt_tokens: int`, `completion_tokens: int`, `total_tokens: int`
  - `AdapterResponse` dataclass: `content: Optional[str]`, `tool_calls: list[ToolCall]`, `finish_reason: str`, `usage: Optional[TokenUsage]`
  - `BaseAdapter` ABC with `async chat(messages: list[dict], tools: list[dict]) -> AdapterResponse`
  - `OpenAIAdapter(BaseAdapter)` with constructor `__init__(model: str, api_key: str, temperature: float)`

- [ ] **Step 1: Write base.py**

```python
# harness/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass
class AdapterResponse:
    content: Optional[str] = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"
    usage: Optional[TokenUsage] = None


class BaseAdapter(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], tools: list[dict]) -> AdapterResponse:
        ...
```

- [ ] **Step 2: Write failing OpenAI test**

```python
# tests/adapters/test_openai.py
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
```

- [ ] **Step 3: Run test to verify it fails**

```bash
pytest tests/adapters/test_openai.py -v
```

Expected: FAIL with import errors

- [ ] **Step 4: Write openai.py**

```python
# harness/adapters/openai.py
import json
from openai import AsyncOpenAI
from harness.adapters.base import BaseAdapter, AdapterResponse, ToolCall, TokenUsage


class OpenAIAdapter(BaseAdapter):
    def __init__(self, model: str, api_key: str, temperature: float):
        self.model = model
        self.temperature = temperature
        self.client = AsyncOpenAI(api_key=api_key)

    async def chat(self, messages: list[dict], tools: list[dict]) -> AdapterResponse:
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(
                    ToolCall(id=tc.id, name=tc.function.name, arguments=args)
                )

        usage = None
        if response.usage:
            usage = TokenUsage(
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
                total_tokens=response.usage.total_tokens,
            )

        return AdapterResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
```

- [ ] **Step 5: Run OpenAI test to verify it passes**

```bash
OPENAI_API_KEY=sk-test pytest tests/adapters/test_openai.py -v
```

Expected: SKIP if no real key, PASS if key is set

- [ ] **Step 6: Commit**

```bash
git add harness/adapters/ tests/adapters/
git commit -m "feat: add adapter layer with OpenAI implementation"
```

---

