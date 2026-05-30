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
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?", "", candidate, flags=re.IGNORECASE).strip()
        candidate = re.sub(r"```$", "", candidate).strip()
    if candidate.startswith("{") and candidate.endswith("}"):
        return candidate

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    return candidate[start : end + 1]

