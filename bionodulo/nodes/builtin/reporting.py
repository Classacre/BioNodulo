"""Reporting nodes for BioNodulo workflows."""
from __future__ import annotations

import base64
import csv
import html
import json
import mimetypes
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _normalise_file_list(value: Any) -> list[Path]:
    if value is None or value == "":
        return []
    if isinstance(value, (list, tuple, set)):
        items = value
    else:
        items = [part.strip() for part in str(value).split(",") if part.strip()]
    paths: list[Path] = []
    for item in items:
        path = Path(str(item))
        if not path.exists():
            raise FileNotFoundError(f"Report input file not found: {path}")
        paths.append(path)
    return paths


def _section_names(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _render_text_sections(text_sections: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    for index, section in enumerate(str(text_sections or "").split("\n---\n")):
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


def _render_image_section(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0]
    if path.suffix.lower() == ".svg":
        mime_type = "image/svg+xml"
    if mime_type is None:
        mime_type = "application/octet-stream"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return (
        '<figure class="report-figure">'
        f'<img src="data:{mime_type};base64,{encoded}" alt="{html.escape(path.stem, quote=True)}">'
        f"<figcaption>{html.escape(path.name)}</figcaption>"
        "</figure>"
    )


def _render_table_section(path: Path, max_rows: int) -> str:
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
    except csv.Error:
        delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","

    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    if not rows:
        return '<div class="table-wrap"><table></table></div>'
    header = rows[0]
    body_rows = rows[1 : max(max_rows, 0) + 1]
    thead = "".join(f"<th>{html.escape(cell)}</th>" for cell in header)
    body = "\n".join(
        "<tr>" + "".join(f"<td>{html.escape(cell)}</td>" for cell in row) + "</tr>"
        for row in body_rows
    )
    return (
        '<div class="table-wrap"><table>'
        f"<thead><tr>{thead}</tr></thead>"
        f"<tbody>{body}</tbody>"
        "</table></div>"
    )


def _read_table_lines(path: Path, max_rows: int = 50) -> list[str]:
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
    except csv.Error:
        delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","
    rows = list(csv.reader(text.splitlines(), delimiter=delimiter))
    return [" | ".join(row) for row in rows[: max(max_rows, 0) + 1]]


def _optional_qc_file(value: Any) -> Path | None:
    if value is None or value == "":
        return None
    path = Path(str(value))
    if not path.exists():
        raise FileNotFoundError(f"QC dashboard input file not found: {path}")
    return path


def _parse_flagstat_metrics(path: Path) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if " in total" in stripped:
            metrics["Total Reads"] = stripped.split()[0]
        elif " mapped (" in stripped:
            metrics["Mapped %"] = stripped.split("(", 1)[1].split("%", 1)[0] + "%"
        elif " properly paired" in stripped and "(" in stripped:
            metrics["Properly Paired"] = stripped.split("(", 1)[1].split("%", 1)[0] + "%"
    return metrics


def _parse_variant_metrics(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        return {}
    metrics: dict[str, str] = {}
    if "total_variants" in data:
        metrics["Total Variants"] = str(data["total_variants"])
    if "titv_ratio" in data:
        metrics["Ti/Tv Ratio"] = str(data["titv_ratio"])
    return metrics


def _parse_custom_metrics(value: str) -> dict[str, str]:
    if not value.strip():
        return {}
    data = json.loads(value)
    if not isinstance(data, dict):
        raise ValueError("Custom QC metrics must be a JSON object")
    return {str(key): str(val) for key, val in data.items()}


def _add_read_retention_metrics(metrics: dict[str, str]) -> None:
    raw = _first_numeric_metric(metrics, "raw_reads", "total_reads", "input_reads", "reads_before")
    retained = _first_numeric_metric(metrics, "trimmed_reads", "filtered_reads", "retained_reads", "reads_after")
    if raw is None or retained is None or raw <= 0:
        return
    retained = max(0.0, min(retained, raw))
    retention = retained / raw * 100
    loss = 100 - retention
    metrics.setdefault("Read Retention", f"{retention:.2f}%")
    metrics.setdefault("Read Loss", f"{loss:.2f}%")


def _first_numeric_metric(metrics: dict[str, str], *keys: str) -> float | None:
    normalized = {_metric_key(key): value for key, value in metrics.items()}
    for key in keys:
        value = normalized.get(_metric_key(key))
        if value is None:
            continue
        try:
            return float(str(value).replace(",", ""))
        except ValueError:
            continue
    return None


def _metric_key(key: str) -> str:
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def _read_coverage_rows(path: Path, max_rows: int = 100) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    sample = text[:4096]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
    except csv.Error:
        delimiter = "\t" if sample.count("\t") >= sample.count(",") else ","
    reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
    rows: list[dict[str, str]] = []
    for row in reader:
        if "depth" not in row or "count" not in row:
            continue
        rows.append({"depth": str(row["depth"]), "count": str(row["count"])})
        if len(rows) >= max_rows:
            break
    return rows


def _pdf_escape(text: str) -> str:
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _pdf_stream_lines(lines: list[str], *, page_width: int, page_height: int) -> str:
    margin = 56
    y = page_height - margin
    parts = ["BT", "/F1 11 Tf", "14 TL"]
    for line in lines:
        if y < margin:
            break
        parts.append(f"1 0 0 1 {margin} {y} Tm")
        parts.append(f"({_pdf_escape(line[:120])}) Tj")
        y -= 16
    parts.append("ET")
    return "\n".join(parts) + "\n"


def _write_simple_pdf(
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

    stream = _pdf_stream_lines(lines, page_width=width, page_height=height)
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width} {height}] "
        "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        f"<< /Length {len(stream.encode('latin-1', errors='replace'))} >>\nstream\n{stream}endstream",
        f"<< /Title ({_pdf_escape(title)}) /Author ({_pdf_escape(author)}) /Producer (BioNodulo) >>",
    ]

    chunks = ["%PDF-1.4\n%\xE2\xE3\xCF\xD3\n"]
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(sum(len(chunk.encode("latin-1", errors="replace")) for chunk in chunks))
        chunks.append(f"{index} 0 obj\n{obj}\nendobj\n")
    xref_offset = sum(len(chunk.encode("latin-1", errors="replace")) for chunk in chunks)
    chunks.append(f"xref\n0 {len(objects) + 1}\n")
    chunks.append("0000000000 65535 f \n")
    for offset in offsets[1:]:
        chunks.append(f"{offset:010d} 00000 n \n")
    chunks.append(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info 6 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    path.write_bytes("".join(chunks).encode("latin-1", errors="replace"))


def _theme_tokens(theme: str) -> dict[str, str]:
    if theme == "light":
        return {
            "bg": "#FFFFFF",
            "text": "#111827",
            "muted": "#475569",
            "section": "#F8FAFC",
            "border": "#CBD5E1",
            "accent": "#2563EB",
            "table_alt": "#F1F5F9",
        }
    if theme == "dark":
        return {
            "bg": "#0F172A",
            "text": "#E5E7EB",
            "muted": "#94A3B8",
            "section": "#1E293B",
            "border": "#334155",
            "accent": "#60A5FA",
            "table_alt": "#111827",
        }
    raise ValueError(f"Unsupported HTML report theme: {theme}")


class HTMLReportNode(BaseNode):
    """Generate a multi-section HTML report from images, tables, and text."""

    NODE_ID = "html_report"
    DISPLAY_NAME = "HTML Report"
    CATEGORY = "reporting"
    DESCRIPTION = "Generate multi-section HTML reports from images, tables, and text."
    SEARCH_ALIASES = ["html report", "report", "interactive report", "multiqc-like", "summary report", "dashboard"]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("html_report",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "title": ("STRING", {"default": "BioNodulo Analysis Report"}),
            },
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

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        title = str(kwargs.get("title", "BioNodulo Analysis Report") or "BioNodulo Analysis Report")
        theme = str(kwargs.get("theme", "light") or "light").strip().lower()
        tokens = _theme_tokens(theme)
        images = _normalise_file_list(kwargs.get("images", ""))
        tables = _normalise_file_list(kwargs.get("tables", ""))
        names = _section_names(kwargs.get("section_names", ""))
        max_rows = int(kwargs.get("max_table_rows", 100) or 100)
        include_toc = bool(kwargs.get("include_toc", True))

        sections: list[tuple[str, str]] = []
        sections.extend(_render_text_sections(str(kwargs.get("text_sections", "") or "")))

        for index, image in enumerate(images):
            name = names[index] if index < len(names) else image.stem
            sections.append((name, _render_image_section(image)))

        table_name_offset = len(images)
        for index, table in enumerate(tables):
            name_index = table_name_offset + index
            name = names[name_index] if name_index < len(names) else table.stem
            sections.append((name, _render_table_section(table, max_rows)))

        section_html = []
        for index, (name, body) in enumerate(sections):
            section_html.append(
                f'<section id="section-{index}" class="report-section" '
                f'data-section="{html.escape(name, quote=True)}">'
                f"<h2>{html.escape(name)}</h2>{body}</section>"
            )

        toc = ""
        if include_toc and sections:
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
body {{ margin: 0; background: {tokens["bg"]}; color: {tokens["text"]}; font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
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
<header>
<h1>{html.escape(title)}</h1>
<div class="report-meta">Generated by BioNodulo</div>
</header>
{toc}
{''.join(section_html)}
</main>
</body>
</html>
"""

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / "report.html"
        output_path.write_text(document, encoding="utf-8")

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="HTML Report")

        return {"outputs": {"html_report": str(output_path)}}


class PDFReportNode(BaseNode):
    """Generate a simple PDF report from text and tables."""

    NODE_ID = "pdf_report"
    DISPLAY_NAME = "PDF Report"
    CATEGORY = "reporting"
    DESCRIPTION = "Generate printable PDF reports with text and table summaries."
    SEARCH_ALIASES = ["pdf report", "pdf", "printable report", "publication", "document", "static report"]
    RETURN_TYPES = ("PDF_REPORT",)
    RETURN_NAMES = ("pdf_report",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "title": ("STRING", {"default": "BioNodulo Report"}),
            },
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

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        title = str(kwargs.get("title", "BioNodulo Report") or "BioNodulo Report")
        author = str(kwargs.get("author", "BioNodulo") or "BioNodulo")
        page_size = str(kwargs.get("page_size", "A4") or "A4").strip().lower()
        orientation = str(kwargs.get("orientation", "portrait") or "portrait").strip().lower()
        tables = _normalise_file_list(kwargs.get("tables", ""))
        images = _normalise_file_list(kwargs.get("images", ""))
        names = _section_names(kwargs.get("section_names", ""))

        lines = [title, f"Generated by {author}"]
        header = str(kwargs.get("header_text", "") or "").strip()
        if header:
            lines.append(header)
        lines.append("")

        text = str(kwargs.get("text", "") or "").strip()
        if text:
            for section in text.split("\n---\n"):
                for line in section.strip().splitlines():
                    if line.strip():
                        lines.append(line.strip())
                lines.append("")

        for index, image in enumerate(images):
            name = names[index] if index < len(names) else image.stem
            lines.extend([name, f"Image: {image.name}", ""])

        table_offset = len(images)
        for index, table in enumerate(tables):
            name_index = table_offset + index
            name = names[name_index] if name_index < len(names) else table.stem
            lines.append(name)
            lines.extend(_read_table_lines(table, max_rows=50))
            lines.append("")

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / "report.pdf"
        _write_simple_pdf(
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


class QCDashboardNode(BaseNode):
    """Generate an HTML QC dashboard from common bioinformatics metrics."""

    NODE_ID = "qc_dashboard"
    DISPLAY_NAME = "QC Dashboard"
    CATEGORY = "reporting"
    DESCRIPTION = "Generate comprehensive QC dashboards from alignment, variant, coverage, and custom statistics."
    SEARCH_ALIASES = [
        "qc dashboard",
        "quality control",
        "fastqc report",
        "alignment stats",
        "multiqc",
        "qc summary",
        "run metrics",
    ]
    RETURN_TYPES = ("HTML_REPORT",)
    RETURN_NAMES = ("qc_dashboard",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "run_name": ("STRING", {"default": "Run"}),
            },
            "optional": {
                "fastqc_dir": ("QC_REPORT_DIR", {"default": "", "advanced": True}),
                "alignment_stats": ("FILE", {"default": "", "advanced": True}),
                "insert_size": ("FILE", {"default": "", "advanced": True}),
                "variant_stats": ("FILE", {"default": "", "advanced": True}),
                "coverage_stats": ("FILE", {"default": "", "advanced": True}),
                "custom_metrics": ("STRING", {"default": "", "multiline": True, "advanced": True}),
                "title": ("STRING", {"default": "QC Dashboard"}),
                "theme": ("STRING", {"default": "light", "options": ["light", "dark"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        run_name = str(kwargs.get("run_name", "Run") or "Run")
        title = str(kwargs.get("title", "QC Dashboard") or "QC Dashboard")
        theme = str(kwargs.get("theme", "light") or "light").strip().lower()
        if theme not in {"light", "dark"}:
            raise ValueError(f"Unsupported QC dashboard theme: {theme}")

        alignment_stats = _optional_qc_file(kwargs.get("alignment_stats", ""))
        insert_size = _optional_qc_file(kwargs.get("insert_size", ""))
        variant_stats = _optional_qc_file(kwargs.get("variant_stats", ""))
        coverage_stats = _optional_qc_file(kwargs.get("coverage_stats", ""))
        fastqc_dir = _optional_qc_file(kwargs.get("fastqc_dir", ""))
        if fastqc_dir is not None and not fastqc_dir.is_dir():
            raise ValueError(f"FastQC input is not a directory: {fastqc_dir}")

        metrics: dict[str, str] = {}
        if alignment_stats is not None:
            metrics.update(_parse_flagstat_metrics(alignment_stats))
        if variant_stats is not None:
            metrics.update(_parse_variant_metrics(variant_stats))
        metrics.update(_parse_custom_metrics(str(kwargs.get("custom_metrics", "") or "")))
        _add_read_retention_metrics(metrics)

        coverage_rows = _read_coverage_rows(coverage_stats) if coverage_stats is not None else []
        max_count = max((int(float(row["count"])) for row in coverage_rows), default=0)
        tokens = _theme_tokens(theme)
        card_bg = tokens["section"]
        border = tokens["border"]
        muted = tokens["muted"]
        accent = tokens["accent"]

        metric_cards = "\n".join(
            '<article class="metric-card">'
            f'<div class="metric-label">{html.escape(key)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div>'
            "</article>"
            for key, value in metrics.items()
        )
        if not metric_cards:
            metric_cards = '<p class="empty-state">No summary metrics were available for this run.</p>'

        coverage_bars = ""
        if coverage_rows:
            bars = []
            for row in coverage_rows:
                count = int(float(row["count"]))
                width = (count / max_count * 100) if max_count else 0
                depth = row["depth"]
                bars.append(
                    '<div class="coverage-row" '
                    f'data-depth="{html.escape(depth, quote=True)}" '
                    f'data-count="{html.escape(row["count"], quote=True)}">'
                    f'<span class="coverage-depth">{html.escape(depth)}</span>'
                    '<span class="coverage-track">'
                    f'<span class="coverage-bar" style="width:{width:.2f}%"></span>'
                    "</span>"
                    f'<span class="coverage-count">{html.escape(row["count"])}</span>'
                    "</div>"
                )
            coverage_bars = (
                '<section class="dashboard-panel">'
                "<h2>Coverage Depth Distribution</h2>"
                '<div class="coverage-chart">'
                + "\n".join(bars)
                + "</div></section>"
            )

        source_items = []
        for label, path in [
            ("FastQC directory", fastqc_dir),
            ("Alignment stats", alignment_stats),
            ("Insert size", insert_size),
            ("Variant stats", variant_stats),
            ("Coverage stats", coverage_stats),
        ]:
            if path is not None:
                source_items.append(f"<li>{html.escape(label)}: {html.escape(path.name)}</li>")
        sources_html = ""
        if source_items:
            sources_html = (
                '<section class="dashboard-panel">'
                "<h2>Input Sources</h2>"
                f"<ul>{''.join(source_items)}</ul>"
                "</section>"
            )

        document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: {theme}; }}
body {{ margin: 0; background: {tokens["bg"]}; color: {tokens["text"]}; font-family: system-ui, -apple-system, Segoe UI, sans-serif; }}
.dashboard-container {{ max-width: 1240px; margin: 0 auto; padding: 28px; }}
header {{ text-align: center; border-bottom: 1px solid {border}; padding-bottom: 18px; margin-bottom: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 30px; }}
h2 {{ margin: 0 0 14px; font-size: 18px; }}
.subtitle {{ color: {muted}; font-size: 14px; }}
.metrics-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 22px; }}
.metric-card, .dashboard-panel {{ background: {card_bg}; border: 1px solid {border}; border-radius: 8px; padding: 18px; }}
.metric-label {{ color: {muted}; font-size: 12px; text-transform: uppercase; }}
.metric-value {{ color: {accent}; font-size: 24px; font-weight: 700; margin-top: 6px; }}
.empty-state {{ color: {muted}; margin: 0; }}
.dashboard-panel {{ margin: 18px 0; }}
.coverage-chart {{ display: grid; gap: 8px; }}
.coverage-row {{ display: grid; grid-template-columns: 70px 1fr 70px; gap: 10px; align-items: center; font-size: 13px; }}
.coverage-track {{ height: 14px; background: {tokens["bg"]}; border: 1px solid {border}; border-radius: 999px; overflow: hidden; }}
.coverage-bar {{ display: block; height: 100%; background: {accent}; }}
.coverage-depth, .coverage-count {{ color: {muted}; }}
ul {{ margin: 0; padding-left: 20px; }}
</style>
</head>
<body>
<main class="dashboard-container">
<header>
<h1>{html.escape(title)}</h1>
<div class="subtitle">{html.escape(run_name)} | Generated by BioNodulo</div>
</header>
<section class="metrics-row">{metric_cards}</section>
{coverage_bars}
{sources_html}
</main>
</body>
</html>
"""

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / "qc_dashboard.html"
        output_path.write_text(document, encoding="utf-8")

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="QC Dashboard")

        return {"outputs": {"qc_dashboard": str(output_path)}}
