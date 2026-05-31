"""Deterministic tests for MiniAPI workflow verification and probes."""

from zharness.envs.miniapi import (
    diagnostic_probe_plan,
    execute_plan,
    make_counterfactual_world,
    make_episode,
    naive_plan,
    oracle_plan,
)
from zharness.eval.miniapi_trace_memory import (
    build_miniapi_trace_text,
    scan_miniapi_trace_for_leakage,
)
from zharness.eval.run_miniapi_adoption import _summarize as summarize_miniapi_adoption
from zharness.eval.run_miniapi_memory_proxy import _run_one_variant


def test_miniapi_oracle_plan_succeeds() -> None:
    episode = make_episode(31)
    result = execute_plan(episode.world, episode.goal, oracle_plan(episode.world, episode.goal))

    assert result.success
    assert result.to_metrics()["success"] == 1.0


def test_miniapi_naive_plan_fails_without_auth_and_hidden_constraints() -> None:
    episode = make_episode(31)
    result = execute_plan(episode.world, episode.goal, naive_plan(episode.goal))

    assert not result.success
    assert result.errors
    assert result.to_metrics()["forbidden_action_rate"] > 0.0


def test_miniapi_source_raw_counterfactual_fails_or_differs() -> None:
    episode = make_episode(31)
    source_world = make_counterfactual_world(episode.world)

    source_plan = oracle_plan(source_world, episode.goal)
    target_plan = oracle_plan(episode.world, episode.goal)
    result = execute_plan(episode.world, episode.goal, source_plan)

    assert source_plan != target_plan
    assert not result.success


def test_miniapi_diagnostic_probe_recovers_without_target_query() -> None:
    episode = make_episode(31)
    plan, probe_trace = diagnostic_probe_plan(episode.world, episode.goal)
    result = execute_plan(episode.world, episode.goal, plan)

    assert result.success
    assert probe_trace
    assert all(probe["probe_id"] != episode.goal.order_id for probe in probe_trace)
    assert any(probe["success"] for probe in probe_trace)


def test_miniapi_trace_scrubber_separates_raw_from_action_memory() -> None:
    episode = make_episode(31)

    raw_scan = scan_miniapi_trace_for_leakage(episode, build_miniapi_trace_text(episode, "raw"))
    safe_scan = scan_miniapi_trace_for_leakage(
        episode,
        build_miniapi_trace_text(episode, "artifact_scrubbed_action"),
    )

    assert not raw_scan["passed"]
    assert safe_scan["passed"]


def test_miniapi_memory_proxy_raw_fails_counterfactual_but_action_memory_recovers() -> None:
    source = make_episode(31)
    target = make_episode(31)
    target = target.__class__(
        episode_id="miniapi-31-counterfactual",
        world=make_counterfactual_world(source.world),
        goal=source.goal,
    )

    raw_record = _run_one_variant(
        source_episode=source,
        target_episode=target,
        transform_name="counterfactual_world",
        variant="raw",
    )
    action_record = _run_one_variant(
        source_episode=source,
        target_episode=target,
        transform_name="counterfactual_world",
        variant="artifact_scrubbed_action",
    )

    assert raw_record["metrics"]["success"] == 0.0
    assert raw_record["memory_leakage_scan"]["passed"] is False
    assert action_record["metrics"]["success"] == 1.0
    assert action_record["memory_leakage_scan"]["passed"] is True


def test_miniapi_robust_adoption_quarantines_source_profile() -> None:
    records = []
    for transform, deltas in {
        "same_world": {
            "kg_auth_first": 1.0,
            "kg_probe_hidden_profile": 0.0,
            "kspec_source_profile": 0.5,
            "trap_skip_receipt": 0.0,
        },
        "counterfactual_world": {
            "kg_auth_first": 1.0,
            "kg_probe_hidden_profile": 1.0,
            "kspec_source_profile": -1.0,
            "trap_skip_receipt": -1.0,
        },
        "heldout_world": {
            "kg_auth_first": 1.0,
            "kg_probe_hidden_profile": 1.0,
            "kspec_source_profile": -1.0,
            "trap_skip_receipt": 0.0,
        },
    }.items():
        for skill_id, delta in deltas.items():
            full_success = 1.0 if delta >= 0 else 0.0
            removed_success = full_success - delta
            records.append(
                {
                    "transform": transform,
                    "skill_id": skill_id,
                    "accuracy_delta": delta,
                    "called": skill_id == "kspec_source_profile",
                    "full_metrics": {"success": full_success},
                    "removal_metrics": {"success": removed_success},
                }
            )

    result = summarize_miniapi_adoption(records, robust_delta_tolerance=0.0)

    assert result["robust_adoption"]["kg_auth_first"]["decision"] == "promote_candidate"
    assert result["robust_adoption"]["kg_probe_hidden_profile"]["decision"] == "promote_candidate"
    assert result["robust_adoption"]["kspec_source_profile"]["decision"] == "quarantine"
    assert result["robust_adoption"]["kspec_source_profile"]["reason"] == "known_source_specific_leakage"
