"""Load and validate the benchmark task set from a YAML file or a directory of them."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.bench.models import Task

TASK_FILE_SUFFIXES = (".yaml", ".yml")


class TaskFileError(Exception):
    pass


def load_tasks(path: Path) -> list[Task]:
    """Load one task file, or every *.yaml in a directory (sorted by file name)."""
    files = _task_files(path)
    tasks = [task for file in files for task in _load_file(file)]

    ids = [task.id for task in tasks]
    duplicates = sorted({task_id for task_id in ids if ids.count(task_id) > 1})
    if duplicates:
        raise TaskFileError(f"duplicate task ids under {path}: {duplicates}")
    return tasks


def _task_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise TaskFileError(f"task path not found: {path}")
    files = sorted(p for p in path.iterdir() if p.suffix in TASK_FILE_SUFFIXES)
    if not files:
        raise TaskFileError(f"no task files (*.yaml) in {path}")
    return files


def _load_file(path: Path) -> list[Task]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise TaskFileError(f"invalid YAML in {path}: {exc}") from exc

    entries = raw.get("tasks") if isinstance(raw, dict) else None
    if not isinstance(entries, list) or not entries:
        raise TaskFileError(f"{path} must contain a non-empty 'tasks' list")

    try:
        return [Task.model_validate(entry) for entry in entries]
    except ValidationError as exc:
        raise TaskFileError(f"invalid task in {path}: {exc}") from exc
