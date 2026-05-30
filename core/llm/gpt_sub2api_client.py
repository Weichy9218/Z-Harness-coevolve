"""
GPT sub2api gateway client.

Chat Completions is the stable route for the current GPT sub2api gateway.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import LLMResponse, register_llm_client
from .env_utils import load_env, resolve_client_setting
from .openai_client import OpenAIClient

load_env()


GPT_SUB2API_API_KEY_ENV = "GPT_sub2api_apikey"
GPT_SUB2API_API_KEY_ENV_2 = "GPT_sub2api_apikey_2"
GPT_SUB2API_BASE_URL_ENV = "GPT_sub2api_URL"


@register_llm_client("gpt_sub2api")
class GPTSub2APIClient(OpenAIClient):
    """Gateway client for GPT sub2api.

    The gateway exposes a Responses-like route, but that route can hang or emit
    SDK-incompatible stream snapshots on full-agent prompts. Use Chat
    Completions as the single active runtime path.
    """

    DEFAULT_MODEL = "gpt-5.4"

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        temperature: Optional[float] = 0.2,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key_env: Optional[str] = None,
        base_url_env: Optional[str] = None,
        max_tokens: Optional[int] = 4096,
        reasoning_effort: Optional[str] = None,
        async_mode: bool = True,
        **kwargs: Any,
    ) -> None:
        resolved_api_key, _ = resolve_client_setting(
            api_key,
            preferred_env=api_key_env,
            fallback_envs=(GPT_SUB2API_API_KEY_ENV, GPT_SUB2API_API_KEY_ENV_2),
        )
        resolved_base_url, _ = resolve_client_setting(
            base_url,
            preferred_env=base_url_env,
            fallback_envs=(GPT_SUB2API_BASE_URL_ENV,),
        )
        if not resolved_api_key:
            raise ValueError(
                "GPTSub2APIClient requires api_key, api_key_env, or "
                f"{GPT_SUB2API_API_KEY_ENV}"
            )
        if not resolved_base_url:
            raise ValueError(
                "GPTSub2APIClient requires base_url, base_url_env, or "
                f"{GPT_SUB2API_BASE_URL_ENV}"
            )

        super().__init__(
            model=model,
            temperature=temperature,
            api_key=resolved_api_key,
            base_url=resolved_base_url,
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
            async_mode=async_mode,
            **kwargs,
        )

    @staticmethod
    def _normalize_tool_for_chat_completions(tool: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(tool, dict):
            return tool
        if tool.get("type") != "function":
            return tool
        if isinstance(tool.get("function"), dict):
            return tool
        if "name" not in tool:
            return tool
        return {
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description"),
                "parameters": tool.get("parameters") or {},
            },
        }

    def _build_chat_completion_request_params(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        response_format: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        tool_choice = kwargs.pop("tool_choice", None)
        max_completion_tokens = kwargs.pop("max_completion_tokens", None)
        kwargs.pop("reasoning_effort", None)
        kwargs.pop("reasoning", None)
        kwargs.pop("max_output_tokens", None)
        kwargs.pop("parallel_tool_calls", None)

        params: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            **self.extra_params,
            **kwargs,
        }
        if self.max_tokens is not None:
            params["max_tokens"] = max_completion_tokens or self.max_tokens
        if self.temperature is not None and self._supports_temperature():
            params["temperature"] = self.temperature

        if tools:
            params["tools"] = [self._normalize_tool_for_chat_completions(tool) for tool in tools]
            params["tool_choice"] = tool_choice or "auto"
        if response_format is not None:
            params["response_format"] = response_format
        return params

    async def _create_chat_completion(
        self,
        params: dict[str, Any],
    ) -> LLMResponse:
        if self.async_mode:
            response = await self.client.chat.completions.create(**params)
        else:
            response = self.client.chat.completions.create(**params)
        llm_response = self._parse_chat_completion_response(response)
        self._update_usage_stats(llm_response.usage)
        return llm_response

    async def chat(
        self,
        messages,
        tools=None,
        response_format=None,
        **kwargs,
    ) -> LLMResponse:
        """Send one non-streaming Chat Completions request."""
        params = self._build_chat_completion_request_params(
            messages=messages,
            tools=tools,
            response_format=response_format,
            **kwargs,
        )
        return await self._create_chat_completion(params)
