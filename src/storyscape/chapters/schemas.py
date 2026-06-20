from pathlib import Path

from pydantic import BaseModel


class Chapter(BaseModel):
    chapter_id: str
    book_id: str
    order_index: int
    title: str
    text: str
    source_path: Path | None = None


class ChapterIndexItem(BaseModel):
    chapter_id: str
    book_id: str
    order_index: int
    title: str
    source_path: Path


class ChapterIndex(BaseModel):
    book_id: str
    chapters: list[ChapterIndexItem]
