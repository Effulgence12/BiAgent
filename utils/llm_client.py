"""OpenAI-compatible Qwen/DashScope chat client with safe local fallback.

The project uses the OpenAI-compatible DashScope endpoint documented by Qwen Cloud.
No API key is stored in code; set QWEN_API_KEY or DASHSCOPE_API_KEY at runtime.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Any

from config.settings import settings


@dataclass(frozen=True)
class LLMResponse:
    """LLM response metadata."""

    content: str
    used_api: bool
    model: str
    provider: str = "qwen"
    error: str = ""
    total_tokens: int | None = None


@dataclass(frozen=True)
class LLMStreamEvent:
    """A normalized streaming event emitted by the LLM client."""

    event: str
    content: str = ""
    reasoning_content: str = ""
    total_tokens: int | None = None
    error: str = ""


def _api_key() -> str:
    """Return the configured Qwen/DashScope key, supporting legacy env names."""
    return settings.qwen_api_key or os.getenv("DASHSCOPE_API_KEY", "") or settings.deepseek_api_key


def _chat_url() -> str:
    """Return the full OpenAI-compatible chat completions endpoint."""
    base_url = settings.qwen_base_url.rstrip("/")
    if base_url.endswith("/chat/completions"):
        return base_url
    return f"{base_url}/chat/completions"


def _payload(system_prompt: str, user_prompt: str, *, stream: bool = False, max_tokens: int | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": settings.qwen_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": settings.llm_temperature,
        "max_tokens": max_tokens or settings.llm_max_tokens,
        # Disable thinking for routine BI copy-editing to reduce latency and token use.
        "extra_body": {"enable_thinking": False},
    }
    if stream:
        payload["stream"] = True
        payload["stream_options"] = {"include_usage": True}
    return payload


def _request(payload: dict[str, Any], timeout: int) -> urllib.request.Request:
    return urllib.request.Request(
        _chat_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_api_key()}"},
        method="POST",
    )


def chat_completion(system_prompt: str, user_prompt: str, timeout: int = 45, max_tokens: int | None = None) -> LLMResponse:
    """Call Qwen chat completions when QWEN_API_KEY/DASHSCOPE_API_KEY is configured."""
    if not settings.enable_llm:
        return LLMResponse(content="", used_api=False, model=settings.qwen_model, error="LLM is disabled by ENABLE_LLM=0")
    if not _api_key():
        return LLMResponse(content="", used_api=False, model=settings.qwen_model, error="QWEN_API_KEY or DASHSCOPE_API_KEY is not configured")
    try:
        with urllib.request.urlopen(_request(_payload(system_prompt, user_prompt, max_tokens=max_tokens), timeout), timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        usage = data.get("usage") or {}
        return LLMResponse(
            content=data["choices"][0]["message"].get("content", ""),
            used_api=True,
            model=data.get("model", settings.qwen_model),
            total_tokens=usage.get("total_tokens"),
        )
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return LLMResponse(content="", used_api=False, model=settings.qwen_model, error=str(exc))


def _iter_sse_lines(byte_lines: Iterable[bytes]) -> Generator[dict[str, Any] | str, None, None]:
    """Parse OpenAI-compatible SSE lines into JSON chunks or the [DONE] marker."""
    for raw_line in byte_lines:
        line = raw_line.decode("utf-8", errors="ignore").strip()
        if not line or not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            yield "[DONE]"
            continue
        try:
            yield json.loads(data)
        except json.JSONDecodeError:
            continue


def stream_chat_completion(system_prompt: str, user_prompt: str, timeout: int = 60, max_tokens: int | None = None) -> Generator[LLMStreamEvent, None, None]:
    """Stream Qwen chat completion deltas as normalized events.

    The final chunk can include usage when the provider supports
    `stream_options={"include_usage": True}`.
    """
    if not settings.enable_llm:
        yield LLMStreamEvent(event="error", error="LLM is disabled by ENABLE_LLM=0")
        return
    if not _api_key():
        yield LLMStreamEvent(event="error", error="QWEN_API_KEY or DASHSCOPE_API_KEY is not configured")
        return
    try:
        with urllib.request.urlopen(_request(_payload(system_prompt, user_prompt, stream=True, max_tokens=max_tokens), timeout), timeout=timeout) as response:
            for chunk in _iter_sse_lines(response):
                if chunk == "[DONE]":
                    yield LLMStreamEvent(event="done")
                    return
                usage = chunk.get("usage") or {}
                if usage:
                    yield LLMStreamEvent(event="usage", total_tokens=usage.get("total_tokens"))
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}
                reasoning = delta.get("reasoning_content") or ""
                content = delta.get("content") or ""
                if reasoning or content:
                    yield LLMStreamEvent(event="delta", content=content, reasoning_content=reasoning)
            yield LLMStreamEvent(event="done")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:300]
        yield LLMStreamEvent(event="error", error=f"HTTP {exc.code}: {detail}")
    except urllib.error.URLError as exc:
        yield LLMStreamEvent(event="error", error=str(exc))
