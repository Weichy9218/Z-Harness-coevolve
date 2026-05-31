"""Prompt builders for no-training MiniLang scaffold-headroom experiments."""

from __future__ import annotations

import random
from typing import Iterable

from zharness.envs.minilang.generator import (
    ACTIONS,
    COLORS,
    COUNTS,
    OBJECTS,
    Episode,
    Meaning,
)


CONDITION_NO_SCAFFOLD = "no_scaffold"
CONDITION_K_SPEC = "k_spec"
CONDITION_K_GEN = "k_gen"
CONDITION_K_SPEC_K_GEN = "k_spec_k_gen"
CONDITION_K_GEN_EXEC = "k_gen_exec"
CONDITION_K_SPEC_K_GEN_EXEC = "k_spec_k_gen_exec"
CONDITION_K_GEN_INTERACTIVE = "k_gen_interactive"
CONDITIONS = (
    CONDITION_NO_SCAFFOLD,
    CONDITION_K_SPEC,
    CONDITION_K_GEN,
    CONDITION_K_SPEC_K_GEN,
)
ALL_CONDITIONS = CONDITIONS + (
    CONDITION_K_GEN_EXEC,
    CONDITION_K_SPEC_K_GEN_EXEC,
    CONDITION_K_GEN_INTERACTIVE,
)
EXECUTABLE_K_GEN_QUERY_BUDGET = 8


K_GEN_PLAYBOOK = """General MiniLang discovery playbook:
- Treat each example as evidence about latent slots, not as a phrase to memorize.
- Compare minimally different examples to isolate action, object, color, count, and negation.
- Check whether meanings are encoded as separate words, affixes, hyphenated morphemes, or agreement markers.
- Infer which token or morpheme disappears when neg=false before inferring word order.
- Test whether word order is conditional on negation or another feature.
- For generation, apply the inferred morphology and slot order exactly.
- Before answering, check every generated command against the same latent slot inventory.
"""


SYSTEM_PROMPT = """You solve synthetic hidden-rule language tasks.
Return only valid JSON. Do not include markdown or explanations.
If your runtime emits thinking text anyway, put the final JSON object after all thinking; the last JSON object must match the requested schema.
"""


def build_user_prompt(episode: Episode, condition: str, override_rulebook: str | None = None) -> str:
    if condition not in ALL_CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")

    sections = [
        "You are solving one MiniLang episode.",
        "MiniLang commands map to JSON meanings with fields: action, object, color, count, neg.",
        "Visible examples:",
        *[f"- {example.to_prompt()}" for example in episode.examples],
    ]

    if override_rulebook is not None:
        sections.extend(["", override_rulebook])
    elif condition in {CONDITION_K_SPEC, CONDITION_K_SPEC_K_GEN, CONDITION_K_SPEC_K_GEN_EXEC}:
        sections.extend(["", episode.world.rulebook_text()])

    if condition in {CONDITION_K_GEN, CONDITION_K_SPEC_K_GEN, CONDITION_K_GEN_EXEC, CONDITION_K_SPEC_K_GEN_EXEC}:
        sections.extend(["", K_GEN_PLAYBOOK])

    if condition in {CONDITION_K_GEN_EXEC, CONDITION_K_SPEC_K_GEN_EXEC}:
        sections.extend(["", build_executable_k_gen_block(episode)])

    sections.extend(
        [
            "",
            "Tasks:",
            *[f"- {task.to_prompt()}" for task in episode.tasks],
            "",
            "Return this JSON schema exactly:",
            '{"answers":[{"task_id":"p0","meaning":{"action":"jump","object":"door","color":"red","count":2,"neg":false}},{"task_id":"g0","command":"dak mip"}]}',
        ]
    )
    return "\n".join(sections)


