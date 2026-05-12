"""OpenAI-compatible Qwen/DashScope chat client.

The project uses the OpenAI-compatible DashScope endpoint documented by Qwen Cloud.
No API key is stored in code; set QWEN_API_KEY or DASHSCOPE_API_KEY at runtime.
LLM failures are surfaced explicitly instead of being replaced by local advice.
"""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.request
from collections.abc import Generator, Iterable
from dataclasses import dataclass
from typing import Any

import httpx

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


class LLMClientError(RuntimeError):
    """Raised when the configured remote LLM cannot produce a real response."""


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
        # 手写 HTTP JSON 时需要放在顶层；OpenAI SDK 的 extra_body 包装在这里不会生效。
        "enable_thinking": False,
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
    """Call Qwen chat completions and fail loudly when the API is unavailable."""
    if not settings.enable_llm:
        raise LLMClientError("LLM is disabled by ENABLE_LLM=0")
    if not _api_key():
        raise LLMClientError("QWEN_API_KEY or DASHSCOPE_API_KEY is not configured")
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
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:500]
        raise LLMClientError(f"LLM HTTP {exc.code}: {detail}") from exc
    except (TimeoutError, socket.timeout) as exc:
        raise LLMClientError(f"LLM request timed out: {exc}") from exc
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        raise LLMClientError(f"LLM request failed: {exc}") from exc


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
        with httpx.stream(
            "POST",
            _chat_url(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {_api_key()}"},
            json=_payload(system_prompt, user_prompt, stream=True, max_tokens=max_tokens),
            timeout=httpx.Timeout(timeout, read=timeout),
        ) as response:
            if response.status_code >= 400:
                yield LLMStreamEvent(event="error", error=f"HTTP {response.status_code}: {response.text[:300]}")
                return
            for chunk in _iter_sse_lines(line.encode("utf-8") for line in response.iter_lines()):
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
    except (TimeoutError, socket.timeout) as exc:
        yield LLMStreamEvent(event="error", error=f"LLM stream timed out: {exc}")
    except (urllib.error.URLError, httpx.HTTPError) as exc:
        yield LLMStreamEvent(event="error", error=str(exc))
