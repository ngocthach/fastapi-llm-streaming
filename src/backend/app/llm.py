"""LLM service abstraction with mock and OpenAI streaming implementations"""
import asyncio
from typing import AsyncGenerator

from app.config import get_settings

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore


settings = get_settings()


async def mock_stream_response(prompt: str) -> AsyncGenerator[str, None]:
    """Mock streaming generator yielding chunks for a given prompt.
    This simulates an LLM streaming response.
    """
    text = f"Echo: {prompt}\nThis is a simulated streaming response."
    for token in text.split():
        await asyncio.sleep(0.05)
        yield token + " "


async def openai_stream_response(prompt: str) -> AsyncGenerator[str, None]:
    """Stream response from OpenAI Chat Completions API (async) with light retries.
    Only retries the initial stream creation; not mid-stream chunks.
    """
    if AsyncOpenAI is None or not settings.openai_api_key:
        # Fallback to mock if SDK not available or API key missing
        async for chunk in mock_stream_response(prompt):
            yield chunk
        return

    client = AsyncOpenAI(api_key=settings.openai_api_key)

    # Try to create a streaming response with a few retries
    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            stream = await client.chat.completions.create(
                model=settings.llm_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                stream=True,
            )
            break
        except Exception as e:  # transient error on creation
            last_exc = e
            await asyncio.sleep(0.5 * (2 ** attempt))
    else:
        # All attempts failed, re-raise last exception
        raise last_exc  # type: ignore[misc]

    async for event in stream:
        try:
            delta = event.choices[0].delta
            content = getattr(delta, "content", None)
            if content:
                yield content
        except Exception:
            # If structure changes, ignore and continue
            continue


def get_llm_streamer():
    """Return the appropriate streaming function based on configuration."""
    if settings.openai_api_key and AsyncOpenAI is not None:
        return openai_stream_response
    return mock_stream_response
