"""Counterfactual transforms for detecting task-specific leakage."""

from __future__ import annotations

import random

from .generator import ORDERS, VOCAB, World


def renamed_vocab_world(source: World, rng: random.Random) -> World:
    tokens = list(VOCAB)
    rng.shuffle(tokens)
    concepts = list(source.concept_to_token)
    return World(
        family_id=f"{source.family_id}-renamed",
        concept_to_token={concept: token for concept, token in zip(concepts, tokens)},
        order=source.order,
    )


def order_swap_world(source: World) -> World:
    for order in ORDERS:
        if order != source.order:
            return World(
                family_id=f"{source.family_id}-order-swap",
                concept_to_token=dict(source.concept_to_token),
                order=order,
            )
    raise RuntimeError("no alternative order is available")

