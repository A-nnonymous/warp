from __future__ import annotations

from .utils import slugify


def parse_markdown_sections(text: str) -> tuple[dict[str, str], dict[str, str]]:
    metadata: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current_section = ""
    before_sections = True
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("## "):
            current_section = line[3:].strip().lower()
            sections.setdefault(current_section, [])
            before_sections = False
            continue
        if before_sections and line and not line.startswith("#") and ":" in line:
            key, value = line.split(":", 1)
            metadata[slugify(key)] = value.strip()
            continue
        if current_section:
            sections.setdefault(current_section, []).append(line)
    return metadata, {key: "\n".join(value).strip() for key, value in sections.items()}


def parse_markdown_list(section_text: str) -> list[str]:
    items: list[str] = []
    for raw_line in section_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        candidate = line[2:].strip() if line.startswith("- ") else line
        if candidate and candidate.lower() != "none":
            items.append(candidate)
    return items


def parse_markdown_paragraph(section_text: str) -> str:
    lines = [line.strip() for line in section_text.splitlines() if line.strip()]
    return " ".join(lines)
