"""Shared CLI parsing helpers for experiment runners."""

from __future__ import annotations

import json
from typing import Dict, Optional


def parse_extra_body_json(raw: Optional[str]) -> Optional[Dict[str, object]]:
    if raw is None or not str(raw).strip():
        return None
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("--extra-body-json must decode to a JSON object")
    return data

