"""Safety checks for the shared training manifest."""

import copy

from zharness.eval.training_manifest import build_manifest_rows, validate_manifest_rows


def test_training_manifest_blocks_raw_and_allows_promoted_safe_action_rows() -> None:
    rows = build_manifest_rows(
        envs=("minilang", "miniapi"),
        seed=31,
        episodes=1,
        run_id="test-manifest",
    )

    assert not validate_manifest_rows(rows)
    assert any(row["trainable"] for row in rows if row["env"] == "MiniAPI")
    assert all(not row["trainable"] for row in rows if row["trace_variant"] == "raw")
    assert all(
        row["leakage_scan"]["passed"] and row["robust_adoption"]["decision"] == "promote_candidate"
        for row in rows
        if row["trainable"]
    )


def test_training_manifest_rejects_trainable_leaky_or_quarantined_rows() -> None:
    rows = build_manifest_rows(
        envs=("miniapi",),
        seed=31,
        episodes=1,
        run_id="test-manifest",
    )

    leaky = copy.deepcopy(next(row for row in rows if row["trace_variant"] == "raw"))
    leaky["trainable"] = True
    leaky["trainable_reason"] = "bad_test_override"

    quarantined = copy.deepcopy(next(row for row in rows if row["trace_variant"] == "artifact_scrubbed"))
    quarantined["trainable"] = True
    quarantined["trainable_reason"] = "bad_test_override"

    errors = validate_manifest_rows([leaky, quarantined])

    assert any("raw/source-specific trace cannot be trainable" in error for error in errors)
    assert any("trainable row failed leakage scan" in error for error in errors)
    assert any("trainable row lacks robust adoption promotion" in error for error in errors)
