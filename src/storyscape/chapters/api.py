from fastapi import APIRouter, HTTPException

from storyscape.books.registry import BookRegistry
from storyscape.chapters.jobs import parse_chapters_job
from storyscape.tasks.queue import enqueue_job
from storyscape.tasks.schemas import TaskSummary
from storyscape.tasks.store import TaskStore

router = APIRouter(prefix="/books", tags=["chapters"])


@router.post("/{book_id}/chapters/parse", response_model=TaskSummary)
def parse_chapters(book_id: str) -> TaskSummary:
    book = BookRegistry().get_book(book_id)
    if book is None:
        raise HTTPException(status_code=404, detail="Book not found")

    store = TaskStore()
    task = store.create("chapter_parse", resource_id=book_id)
    enqueue_job(parse_chapters_job, task.task_id, book_id)
    return store.summary(task)
