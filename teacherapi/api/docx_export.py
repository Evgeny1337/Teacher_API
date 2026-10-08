import re
from io import BytesIO
from pathlib import Path
from typing import Any

from django.conf import settings
from docxtpl import DocxTemplate, RichText

TEMPLATE_PATH = Path(settings.BASE_DIR) / "templates" / "lesson.docx"

STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "title": {"bold": True, "size": 32, "color": "1F4E79", "font": "Calibri"},
    "meta": {"size": 20, "color": "444444", "font": "Calibri"},
    "label": {"bold": True, "size": 22, "color": "1F4E79", "font": "Calibri"},
    "body": {"size": 22, "font": "Calibri"},
    "stage": {"bold": True, "size": 20, "font": "Calibri"},
    "procedure": {"size": 20, "font": "Calibri"},
    "time": {"size": 18, "color": "666666", "font": "Calibri"},
}


def _plain(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    text = re.sub(r"__(.+?)__", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"\1", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.MULTILINE)
    return text.strip()


def _merge_style(preset: str | None, style: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(STYLE_PRESETS.get(preset or "", {}))
    if style:
        for key in ("bold", "italic", "underline", "color", "highlight", "size", "font"):
            if key in style and style[key] is not None:
                merged[key] = style[key]
    return merged


def _rich(text: str, *, preset: str | None = None, style: dict[str, Any] | None = None) -> RichText:
    props = _merge_style(preset, style)
    rt = RichText()
    parts = _plain(text).split("\n") if text else [""]
    for index, part in enumerate(parts):
        if index:
            rt.add("\n")
        rt.add(part, **props)
    return rt


def _rich_labeled(label: str, value: str, *, style: dict[str, Any] | None = None) -> RichText:
    rt = RichText()
    label_props = _merge_style("label", (style or {}).get("label"))
    body_props = _merge_style("body", (style or {}).get("body"))
    rt.add(f"{label}: ", **label_props)
    parts = _plain(value).split("\n") if value else [""]
    for index, part in enumerate(parts):
        if index:
            rt.add("\n")
        rt.add(part, **body_props)
    return rt


def _append_stage_rows(
    rows: list[dict[str, Any]],
    stage_rows: list[dict[str, Any]],
    row_styles: dict[str, Any] | None = None,
) -> None:
    row_styles = row_styles or {}
    for row in stage_rows:
        role = row.get("role") or ""
        role_style = row_styles.get(role) if isinstance(row_styles.get(role), dict) else {}
        time = str(row.get("time") or "").strip()
        interaction = str(row.get("interaction") or "").strip()
        time_ip = " ".join(part for part in [time, interaction] if part)
        rows.append({
            "stage": _rich(
                str(row.get("stage") or ""),
                preset="stage",
                style=role_style.get("stage") if isinstance(role_style.get("stage"), dict) else role_style,
            ),
            "procedure": _rich(
                str(row.get("procedure") or ""),
                preset="procedure",
                style=role_style.get("procedure") if isinstance(role_style.get("procedure"), dict) else None,
            ),
            "time_ip": _rich(
                time_ip,
                preset="time",
                style=role_style.get("time") if isinstance(role_style.get("time"), dict) else None,
            ),
        })


def _prepare_from_blocks(draft: dict[str, Any]) -> dict[str, Any]:
    title_style = draft.get("style") if isinstance(draft.get("style"), dict) else None
    title = _rich(str(draft.get("title") or "Lesson"), preset="title", style=title_style)

    items: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    blocks = draft.get("blocks") or draft.get("items") or []
    for block in blocks:
        name = block.get("name") or block.get("type") or ""
        content = block.get("content") or {}
        style = block.get("style") if isinstance(block.get("style"), dict) else {}

        if name == "meta_header":
            date = content.get("date") or ""
            level = content.get("level") or ""
            teacher = content.get("teacher") or ""
            line = f"Date: {date}    Level: {level}    Teacher: {teacher}"
            items.append({
                "name": "meta_header",
                "line": _rich(line, preset="meta", style=style),
            })
        elif name == "aims":
            items.append({
                "name": "aims",
                "aim_line": _rich_labeled("Aim", str(content.get("aim") or ""), style=style),
                "sub_aim_line": _rich_labeled(
                    "Sub aim",
                    str(content.get("sub_aim") or ""),
                    style=style,
                ),
            })
        elif name == "homework":
            hw = str(content.get("text") or "")
            if hw.strip():
                items.append({
                    "name": "homework",
                    "line": _rich_labeled("H/W", hw, style=style),
                })
        elif name == "paragraph":
            items.append({
                "name": "paragraph",
                "line": _rich(str(content.get("text") or ""), preset="body", style=style),
            })
        elif name in {"stage_table", "stages_table"}:
            row_styles = style.get("row_styles") if isinstance(style.get("row_styles"), dict) else {}
            _append_stage_rows(rows, content.get("rows") or [], row_styles)

    return {"title": title, "items": items, "rows": rows}


def _prepare_from_stages(draft: dict[str, Any]) -> dict[str, Any]:
    blocks: list[dict[str, Any]] = []
    if draft.get("date") or draft.get("level") or draft.get("teacher"):
        blocks.append({
            "type": "meta_header",
            "content": {
                "date": draft.get("date") or "",
                "level": draft.get("level") or "",
                "teacher": draft.get("teacher") or "",
            },
        })
    blocks.append({
        "type": "aims",
        "content": {
            "aim": draft.get("aim") or "",
            "sub_aim": draft.get("sub_aim") or "",
        },
    })
    if draft.get("homework"):
        blocks.append({
            "type": "homework",
            "content": {"text": draft.get("homework") or ""},
        })
    blocks.append({
        "type": "stages_table",
        "content": {"rows": draft.get("stages") or []},
    })
    return _prepare_from_blocks({"title": draft.get("title"), "blocks": blocks})


def _extract_labeled(text: str, label: str) -> str:
    match = re.search(
        rf"(?im)^\**{re.escape(label)}\**:?\**\s*(.+?)(?=\n\**[A-Za-z][A-Za-z /]*\**:|\Z)",
        text,
        flags=re.S,
    )
    return _plain(match.group(1)) if match else ""


def _prepare_from_legacy_sections(draft: dict[str, Any]) -> dict[str, Any]:
    title = _rich(str(draft.get("title") or "Lesson"), preset="title")
    items: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []

    for section in draft.get("lesson_section") or []:
        heading = (section.get("title") or section.get("section_type") or "Section").strip()
        body = _plain(str(section.get("content") or ""))
        heading_lower = heading.lower()

        if "overview" in heading_lower or heading_lower in {"aims", "aim"}:
            aim = _extract_labeled(body, "Main Aim") or _extract_labeled(body, "Aim")
            sub_aim = _extract_labeled(body, "Sub Aim") or _extract_labeled(body, "Sub-aim")
            if aim or sub_aim:
                items.append({
                    "name": "aims",
                    "aim_line": _rich_labeled("Aim", aim or "-"),
                    "sub_aim_line": _rich_labeled("Sub aim", sub_aim or "-"),
                })
            level = _extract_labeled(body, "Level")
            duration = _extract_labeled(body, "Duration")
            if level or duration:
                meta = "    ".join(
                    part for part in [
                        f"Level: {level}" if level else "",
                        f"Duration: {duration}" if duration else "",
                    ]
                    if part
                )
                items.append({"name": "meta_header", "line": _rich(meta, preset="meta")})
            continue

        time_match = re.search(r"(?i)\b(?:time|duration)\s*:?\s*(\d+\s*(?:minutes?|mins?|min)?)", body)
        interaction_match = re.search(r"(?i)\b(?:interaction|ip)\s*:?\s*([^\n]+)", body)
        time_ip = " ".join(
            part for part in [
                time_match.group(1).strip() if time_match else "",
                interaction_match.group(1).strip() if interaction_match else "",
            ]
            if part
        )
        rows.append({
            "stage": _rich(heading or section.get("section_type") or "Stage", preset="stage"),
            "procedure": _rich(body, preset="procedure"),
            "time_ip": _rich(time_ip or "—", preset="time"),
        })

    return {"title": title, "items": items, "rows": rows}


def _prepare_draft(draft: dict[str, Any]) -> dict[str, Any]:
    if draft.get("blocks") or draft.get("items"):
        return _prepare_from_blocks(draft)
    if "stages" in draft:
        return _prepare_from_stages(draft)
    return _prepare_from_legacy_sections(draft)


def render_lesson_docx(draft: dict[str, Any]) -> BytesIO:
    doc = DocxTemplate(TEMPLATE_PATH)
    doc.render(_prepare_draft(draft))
    buffer = BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer
