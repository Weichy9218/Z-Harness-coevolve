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
from zharness.eval.interactive_kgen import (
    build_executable_probe_actions,
    build_repair_prompt,
    coarse_verifier_feedback,
    preserve_correct_draft_answers,
)
from zharness.eval.run_adoption import _classify_robust_adoption
from zharness.eval.trace_memory import TRACE_VARIANTS, build_trace_text, scan_trace_for_leakage


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
    safe_scans = [
        scan_trace_for_leakage(episode, build_trace_text(episode, variant))
        for variant in TRACE_VARIANTS
        if variant != "raw"
    ]

    assert not raw_scan["passed"]
    assert all(scan["passed"] for scan in safe_scans)


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
    assert list(parse_conditions("no_scaffold,k_gen_exec,k_gen_interactive")) == [
        "no_scaffold",
        "k_gen_exec",
        "k_gen_interactive",
    ]


def test_interactive_probe_observation_is_structured() -> None:
    episode = make_episode(7, support_budget=4, parse_tasks=1, generate_tasks=1, difficulty="hard")
    action = build_executable_probe_actions(episode)[0]

    observation = action["observation"]
    assert isinstance(observation, dict)
    assert observation["command"]
    assert observation["meaning"] == action["meaning"]
    assert observation["morphemes"]


def test_interactive_probe_actions_match_executable_k_gen() -> None:
    episode = make_episode(7, support_budget=4, parse_tasks=1, generate_tasks=1, difficulty="hard")
    actions = build_executable_probe_actions(episode)
    probes = executable_probe_examples(episode)

    assert len(actions) == len(probes)
    assert actions[0]["source"] == "k_gen_exec"
    assert actions[0]["observation"]["command"] == probes[0].command


def test_interactive_repair_prompt_is_short_and_preserves_correct_answers() -> None:
    episode = make_episode(7, support_budget=4, parse_tasks=1, generate_tasks=1, difficulty="hard")
    prompt = build_repair_prompt(
        episode=episode,
        probe_actions=build_executable_probe_actions(episode),
        draft_answers=[{"task_id": "p0", "meaning": {"action": "jump"}}],
        feedback=[
            {"task_id": "p0", "correct": True, "labels": []},
            {"task_id": "g0", "correct": False, "labels": ["wrong_count"]},
        ],
    )

    assert "Preserve draft answers for tasks marked correct=true." in prompt
    assert "slot_table" not in prompt
    assert "wrong_count" in prompt


def test_interactive_verifier_feedback_is_coarse() -> None:
    episode = make_episode(7, support_budget=4, parse_tasks=1, generate_tasks=1, difficulty="hard")
    verification = verify_answers(episode.world, episode.tasks, [])
    feedback = coarse_verifier_feedback(verification)

    assert feedback
    assert all("labels" in item for item in feedback)
    assert all("expected" not in item for item in feedback)
    assert all("observed" not in item for item in feedback)


def test_interactive_no_regression_merge_preserves_correct_draft() -> None:
    draft = [{"task_id": "p0", "meaning": {"action": "jump"}}]
    final = [{"task_id": "p0", "meaning": {"action": "walk"}}]
    feedback = [{"task_id": "p0", "correct": True, "labels": []}]

    merged, changed = preserve_correct_draft_answers(
        draft_answers=draft,
        final_answers=final,
        feedback=feedback,
    )

    assert merged == draft
    assert changed == ["p0"]


def test_robust_adoption_quarantines_seen_only_and_negative_transfer() -> None:
    removal_delta_by_transform = {
        "same_world": {
            "kg_skill": {"n": 1, "mean_accuracy_delta": 0.0},
            "kspec_skill": {"n": 1, "mean_accuracy_delta": 0.5},
            "seen_only": {"n": 1, "mean_accuracy_delta": 0.25},
        },
        "composition_swap": {
            "kg_skill": {"n": 1, "mean_accuracy_delta": 0.125},
            "kspec_skill": {"n": 1, "mean_accuracy_delta": -0.25},
            "seen_only": {"n": 1, "mean_accuracy_delta": 0.0},
        },
        "heldout_family": {
            "kg_skill": {"n": 1, "mean_accuracy_delta": 0.125},
            "kspec_skill": {"n": 1, "mean_accuracy_delta": -0.125},
            "seen_only": {"n": 1, "mean_accuracy_delta": 0.0},
        },
    }

    result = _classify_robust_adoption(
        skill_ids=("kg_skill", "kspec_skill", "seen_only"),
        removal_delta_by_transform=removal_delta_by_transform,
        tolerance=0.0,
    )

    assert result["kg_skill"]["decision"] == "promote_candidate"
    assert result["kspec_skill"]["decision"] == "quarantine"
    assert result["seen_only"]["decision"] == "quarantine"
    assert result["seen_only"]["reason"] == "seen_only_positive"


def test_robust_adoption_hard_quarantines_known_source_rulebook() -> None:
    removal_delta_by_transform = {
        "same_world": {"kspec_source_rulebook": {"n": 1, "mean_accuracy_delta": 1.0}},
        "composition_swap": {"kspec_source_rulebook": {"n": 1, "mean_accuracy_delta": 0.5}},
        "heldout_family": {"kspec_source_rulebook": {"n": 1, "mean_accuracy_delta": 0.0}},
    }

    result = _classify_robust_adoption(
        skill_ids=("kspec_source_rulebook",),
        removal_delta_by_transform=removal_delta_by_transform,
        tolerance=0.0,
        quarantine_skill_ids={"kspec_source_rulebook"},
    )

    assert result["kspec_source_rulebook"]["decision"] == "quarantine"
    assert result["kspec_source_rulebook"]["reason"] == "known_source_specific_leakage"
