"""Bounded interactive K_gen runner for MiniLang headroom experiments."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from zharness.agents.answer_parser import parse_answer_payload
from zharness.agents.llm_agent import AgentRun, MiniLangLLMAgent
from zharness.agents.prompts import CONDITION_K_GEN_EXEC, SYSTEM_PROMPT, executable_probe_examples
from zharness.envs.minilang.generator import Episode, Example, Task
from zharness.envs.minilang.verifier import TaskResult, VerificationResult, verify_answers


INTERACTIVE_QUERY_BUDGET = 8
INTERACTIVE_VERIFIER_BUDGET = 1


@dataclass(frozen=True)
class InteractiveRun:
    agent_run: AgentRun
    action_trace: List[Dict[str, object]]
    scaffold_costs: Dict[str, int]
    errors: List[str]


async def run_interactive_k_gen(
    *,
    episode: Episode,
    agent: MiniLangLLMAgent,
    max_retries: int,
) -> InteractiveRun:
    """Run one lean executable-probe draft plus verifier repair cycle."""

    errors: List[str] = []
    action_trace: List[Dict[str, object]] = []
    usage = _empty_usage()
    model = getattr(agent.client, "model", "")

    action_trace.append(
        {
            "type": "propose_hypothesis",
            "source": "k_gen_exec_draft",
            "hypothesis": {"repair_policy": "verify_and_repair_failed_fields"},
            "unknowns": [],
            "response_chars": 0,
        }
    )

    probe_actions = build_executable_probe_actions(episode)
    action_trace.extend(probe_actions)

    draft_run: AgentRun | None = None
    try:
        draft_run = await agent.solve(episode, CONDITION_K_GEN_EXEC)
        _add_usage(usage, draft_run.usage)
        model = draft_run.model or model
    except Exception as exc:
        errors.append(repr(exc))

    if draft_run is None:
        draft_run = AgentRun(answers=[], raw_response="", usage=_empty_usage(), model=model)

    draft_answers = draft_run.answers
    draft_verification = verify_answers(episode.world, episode.tasks, draft_answers)
    feedback = coarse_verifier_feedback(draft_verification, episode=episode)
    action_trace.append(
        {
            "type": "verify_candidate",
            "answers": draft_answers,
            "feedback": feedback,
            "response_chars": len(draft_run.raw_response),
        }
    )

    final_answers = draft_answers
    final_text = ""
    final_payload: Dict[str, object] = {}
    attempted_repair = any(not item.get("correct", False) for item in feedback)
    if attempted_repair:
        try:
            final_text, final_payload, final_usage, final_model = await _chat_json(
                agent=agent,
                user_prompt=build_repair_prompt(
                    episode=episode,
                    probe_actions=probe_actions,
                    draft_answers=draft_answers,
                    feedback=feedback,
                ),
                max_retries=max_retries,
            )
            _add_usage(usage, final_usage)
            model = final_model or model
        except Exception as exc:
            errors.append(repr(exc))

        repair = final_payload.get("repair") if isinstance(final_payload.get("repair"), dict) else {}
        repair_answers = _answers_from_payload(final_payload)
        if repair_answers:
            final_answers, merged_task_ids = preserve_correct_draft_answers(
                draft_answers=draft_answers,
                final_answers=repair_answers,
                feedback=feedback,
            )
        else:
            merged_task_ids = []
        action_trace.append({"type": "repair_candidate", "repair": repair, "response_chars": len(final_text)})
        if merged_task_ids:
            action_trace.append({"type": "no_regression_merge", "task_ids": merged_task_ids})
    else:
        repair = {}
        merged_task_ids = []

    audit = final_payload.get("audit") if isinstance(final_payload.get("audit"), dict) else {"checked": True}
    action_trace.append(
        {
            "type": "final_answer",
            "answers": final_answers,
            "audit": audit,
            "response_chars": len(final_text),
        }
    )

    return InteractiveRun(
        agent_run=AgentRun(
            answers=final_answers,
            raw_response=final_text or draft_run.raw_response,
            usage=usage,
            model=model,
        ),
        action_trace=action_trace,
        scaffold_costs={
            "query_calls": len(probe_actions),
            "verifier_calls": INTERACTIVE_VERIFIER_BUDGET,
            "repair_count": 1 if attempted_repair else 0,
            "final_attempts": 1 if attempted_repair else 0,
            "direct_target_query_violations": 0,
            "rejected_query_calls": 0,
            "no_regression_merges": len(merged_task_ids),
        },
        errors=errors,
    )


def build_executable_probe_actions(episode: Episode) -> List[Dict[str, object]]:
    actions: List[Dict[str, object]] = []
    for index, example in enumerate(executable_probe_examples(episode)):
        actions.append(
            {
                "type": "query_example",
                "query_index": index,
                "source": "k_gen_exec",
                "reason": "executable diagnostic probe",
                "meaning": example.meaning.to_dict(),
                "status": "ok",
                "observation": _example_observation(example),
            }
        )
    return actions


def preserve_correct_draft_answers(
    *,
    draft_answers: Sequence[Dict[str, object]],
    final_answers: Sequence[Dict[str, object]],
    feedback: Sequence[Dict[str, object]],
) -> tuple[List[Dict[str, object]], List[str]]:
    """Preserve draft answers that verifier feedback already marked correct."""

    correct_task_ids = {
        str(item.get("task_id"))
        for item in feedback
        if isinstance(item, dict) and item.get("correct") is True and item.get("task_id")
    }
    if not correct_task_ids:
        return list(final_answers), []

    draft_by_id = {
        str(answer.get("task_id")): answer
        for answer in draft_answers
        if isinstance(answer, dict) and answer.get("task_id")
    }
    merged = [dict(answer) for answer in final_answers if isinstance(answer, dict)]
    changed: List[str] = []
    for task_id in sorted(correct_task_ids):
        draft_answer = draft_by_id.get(task_id)
        if draft_answer is None:
            continue
        did_replace = False
        for index, final_answer in enumerate(merged):
            if str(final_answer.get("task_id")) != task_id:
                continue
            did_replace = True
            if final_answer != draft_answer:
                merged[index] = dict(draft_answer)
                changed.append(task_id)
            break
        if not did_replace:
            merged.append(dict(draft_answer))
            changed.append(task_id)
    return merged, changed


def coarse_verifier_feedback(
    verification: VerificationResult,
    *,
    episode: Episode | None = None,
) -> List[Dict[str, object]]:
    tasks_by_id = {task.task_id: task for task in episode.tasks} if episode is not None else {}
    feedback: List[Dict[str, object]] = []
    for result in verification.task_results:
        feedback.append(
            {
                "task_id": result.task_id,
                "correct": result.correct,
                "labels": [] if result.correct else _feedback_labels(result, tasks_by_id.get(result.task_id), episode),
            }
        )
    return feedback


def build_repair_prompt(
    *,
    episode: Episode,
    probe_actions: Sequence[Dict[str, object]],
    draft_answers: Sequence[Dict[str, object]],
    feedback: Sequence[Dict[str, object]],
) -> str:
    sections = _shared_interactive_context(episode)
    sections.extend(
        [
            "",
            "Executable diagnostic probes used for the draft:",
            *_format_query_actions(probe_actions),
            "",
            "Your draft answers:",
            _jsonish(list(draft_answers), max_chars=1200),
            "",
            "Verifier feedback on your draft. It gives labels only, not corrected answers.",
            "Use labels to repair only failed fields:",
            _jsonish(list(feedback), max_chars=900),
            "Preserve draft answers for tasks marked correct=true.",
            "Return compact JSON only. Do not explain your reasoning.",
            "Return only this JSON schema:",
            '{"repair":{"fields":["count"],"evidence_ids":["q0"]},"answers":[{"task_id":"p0","meaning":{"action":"jump","object":"door","color":"red","count":2,"neg":false}},{"task_id":"g0","command":"dak mip"}],"audit":{"checked":true}}',
        ]
    )
    return "\n".join(sections)


def _shared_interactive_context(episode: Episode) -> List[str]:
    return [
        "You are solving one MiniLang episode with an interactive K_gen harness.",
        "Use only current-episode examples and query observations.",
        "Do not reuse prior episode vocabulary, rulebooks, family ids, or final answers.",
        "MiniLang commands map to JSON meanings with fields: action, object, color, count, neg.",
        "Visible examples:",
        *[f"- {example.to_prompt()}" for example in episode.examples],
        "",
        "Tasks:",
        *[f"- {task.to_prompt()}" for task in episode.tasks],
    ]


async def _chat_json(
    *,
    agent: MiniLangLLMAgent,
    user_prompt: str,
    max_retries: int,
) -> tuple[str, Dict[str, object], Dict[str, int], str]:
    errors: List[str] = []
    for _attempt in range(max_retries + 1):
        try:
            response = await agent.client.chat(
                [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ]
            )
            payload = parse_answer_payload(response.content)
            return (
                response.content,
                payload,
                response.usage,
                response.model or getattr(agent.client, "model", ""),
            )
        except Exception as exc:
            errors.append(repr(exc))
    raise RuntimeError("interactive chat failed: " + " | ".join(errors))


def _answers_from_payload(payload: Dict[str, object]) -> List[Dict[str, object]]:
    answers = payload.get("answers")
    if not isinstance(answers, list):
        return []
    return [answer for answer in answers if isinstance(answer, dict)]


def _feedback_labels(result: TaskResult, task: Task | None, episode: Episode | None) -> List[str]:
    if result.kind == "parse":
        return _parse_feedback_labels(result)
    if result.kind == "generate":
        return _generation_feedback_labels(result, task, episode)
    return ["unknown_error"]


def _generation_feedback_labels(result: TaskResult, task: Task | None, episode: Episode | None) -> List[str]:
    observed = str(result.observed or "").strip()
    if not observed:
        return ["malformed_command"]
    if task is None or task.meaning is None or episode is None:
        return ["wrong_order_or_morphology"]

    world = episode.world
    meaning = task.meaning
    labels: List[str] = []
    if hasattr(world, "concept_to_stem"):
        concept_to_stem = getattr(world, "concept_to_stem")
        if concept_to_stem[f"action:{meaning.action}"] not in observed:
            labels.append("wrong_action")
        if concept_to_stem[f"object:{meaning.object}"] not in observed:
            labels.append("wrong_object")
        if concept_to_stem[f"color:{meaning.color}"] not in observed:
            labels.append("wrong_color")
        count_marker = getattr(world, "count_to_marker")[meaning.count]
        agreement = getattr(world, "agreement_by_count")[meaning.count]
        if count_marker not in observed or agreement not in observed:
            labels.append("wrong_count")
        neg_token = getattr(world, "neg_token")
        if meaning.neg != (neg_token in observed.split()):
            labels.append("wrong_negation")
    else:
        concept_to_token = getattr(world, "concept_to_token")
        expected_tokens = {
            "wrong_action": concept_to_token[f"action:{meaning.action}"],
            "wrong_object": concept_to_token[f"object:{meaning.object}"],
            "wrong_color": concept_to_token[f"color:{meaning.color}"],
            "wrong_count": concept_to_token[f"count:{meaning.count}"],
        }
        observed_tokens = set(observed.split())
        for label, token in expected_tokens.items():
            if token not in observed_tokens:
                labels.append(label)
        neg_token = concept_to_token["neg:true"]
        if meaning.neg != (neg_token in observed_tokens):
            labels.append("wrong_negation")

    return labels or ["wrong_order_or_morphology"]


def _parse_feedback_labels(result: TaskResult) -> List[str]:
    labels: List[str] = []
    expected = result.expected if isinstance(result.expected, dict) else {}
    observed = result.observed if isinstance(result.observed, dict) else {}
    for field, label in (
        ("action", "wrong_action"),
        ("object", "wrong_object"),
        ("color", "wrong_color"),
        ("count", "wrong_count"),
        ("neg", "wrong_negation"),
    ):
        if observed.get(field) != expected.get(field):
            labels.append(label)
    return labels or ["malformed_meaning"]


def _format_query_actions(actions: Sequence[Dict[str, object]]) -> List[str]:
    lines: List[str] = []
    for index, action in enumerate(actions):
        if action.get("status") != "ok":
            lines.append(
                f"- q{index}: rejected ({action.get('rejection_reason', 'unknown')}) "
                f"for {action.get('meaning', {})}"
            )
            continue
        lines.append(f"- q{index}: {_jsonish(action.get('observation', {}), max_chars=400)}")
    return lines


def _example_observation(example: Example) -> Dict[str, object]:
    return {
        "command": example.command,
        "morphemes": _split_morphemes(example.command),
        "meaning": example.meaning.to_dict(),
    }


def _split_morphemes(command: str) -> List[List[str]]:
    return [piece.split("-") for piece in command.split()]


def _empty_usage() -> Dict[str, int]:
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _add_usage(total: Dict[str, int], usage: Dict[str, int]) -> None:
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        total[key] = int(total.get(key, 0) or 0) + int(usage.get(key, 0) or 0)


def _jsonish(value: object, *, max_chars: int = 1200) -> str:
    try:
        import json

        text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "...<truncated>"
