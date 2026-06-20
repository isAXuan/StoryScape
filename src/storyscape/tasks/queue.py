import importlib
import json
import sqlite3
import time
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from storyscape.settings import get_settings

QUEUE_NAME = "storyscape"


def _job_id() -> str:
    return f"job_{uuid.uuid4().hex[:8]}"


def _callable_path(func: Callable[..., Any]) -> str:
    return f"{func.__module__}:{func.__name__}"


def _connect(db_path: Path | None = None) -> sqlite3.Connection:
    settings = get_settings()
    path = db_path or settings.storyscape_task_queue_db
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS queued_jobs (
            job_id TEXT PRIMARY KEY,
            func_path TEXT NOT NULL,
            args_json TEXT NOT NULL,
            status TEXT NOT NULL,
            attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 1,
            error TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    return conn


def enqueue_job(func: Callable[..., Any], *args: Any, retry_count: int = 0) -> str:
    job_id = _job_id()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO queued_jobs (job_id, func_path, args_json, status, max_attempts)
            VALUES (?, ?, ?, 'queued', ?)
            """,
            (
                job_id,
                _callable_path(func),
                json.dumps(args, ensure_ascii=False),
                retry_count + 1,
            ),
        )
    return job_id


def work_forever(poll_interval: float = 1.0) -> None:
    while True:
        try:
            worked = work_once()
        except Exception as exc:
            print(f"Job failed: {exc}")
            worked = True
        if not worked:
            time.sleep(poll_interval)


def work_once() -> bool:
    job = _claim_next_job()
    if job is None:
        return False

    try:
        func = _load_callable(job["func_path"])
        args = json.loads(job["args_json"])
        func(*args)
    except Exception as exc:
        _mark_failed_or_retry(job, exc)
        raise
    else:
        _mark_done(job["job_id"])
    return True


def _claim_next_job() -> sqlite3.Row | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT * FROM queued_jobs
            WHERE status = 'queued'
            ORDER BY created_at, job_id
            LIMIT 1
            """
        ).fetchone()
        if row is None:
            return None

        conn.execute(
            """
            UPDATE queued_jobs
            SET status = 'running', attempts = attempts + 1, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (row["job_id"],),
        )
        return row


def _load_callable(func_path: str) -> Callable[..., Any]:
    module_name, func_name = func_path.split(":", 1)
    module = importlib.import_module(module_name)
    func = getattr(module, func_name)
    if not callable(func):
        raise TypeError(f"Queued object is not callable: {func_path}")
    return func


def _mark_failed_or_retry(job: sqlite3.Row, exc: Exception) -> None:
    status = "queued" if job["attempts"] + 1 < job["max_attempts"] else "failed"
    with _connect() as conn:
        conn.execute(
            """
            UPDATE queued_jobs
            SET status = ?, error = ?, updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (status, str(exc), job["job_id"]),
        )


def _mark_done(job_id: str) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE queued_jobs
            SET status = 'done', updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """,
            (job_id,),
        )
