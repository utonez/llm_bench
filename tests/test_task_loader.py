from pathlib import Path

import pytest

from app.bench.models import TaskCategory
from app.bench.task_loader import TaskFileError, load_tasks

REPO_TASKS = Path(__file__).resolve().parents[1] / "tasks" / "finance_tasks.yaml"


def test_repo_task_file_loads_with_unique_ids():
    tasks = load_tasks(REPO_TASKS)

    assert len(tasks) >= 12
    assert len({t.id for t in tasks}) == len(tasks)


def test_repo_task_file_covers_every_category():
    tasks = load_tasks(REPO_TASKS)

    assert {t.category for t in tasks} == set(TaskCategory)


def test_graded_tasks_have_answers():
    for task in load_tasks(REPO_TASKS):
        if task.category is TaskCategory.CLASSIFICATION:
            assert task.expected
        if task.category is TaskCategory.EXTRACTION:
            assert task.expected_fields


def test_rejects_duplicate_ids(tmp_path):
    path = tmp_path / "dup.yaml"
    path.write_text(
        "tasks:\n"
        "  - {id: a, category: summary, prompt: x}\n"
        "  - {id: a, category: summary, prompt: y}\n",
        encoding="utf-8",
    )

    with pytest.raises(TaskFileError, match="duplicate"):
        load_tasks(path)


def test_rejects_invalid_schema(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("tasks:\n  - {id: a, category: poetry, prompt: x}\n", encoding="utf-8")

    with pytest.raises(TaskFileError):
        load_tasks(path)


def test_rejects_missing_file(tmp_path):
    with pytest.raises(TaskFileError, match="not found"):
        load_tasks(tmp_path / "nope.yaml")
