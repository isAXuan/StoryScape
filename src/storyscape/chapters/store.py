import json
import shutil
from pathlib import Path

from storyscape.chapters.schemas import Chapter, ChapterIndex, ChapterIndexItem
from storyscape.settings import get_settings


class ChapterStore:
    def __init__(self, data_dir: Path | None = None, run_dir: Path | None = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or settings.storyscape_data_dir
        self.chapters_dir = (run_dir or self.data_dir) / "chapters"
        self.chapters_dir.mkdir(parents=True, exist_ok=True)

    def save_book_chapters(self, book_id: str, chapters: list[Chapter]) -> ChapterIndex:
        book_dir = self.chapters_dir
        if book_dir.exists():
            shutil.rmtree(book_dir)
        book_dir.mkdir(parents=True, exist_ok=True)
        items: list[ChapterIndexItem] = []

        for chapter in chapters:
            path = book_dir / _chapter_filename(chapter)
            chapter = chapter.model_copy(update={"source_path": path})
            path.write_text(
                json.dumps(chapter.model_dump(mode="json"), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            items.append(
                ChapterIndexItem(
                    chapter_id=chapter.chapter_id,
                    book_id=chapter.book_id,
                    order_index=chapter.order_index,
                    title=chapter.title,
                    source_path=path,
                )
            )

        index = ChapterIndex(book_id=book_id, chapters=items)
        (book_dir.parent / "chapters.json").write_text(
            json.dumps(index.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return index

    def find_chapter(self, chapter_id: str) -> Chapter | None:
        for path in self.data_dir.glob(f"*/chapters/*_{chapter_id}.json"):
            return Chapter.model_validate_json(path.read_text(encoding="utf-8"))
        for path in self.chapters_dir.glob(f"*_{chapter_id}.json"):
            return Chapter.model_validate_json(path.read_text(encoding="utf-8"))
        for path in self.data_dir.glob(f"*/chapters/{chapter_id}.json"):
            return Chapter.model_validate_json(path.read_text(encoding="utf-8"))
        return None


def _chapter_filename(chapter: Chapter) -> str:
    return f"{chapter.order_index:04d}_{chapter.chapter_id}.json"
