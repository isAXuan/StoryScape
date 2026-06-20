from loguru import logger

from storyscape.books.registry import BookRegistry
from storyscape.chapters.parser import parse_book
from storyscape.chapters.store import ChapterStore
from storyscape.tasks.store import TaskStore


def parse_chapters_job(task_id: str, book_id: str) -> None:
    store = TaskStore()
    logger.info("parse_chapters_job start | task_id={} book_id={}", task_id, book_id)
    try:
        store.update(task_id, "running")
        task = store.require(task_id)
        book = BookRegistry().get_book(book_id)
        if book is None:
            raise ValueError(f"Book not found: {book_id}")
        if not book.path.exists():
            raise FileNotFoundError(f"Book file not found: {book.path}")

        chapters = parse_book(book)
        logger.info("parsed {} chapters for book_id={}", len(chapters), book_id)
        ChapterStore(run_dir=task.run_dir).save_book_chapters(book_id, chapters)
        result_path = task.run_dir / "chapters.json"
        store.update(task_id, "done", result_path=result_path)
        logger.info("parse_chapters_job done | task_id={} result={}", task_id, result_path)
    except Exception as exc:
        logger.error("parse_chapters_job failed | task_id={} error={}", task_id, exc)
        store.update(task_id, "failed", error=str(exc))
        raise
