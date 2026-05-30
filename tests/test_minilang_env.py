"""Deterministic tests for MiniLang generation and verification."""

import random

from zharness.agents.prompts import (
    build_user_prompt,
    executable_probe_examples,
    parse_conditions,
    scaffold_costs_for_condition,
)
from zharness.envs.minilang.generator import all_expected_answers, make_episode, support_examples
from zharness.envs.minilang.transforms import composition_swap_world, order_swap_world, renamed_vocab_world
from zharness.envs.minilang.verifier import verify_answers
from zharness.eval.trace_memory import build_trace_text, scan_trace_for_leakage


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


def test_support_examples_do_not_waste_budget_on_duplicates() -> None:
    episode = make_episode(10, support_budget=12, parse_tasks=1, generate_tasks=1, difficulty="hard")
    examples = support_examples(episode.world, random.Random(20_000), 12)

    assert len({example.meaning for example in examples}) == len(examples)


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
    composition_swapped = composition_swap_world(episode.world)

    assert renamed.encode(meaning) != episode.world.encode(meaning)
    assert swapped.encode(meaning) != episode.world.encode(meaning)
    assert composition_swapped.encode(meaning) != episode.world.encode(meaning)


def test_hard_counterfactual_transforms_change_expected_surface_form() -> None:
    episode = make_episode(7, support_budget=8, parse_tasks=1, generate_tasks=1, difficulty="hard")
    meaning = episode.tasks[0].meaning
    assert meaning is not None

    renamed = renamed_vocab_world(episode.world, random.Random(11))
    swapped = order_swap_world(episode.world)
    composition_swapped = composition_swap_world(episode.world)

    assert renamed.encode(meaning) != episode.world.encode(meaning)
    assert swapped.encode(meaning) != episode.world.encode(meaning)
    assert composition_swapped.encode(meaning) != episode.world.encode(meaning)


def test_trace_scrubber_separates_raw_from_scrubbed() -> None:
    episode = make_episode(7, support_budget=8, parse_tasks=1, generate_tasks=1, difficulty="hard")

    raw_scan = scan_trace_for_leakage(episode, build_trace_text(episode, "raw"))
    stripped_scan = scan_trace_for_leakage(episode, build_trace_text(episode, "stripped"))
    scrubbed_scan = scan_trace_for_leakage(episode, build_trace_text(episode, "artifact_scrubbed"))

    assert not raw_scan["passed"]
    assert stripped_scan["passed"]
    assert scrubbed_scan["passed"]


def test_executable_k_gen_is_query_scaffold_without_rulebook() -> None:
    episode = make_episode(7, support_budget=4, parse_tasks=1, generate_tasks=1, difficulty="hard")

    prompt = build_user_prompt(episode, "k_gen_exec")
    probe_examples = executable_probe_examples(episode)
    costs = scaffold_costs_for_condition(episode, "k_gen_exec")

    assert "Executable K_gen scaffold output" in prompt
    assert "Current MiniLang hard-mode rulebook" not in prompt
    assert costs["query_calls"] == len(probe_examples)
    assert costs["query_calls"] > 0
    assert costs["verifier_calls"] == 0
    for example in probe_examples:
        assert example.to_prompt() in prompt


def test_executable_k_gen_does_not_query_generation_targets_exactly() -> None:
    episode = make_episode(10, support_budget=4, parse_tasks=4, generate_tasks=4, difficulty="hard")
    probe_meanings = {example.meaning for example in executable_probe_examples(episode)}
    generation_targets = {
        task.meaning for task in episode.tasks if task.kind == "generate" and task.meaning is not None
    }

    assert probe_meanings.isdisjoint(generation_targets)


def test_parse_conditions_accepts_executable_k_gen_arm() -> None:
    assert list(parse_conditions("no_scaffold,k_gen_exec")) == ["no_scaffold", "k_gen_exec"]
