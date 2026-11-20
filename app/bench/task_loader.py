"""Load and validate the benchmark task set from YAML."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.bench.models import Task


class TaskFileError(Exception):
    pass


def load_tasks(path: Path) -> list[Task]:
    if not path.is_file():
        raise TaskFileError(f"task file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise TaskFileError(f"invalid YAML in {path}: {exc}") from exc

    entries = raw.get("tasks") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise TaskFileError(f"{path} must contain a non-empty 'tasks' list")

    try:
        tasks = [Task.model_validate(entry) for entry in entries]
    except ValidationError as exc:
        raise TaskFileError(f"invalid task in {path}: {exc}") from exc

    ids = [task.id for task in tasks]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise TaskFileError(f"duplicate task ids in {path}: {duplicates}")

    return tasks
