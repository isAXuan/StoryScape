from fastapi.testclient import TestClient

from storyscape.main import create_app
from storyscape.tasks.store import TaskStore


def test_get_task_returns_task_detail(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYSCAPE_DATA_DIR", str(tmp_path / "data"))
    task = TaskStore().create("chapter_parse", "book_demo_txt")

    client = TestClient(create_app())
    response = client.get(f"/tasks/{task.task_id}")

    assert response.status_code == 200
    assert response.json()["task_id"] == task.task_id


def test_get_task_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYSCAPE_DATA_DIR", str(tmp_path / "data"))

    client = TestClient(create_app())
    response = client.get("/tasks/missing")

    assert response.status_code == 404
