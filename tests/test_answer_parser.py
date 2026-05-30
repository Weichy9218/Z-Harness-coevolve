"""Tests for robust extraction of model answer JSON."""

from zharness.agents.answer_parser import parse_answer_json


def test_parse_plain_json_answers() -> None:
    answers = parse_answer_json('{"answers":[{"task_id":"p0","meaning":{"action":"jump"}}]}')
    assert answers == [{"task_id": "p0", "meaning": {"action": "jump"}}]


def test_parse_fenced_json_answers() -> None:
    answers = parse_answer_json('```json\n{"answers":[{"task_id":"g0","command":"dak mip"}]}\n```')
    assert answers == [{"task_id": "g0", "command": "dak mip"}]


def test_parse_qwen_thinking_then_final_json() -> None:
    text = """
Thinking Process:
The examples contain {"not": "the final answer"}.
</think>

{"answers":[{"task_id":"p0","meaning":{"action":"jump","object":"door","color":"red","count":2,"neg":false}}]}
"""
    answers = parse_answer_json(text)
    assert answers == [
        {
            "task_id": "p0",
            "meaning": {
                "action": "jump",
                "object": "door",
                "color": "red",
                "count": 2,
                "neg": False,
            },
        }
    ]
