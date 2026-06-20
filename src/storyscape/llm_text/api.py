from fastapi import APIRouter, HTTPException

from storyscape.chapters.store import ChapterStore
from storyscape.llm_text.jobs import llm_text_job
from storyscape.llm_text.schemas import TextTaskRequest
from storyscape.tasks.queue import enqueue_job
from storyscape.tasks.schemas import TaskSummary
from storyscape.tasks.store import TaskStore

router = APIRouter(prefix="/chapters", tags=["llm_text"])


@router.post("/{chapter_id}/text-task", response_model=TaskSummary)
def create_text_task(chapter_id: str, request: TextTaskRequest) -> TaskSummary:
    chapter = ChapterStore().find_chapter(chapter_id)
    if chapter is None:
        raise HTTPException(status_code=404, detail="Chapter not found")

    store = TaskStore()
    task = store.create(
        "llm_text",
        resource_id=chapter_id,
        payload={"audio_profile": request.audio_profile.model_dump()},
    )
    enqueue_job(
        llm_text_job,
        task.task_id,
        chapter_id,
        request.audio_profile.model_dump(),
        retry_count=5,
    )
    return store.summary(task)
