from pathlib import Path

import yaml

from storyscape.books.schemas import Book, BooksConfig
from storyscape.settings import get_settings


class BookRegistry:
    def __init__(self, config_path: Path | None = None) -> None:
        settings = get_settings()
        self.config_path = config_path or settings.storyscape_books_config

    def list_books(self) -> list[Book]:
        if not self.config_path.exists():
            return []

        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        config = BooksConfig.model_validate(raw)
        books: list[Book] = []
        for book in config.books:
            path = book.path
            if not path.is_absolute():
                path = path.resolve()
            books.append(book.model_copy(update={"path": path}))
        return books

    def get_book(self, book_id: str) -> Book | None:
        return next((book for book in self.list_books() if book.id == book_id), None)