def build_executable_k_gen_block(episode: Episode) -> str:
    """Return deterministic query-scaffold observations for the current episode."""

    probe_examples = executable_probe_examples(episode)
    sections = [
        "Executable K_gen scaffold output:",
        (
            "A generic query planner used "
            f"{len(probe_examples)} environment queries to request diagnostic examples. "
            "These observations are current-episode evidence, not reusable memory."
        ),
        "Use these probes to isolate morphology, slot order, negation, and agreement before answering.",
    ]
    sections.extend(f"- q{index}: {example.to_prompt()}" for index, example in enumerate(probe_examples))
    return "\n".join(sections)


def executable_probe_examples(episode: Episode) -> list:
    seed = _episode_seed(episode.episode_id) + 50_000
    rng = random.Random(seed)
    base = _base_probe_meaning(episode, rng)
    forbidden_targets = {
        task.meaning for task in episode.tasks if task.kind == "generate" and task.meaning is not None
    }
    visible_commands = {example.command for example in episode.examples}
    candidates = _task_relevant_probe_meanings(episode, base)
    candidates.extend(_ontology_probe_meanings(base, rng))

    probe_examples = []
    seen_meanings = set()
    for meaning in candidates:
        if meaning in forbidden_targets or meaning in seen_meanings:
            continue
        example = episode.world.example(meaning)
        if example.command in visible_commands:
            continue
        probe_examples.append(example)
        seen_meanings.add(meaning)
        if len(probe_examples) >= EXECUTABLE_K_GEN_QUERY_BUDGET:
            break
    return probe_examples


def _base_probe_meaning(episode: Episode, rng: random.Random) -> Meaning:
    if episode.examples:
        return episode.examples[0].meaning
    return Meaning(
        action=rng.choice(ACTIONS),
        object=rng.choice(OBJECTS),
        color=rng.choice(COLORS),
        count=rng.choice(COUNTS),
        neg=False,
    )


def _task_relevant_probe_meanings(episode: Episode, base: Meaning) -> list[Meaning]:
    meanings = []
    for task in episode.tasks:
        if task.kind != "generate" or task.meaning is None:
            continue
        target = task.meaning
        meanings.extend(
            [
                Meaning(target.action, base.object, base.color, base.count),
                Meaning(base.action, target.object, base.color, base.count),
                Meaning(base.action, base.object, target.color, base.count),
                Meaning(base.action, base.object, base.color, target.count),
            ]
        )
        if target.neg:
            meanings.append(Meaning(base.action, base.object, base.color, base.count, neg=True))
    return meanings


def _ontology_probe_meanings(base: Meaning, rng: random.Random) -> list[Meaning]:
    actions = list(ACTIONS)
    objects = list(OBJECTS)
    colors = list(COLORS)
    counts = list(COUNTS)
    rng.shuffle(actions)
    rng.shuffle(objects)
    rng.shuffle(colors)
    rng.shuffle(counts)

    meanings = []
    meanings.extend(Meaning(action, base.object, base.color, base.count) for action in actions)
    meanings.extend(Meaning(base.action, obj, base.color, base.count) for obj in objects)
    meanings.extend(Meaning(base.action, base.object, color, base.count) for color in colors)
    meanings.extend(Meaning(base.action, base.object, base.color, count) for count in counts)
    meanings.append(Meaning(base.action, base.object, base.color, base.count, neg=True))
    return meanings


def scaffold_costs_for_condition(episode: Episode, condition: str) -> dict:
    if condition in {CONDITION_K_GEN_EXEC, CONDITION_K_SPEC_K_GEN_EXEC}:
        return {
            "query_calls": len(executable_probe_examples(episode)),
            "verifier_calls": 0,
        }
    return {
        "query_calls": 0,
        "verifier_calls": 0,
    }


def parse_conditions(raw: str) -> Iterable[str]:
    for item in str(raw or "").split(","):
        condition = item.strip()
        if not condition:
            continue
        if condition not in ALL_CONDITIONS:
            known = ", ".join(ALL_CONDITIONS)
            raise ValueError(f"unknown condition '{condition}'. Known: {known}")
        yield condition


def _episode_seed(episode_id: str) -> int:
    digits = "".join(char for char in episode_id if char.isdigit())
    if digits:
        return int(digits)
    return sum(ord(char) for char in episode_id)
