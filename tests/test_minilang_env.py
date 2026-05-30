"""Deterministic tests for MiniLang generation and verification."""

from zharness.envs.minilang.generator import all_expected_answers, make_episode
from zharness.envs.minilang.transforms import order_swap_world, renamed_vocab_world
from zharness.envs.minilang.verifier import verify_answers

import random


def test_oracle_answers_verify_perfectly() -> None:
    episode = make_episode(7, support_budget=12, parse_tasks=3, generate_tasks=3)
    answers = all_expected_answers(episode.world, episode.tasks)
    result = verify_answers(episode.world, episode.tasks, answers)
    assert result.accuracy == 1.0
    assert result.parse_accuracy == 1.0
    assert result.generate_accuracy == 1.0


def test_hard_oracle_answers_verify_perfectly() -> None:
    episode = make_episode(7, support_budget=8, parse_tasks=3, generate_tasks=3, difficulty="hard")
    answers = all_expected_answers(episode.world, episode.tasks)
    result = verify_answers(episode.world, episode.tasks, answers)
    assert result.accuracy == 1.0


def test_empty_answers_fail() -> None:
    episode = make_episode(7, support_budget=12, parse_tasks=3, generate_tasks=3)
    result = verify_answers(episode.world, episode.tasks, [])
    assert result.accuracy == 0.0


def test_counterfactual_transforms_change_expected_surface_form() -> None:
    episode = make_episode(7, support_budget=12, parse_tasks=1, generate_tasks=1)
    meaning = episode.tasks[0].meaning
    assert meaning is not None

    renamed = renamed_vocab_world(episode.world, random.Random(11))
    swapped = order_swap_world(episode.world)

    assert renamed.encode(meaning) != episode.world.encode(meaning)
    assert swapped.encode(meaning) != episode.world.encode(meaning)


def test_hard_counterfactual_transforms_change_expected_surface_form() -> None:
    episode = make_episode(7, support_budget=8, parse_tasks=1, generate_tasks=1, difficulty="hard")
    meaning = episode.tasks[0].meaning
    assert meaning is not None

    renamed = renamed_vocab_world(episode.world, random.Random(11))
    swapped = order_swap_world(episode.world)

    assert renamed.encode(meaning) != episode.world.encode(meaning)
    assert swapped.encode(meaning) != episode.world.encode(meaning)
