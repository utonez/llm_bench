from pathlib import Path

import pytest

from app.bench.models import TaskCategory
from app.bench.task_loader import TaskFileError, load_tasks

REPO_TASKS_DIR = Path(__file__).resolve().parents[1] / "tasks"

VALID_SOURCE = "{name: s, url: 'https://example.com', license: CC-BY-4.0, locator: row 1}"


def write(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_repo_task_dir_loads_with_unique_ids():
    tasks = load_tasks(REPO_TASKS_DIR)

    assert len(tasks) >= 20
    assert len({t.id for t in tasks}) == len(tasks)


def test_repo_tasks_cover_every_category():
    tasks = load_tasks(REPO_TASKS_DIR)

    assert {t.category for t in tasks} == set(TaskCategory)


def test_every_repo_task_cites_a_source_with_license():
    for task in load_tasks(REPO_TASKS_DIR):
        assert task.source.url.startswith("https://")
        assert task.source.license
        assert task.source.locator


def test_directory_loading_merges_files_in_name_order(tmp_path):
    write(
        tmp_path / "b.yaml",
        f"tasks:\n  - {{id: b1, category: summary, prompt: x, source: {VALID_SOURCE}}}\n",
    )
    write(
        tmp_path / "a.yaml",
        f"tasks:\n  - {{id: a1, category: summary, prompt: x, source: {VALID_SOURCE}}}\n",
    )
    write(tmp_path / "notes.md", "ignored")

    assert [t.id for t in load_tasks(tmp_path)] == ["a1", "b1"]


def test_rejects_duplicate_ids_across_files(tmp_path):
    for name in ("a.yaml", "b.yaml"):
        write(
            tmp_path / name,
            f"tasks:\n  - {{id: same, category: summary, prompt: x, source: {VALID_SOURCE}}}\n",
        )

    with pytest.raises(TaskFileError, match="duplicate"):
        load_tasks(tmp_path)


def test_rejects_task_without_source(tmp_path):
    path = write(tmp_path / "t.yaml", "tasks:\n  - {id: a, category: summary, prompt: x}\n")

    with pytest.raises(TaskFileError):
        load_tasks(path)


def test_rejects_invalid_category(tmp_path):
    path = write(
        tmp_path / "t.yaml",
        f"tasks:\n  - {{id: a, category: poetry, prompt: x, source: {VALID_SOURCE}}}\n",
    )

    with pytest.raises(TaskFileError):
        load_tasks(path)


def test_rejects_empty_directory(tmp_path):
    with pytest.raises(TaskFileError, match="no task files"):
        load_tasks(tmp_path)


def test_rejects_missing_path(tmp_path):
    with pytest.raises(TaskFileError, match="not found"):
        load_tasks(tmp_path / "nope.yaml")
