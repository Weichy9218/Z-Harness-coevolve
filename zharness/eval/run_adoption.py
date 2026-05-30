"""Run offline skill-adoption and removal ablations for MiniLang."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
from statistics import mean
from typing import Dict, List, Optional, Sequence

from dotenv import load_dotenv

from zharness.agents.answer_parser import parse_answer_payload
from zharness.agents.llm_agent import AgentRun, MiniLangLLMAgent, mock_agent_run
from zharness.agents.prompts import SYSTEM_PROMPT
from zharness.envs.minilang.generator import Episode, make_episode
from zharness.envs.minilang.verifier import verify_answers
from zharness.eval.cli_utils import parse_extra_body_json
from zharness.eval.minilang_splits import TRANSFORMS, make_target_episode, parse_csv


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Skill:
    skill_id: str
    description: str


def _load_repo_env() -> None:
    load_dotenv(REPO_ROOT / ".env", override=False)


async def run_experiment(args: argparse.Namespace) -> Dict[str, object]:
    _load_repo_env()
    transforms = parse_csv(args.transforms, TRANSFORMS)
    output_dir = _make_output_dir(args.output_dir)

    agent: Optional[MiniLangLLMAgent] = None
    if args.mock_policy is None:
        agent = MiniLangLLMAgent(
            client_name=args.client,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            api_key_env=args.api_key_env,
            base_url_env=args.base_url_env,
            reasoning_effort=args.reasoning_effort,
            extra_body=parse_extra_body_json(args.extra_body_json),
        )

    records: List[Dict[str, object]] = []
    try:
        for episode_index in range(args.episodes):
            seed = args.seed + episode_index
            source_episode = make_episode(
                seed,
                support_budget=args.support_budget,
                parse_tasks=args.parse_tasks,
                generate_tasks=args.generate_tasks,
                difficulty=args.difficulty,
            )
            library = build_skill_library(source_episode)
            removal_ids = [None] + [skill.skill_id for skill in library]
            for transform_name in transforms:
                target_episode = make_target_episode(source_episode, transform_name, seed)
                for removed_skill_id in removal_ids:
                    active_skills = [
                        skill for skill in library if skill.skill_id != removed_skill_id
                    ]
                    record = await _run_one_library(
                        source_episode=source_episode,
                        target_episode=target_episode,
                        transform_name=transform_name,
                        skills=active_skills,
                        removed_skill_id=removed_skill_id,
                        max_called_skills=args.max_called_skills,
                        agent=agent,
                        mock_policy=args.mock_policy,
                        max_retries=args.max_retries,
                    )
                    records.append(record)
                    _append_jsonl(output_dir / "records.jsonl", record)
                    _print_record(record)
    finally:
        if agent is not None:
            await agent.aclose()

    summary = _summarize(records)
    payload = {
        "config": vars(args),
        "skill_ids": [skill.skill_id for skill in build_skill_library(make_episode(args.seed, difficulty=args.difficulty))],
        "summary": summary,
        "num_records": len(records),
    }
    (output_dir / "summary.json").write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote adoption artifacts to {output_dir}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return payload


def build_skill_library(source_episode: Episode) -> List[Skill]:
    return [
        Skill(
            "kg_minimal_contrast",
            "Use minimally different examples to isolate one changing factor at a time before answering.",
        ),
        Skill(
            "kg_generation_audit",
            "For generation tasks, verify that action, object, color, quantity, and negation are each represented exactly once using current evidence.",
        ),
        Skill(
            "kspec_source_rulebook",
            "Previous episode-specific rulebook. This may be useful only if the current episode is the same family:\n"
            + source_episode.world.rulebook_text(),
        ),
        Skill(
            "trap_ignore_agreement",
            "If a command has hyphenated forms, ignore agreement markers because they are decorative and do not affect quantity.",
        ),
        Skill(
            "redundant_minimal_probe",
            "Compare close examples and infer the latent slots before producing final JSON.",
        ),
    ]


async def _run_one_library(
    *,
    source_episode: Episode,
    target_episode: Episode,
    transform_name: str,
    skills: Sequence[Skill],
    removed_skill_id: Optional[str],
    max_called_skills: int,
    agent: Optional[MiniLangLLMAgent],
    mock_policy: Optional[str],
    max_retries: int,
) -> Dict[str, object]:
    errors: List[str] = []
    agent_run = None
    called_skill_ids: List[str] = []
    if mock_policy is not None:
        agent_run = mock_agent_run(target_episode, policy=mock_policy)
    elif agent is None:
        errors.append("ValueError('agent is not initialized')")
    else:
        prompt = build_adoption_prompt(target_episode, skills, max_called_skills)
        for _attempt in range(max_retries + 1):
            try:
                response = await agent.client.chat(
                    [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ]
                )
                payload = parse_answer_payload(response.content)
                raw_called = payload.get("called_skill_ids", [])
                if isinstance(raw_called, list):
                    active_ids = {skill.skill_id for skill in skills}
                    called_skill_ids = [
                        str(skill_id)
                        for skill_id in raw_called
                        if str(skill_id) in active_ids
                    ][:max_called_skills]
                answers = payload.get("answers") if isinstance(payload.get("answers"), list) else []
                agent_run = AgentRun(
                    answers=[answer for answer in answers if isinstance(answer, dict)],
                    raw_response=response.content,
                    usage=response.usage,
                    model=response.model or getattr(agent.client, "model", ""),
                )
                break
            except Exception as exc:
                errors.append(repr(exc))

    if agent_run is None:
        agent_run = mock_agent_run(target_episode, policy="empty")

    verification = verify_answers(target_episode.world, target_episode.tasks, agent_run.answers)
    metrics = verification.to_metrics()
    return {
        "source_episode_id": source_episode.episode_id,
        "target_episode_id": target_episode.episode_id,
        "source_family_id": source_episode.world.family_id,
        "target_family_id": target_episode.world.family_id,
        "transform": transform_name,
        "removed_skill_id": removed_skill_id,
        "active_skill_ids": [skill.skill_id for skill in skills],
        "called_skill_ids": called_skill_ids,
        "metrics": metrics,
        "usage": agent_run.usage,
        "model": agent_run.model,
        "error": " | ".join(errors) if errors else None,
        "attempts": len(errors) + 1 if errors else 1,
        "answers": agent_run.answers,
        "raw_response": agent_run.raw_response,
        "task_results": [asdict(result) for result in verification.task_results],
    }


def build_adoption_prompt(target_episode: Episode, skills: Sequence[Skill], max_called_skills: int) -> str:
    sections = [
        "You are solving one MiniLang episode with a bounded skill library.",
        f"You may invoke at most {max_called_skills} skills. Choose only skills that causally help this current episode.",
        "MiniLang commands map to JSON meanings with fields: action, object, color, count, neg.",
        "Visible examples:",
        *[f"- {example.to_prompt()}" for example in target_episode.examples],
        "",
        "Skill library:",
    ]
    for skill in skills:
        sections.append(f"[{skill.skill_id}] {skill.description}")
    sections.extend(
        [
            "",
            "Tasks:",
            *[f"- {task.to_prompt()}" for task in target_episode.tasks],
            "",
            "Return this JSON schema exactly:",
            '{"called_skill_ids":["kg_minimal_contrast"],"answers":[{"task_id":"p0","meaning":{"action":"jump","object":"door","color":"red","count":2,"neg":false}},{"task_id":"g0","command":"dak mip"}]}',
        ]
    )
    return "\n".join(sections)


def _summarize(records: List[Dict[str, object]]) -> Dict[str, object]:
    full_records = [record for record in records if record["removed_skill_id"] is None]
    removal_records = [record for record in records if record["removed_skill_id"] is not None]
    skill_ids = sorted({skill_id for record in records for skill_id in record["active_skill_ids"]})

    adoption: Dict[str, Dict[str, float]] = {}
    for skill_id in skill_ids:
        called = [record for record in full_records if skill_id in record["called_skill_ids"]]
        adoption[skill_id] = {
            "call_count": len(called),
            "call_rate": len(called) / len(full_records) if full_records else 0.0,
            "success_when_called": mean(
                record["metrics"]["accuracy"] for record in called
            )
            if called
            else 0.0,
        }
        adoption[skill_id]["adoption_score"] = (
            adoption[skill_id]["call_rate"] * adoption[skill_id]["success_when_called"]
        )

    full_by_key = {
        (record["source_episode_id"], record["transform"]): record
        for record in full_records
    }
    removal_delta: Dict[str, Dict[str, float]] = {}
    removal_delta_by_transform: Dict[str, Dict[str, Dict[str, float]]] = {}
    for skill_id in skill_ids:
        deltas = []
        for record in removal_records:
            if record["removed_skill_id"] != skill_id:
                continue
            key = (record["source_episode_id"], record["transform"])
            full = full_by_key.get(key)
            if full is None:
                continue
            deltas.append(full["metrics"]["accuracy"] - record["metrics"]["accuracy"])
        removal_delta[skill_id] = {
            "n": len(deltas),
            "mean_accuracy_delta": mean(deltas) if deltas else 0.0,
        }

    for transform_name in sorted({str(record["transform"]) for record in full_records}):
        removal_delta_by_transform[transform_name] = {}
        for skill_id in skill_ids:
            deltas = []
            for record in removal_records:
                if record["transform"] != transform_name or record["removed_skill_id"] != skill_id:
                    continue
                key = (record["source_episode_id"], record["transform"])
                full = full_by_key.get(key)
                if full is None:
                    continue
                deltas.append(full["metrics"]["accuracy"] - record["metrics"]["accuracy"])
            removal_delta_by_transform[transform_name][skill_id] = {
                "n": len(deltas),
                "mean_accuracy_delta": mean(deltas) if deltas else 0.0,
            }

    by_transform: Dict[str, Dict[str, float]] = {}
    for transform_name in sorted({str(record["transform"]) for record in full_records}):
        matching = [record for record in full_records if record["transform"] == transform_name]
        by_transform[transform_name] = {
            "n": len(matching),
            "accuracy": mean(record["metrics"]["accuracy"] for record in matching),
            "parse_accuracy": mean(record["metrics"]["parse_accuracy"] for record in matching),
            "generate_accuracy": mean(record["metrics"]["generate_accuracy"] for record in matching),
            "avg_total_tokens": mean(
                int(record.get("usage", {}).get("total_tokens", 0) or 0)
                for record in matching
            ),
        }

    adoption_scores = [adoption[skill_id]["adoption_score"] for skill_id in skill_ids]
    deltas = [removal_delta[skill_id]["mean_accuracy_delta"] for skill_id in skill_ids]
    return {
        "full_library": by_transform,
        "adoption": adoption,
        "removal_delta": removal_delta,
        "removal_delta_by_transform": removal_delta_by_transform,
        "spearman_adoption_vs_removal_delta": _spearman(adoption_scores, deltas),
        "num_full_records": len(full_records),
        "num_removal_records": len(removal_records),
    }


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    x_ranks = _ranks(xs)
    y_ranks = _ranks(ys)
    x_mean = mean(x_ranks)
    y_mean = mean(y_ranks)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_ranks, y_ranks))
    x_denom = sum((x - x_mean) ** 2 for x in x_ranks) ** 0.5
    y_denom = sum((y - y_mean) ** 2 for y in y_ranks) ** 0.5
    if x_denom == 0 or y_denom == 0:
        return 0.0
    return numerator / (x_denom * y_denom)


def _ranks(values: Sequence[float]) -> List[float]:
    sorted_pairs = sorted((value, index) for index, value in enumerate(values))
    ranks = [0.0] * len(values)
    cursor = 0
    while cursor < len(sorted_pairs):
        end = cursor + 1
        while end < len(sorted_pairs) and sorted_pairs[end][0] == sorted_pairs[cursor][0]:
            end += 1
        avg_rank = (cursor + end + 1) / 2.0
        for _, index in sorted_pairs[cursor:end]:
            ranks[index] = avg_rank
        cursor = end
    return ranks


def _make_output_dir(raw_output_dir: Optional[str]) -> Path:
    if raw_output_dir:
        output_dir = Path(raw_output_dir)
    else:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_dir = REPO_ROOT / "runs" / "minilang_adoption" / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _append_jsonl(path: Path, record: Dict[str, object]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _print_record(record: Dict[str, object]) -> None:
    metrics = record["metrics"]
    removed = record["removed_skill_id"] or "full"
    called = ",".join(record["called_skill_ids"]) or "-"
    error_marker = " ERROR" if record.get("error") else ""
    print(
        f"{record['source_episode_id']} {record['transform']:<17s} remove={removed:<24s} "
        f"called={called:<44s} acc={metrics['accuracy']:.3f} "
        f"gen={metrics['generate_accuracy']:.3f}{error_marker}"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--episodes", type=int, default=3)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--support-budget", type=int, default=8)
    parser.add_argument("--parse-tasks", type=int, default=4)
    parser.add_argument("--generate-tasks", type=int, default=4)
    parser.add_argument("--difficulty", choices=("basic", "hard"), default="hard")
    parser.add_argument("--transforms", default="same_world,composition_swap,heldout_family")
    parser.add_argument("--max-called-skills", type=int, default=2)
    parser.add_argument("--client", default="openrouter_newapi")
    parser.add_argument("--model", default="deepseek-v3.2")
    parser.add_argument("--api-key-env", default="apihy_API_KEY_deepseek")
    parser.add_argument("--base-url-env", default="apihy_BASE_URL")
    parser.add_argument("--reasoning-effort", default="none")
    parser.add_argument("--extra-body-json", default=None)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max-tokens", type=int, default=2048)
    parser.add_argument("--max-retries", type=int, default=1)
    parser.add_argument("--mock-policy", choices=("oracle", "empty"), default=None)
    parser.add_argument("--output-dir", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
