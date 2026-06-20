from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["queued", "running", "done", "failed"]
TaskType = Literal["chapter_parse", "llm_text"]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Task(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus
    resource_id: str
    run_dir: Path
    result_path: Path | None = None
    error: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=utc_now)
    updated_at: str = Field(default_factory=utc_now)


class TaskSummary(BaseModel):
    task_id: str
    task_type: TaskType
    status: TaskStatus
    resource_id: str


class TaskDetail(Task):
    pass
