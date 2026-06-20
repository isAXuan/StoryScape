from pathlib import Path

from storyscape.books.schemas import Book
from storyscape.chapters.parser import parse_epub, parse_txt


def test_parse_txt_detects_common_chapters(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("第一章 开始\n内容一\n\nChapter 2 Return\n内容二", encoding="utf-8")
    book = Book(id="book_1", title="Book", format="txt", path=path)

    chapters = parse_txt(book)

    assert [chapter.title for chapter in chapters] == ["第一章 开始", "Chapter 2 Return"]
    assert chapters[0].order_index == 1
    assert chapters[0].book_id == "book_1"


def test_parse_txt_detects_chinese_title_without_space(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("第一章活着\n内容一\n\n第二章异质\n内容二", encoding="utf-8")
    book = Book(id="book_1", title="Book", format="txt", path=path)

    chapters = parse_txt(book)

    assert [chapter.title for chapter in chapters] == ["第一章活着", "第二章异质"]


def test_parse_txt_ignores_volume_titles_and_inline_ordinals(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text(
        "\n".join(
            [
                "第一章活着",
                "内容一",
                "　　第二天清晨，许青醒来。",
                "　　第一卷，惊蛰。",
                "第二章异质",
                "内容二",
                "　　第三个，是那个青年。",
            ]
        ),
        encoding="utf-8",
    )
    book = Book(id="book_1", title="Book", format="txt", path=path)

    chapters = parse_txt(book)

    assert [chapter.title for chapter in chapters] == ["第一章活着", "第二章异质"]


def test_parse_txt_ignores_site_noise_and_duplicate_free_reading_lines(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text(
        "\n".join(
            [
                "------章节内容开始-------",
                "第一章活着",
                "内容一",
                "　　第一章活着免费阅读.",
                "第二章异质",
                "内容二",
            ]
        ),
        encoding="utf-8",
    )
    book = Book(id="book_1", title="Book", format="txt", path=path)

    chapters = parse_txt(book)

    assert [chapter.title for chapter in chapters] == ["第一章活着", "第二章异质"]


def test_parse_txt_without_headings_creates_single_chapter(tmp_path):
    path = tmp_path / "book.txt"
    path.write_text("没有章节标题的正文", encoding="utf-8")
    book = Book(id="book_1", title="Book", format="txt", path=path)

    chapters = parse_txt(book)

    assert len(chapters) == 1
    assert chapters[0].title == "Book"


def test_parse_epub_reads_sample_chapter():
    book = Book(
        id="book_demo_epub",
        title="Demo EPUB Book",
        format="epub",
        path=Path("samples/books/demo.epub"),
    )

    chapters = parse_epub(book)

    assert len(chapters) == 1
    assert chapters[0].book_id == "book_demo_epub"
    assert chapters[0].title == "第一章 EPUB"
    assert "这是 EPUB 样例章节" in chapters[0].text
