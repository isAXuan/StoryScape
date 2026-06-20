import json

from storyscape.chapters.schemas import Chapter
from storyscape.chapters.store import ChapterStore


def test_save_book_chapters_uses_ordered_filenames(tmp_path):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "book_1_abcd1234"
    store = ChapterStore(data_dir=data_dir, run_dir=run_dir)
    chapters = [
        Chapter(
            chapter_id="chapter_bbbb",
            book_id="book_1",
            order_index=2,
            title="第二章",
            text="正文二",
        ),
        Chapter(
            chapter_id="chapter_aaaa",
            book_id="book_1",
            order_index=1,
            title="第一章",
            text="正文一",
        ),
    ]

    index = store.save_book_chapters("book_1", chapters)

    book_dir = run_dir / "chapters"
    assert sorted(path.name for path in book_dir.glob("*.json")) == [
        "0001_chapter_aaaa.json",
        "0002_chapter_bbbb.json",
        "chapters.json",
    ]
    assert [item.source_path.name for item in index.chapters] == [
        "0002_chapter_bbbb.json",
        "0001_chapter_aaaa.json",
    ]

    index_data = json.loads((book_dir / "chapters.json").read_text(encoding="utf-8"))
    assert [item["source_path"] for item in index_data["chapters"]] == [
        str(book_dir / "0002_chapter_bbbb.json"),
        str(book_dir / "0001_chapter_aaaa.json"),
    ]


def test_save_book_chapters_removes_stale_files(tmp_path):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "book_1_abcd1234"
    store = ChapterStore(data_dir=data_dir, run_dir=run_dir)
    old_dir = run_dir / "chapters"
    (old_dir / "chapter_stale.json").write_text("{}", encoding="utf-8")

    store.save_book_chapters(
        "book_1",
        [
            Chapter(
                chapter_id="chapter_fresh",
                book_id="book_1",
                order_index=1,
                title="第一章",
                text="正文",
            )
        ],
    )

    assert not (old_dir / "chapter_stale.json").exists()
    assert (old_dir / "0001_chapter_fresh.json").exists()


def test_find_chapter_reads_ordered_filename(tmp_path):
    data_dir = tmp_path / "data"
    run_dir = data_dir / "book_1_abcd1234"
    store = ChapterStore(data_dir=data_dir, run_dir=run_dir)
    store.save_book_chapters(
        "book_1",
        [
            Chapter(
                chapter_id="chapter_1234",
                book_id="book_1",
                order_index=1,
                title="第一章",
                text="正文",
            )
        ],
    )

    chapter = store.find_chapter("chapter_1234")

    assert chapter is not None
    assert chapter.title == "第一章"
