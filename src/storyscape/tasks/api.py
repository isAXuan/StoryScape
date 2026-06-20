from fastapi import APIRouter, HTTPException

from storyscape.tasks.schemas import TaskDetail
from storyscape.tasks.store import TaskStore

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("/{task_id}", response_model=TaskDetail)
def get_task(task_id: str) -> TaskDetail:
    task = TaskStore().get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskDetail.model_validate(task.model_dump())
