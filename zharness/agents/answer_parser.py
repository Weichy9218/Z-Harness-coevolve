"""Parse model JSON answers from occasionally noisy chat completions."""

from __future__ import annotations

import json
import re
from typing import Dict, List


def parse_answer_json(text: str) -> List[Dict[str, object]]:
    payload = _extract_json_payload(text)
    if payload is None:
        return []
    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, list):
        return []
    return [answer for answer in answers if isinstance(answer, dict)]


def _extract_json_payload(text: str) -> str | None:
    candidate = str(text or "").strip()
    if not candidate:
        return None
    if "</think>" in candidate:
        candidate = candidate.rsplit("</think>", 1)[-1].strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"```$", "", candidate).strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        return candidate

    return _last_balanced_json_object(candidate)


def _last_balanced_json_object(text: str) -> str | None:
    end = text.rfind("}")
    if end == -1:
        return None

    depth = 0
    in_string = False
    escaped = False
    for index in range(end, -1, -1):
        char = text[index]
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_string:
            escaped = True
            continue
        if char == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if char == "}":
            depth += 1
            continue
        if char == "{":
            depth -= 1
            if depth == 0:
                return text[index : end + 1]
    return None
