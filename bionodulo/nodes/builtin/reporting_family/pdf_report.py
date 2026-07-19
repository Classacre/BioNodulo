"""Small multi-page PDF 1.4 reporting contract."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import ReportingNode, node_output_path, normalise_file_list, read_table_rows, section_names


PDF_REFERENCE_URL = "https://opensource.adobe.com/dc-acrobat-sdk-docs/pdfstandards/pdfreference1.4.pdf"


def _pdf_escape(value: Any) -> str:
    return (
        str(value)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _wrapped_lines(lines: list[str], *, max_chars: int) -> list[str]:
    wrapped: list[str] = []
    for line in lines:
        expanded = str(line).expandtabs(4)
        if not expanded:
            wrapped.append("")
            continue
        wrapped.extend(
            textwrap.wrap(
                expanded,
                width=max_chars,
                replace_whitespace=False,
                drop_whitespace=False,
                break_long_words=True,
                break_on_hyphens=False,
            )
            or [""]
        )
    return wrapped


def _page_stream(lines: list[str], *, page_height: int, margin: int = 56) -> bytes:
    parts = ["BT", "/F1 11 Tf", "14 TL", f"1 0 0 1 {margin} {page_height - margin} Tm"]
    for index, line in enumerate(lines):
        if index:
            parts.append("T*")
        parts.append(f"({_pdf_escape(line)}) Tj")
    parts.append("ET")
    return ("\n".join(parts) + "\n").encode("latin-1", errors="replace")


def write_pdf14(
    path: Path,
    *,
    lines: list[str],
    title: str,
    author: str,
    page_size: str,
    orientation: str,
) -> None:
    sizes = {"a4": (595, 842), "letter": (612, 792)}
    if page_size not in sizes:
        raise ValueError(f"Unsupported PDF page size: {page_size}")
    if orientation not in {"portrait", "landscape"}:
        raise ValueError(f"Unsupported PDF orientation: {orientation}")
    width, height = sizes[page_size]
    if orientation == "landscape":
        width, height = height, width

    margin = 56
    max_chars = max(20, int((width - 2 * margin) / 6.1))
    lines_per_page = max(1, int((height - 2 * margin) / 14))
    wrapped = _wrapped_lines(lines, max_chars=max_chars)
    pages = [wrapped[index : index + lines_per_page] for index in range(0, len(wrapped), lines_per_page)]
    if not pages:
        pages = [[]]

    page_ids = [4 + index * 2 for index in range(len(pages))]
    content_ids = [page_id + 1 for page_id in page_ids]
    info_id = 4 + len(pages) * 2
    objects: list[bytes | None] = [None] * (info_id + 1)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode("ascii")
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    for page_id, content_id, page_lines in zip(page_ids, content_ids, pages, strict=True):
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
            f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
        ).encode("ascii")
        stream = _page_stream(page_lines, page_height=height, margin=margin)
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii") + stream + b"endstream"
        )
    objects[info_id] = (
        f"<< /Title ({_pdf_escape(title)}) /Author ({_pdf_escape(author)}) /Producer (BioNodulo) >>"
    ).encode("latin-1", errors="replace")

    chunks = [b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"]
    offsets = [0] * (info_id + 1)
    for object_id in range(1, info_id + 1):
        offsets[object_id] = sum(map(len, chunks))
        payload = objects[object_id]
        assert payload is not None
        chunks.append(f"{object_id} 0 obj\n".encode("ascii") + payload + b"\nendobj\n")
    xref_offset = sum(map(len, chunks))
    chunks.append(f"xref\n0 {info_id + 1}\n".encode("ascii"))
    chunks.append(b"0000000000 65535 f \n")
    chunks.extend(f"{offsets[index]:010d} 00000 n \n".encode("ascii") for index in range(1, info_id + 1))
    chunks.append(
        (
            f"trailer\n<< /Size {info_id + 1} /Root 1 0 R /Info {info_id} 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    path.write_bytes(b"".join(chunks))


class PDFReportNode(ReportingNode):
    """Generate a wrapped, multi-page PDF 1.4 text and table report."""

    NODE_ID = "pdf_report"
    DISPLAY_NAME = "PDF Report"
    DESCRIPTION = "Generate printable multi-page PDF reports with text and table summaries."
    SEARCH_ALIASES = ["pdf report", "pdf", "printable report", "publication", "document", "static report"]
    RETURN_TYPES = ("PDF_REPORT",)
    RETURN_NAMES = ("pdf_report",)
    OUTPUT_NODE = True
    VERSION = "1.4"
    DOCUMENTATION_URL = PDF_REFERENCE_URL
    UPSTREAM_SOURCE = "PDF Reference, Third Edition, version 1.4; BioNodulo native reporting baseline"
    PDF_SPEC_VERSION = "1.4"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"title": ("STRING", {"default": "BioNodulo Report"})},
            "optional": {
                "images": ("FILE", {"default": "", "description": "Accepted for API compatibility; listed in report"}),
                "tables": ("FILE", {"default": "", "description": "Comma-separated CSV/TSV tables"}),
                "text": ("STRING", {"default": "", "multiline": True}),
                "section_names": ("STRING", {"default": ""}),
                "page_size": ("STRING", {"default": "A4", "options": ["A4", "Letter"]}),
                "orientation": ("STRING", {"default": "portrait", "options": ["portrait", "landscape"]}),
                "author": ("STRING", {"default": "BioNodulo"}),
                "header_text": ("STRING", {"default": ""}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        page_size = str(inputs.get("page_size", "A4") or "A4").strip().lower()
        if page_size not in {"a4", "letter"}:
            return f"Unsupported PDF page size: {inputs.get('page_size')}"
        orientation = str(inputs.get("orientation", "portrait") or "portrait").strip().lower()
        if orientation not in {"portrait", "landscape"}:
            return f"Unsupported PDF orientation: {orientation}"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        title = str(kwargs.get("title", "BioNodulo Report") or "BioNodulo Report")
        author = str(kwargs.get("author", "BioNodulo") or "BioNodulo")
        page_size = str(kwargs.get("page_size", "A4") or "A4").strip().lower()
        orientation = str(kwargs.get("orientation", "portrait") or "portrait").strip().lower()
        images = normalise_file_list(kwargs.get("images", ""))
        tables = normalise_file_list(kwargs.get("tables", ""))
        names = section_names(kwargs.get("section_names", ""))

        lines = [title, f"Generated by {author}"]
        header = str(kwargs.get("header_text", "") or "").strip()
        if header:
            lines.append(header)
        lines.append("")
        text = str(kwargs.get("text", "") or "").strip()
        if text:
            for section in text.split("\n---\n"):
                lines.extend(line.strip() for line in section.strip().splitlines() if line.strip())
                lines.append("")
        for index, image_path in enumerate(images):
            name = names[index] if index < len(names) else image_path.stem
            lines.extend([name, f"Image: {image_path.name}", ""])
        table_offset = len(images)
        for index, table_path in enumerate(tables):
            name_index = table_offset + index
            name = names[name_index] if name_index < len(names) else table_path.stem
            header_row, body_rows = read_table_rows(table_path, max_body_rows=50)
            lines.append(name)
            lines.extend(" | ".join(row) for row in ([header_row] if header_row else []) + body_rows)
            lines.append("")

        output_path = node_output_path(context, self.NODE_ID, "report.pdf")
        write_pdf14(
            output_path,
            lines=lines,
            title=title,
            author=author,
            page_size=page_size,
            orientation=orientation,
        )
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="PDF Report")
        return {"outputs": {"pdf_report": str(output_path)}}
