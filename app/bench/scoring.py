"""Objective auto-grading. Free-text categories are measured, not graded."""

import json
import re

from app.bench.models import Task, TaskCategory

_STRIP_CHARS = " \t\r\n。.,，、!！:：;；「」『』\"'`*"
_JSON_OBJECT = re.compile(r"\{.*\}", re.DOTALL)


def score_response(task: Task, text: str) -> bool | None:
    if task.category is TaskCategory.CLASSIFICATION:
        return _first_line(text) == _normalize(task.expected or "")
    if task.category is TaskCategory.EXTRACTION:
        return _fields_match(task.expected_fields or {}, text)
    return None


def _normalize(value: str) -> str:
    return value.strip(_STRIP_CHARS).casefold()


def _first_line(text: str) -> str:
    for line in text.splitlines():
        cleaned = _normalize(line)
        if cleaned:
            return cleaned
    return ""


def _fields_match(expected: dict[str, str], text: str) -> bool:
    actual = _extract_json_object(text)
    if actual is None:
        return False
    return all(
        key in actual and _values_equal(actual[key], value) for key, value in expected.items()
    )


def _extract_json_object(text: str) -> dict | None:
    match = _JSON_OBJECT.search(text)
    if match is None:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _values_equal(actual: object, expected: str) -> bool:
    actual_text = _normalize(str(actual)).replace(",", "")
    expected_text = _normalize(expected).replace(",", "")
    try:
        return float(actual_text) == float(expected_text)
    except ValueError:
        return actual_text == expected_text
