import json
import asyncio
import logging
from openai import AsyncOpenAI, RateLimitError, APIStatusError, APITimeoutError, APIConnectionError
from harness.adapters.base import BaseAdapter, AdapterResponse, ToolCall, TokenUsage

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
BASE_DELAY = 1.0


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

        last_exc = None
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.client.chat.completions.create(**kwargs)
                break
            except RateLimitError as e:
                last_exc = e
                retry_after = self._get_retry_after(e)
                delay = retry_after if retry_after else BASE_DELAY * (2 ** attempt)
                if attempt < MAX_RETRIES - 1:
                    logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs", attempt + 1, MAX_RETRIES, delay)
                    await asyncio.sleep(delay)
                else:
                    raise
            except (APITimeoutError, APIConnectionError) as e:
                last_exc = e
                delay = BASE_DELAY * (2 ** attempt)
                if attempt < MAX_RETRIES - 1:
                    logger.warning("API error (attempt %d/%d): %s, retrying in %.1fs", attempt + 1, MAX_RETRIES, e, delay)
                    await asyncio.sleep(delay)
                else:
                    raise
            except APIStatusError as e:
                if e.status_code >= 500:
                    last_exc = e
                    delay = BASE_DELAY * (2 ** attempt)
                    if attempt < MAX_RETRIES - 1:
                        logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs", e.status_code, attempt + 1, MAX_RETRIES, delay)
                        await asyncio.sleep(delay)
                    else:
                        raise
                else:
                    raise

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

    def _get_retry_after(self, error: RateLimitError) -> float | None:
        try:
            if hasattr(error, 'response') and error.response is not None:
                headers = getattr(error.response, 'headers', {})
                retry_after = headers.get('Retry-After') or headers.get('retry-after')
                if retry_after is not None:
                    return float(retry_after)
        except Exception:
            pass
        return None