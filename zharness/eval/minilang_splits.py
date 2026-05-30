"""Shared MiniLang split and counterfactual helpers for evaluation runners."""

from __future__ import annotations

from dataclasses import replace
import random
from typing import List

from zharness.envs.minilang.generator import Episode, HardWorld, make_episode, make_tasks, support_examples
from zharness.envs.minilang.transforms import composition_swap_world, order_swap_world, renamed_vocab_world


TRANSFORMS = ("same_world", "renamed_vocab", "order_swap", "composition_swap", "heldout_family")


def make_target_episode(source_episode: Episode, transform_name: str, seed: int) -> Episode:
    source_world = source_episode.world
    if transform_name == "same_world":
        target_world = source_world
    elif transform_name == "renamed_vocab":
        target_world = renamed_vocab_world(source_world, random.Random(seed + 30_000))
    elif transform_name == "order_swap":
        target_world = order_swap_world(source_world)
    elif transform_name == "composition_swap":
        target_world = composition_swap_world(source_world)
    elif transform_name == "heldout_family":
        difficulty = "hard" if isinstance(source_world, HardWorld) else "basic"
        return make_episode(
            seed + 90_000,
            support_budget=len(source_episode.examples),
            parse_tasks=count_kind(source_episode, "parse"),
            generate_tasks=count_kind(source_episode, "generate"),
            difficulty=difficulty,
        )
    else:
        raise ValueError(f"unknown transform: {transform_name}")

    if target_world is source_world:
        return source_episode

    return replace(
        source_episode,
        episode_id=f"{source_episode.episode_id}-{transform_name}",
        world=target_world,
        examples=support_examples(target_world, random.Random(seed + 10_000), len(source_episode.examples)),
        tasks=make_tasks(
            target_world,
            random.Random(seed + 20_000),
            count_kind(source_episode, "parse"),
            count_kind(source_episode, "generate"),
        ),
    )


def count_kind(episode: Episode, kind: str) -> int:
    return sum(1 for task in episode.tasks if task.kind == kind)


def parse_csv(raw: str, allowed: tuple[str, ...]) -> List[str]:
    values: List[str] = []
    for item in str(raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        if item not in allowed:
            raise ValueError(f"unknown value '{item}'. Allowed: {', '.join(allowed)}")
        values.append(item)
    return values
