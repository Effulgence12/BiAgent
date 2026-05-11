"""Minimal DeepSeek-compatible chat client using the Python standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

from config.settings import settings


@dataclass(frozen=True)
class LLMResponse:
    """LLM response metadata."""

    content: str
    used_api: bool
    error: str = ""


def chat_completion(system_prompt: str, user_prompt: str, timeout: int = 45) -> LLMResponse:
    """Call DeepSeek chat completions when DEEPSEEK_API_KEY is configured.

    The function returns a graceful fallback response when no key is present so the
    rest of the application remains usable for demos and offline testing.
    """
    if not settings.deepseek_api_key:
        return LLMResponse(content="", used_api=False, error="DEEPSEEK_API_KEY is not configured")
    payload = {
        "model": settings.deepseek_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    request = urllib.request.Request(
        settings.deepseek_base_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {settings.deepseek_api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
        return LLMResponse(content=data["choices"][0]["message"]["content"], used_api=True)
    except (urllib.error.URLError, KeyError, IndexError, json.JSONDecodeError) as exc:
        return LLMResponse(content="", used_api=False, error=str(exc))
