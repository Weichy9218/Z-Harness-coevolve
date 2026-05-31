"""Deterministic tests for MiniAPI workflow verification and probes."""

from zharness.envs.miniapi import (
    diagnostic_probe_plan,
    execute_plan,
    make_counterfactual_world,
    make_episode,
    naive_plan,
    oracle_plan,
)


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
