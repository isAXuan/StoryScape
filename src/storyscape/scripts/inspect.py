from storyscape.books.registry import BookRegistry
from storyscape.settings import get_settings


def run() -> None:
    settings = get_settings()
    print(f"Books config: {settings.storyscape_books_config}")
    for book in BookRegistry().list_books():
        print(f"- {book.id}: {book.title} ({book.format}) -> {book.path}")

    print(f"Data dir: {settings.storyscape_data_dir}")
    for path in sorted(settings.storyscape_data_dir.glob("*/task.json")):
        print(f"- {path}")
