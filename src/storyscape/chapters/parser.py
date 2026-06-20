import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT
from ebooklib import epub

from storyscape.books.schemas import Book
from storyscape.chapters.schemas import Chapter
from storyscape.tasks.store import new_id

TXT_TITLE_MAX_LENGTH = 80
TXT_CHINESE_NUMERAL = "零〇一二两三四五六七八九十百千万亿壹贰叁肆伍陆柒捌玖拾佰仟萬"
TXT_CHAPTER_PATTERNS = [
    re.compile(
        rf"^[【\[]?第[{TXT_CHINESE_NUMERAL}\d０-９]{{1,12}}[章节回][】\]]?"
        r"(?:[ \t\u3000:：、，,.-]*[^\r\n]{0,60})?$"
    ),
    re.compile(r"^(?:序章|楔子|引子|前言|后记|尾声|终章)(?:[ \t\u3000:：、，,.-]*[^\r\n]{0,50})?$"),
    re.compile(r"^(?:番外|番外篇|外传|特别篇|插话)(?:[ \t\u3000:：、，,.-]*[^\r\n]{0,50})?$"),
    re.compile(r"^(?:chapter|chap\.?|ch\.?)\s+[0-9ivxlcdm]+(?:[:.\s-]+[^\r\n]{0,60})?$", re.IGNORECASE),
]
TXT_NOISE_KEYWORDS = (
    "章节目录",
    "正文目录",
    "免费阅读",
    "最新网址",
    "最新章节",
    "请收藏",
    "浏览器搜索",
    "爱下电子书",
    "www.",
    "http://",
    "https://",
)


def parse_book(book: Book) -> list[Chapter]:
    if book.format == "txt":
        return parse_txt(book)
    if book.format == "epub":
        return parse_epub(book)
    raise ValueError(f"Unsupported book format: {book.format}")


def parse_txt(book: Book) -> list[Chapter]:
    text = _read_text(book.path)
    lines = text.splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        title = _txt_chapter_title(line)
        if title is not None:
            starts.append((index, title))

    if not starts:
        return [
            Chapter(
                chapter_id=new_id("chapter"),
                book_id=book.id,
                order_index=1,
                title=book.title,
                text=text.strip(),
            )
        ]

    chapters: list[Chapter] = []
    preface = _clean_txt_preface(lines[: starts[0][0]])
    order_index = 1
    if preface:
        chapters.append(
            Chapter(
                chapter_id=new_id("chapter"),
                book_id=book.id,
                order_index=order_index,
                title="Preface",
                text=preface,
            )
        )
        order_index += 1

    for position, (line_index, title) in enumerate(starts):
        next_index = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        chapter_text = "\n".join(lines[line_index:next_index]).strip()
        if chapter_text:
            chapters.append(
                Chapter(
                    chapter_id=new_id("chapter"),
                    book_id=book.id,
                    order_index=order_index,
                    title=title,
                    text=chapter_text,
                )
            )
            order_index += 1

    return chapters


def _txt_chapter_title(line: str) -> str | None:
    title = line.strip()
    if not title or len(title) > TXT_TITLE_MAX_LENGTH:
        return None

    compact_title = re.sub(r"[ \t\u3000]+", "", title)
    if any(keyword in compact_title for keyword in TXT_NOISE_KEYWORDS):
        return None

    if _is_txt_volume_title(compact_title):
        return None

    if any(pattern.fullmatch(title) or pattern.fullmatch(compact_title) for pattern in TXT_CHAPTER_PATTERNS):
        return title
    return None


def _clean_txt_preface(lines: list[str]) -> str:
    content_lines = [line for line in lines if not _is_txt_noise_line(line)]
    return "\n".join(content_lines).strip()


def _is_txt_noise_line(line: str) -> bool:
    compact_line = re.sub(r"[ \t\u3000]+", "", line.strip())
    if not compact_line:
        return False
    if any(keyword in compact_line for keyword in TXT_NOISE_KEYWORDS):
        return True
    return bool(re.fullmatch(r"[-_=—]+(?:章节内容开始)?[-_=—]+", compact_line))


def _is_txt_volume_title(title: str) -> bool:
    return bool(
        re.fullmatch(
            rf"第[{TXT_CHINESE_NUMERAL}\d０-９]{{1,12}}[卷部篇](?:[，,:：、.-]?[^\r\n]{{0,50}})?",
            title,
        )
    )


def parse_epub(book: Book) -> list[Chapter]:
    epub_book = epub.read_epub(str(book.path))
    chapters: list[Chapter] = []
    for item in epub_book.get_items_of_type(ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "html.parser")
        text = soup.get_text("\n", strip=True)
        if not text:
            continue
        title_tag = soup.find(["h1", "h2", "title"])
        title = title_tag.get_text(" ", strip=True) if title_tag else item.get_name()
        chapters.append(
            Chapter(
                chapter_id=new_id("chapter"),
                book_id=book.id,
                order_index=len(chapters) + 1,
                title=title,
                text=text,
            )
        )

    if not chapters:
        raise ValueError(f"No readable chapters found in EPUB: {book.path}")
    return chapters


def _read_text(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="replace")
