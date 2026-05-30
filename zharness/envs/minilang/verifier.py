"""Verify MiniLang parse/generation answers and compute task metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Sequence

from .generator import Meaning, Task, World, normalized_command


@dataclass(frozen=True)
class TaskResult:
    task_id: str
    kind: str
    correct: bool
    expected: object
    observed: object


@dataclass(frozen=True)
class VerificationResult:
    task_results: List[TaskResult]

    @property
    def accuracy(self) -> float:
        if not self.task_results:
            return 0.0
        return sum(result.correct for result in self.task_results) / len(self.task_results)

    @property
    def parse_accuracy(self) -> float:
        return _accuracy_for_kind(self.task_results, "parse")

    @property
    def generate_accuracy(self) -> float:
        return _accuracy_for_kind(self.task_results, "generate")

    def to_metrics(self) -> Dict[str, float]:
        return {
            "accuracy": self.accuracy,
            "parse_accuracy": self.parse_accuracy,
            "generate_accuracy": self.generate_accuracy,
            "num_tasks": float(len(self.task_results)),
        }


def verify_answers(world: World, tasks: Sequence[Task], answers: Sequence[Dict[str, object]]) -> VerificationResult:
    by_id = {str(answer.get("task_id", "")): answer for answer in answers if isinstance(answer, dict)}
    results: List[TaskResult] = []

    for task in tasks:
        answer = by_id.get(task.task_id, {})
        if task.kind == "parse" and task.meaning is not None:
            observed_raw = answer.get("meaning") if isinstance(answer, dict) else None
            try:
                observed = Meaning.from_dict(observed_raw if isinstance(observed_raw, dict) else {})
            except (TypeError, ValueError):
                observed = None
            results.append(
                TaskResult(
                    task_id=task.task_id,
                    kind=task.kind,
                    correct=observed == task.meaning,
                    expected=task.meaning.to_dict(),
                    observed=observed.to_dict() if observed is not None else observed_raw,
                )
            )
            continue

        if task.kind == "generate" and task.meaning is not None:
            expected_command = world.encode(task.meaning)
            observed_command = normalized_command(answer.get("command") if isinstance(answer, dict) else "")
            results.append(
                TaskResult(
                    task_id=task.task_id,
                    kind=task.kind,
                    correct=observed_command == expected_command,
                    expected=expected_command,
                    observed=observed_command,
                )
            )
            continue

        raise ValueError(f"unknown task kind: {task.kind}")

    return VerificationResult(task_results=results)


def _accuracy_for_kind(results: Sequence[TaskResult], kind: str) -> float:
    subset = [result for result in results if result.kind == kind]
    if not subset:
        return 0.0
    return sum(result.correct for result in subset) / len(subset)

