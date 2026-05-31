"""Build and scrub MiniAPI action-trace memory artifacts."""

from __future__ import annotations

import json
from typing import Dict, List

from zharness.envs.miniapi import MiniAPIEpisode, oracle_plan


MINIAPI_TRACE_VARIANTS = (
    "raw",
    "action_stripped",
    "artifact_scrubbed",
    "artifact_scrubbed_action",
)


def build_miniapi_trace_text(episode: MiniAPIEpisode, variant: str) -> str:
    if variant == "raw":
        return _build_raw_trace(episode)
    if variant == "action_stripped":
        return _build_action_stripped_trace()
    if variant == "artifact_scrubbed":
        return _build_artifact_scrubbed_trace()
    if variant == "artifact_scrubbed_action":
        return _build_artifact_scrubbed_action_trace()
    raise ValueError(f"unknown MiniAPI trace variant: {variant}")


def scan_miniapi_trace_for_leakage(episode: MiniAPIEpisode, trace_text: str) -> Dict[str, object]:
    text = str(trace_text or "")
    violations: List[Dict[str, str]] = []

    exact_values = {
        "family_id": episode.world.family_id,
        "order_id": episode.goal.order_id,
        "customer_id": episode.goal.customer_id,
        "sku": episode.goal.sku,
        "auth_token": episode.goal.auth_token,
        "coupon_code": episode.goal.coupon_code,
    }
    for kind, value in exact_values.items():
        if value and value in text:
            violations.append({"kind": kind, "value": value})

    if "Current MiniAPI rulebook" in text:
        violations.append({"kind": "rulebook_marker", "value": "Current MiniAPI rulebook"})
    if "source_hidden_profile" in text:
        violations.append({"kind": "source_hidden_profile", "value": "source_hidden_profile"})

    return {
        "passed": not violations,
        "num_violations": len(violations),
        "violations": violations[:30],
    }


def build_miniapi_trace_record(episode: MiniAPIEpisode, variant: str) -> Dict[str, object]:
    trace_text = build_miniapi_trace_text(episode, variant)
    return {
        "episode_id": episode.episode_id,
        "family_id": episode.world.family_id,
        "trace_variant": variant,
        "trace_text": trace_text,
        "trace_chars": len(trace_text),
        "leakage_scan": scan_miniapi_trace_for_leakage(episode, trace_text),
    }


def _build_raw_trace(episode: MiniAPIEpisode) -> str:
    plan = [call.to_dict() for call in oracle_plan(episode.world, episode.goal)]
    return "\n".join(
        [
            "RAW TRACE FROM A PREVIOUS MINIAPI EPISODE.",
            f"episode_id: {episode.episode_id}",
            f"source_hidden_profile: {episode.world.family_id}",
            "",
            episode.world.rulebook_text(),
            "",
            "Goal:",
            json.dumps(episode.goal.to_dict(), sort_keys=True),
            "",
            "Successful API plan:",
            json.dumps(plan, sort_keys=True),
            "",
            "Verifier outcome: final state matched the source hidden profile.",
        ]
    )


def _build_action_stripped_trace() -> str:
    return "\n".join(
        [
            "ACTION-STRIPPED TRACE TEMPLATE FROM A PREVIOUS MINIAPI EPISODE.",
            "Reusable protocol:",
            "1. authenticate before any write tool.",
            "2. create the target record with current request fields only.",
            "3. use bounded probe orders to identify hidden ordering constraints.",
            "4. compute payment from current request fields and current coupon evidence.",
            "5. run optional guard actions only when current probe feedback requires them.",
            "6. ship only after verifier-relevant preconditions have been satisfied.",
            "Do not copy prior order ids, tokens, coupons, carriers, profiles, or concrete API plans.",
        ]
    )


def _build_artifact_scrubbed_trace() -> str:
    return "\n".join(
        [
            "ARTIFACT-SCRUBBED MINIAPI MEMORY.",
            "Reusable policy:",
            "- Treat prior successful workflows as possible strategies, not as source of target facts.",
            "- Prefer current-state verifier feedback over remembered ordering rules.",
            "- Reject any memory that names concrete prior identifiers, credentials, coupons, or hidden profiles.",
            "- Do not transfer a plan if a counterfactual world changes its verifier outcome.",
        ]
    )


def _build_artifact_scrubbed_action_trace() -> str:
    return "\n".join(
        [
            "ARTIFACT-SCRUBBED MINIAPI ACTION MEMORY.",
            "Reusable protocol:",
            "- Use hypothesis -> bounded probe -> verifier label -> repair -> final audit.",
            "- Probe on non-target records, never on the exact target record.",
            "- Store only abstract action types and coarse verifier labels.",
            "- Promote a workflow memory only when counterfactual and heldout removal deltas are nonnegative.",
            "- Quarantine source-specific profiles even when they help same-world tasks.",
        ]
    )
