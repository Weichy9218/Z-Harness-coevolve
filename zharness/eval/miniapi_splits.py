"""Target-world transforms for MiniAPI no-GPU proxy evaluations."""

from __future__ import annotations

from dataclasses import replace

from zharness.envs.miniapi import MiniAPIEpisode, make_counterfactual_world, make_episode


MINIAPI_TRANSFORMS = ("same_world", "counterfactual_world", "heldout_world")


def make_miniapi_target_episode(
    source_episode: MiniAPIEpisode,
    transform_name: str,
    seed: int,
) -> MiniAPIEpisode:
    if transform_name == "same_world":
        return source_episode

    if transform_name == "counterfactual_world":
        return replace(
            source_episode,
            episode_id=f"{source_episode.episode_id}-counterfactual",
            world=make_counterfactual_world(source_episode.world),
        )

    if transform_name == "heldout_world":
        heldout = make_episode(seed + 10_000)
        return replace(
            heldout,
            episode_id=f"{source_episode.episode_id}-heldout",
            goal=source_episode.goal,
        )

    raise ValueError(f"unknown MiniAPI transform: {transform_name}")


def parse_csv(raw: str, allowed: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for item in str(raw or "").split(","):
        value = item.strip()
        if not value:
            continue
        if value not in allowed:
            known = ", ".join(allowed)
            raise ValueError(f"unknown value '{value}'. Known: {known}")
        values.append(value)
    return values
