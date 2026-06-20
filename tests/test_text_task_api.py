import json

from fastapi.testclient import TestClient

from storyscape.chapters.schemas import Chapter
from storyscape.chapters.store import ChapterStore
from storyscape.main import create_app


def test_text_task_chapter_not_found(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYSCAPE_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    response = client.post(
        "/chapters/missing/text-task",
        json={"audio_profile": {"audio_model": "m", "required_fields": [], "voice_mapping": {}}},
    )

    assert response.status_code == 404


def test_text_task_creates_task(monkeypatch, tmp_path):
    monkeypatch.setenv("STORYSCAPE_DATA_DIR", str(tmp_path / "data"))
    chapter = Chapter(
        chapter_id="chapter_1234",
        book_id="book_1",
        order_index=1,
        title="第一章",
        text="正文",
    )
    ChapterStore(data_dir=tmp_path / "data").save_book_chapters("book_1", [chapter])
    monkeypatch.setattr("storyscape.llm_text.api.enqueue_job", lambda *args, **kwargs: "local-job")

    client = TestClient(create_app())
    response = client.post(
        "/chapters/chapter_1234/text-task",
        json={
            "audio_profile": {
                "audio_model": "audio-model",
                "required_fields": ["voice_id"],
                "voice_mapping": {"narrator": {"voice_id": "v1"}},
            }
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["task_type"] == "llm_text"
    assert body["resource_id"] == "chapter_1234"
    task_path = next((tmp_path / "data").glob("chapter_1234_*/task.json"))
    assert json.loads(task_path.read_text(encoding="utf-8"))["payload"]["audio_profile"]["audio_model"]
