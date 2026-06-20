from storyscape.tasks.store import TaskStore


def test_task_store_create_and_update(tmp_path):
    store = TaskStore(data_dir=tmp_path)

    task = store.create("chapter_parse", "book_demo_txt")

    assert task.status == "queued"
    assert task.run_dir.parent == tmp_path
    assert task.run_dir.name.startswith("book_demo_txt_")
    assert (task.run_dir / "task.json").exists()
    assert store.get(task.task_id) is not None

    updated = store.update(task.task_id, "done", result_path=tmp_path / "result.json")

    assert updated.status == "done"
    assert updated.result_path == tmp_path / "result.json"
