import json
import re
import uuid
from pathlib import Path
from typing import Any

from storyscape.settings import get_settings
from storyscape.tasks.schemas import Task, TaskStatus, TaskSummary, TaskType, utc_now


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TaskStore:
    def __init__(self, data_dir: Path | None = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or settings.storyscape_data_dir
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        task_type: TaskType,
        resource_id: str,
        payload: dict[str, Any] | None = None,
    ) -> Task:
        task_id = new_id("task")
        task = Task(
            task_id=task_id,
            task_type=task_type,
            status="queued",
            resource_id=resource_id,
            run_dir=self._run_dir(resource_id, task_id),
            payload=payload or {},
        )
        self.save(task)
        return task

    def get(self, task_id: str) -> Task | None:
        path = self._path(task_id)
        if path is None:
            return None
        return Task.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, task: Task) -> None:
        task.updated_at = utc_now()
        task.run_dir.mkdir(parents=True, exist_ok=True)
        self._task_file(task).write_text(
            json.dumps(task.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def update(
        self,
        task_id: str,
        status: TaskStatus,
        result_path: Path | None = None,
        error: str | None = None,
    ) -> Task:
        task = self.require(task_id)
        task.status = status
        task.result_path = result_path
        task.error = error
        self.save(task)
        return task

    def require(self, task_id: str) -> Task:
        task = self.get(task_id)
        if task is None:
            raise FileNotFoundError(f"Task not found: {task_id}")
        return task

    def summary(self, task: Task) -> TaskSummary:
        return TaskSummary(
            task_id=task.task_id,
            task_type=task.task_type,
            status=task.status,
            resource_id=task.resource_id,
        )

    def _path(self, task_id: str) -> Path | None:
        for path in self.data_dir.glob("*/task.json"):
            try:
                task = Task.model_validate_json(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            if task.task_id == task_id:
                return path

        legacy_path = self.data_dir / "tasks" / f"{task_id}.json"
        if legacy_path.exists():
            return legacy_path
        return None

    def _run_dir(self, resource_id: str, task_id: str) -> Path:
        task_uuid = task_id.removeprefix("task_")
        return self.data_dir / f"{_safe_path_part(resource_id)}_{task_uuid}"

    def _task_file(self, task: Task) -> Path:
        return task.run_dir / "task.json"


def _safe_path_part(value: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff.-]+", "_", value, flags=re.UNICODE)
    return cleaned.strip("._") or "task"
