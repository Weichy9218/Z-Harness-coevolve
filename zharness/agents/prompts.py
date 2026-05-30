"""Prompt builders for no-training MiniLang scaffold-headroom experiments."""

from __future__ import annotations

from typing import Iterable

from zharness.envs.minilang.generator import Episode


CONDITION_NO_SCAFFOLD = "no_scaffold"
CONDITION_K_SPEC = "k_spec"
CONDITION_K_GEN = "k_gen"
CONDITION_K_SPEC_K_GEN = "k_spec_k_gen"
CONDITIONS = (
    CONDITION_NO_SCAFFOLD,
    CONDITION_K_SPEC,
    CONDITION_K_GEN,
    CONDITION_K_SPEC_K_GEN,
)


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
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition: {condition}")

    sections = [
        "You are solving one MiniLang episode.",
        "MiniLang commands map to JSON meanings with fields: action, object, color, count, neg.",
        "Visible examples:",
        *[f"- {example.to_prompt()}" for example in episode.examples],
    ]

    if override_rulebook is not None:
        sections.extend(["", override_rulebook])
    elif condition in {CONDITION_K_SPEC, CONDITION_K_SPEC_K_GEN}:
        sections.extend(["", episode.world.rulebook_text()])

    if condition in {CONDITION_K_GEN, CONDITION_K_SPEC_K_GEN}:
        sections.extend(["", K_GEN_PLAYBOOK])

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


def parse_conditions(raw: str) -> Iterable[str]:
    for item in str(raw or "").split(","):
        condition = item.strip()
        if not condition:
            continue
        if condition not in CONDITIONS:
            known = ", ".join(CONDITIONS)
            raise ValueError(f"unknown condition '{condition}'. Known: {known}")
        yield condition
