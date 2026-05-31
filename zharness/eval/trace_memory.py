"""Build and scrub MiniLang trace-memory artifacts for no-weight experiments."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence

from zharness.envs.minilang.generator import Episode, HardWorld, World, all_expected_answers, normalized_command


TRACE_VARIANTS = (
    "raw",
    "stripped",
    "executable_stripped",
    "artifact_scrubbed",
    "artifact_scrubbed_executable",
)


def build_trace_text(episode: Episode, variant: str) -> str:
    if variant == "raw":
        return _build_raw_trace(episode)
    if variant == "stripped":
        return _build_stripped_trace()
    if variant == "executable_stripped":
        return _build_executable_stripped_trace()
    if variant == "artifact_scrubbed":
        return _build_artifact_scrubbed_trace()
    if variant == "artifact_scrubbed_executable":
        return _build_artifact_scrubbed_executable_trace()
    raise ValueError(f"unknown trace variant: {variant}")


def build_trace_record(episode: Episode, variant: str) -> Dict[str, object]:
    trace_text = build_trace_text(episode, variant)
    leakage_scan = scan_trace_for_leakage(episode, trace_text)
    return {
        "episode_id": episode.episode_id,
        "family_id": episode.world.family_id,
        "trace_variant": variant,
        "trace_text": trace_text,
        "trace_chars": len(trace_text),
        "leakage_scan": leakage_scan,
    }


def scan_trace_for_leakage(episode: Episode, trace_text: str) -> Dict[str, object]:
    text = str(trace_text or "")
    violations: List[Dict[str, str]] = []

    for label, value in (
        ("episode_id", episode.episode_id),
        ("family_id", episode.world.family_id),
    ):
        if value and value in text:
            violations.append({"kind": label, "value": value})

    if "Current MiniLang" in text:
        violations.append({"kind": "rulebook_marker", "value": "Current MiniLang"})

    for atom in _surface_atoms(episode.world):
        if _contains_atom(text, atom):
            violations.append({"kind": "surface_atom", "value": atom})

    for command in _episode_commands(episode):
        if command and command in text:
            violations.append({"kind": "surface_command", "value": command})

    return {
        "passed": not violations,
        "num_violations": len(violations),
        "violations": violations[:30],
    }


def _build_raw_trace(episode: Episode) -> str:
    lines = [
        "RAW TRACE FROM A PREVIOUS MINILANG EPISODE.",
        f"episode_id: {episode.episode_id}",
        f"family_id: {episode.world.family_id}",
        "",
        episode.world.rulebook_text(),
        "",
        "Visible examples:",
        *[f"- {example.to_prompt()}" for example in episode.examples],
        "",
        "Solved tasks and final answers:",
    ]
    for answer in all_expected_answers(episode.world, episode.tasks):
        lines.append(f"- {answer}")
    lines.append("")
    lines.append("Verifier outcome: all final answers matched the current rulebook.")
    return "\n".join(lines)


def _build_stripped_trace() -> str:
    return "\n".join(
        [
            "STRIPPED TRACE TEMPLATE FROM A PREVIOUS MINILANG EPISODE.",
            "Goal: recover the latent mapping for this episode without copying any surface strings from earlier episodes.",
            "Procedure:",
            "- Treat examples as evidence about latent slots, not phrases to memorize.",
            "- First isolate which parts of a command encode semantic roles and quantities.",
            "- Use minimally different examples to separate role identity from quantity marking.",
            "- Check whether the phrase order changes under negation before answering generation tasks.",
            "- For generation, assemble the target episode's own morphemes and verify each slot is represented once.",
            "- If a hypothesis fails, repair the smallest rule that explains the mismatch before changing unrelated rules.",
            "Do not reuse any previous episode's vocabulary, rulebook, or final answers.",
        ]
    )


def _build_executable_stripped_trace() -> str:
    return "\n".join(
        [
            "EXECUTABLE-STRIPPED TRACE TEMPLATE FROM A PREVIOUS MINILANG EPISODE.",
            "Reusable action sequence:",
            "1. propose a compact hypothesis over latent slots and unknowns.",
            "2. request bounded diagnostic examples that change one factor at a time.",
            "3. convert each observation into morpheme-level evidence, not memorized words.",
            "4. draft answers only after action, object, color, count, and negation have evidence.",
            "5. ask verifier for coarse labels, then repair the smallest failing slot rule.",
            "6. preserve answers already marked correct and audit generation forms for all slots.",
            "Do not copy prior commands, vocabulary, family ids, rulebooks, or final answers.",
        ]
    )


def _build_artifact_scrubbed_trace() -> str:
    return "\n".join(
        [
            "ARTIFACT-SCRUBBED TRACE TEMPLATE.",
            "Reusable policy:",
            "- Infer the current episode from current evidence only.",
            "- Build a slot inventory from paired examples.",
            "- Test one unknown factor at a time.",
            "- Separate semantic decoding from exact surface generation.",
            "- Before final output, audit that every generated form uses only current-episode evidence.",
            "Quarantine rule: discard any memory that names prior surface forms, task answers, family identifiers, or concrete rulebooks.",
        ]
    )


def _build_artifact_scrubbed_executable_trace() -> str:
    return "\n".join(
        [
            "ARTIFACT-SCRUBBED EXECUTABLE TRACE TEMPLATE.",
            "Reusable policy:",
            "- Use a fixed action protocol: hypothesis, bounded query, verifier label, repair, audit.",
            "- Query only current-episode diagnostic examples; reject direct target queries.",
            "- Keep action traces as abstract operations and coarse feedback categories.",
            "- Promote a learned action only if counterfactual and held-out removal deltas are nonnegative.",
            "- Quarantine any memory whose benefit disappears without the source-specific harness.",
            "No prior surface forms, task answers, family identifiers, or concrete rulebooks are reusable.",
        ]
    )


def _surface_atoms(world: World | HardWorld) -> List[str]:
    if isinstance(world, HardWorld):
        atoms = list(world.concept_to_stem.values())
        atoms.extend(world.count_to_marker.values())
        atoms.extend(world.agreement_by_count.values())
        atoms.append(world.neg_token)
        return sorted(set(atoms), key=len, reverse=True)
    return sorted(set(world.concept_to_token.values()), key=len, reverse=True)


def _episode_commands(episode: Episode) -> List[str]:
    commands = [normalized_command(example.command) for example in episode.examples]
    for task in episode.tasks:
        if task.command:
            commands.append(normalized_command(task.command))
    return sorted(set(commands), key=len, reverse=True)


def _contains_atom(text: str, atom: str) -> bool:
    if not atom:
        return False
    escaped = re.escape(atom)
    pattern = rf"(?<![A-Za-z0-9_-]){escaped}(?![A-Za-z0-9_-])"
    return re.search(pattern, text) is not None
