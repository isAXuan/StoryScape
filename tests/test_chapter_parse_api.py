from fastapi.testclient import TestClient

from storyscape.main import create_app


def test_parse_chapters_book_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYSCAPE_BOOKS_CONFIG", str(tmp_path / "missing.yml"))
    monkeypatch.setenv("STORYSCAPE_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    response = client.post("/books/unknown/chapters/parse")

    assert response.status_code == 404


def test_parse_chapters_creates_task(monkeypatch, tmp_path):
    book_path = tmp_path / "book.txt"
    book_path.write_text("第一章\n正文", encoding="utf-8")
    config_path = tmp_path / "books.yml"
    config_path.write_text(
        f"books:\n  - id: book_1\n    title: Book\n    format: txt\n    path: {book_path}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("STORYSCAPE_BOOKS_CONFIG", str(config_path))
    monkeypatch.setenv("STORYSCAPE_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr("storyscape.chapters.api.enqueue_job", lambda *args, **kwargs: "local-job")

    client = TestClient(create_app())
    response = client.post("/books/book_1/chapters/parse")

    assert response.status_code == 200
    body = response.json()
    assert body["task_type"] == "chapter_parse"
    assert body["status"] == "queued"
    assert body["resource_id"] == "book_1"
    task_files = list((tmp_path / "data").glob("book_1_*/task.json"))
    assert len(task_files) == 1
