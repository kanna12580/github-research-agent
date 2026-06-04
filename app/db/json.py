from __future__ import annotations

import json
from enum import Enum
from typing import Any


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def dumps_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, default=_json_default)
