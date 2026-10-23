from pathlib import Path

import docx
import pypdf
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

type PathLike = str | Path


def get_pdf_pages(path: Path) -> list[tuple[int, str]]:
    reader = pypdf.PdfReader(path)
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append((index, text))
    return pages


def get_pdf(path: Path, *, pages: list[int] | None = None) -> str:
    all_pages = get_pdf_pages(path)
    if pages:
        wanted = set(pages)
        selected = [(num, text) for num, text in all_pages if num in wanted]
        if not selected:
            raise ValueError(
                f"no PDF pages match filter {pages} "
                f"(document has {len(all_pages)} page(s))"
            )
    else:
        selected = all_pages

    blocks = [
        f"[Page {num}]\n{text}" if text else f"[Page {num}]"
        for num, text in selected
    ]
    return "\n\n".join(blocks)


def _table_row_blocks(table: Table) -> list[str]:
    blocks: list[str] = []
    for row in table.rows:
        cells = [" ".join(cell.text.split()) for cell in row.cells]
        deduped: list[str] = []
        for cell in cells:
            if cell and (not deduped or cell != deduped[-1]):
                deduped.append(cell)
        if deduped:
            blocks.append(" | ".join(deduped))
    return blocks


def get_docx(path: Path) -> str:
    document = docx.Document(path)
    blocks: list[str] = []

    for child in document.element.body.iterchildren():
        if child.tag == qn("w:p"):
            text = Paragraph(child, document).text.strip()
            if text:
                blocks.append(text)
        elif child.tag == qn("w:tbl"):
            blocks.extend(_table_row_blocks(Table(child, document)))

    return "\n\n".join(blocks)


def extract_text(file_path: PathLike, *, pages: list[int] | None = None) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")

    ext = path.suffix.lower().lstrip(".")
    match ext:
        case "pdf":
            return get_pdf(path, pages=pages or None)
        case "docx":
            return get_docx(path)
        case _:
            raise ValueError(f"unsupported format: {ext!r}")


MIN_CHUNK = 40
MAX_CHUNK = 500
OVERLAP = 80


def _split_long_paragraph(paragraph: str) -> list[str]:
    pieces: list[str] = []
    start = 0
    length = len(paragraph)

    while start < length:
        end = min(start + MAX_CHUNK, length)
        if end < length:
            window = paragraph[start:end]
            cut = max(
                window.rfind(". "),
                window.rfind(".\n"),
                window.rfind("? "),
                window.rfind("! "),
            )
            if cut >= MIN_CHUNK // 2:
                end = start + cut + 1
        piece = paragraph[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= length:
            break
        start = max(end - OVERLAP, start + 1)

    return pieces


def get_chunks(text: str) -> list[str]:
    paragraphs = [p.strip() for p in text.split("\n\n")]
    chunks: list[str] = []

    for paragraph in paragraphs:
        if len(paragraph) < MIN_CHUNK:
            continue
        if len(paragraph) <= MAX_CHUNK:
            chunks.append(paragraph)
        else:
            chunks.extend(_split_long_paragraph(paragraph))

    return chunks
