from __future__ import annotations

import json
import os
import time
from typing import Any

from providers.base import ModelResponse, ToolCall


MAX_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = 2.0


def _empty_response_detail(resp: Any) -> str:
    payload = resp.model_dump() if hasattr(resp, "model_dump") else {}
    error = payload.get("error") if isinstance(payload, dict) else None
    if isinstance(error, dict) and error.get("message"):
        code = error.get("code")
        return f"{error['message']}" + (f" (code {code})" if code else "")
    return "response contained no choices"


class OpenAIProvider:
    """OpenAI Chat Completions provider with normalized tool_calls output."""

    def __init__(
        self,
        *,
        api_key_env: str = "OPENAI_API_KEY",
        base_url: str | None = None,
        default_model: str = "gpt-4o-mini",
    ) -> None:
        self.api_key_env = api_key_env
        self.base_url = base_url
        self.default_model = default_model

    def complete(
        self,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        *,
        model: str | None = None,
        temperature: float = 0.0,
        tool_choice: Any | None = None,
    ) -> ModelResponse:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install live provider dependency first: pip install openai") from exc

        api_key = os.getenv(self.api_key_env)
        if not api_key:
            raise RuntimeError(f"Missing API key env var: {self.api_key_env}")

        client = OpenAI(api_key=api_key, base_url=self.base_url)
        kwargs: dict[str, Any] = {
            "model": model or self.default_model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
        if tool_choice is not None:
            kwargs["tool_choice"] = tool_choice

        # OpenRouter answers HTTP 200 with an error payload and no `choices` when
        # the upstream model is rate-limited, so an empty choices list is a
        # transient condition to retry rather than a malformed SDK response.
        detail = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            resp = client.chat.completions.create(**kwargs)
            if resp.choices:
                break
            detail = _empty_response_detail(resp)
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
        else:
            raise RuntimeError(f"Provider returned no choices after {MAX_ATTEMPTS} attempts: {detail}")

        msg = resp.choices[0].message
        calls: list[ToolCall] = []
        for call in msg.tool_calls or []:
            args = json.loads(call.function.arguments or "{}")
            calls.append(ToolCall(name=call.function.name, args=args))
        return ModelResponse(text=msg.content, tool_calls=calls, raw=resp)
