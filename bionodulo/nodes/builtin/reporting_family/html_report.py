"""Deterministic embedded HTML report contract."""

from __future__ import annotations

import base64
import html
import mimetypes
from pathlib import Path
from typing import Any

from .adapter import (
    ReportingNode,
    node_output_path,
    normalise_file_list,
    read_table_rows,
    section_names,
    theme_tokens,
)


def _render_text_sections(value: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for index, section in enumerate(str(value or "").split("\n---\n")):
        stripped = section.strip()
        if not stripped:
            continue
        title = f"Text Section {index + 1}"
        lines = stripped.splitlines()
        if lines and lines[0].startswith("#"):
            title = lines[0].lstrip("#").strip() or title
            lines = lines[1:]
        body = "<br>\n".join(html.escape(line) for line in lines)
        sections.append((title, f'<div class="section-text">{body}</div>'))
    return sections


def _render_image(path: Path) -> str:
    mime_type = "image/svg+xml" if path.suffix.lower() == ".svg" else mimetypes.guess_type(path.name)[0]
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        '<figure class="report-figure">'
        f'<img src="data:{mime_type or "application/octet-stream"};base64,{encoded}" '
        f'alt="{html.escape(path.stem, quote=True)}">'
        f"<figcaption>{html.escape(path.name)}</figcaption>"
        "</figure>"
    )


def _render_table(path: Path, max_rows: int) -> str:
    header, body = read_table_rows(path, max_body_rows=max_rows)
    thead = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
    tbody = "".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in body
    )
    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody>"
        "</table></div>"
    )


class HTMLReportNode(ReportingNode):
    """Generate a self-contained report from bounded tables, images, and text."""

    NODE_ID = "html_report"
    DISPLAY_NAME = "HTML Report"
    DESCRIPTION = "Generate multi-section HTML reports from images, tables, and text."
    SEARCH_ALIASES = ["html report", "report", "interactive report", "multiqc-like", "summary report", "dashboard"]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("html_report",)
    OUTPUT_NODE = True
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/html.html"
    UPSTREAM_SOURCE = "Lib/html/__init__.py; Lib/base64.py; Lib/csv.py; Lib/mimetypes.py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"title": ("STRING", {"default": "BioNodulo Analysis Report"})},
            "optional": {
                "images": ("FILE", {"default": "", "description": "Comma-separated image files to embed"}),
                "tables": ("FILE", {"default": "", "description": "Comma-separated CSV/TSV tables to include"}),
                "text_sections": ("STRING", {"default": "", "multiline": True}),
                "section_names": ("STRING", {"default": ""}),
                "theme": ("STRING", {"default": "light", "options": ["light", "dark"]}),
                "include_toc": ("BOOLEAN", {"default": True}),
                "max_table_rows": ("INT", {"default": 100, "min": 1, "max": 1000}),
                "custom_css": ("STRING", {"default": "", "multiline": True}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        theme = str(inputs.get("theme", "light") or "light").strip().lower()
        if theme not in {"light", "dark"}:
            return f"Unsupported HTML report theme: {theme}"
        max_rows = inputs.get("max_table_rows", 100)
        if isinstance(max_rows, bool) or not isinstance(max_rows, int) or not 1 <= max_rows <= 1000:
            return "Input 'max_table_rows' must be an integer from 1 to 1000"
        if "<" in str(inputs.get("custom_css", "") or ""):
            return "Input 'custom_css' cannot contain '<'"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        title = str(kwargs.get("title", "BioNodulo Analysis Report") or "BioNodulo Analysis Report")
        theme = str(kwargs.get("theme", "light") or "light").strip().lower()
        tokens = theme_tokens(theme)
        images = normalise_file_list(kwargs.get("images", ""))
        tables = normalise_file_list(kwargs.get("tables", ""))
        names = section_names(kwargs.get("section_names", ""))
        max_rows = int(kwargs.get("max_table_rows", 100))

        sections = _render_text_sections(str(kwargs.get("text_sections", "") or ""))
        for index, image_path in enumerate(images):
            name = names[index] if index < len(names) else image_path.stem
            sections.append((name, _render_image(image_path)))
        table_offset = len(images)
        for index, table_path in enumerate(tables):
            name_index = table_offset + index
            name = names[name_index] if name_index < len(names) else table_path.stem
            sections.append((name, _render_table(table_path, max_rows)))

        section_html = "".join(
            f'<section id="section-{index}" class="report-section" '
            f'data-section="{html.escape(name, quote=True)}">'
            f"<h2>{html.escape(name)}</h2>{body}</section>"
            for index, (name, body) in enumerate(sections)
        )
        toc = ""
        if bool(kwargs.get("include_toc", True)) and sections:
            items = "".join(
                f'<li><a href="#section-{index}">{html.escape(name)}</a></li>'
                for index, (name, _) in enumerate(sections)
            )
            toc = f'<nav class="report-toc"><h2>Contents</h2><ul>{items}</ul></nav>'
        custom_css = str(kwargs.get("custom_css", "") or "")

        document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: {theme}; }}
body {{ margin: 0; background: {tokens["bg"]}; color: {tokens["text"]}; font-family: system-ui, sans-serif; }}
.report-container {{ max-width: 1180px; margin: 0 auto; padding: 28px; }}
header {{ border-bottom: 1px solid {tokens["border"]}; margin-bottom: 20px; padding-bottom: 14px; }}
h1 {{ margin: 0 0 8px; font-size: 30px; }}
h2 {{ margin: 0 0 14px; font-size: 19px; }}
.report-meta {{ color: {tokens["muted"]}; font-size: 13px; }}
.report-toc, .report-section {{ background: {tokens["section"]}; border: 1px solid {tokens["border"]}; border-radius: 8px; padding: 18px; margin: 18px 0; }}
.report-toc ul {{ margin: 0; padding-left: 20px; }}
.report-toc a {{ color: {tokens["accent"]}; text-decoration: none; }}
.section-text {{ line-height: 1.55; }}
.report-figure {{ margin: 0; }}
.report-figure img {{ display: block; max-width: 100%; height: auto; border: 1px solid {tokens["border"]}; border-radius: 6px; background: #fff; }}
.report-figure figcaption {{ color: {tokens["muted"]}; font-size: 12px; margin-top: 8px; }}
.table-wrap {{ overflow-x: auto; }}
table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
th, td {{ border: 1px solid {tokens["border"]}; padding: 7px 9px; text-align: left; }}
th {{ background: {tokens["border"]}; font-weight: 700; }}
tbody tr:nth-child(even) {{ background: {tokens["table_alt"]}; }}
{custom_css}
</style>
</head>
<body>
<main class="report-container">
<header><h1>{html.escape(title)}</h1><div class="report-meta">Generated by BioNodulo</div></header>
{toc}{section_html}
</main>
</body>
</html>
"""
        output_path = node_output_path(context, self.NODE_ID, "report.html")
        output_path.write_text(document, encoding="utf-8")
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="HTML Report")
        return {"outputs": {"html_report": str(output_path)}}
