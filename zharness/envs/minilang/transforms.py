"""Counterfactual transforms for detecting task-specific leakage."""

from __future__ import annotations

import random
from typing import Union

from .generator import AFFIXES, COUNTS, ORDERS, VOCAB, HardWorld, World


MiniLangWorld = Union[World, HardWorld]


def renamed_vocab_world(source: MiniLangWorld, rng: random.Random) -> MiniLangWorld:
    if isinstance(source, HardWorld):
        return _renamed_hard_world(source, rng)

    tokens = list(VOCAB)
    rng.shuffle(tokens)
    concepts = list(source.concept_to_token)
    return World(
        family_id=f"{source.family_id}-renamed",
        concept_to_token={concept: token for concept, token in zip(concepts, tokens)},
        order=source.order,
    )


def order_swap_world(source: MiniLangWorld) -> MiniLangWorld:
    if isinstance(source, HardWorld):
        return HardWorld(
            family_id=f"{source.family_id}-order-swap",
            concept_to_stem=dict(source.concept_to_stem),
            count_to_marker=dict(source.count_to_marker),
            agreement_by_count=dict(source.agreement_by_count),
            neg_token=source.neg_token,
            affirmative_order=source.negative_order,
            negative_order=source.affirmative_order,
            color_position=source.color_position,
            count_position=source.count_position,
        )

    for order in ORDERS:
        if order != source.order:
            return World(
                family_id=f"{source.family_id}-order-swap",
                concept_to_token=dict(source.concept_to_token),
                order=order,
            )
    raise RuntimeError("no alternative order is available")


def composition_swap_world(source: MiniLangWorld) -> MiniLangWorld:
    if isinstance(source, HardWorld):
        return HardWorld(
            family_id=f"{source.family_id}-composition-swap",
            concept_to_stem=dict(source.concept_to_stem),
            count_to_marker=dict(source.count_to_marker),
            agreement_by_count=_rotated_count_mapping(source.agreement_by_count),
            neg_token=source.neg_token,
            affirmative_order=source.affirmative_order,
            negative_order=source.negative_order,
            color_position=_flipped_position(source.color_position),
            count_position=_flipped_position(source.count_position),
        )

    for order in reversed(ORDERS):
        if order != source.order:
            return World(
                family_id=f"{source.family_id}-composition-swap",
                concept_to_token=dict(source.concept_to_token),
                order=order,
            )
    raise RuntimeError("no alternative composition is available")


def _renamed_hard_world(source: HardWorld, rng: random.Random) -> HardWorld:
    stems = list(VOCAB)
    rng.shuffle(stems)
    concepts = list(source.concept_to_stem)

    markers = list(AFFIXES)
    rng.shuffle(markers)
    count_markers = markers[: len(COUNTS)]
    agreement_markers = markers[len(COUNTS) : len(COUNTS) * 2]
    neg_token = markers[-1]

    return HardWorld(
        family_id=f"{source.family_id}-renamed",
        concept_to_stem={concept: stem for concept, stem in zip(concepts, stems)},
        count_to_marker={count: marker for count, marker in zip(COUNTS, count_markers)},
        agreement_by_count={count: marker for count, marker in zip(COUNTS, agreement_markers)},
        neg_token=neg_token,
        affirmative_order=source.affirmative_order,
        negative_order=source.negative_order,
        color_position=source.color_position,
        count_position=source.count_position,
    )


def _flipped_position(position: str) -> str:
    if position == "prefix":
        return "suffix"
    if position == "suffix":
        return "prefix"
    raise ValueError(f"unknown position: {position}")


def _rotated_count_mapping(mapping: dict[int, str]) -> dict[int, str]:
    return {
        count: mapping[COUNTS[(index + 1) % len(COUNTS)]]
        for index, count in enumerate(COUNTS)
    }
