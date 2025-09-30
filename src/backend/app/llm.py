"""LLM service abstraction with mock and OpenAI streaming implementations"""
import asyncio
import json

from typing import AsyncGenerator, Literal

from app.config import get_settings

try:
    from openai import AsyncOpenAI
except Exception:  # pragma: no cover
    AsyncOpenAI = None  # type: ignore


settings = get_settings()


async def mock_stream_response(prompt: str, stream_format: Literal["text", "openai"] = "text") -> AsyncGenerator[str, None]:
    """Mock streaming generator yielding chunks for a given prompt.
    If stream_format == "openai", yields minimal OpenAI-like JSON lines.
    """
    text = f"Echo: {prompt}\nThis is a simulated streaming response."
    for token in text.split():
        await asyncio.sleep(0.05)
        if stream_format == "openai":
            yield json.dumps({
                "choices": [{"delta": {"content": token + " "}}]
            })
        else:
            yield token + " "


async def openai_stream_response(prompt: str, stream_format: Literal["text", "openai"] = "text") -> AsyncGenerator[str, None]:
    """Stream response from OpenAI Chat Completions API (async) with light retries.
    Only retries the initial stream creation; not mid-stream chunks.
    If stream_format == "openai", yields minimal OpenAI-like JSON lines per chunk.
    """
    if AsyncOpenAI is None or not settings.openai_api_key:
        # Fallback to mock if SDK not available or API key missing
        async for chunk in mock_stream_response(prompt, stream_format=stream_format):
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
            if not content:
                continue
            if stream_format == "openai":
                yield json.dumps({
                    "choices": [{"delta": {"content": content}}]
                })
            else:
                yield content
        except Exception:
            # If structure changes, ignore and continue
            continue


def get_llm_streamer(stream_format: Literal["text", "openai"] = "text"):
    """Return a streaming function for the configured provider with the given format.
    The returned function will accept only (prompt: str).
    """
    if settings.openai_api_key and AsyncOpenAI is not None:
        async def _streamer(prompt: str):
            async for ch in openai_stream_response(prompt, stream_format=stream_format):
                yield ch
        return _streamer

    async def _mock_streamer(prompt: str):
        async for ch in mock_stream_response(prompt, stream_format=stream_format):
            yield ch
    return _mock_streamer
