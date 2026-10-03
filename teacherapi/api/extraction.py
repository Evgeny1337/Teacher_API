from pathlib import Path

import docx
import pypdf

PathLike = str | Path


def get_pdf(path: Path) -> str:
    reader = pypdf.PdfReader(path)
    pages = (page.extract_text() or "" for page in reader.pages)
    return "\n".join(pages)


def get_docx(path: Path) -> str:
    document = docx.Document(path)
    return "\n".join(para.text for para in document.paragraphs)


ACTIONS = {
    "pdf": get_pdf,
    "docx": get_docx,
}


def extract_text(file_path: PathLike) -> str:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")

    ext = path.suffix.lower().lstrip(".")
    action = ACTIONS.get(ext)
    if action is None:
        raise ValueError(f"unsupported format: {ext!r}")

    return action(path)
