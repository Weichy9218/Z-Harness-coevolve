"""Tests for robust extraction of model answer JSON."""

from zharness.agents.answer_parser import parse_answer_json


def test_parse_plain_json_answers() -> None:
    answers = parse_answer_json('{"answers":[{"task_id":"p0","meaning":{"action":"jump"}}]}')
    assert answers == [{"task_id": "p0", "meaning": {"action": "jump"}}]


def test_parse_fenced_json_answers() -> None:
    answers = parse_answer_json('```json\n{"answers":[{"task_id":"g0","command":"dak mip"}]}\n```')
    assert answers == [{"task_id": "g0", "command": "dak mip"}]

