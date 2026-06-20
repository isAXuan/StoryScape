import sqlite3

from storyscape.tasks.queue import enqueue_job, work_once


def _write_marker(path: str, value: str) -> None:
    with open(path, "w", encoding="utf-8") as file:
        file.write(value)


def test_sqlite_queue_runs_one_job(monkeypatch, tmp_path):
    db_path = tmp_path / "queue.sqlite3"
    marker_path = tmp_path / "marker.txt"
    monkeypatch.setenv("STORYSCAPE_TASK_QUEUE_DB", str(db_path))

    job_id = enqueue_job(_write_marker, str(marker_path), "done")

    assert work_once() is True
    assert marker_path.read_text(encoding="utf-8") == "done"

    with sqlite3.connect(db_path) as conn:
        status = conn.execute(
            "SELECT status FROM queued_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()[0]
    assert status == "done"
