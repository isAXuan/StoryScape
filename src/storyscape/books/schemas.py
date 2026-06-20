from pathlib import Path
from typing import Literal

from pydantic import BaseModel


BookFormat = Literal["txt", "epub"]


class Book(BaseModel):
    id: str
    title: str
    format: BookFormat
    path: Path


class BooksConfig(BaseModel):
    books: list[Book]
