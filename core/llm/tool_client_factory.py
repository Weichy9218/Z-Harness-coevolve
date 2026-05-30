"""Route-aware helpers for tool-side LLM selection.

Tool-side LLM usage is intentionally defined by explicit route names rather than
generic "text" and "vision" buckets. Each route corresponds to a concrete tool
workflow with its own quality/cost tradeoff.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional, Type

from .base import BaseLLMClient, instantiate_llm_client, resolve_llm_client_name

try:
    from core.config import get_global_config
    from core.config.config_manager import ToolLLMRoute
except ModuleNotFoundError:
    @dataclass(frozen=True)
    class ToolLLMRoute:
        """Minimal local fallback when only core.llm is copied into this repo."""

        client: str
        model: str
        reasoning_effort: Optional[str] = None
        client_args: Optional[dict] = None

    def get_global_config():
        raise RuntimeError("core.config is not available in this experiment repo")


_TEXT_CATEGORY = "text"
_VISION_CATEGORY = "vision"


@dataclass(frozen=True)
class ToolLLMRouteSpec:
    """Canonical tool-side route metadata owned in code."""

    name: str
    category: str
    client: str
    model: str
    reasoning_effort: Optional[str]
    description: str


_ROUTE_NAME_ALIASES = {
    "text_summary": "webpage_summary",
}

_TOOL_LLM_ROUTE_SPECS = {
    "search_summary": ToolLLMRouteSpec(
        name="search_summary",
        category=_TEXT_CATEGORY,
        client="openrouter_newapi",
        model="qwen3-next-80b-a3b-instruct",
        reasoning_effort="low",
        description="Compress search-result snippets into faithful, cited bullets.",
    ),
    "webpage_summary": ToolLLMRouteSpec(
        name="webpage_summary",
        category=_TEXT_CATEGORY,
        client="openrouter_newapi",
        model="qwen3-next-80b-a3b-instruct",
        reasoning_effort="low",
        description="Compress long webpage text while preserving key facts.",
    ),
    "llm_inference": ToolLLMRouteSpec(
        name="llm_inference",
        category=_TEXT_CATEGORY,
        client="gpt_sub2api",
        model="gpt-5.4",
        reasoning_effort="high",
        description="General synthesis, diagnosis, and planning tool calls.",
    ),
    "ranking_extractor": ToolLLMRouteSpec(
        name="ranking_extractor",
        category=_TEXT_CATEGORY,
        client="openrouter_newapi",
        model="qwen3-next-80b-a3b-instruct",
        reasoning_effort="low",
        description="Extract structured ranked items from noisy webpage text.",
    ),
    "read_image": ToolLLMRouteSpec(
        name="read_image",
        category=_VISION_CATEGORY,
        client="openrouter_newapi",
        model="qwen/qwen3-vl-32b-instruct",
        reasoning_effort="low",
        description="OCR and visual question answering over images.",
    ),
}

_DEFAULT_MODEL_BY_CATEGORY_AND_CLIENT = {
    (_TEXT_CATEGORY, "gpt_sub2api"): "gpt-5.4",
    (_TEXT_CATEGORY, "openrouter_newapi"): "qwen3-next-80b-a3b-instruct",
    (_TEXT_CATEGORY, "openai"): "gpt-4.1-mini",
    (_VISION_CATEGORY, "gpt_sub2api"): "gpt-5.4",
    (_VISION_CATEGORY, "openrouter_newapi"): "qwen/qwen3-vl-32b-instruct",
    (_VISION_CATEGORY, "openai"): "gpt-4.1-mini",
}


def resolve_tool_llm_route_name(route_name: str) -> str:
    """Normalize route aliases to one canonical tool-side route name."""
    candidate = str(route_name or "").strip()
    if not candidate:
        raise KeyError("Tool LLM route name must be a non-empty string")
    return _ROUTE_NAME_ALIASES.get(candidate, candidate)


def get_tool_llm_route_spec(route_name: str) -> ToolLLMRouteSpec:
    """Return the canonical route spec for one tool-side LLM workflow."""
    resolved_name = resolve_tool_llm_route_name(route_name)
    spec = _TOOL_LLM_ROUTE_SPECS.get(resolved_name)
    if spec is None:
        known = ", ".join(sorted(_TOOL_LLM_ROUTE_SPECS))
        raise KeyError(f"Unknown tool LLM route '{route_name}'. Known routes: {known}")
    return spec


def _default_model_for_route_client(route_name: str, client_name: str) -> str:
    spec = get_tool_llm_route_spec(route_name)
    normalized_client = resolve_llm_client_name(client_name)
    return _DEFAULT_MODEL_BY_CATEGORY_AND_CLIENT.get(
        (spec.category, normalized_client),
        spec.model,
    )


def _env_route_override(category: str) -> Optional[ToolLLMRoute]:
    if category == _VISION_CATEGORY:
        env_client = str(os.getenv("TOOL_VISION_LLM_CLIENT", "")).strip()
        env_model = str(os.getenv("TOOL_VISION_MODEL", "")).strip()
        if env_client and env_model:
            return ToolLLMRoute(client=env_client, model=env_model, reasoning_effort="low")
        return None

    env_client = str(os.getenv("TOOL_TEXT_LLM_CLIENT", "")).strip()
    env_model = str(os.getenv("TOOL_TEXT_MODEL", "")).strip()
    if env_client and env_model:
        return ToolLLMRoute(client=env_client, model=env_model, reasoning_effort="high")
    return None


def resolve_tool_llm_route(route_name: str) -> ToolLLMRoute:
    """Resolve one tool-side route from config, env fallback, or code defaults."""
    spec = get_tool_llm_route_spec(route_name)
    try:
        configured = get_global_config().get_tool_llm_route(spec.name, category=spec.category)
    except Exception:
        configured = None
    if configured is not None:
        return configured

    env_override = _env_route_override(spec.category)
    if env_override is not None:
        return env_override

    return ToolLLMRoute(
        client=spec.client,
        model=spec.model,
        reasoning_effort=spec.reasoning_effort,
    )


def resolve_tool_llm_client_name(route_name: str) -> str:
    return resolve_llm_client_name(resolve_tool_llm_route(route_name).client)


def resolve_tool_llm_model(
    *,
    route_name: str,
    model: Optional[str] = None,
    client_name: Optional[str] = None,
) -> str:
    if model and str(model).strip():
        return str(model).strip()

    resolved_route = resolve_tool_llm_route(route_name)
    resolved_client = resolve_llm_client_name(client_name or resolved_route.client)
    configured_client = resolve_llm_client_name(resolved_route.client)
    if resolved_client != configured_client:
        return _default_model_for_route_client(route_name, resolved_client)
    return resolved_route.model


def resolve_tool_text_client_name(route_name: str = "llm_inference") -> str:
    spec = get_tool_llm_route_spec(route_name)
    if spec.category != _TEXT_CATEGORY:
        raise ValueError(f"Tool route '{route_name}' is not a text route")
    return resolve_tool_llm_client_name(route_name)


def resolve_tool_vision_client_name(route_name: str = "read_image") -> str:
    spec = get_tool_llm_route_spec(route_name)
    if spec.category != _VISION_CATEGORY:
        raise ValueError(f"Tool route '{route_name}' is not a vision route")
    return resolve_tool_llm_client_name(route_name)


def resolve_tool_text_model(
    *,
    route_name: str = "llm_inference",
    model: Optional[str] = None,
    client_name: Optional[str] = None,
) -> str:
    spec = get_tool_llm_route_spec(route_name)
    if spec.category != _TEXT_CATEGORY:
        raise ValueError(f"Tool route '{route_name}' is not a text route")
    return resolve_tool_llm_model(route_name=route_name, model=model, client_name=client_name)


def resolve_tool_vision_model(
    *,
    route_name: str = "read_image",
    model: Optional[str] = None,
    client_name: Optional[str] = None,
) -> str:
    spec = get_tool_llm_route_spec(route_name)
    if spec.category != _VISION_CATEGORY:
        raise ValueError(f"Tool route '{route_name}' is not a vision route")
    return resolve_tool_llm_model(route_name=route_name, model=model, client_name=client_name)


def build_tool_llm_client(
    *,
    route_name: str,
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    client_name: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    resolved_route = resolve_tool_llm_route(route_name)
    resolved_client = resolve_llm_client_name(client_name or resolved_route.client)
    resolved_model = resolve_tool_llm_model(
        route_name=route_name,
        model=model,
        client_name=resolved_client,
    )

    resolved_effort = reasoning_effort
    if resolved_effort is None and resolved_route.reasoning_effort is not None:
        resolved_effort = resolved_route.reasoning_effort

    init_kwargs = dict(resolved_route.client_args or {})
    init_kwargs.update(
        model=resolved_model,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    init_kwargs.update(kwargs)
    if resolved_effort is not None:
        init_kwargs["reasoning_effort"] = resolved_effort
    return instantiate_llm_client(resolved_client, init_kwargs)


def build_tool_text_client(
    *,
    route_name: str = "llm_inference",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 4096,
    client_name: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    spec = get_tool_llm_route_spec(route_name)
    if spec.category != _TEXT_CATEGORY:
        raise ValueError(f"Tool route '{route_name}' is not a text route")
    return build_tool_llm_client(
        route_name=route_name,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        client_name=client_name,
        reasoning_effort=reasoning_effort,
        **kwargs,
    )


def build_tool_vision_client(
    *,
    route_name: str = "read_image",
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048,
    client_name: Optional[str] = None,
    reasoning_effort: Optional[str] = None,
    **kwargs,
) -> BaseLLMClient:
    spec = get_tool_llm_route_spec(route_name)
    if spec.category != _VISION_CATEGORY:
        raise ValueError(f"Tool route '{route_name}' is not a vision route")
    return build_tool_llm_client(
        route_name=route_name,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        client_name=client_name,
        reasoning_effort=reasoning_effort,
        **kwargs,
    )


def get_tool_text_context_limit_error_type(
    client_name: Optional[str] = None,
    *,
    route_name: str = "llm_inference",
) -> Optional[Type[BaseException]]:
    resolved_client = resolve_llm_client_name(client_name or resolve_tool_llm_client_name(route_name))
    if resolved_client != "openrouter_newapi":
        return None
    from .openrouter_newapi_client import ContextLimitError

    return ContextLimitError
