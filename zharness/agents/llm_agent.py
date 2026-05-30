"""Thin async LLM runner backed by the copied galaxy-selfevolve clients."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from core.llm import instantiate_llm_client

from .answer_parser import parse_answer_json
from .prompts import SYSTEM_PROMPT, build_user_prompt
from zharness.envs.minilang.generator import Episode, all_expected_answers


@dataclass(frozen=True)
class AgentRun:
    answers: List[Dict[str, object]]
    raw_response: str
    usage: Dict[str, int]
    model: str


class MiniLangLLMAgent:
    def __init__(
        self,
        *,
        client_name: str,
        model: str,
        temperature: float = 0.0,
        max_tokens: int = 2048,
        api_key_env: Optional[str] = None,
        base_url_env: Optional[str] = None,
        reasoning_effort: Optional[str] = None,
    ) -> None:
        client_args = {
            "model": model,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if api_key_env:
            client_args["api_key_env"] = api_key_env
        if base_url_env:
            client_args["base_url_env"] = base_url_env
        if reasoning_effort:
            client_args["reasoning_effort"] = reasoning_effort

        self.client = instantiate_llm_client(
            client_name,
            client_args,
        )

    async def solve(self, episode: Episode, condition: str) -> AgentRun:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(episode, condition)},
        ]
        response = await self.client.chat(messages)
        return AgentRun(
            answers=parse_answer_json(response.content),
            raw_response=response.content,
            usage=response.usage,
            model=response.model or getattr(self.client, "model", ""),
        )

    async def aclose(self) -> None:
        await self.client.aclose()


def mock_agent_run(episode: Episode, *, policy: Optional[str]) -> AgentRun:
    if policy == "oracle":
        answers = all_expected_answers(episode.world, episode.tasks)
    elif policy == "empty":
        answers = []
    else:
        raise ValueError("mock policy must be 'oracle' or 'empty'")
    return AgentRun(
        answers=answers,
        raw_response=f"<mock:{policy}>",
        usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        model=f"mock:{policy}",
    )
