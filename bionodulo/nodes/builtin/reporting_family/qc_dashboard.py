"""Deterministic QC dashboard parsing and rendering contract."""

from __future__ import annotations

import html
import json
import math
from pathlib import Path
from typing import Any

from .adapter import ReportingNode, node_output_path, path_value, read_table_rows, theme_tokens


def _optional_path(value: Any, *, label: str, directory: bool = False) -> Path | None:
    raw_path = path_value(value)
    if not raw_path:
        return None
    path = Path(raw_path)
    if not path.exists():
        raise FileNotFoundError(f"QC dashboard input file not found: {path}")
    if directory and not path.is_dir():
        raise ValueError(f"{label} is not a directory: {path}")
    if not directory and not path.is_file():
        raise ValueError(f"{label} is not a regular file: {path}")
    return path


def _parse_flagstat_metrics(path: Path) -> dict[str, str]:
    metrics: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        stripped = line.strip()
        if " in total" in stripped:
            metrics["Total Reads"] = stripped.split()[0]
        elif " mapped (" in stripped:
            metrics["Mapped %"] = stripped.split("(", 1)[1].split("%", 1)[0] + "%"
        elif " properly paired" in stripped and "(" in stripped:
            metrics["Properly Paired"] = stripped.split("(", 1)[1].split("%", 1)[0] + "%"
    if not metrics:
        raise ValueError(f"Alignment stats do not contain recognizable flagstat metrics: {path}")
    return metrics


def _parse_variant_metrics(path: Path) -> dict[str, str]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError(f"Variant metrics must be a JSON object: {path}")
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
    return {str(key): str(item) for key, item in data.items()}


def _metric_key(key: str) -> str:
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def _first_numeric_metric(metrics: dict[str, str], *keys: str) -> float | None:
    normalized = {_metric_key(key): value for key, value in metrics.items()}
    for key in keys:
        value = normalized.get(_metric_key(key))
        if value is None:
            continue
        try:
            number = float(str(value).replace(",", ""))
        except ValueError:
            continue
        if math.isfinite(number):
            return number
    return None


def _add_read_retention(metrics: dict[str, str]) -> None:
    raw = _first_numeric_metric(metrics, "raw_reads", "total_reads", "input_reads", "reads_before")
    retained = _first_numeric_metric(metrics, "trimmed_reads", "filtered_reads", "retained_reads", "reads_after")
    if raw is None or retained is None or raw <= 0:
        return
    retained = max(0.0, min(retained, raw))
    retention = retained / raw * 100
    metrics.setdefault("Read Retention", f"{retention:.2f}%")
    metrics.setdefault("Read Loss", f"{100 - retention:.2f}%")


def _coverage_rows(path: Path, *, max_rows: int = 100) -> list[tuple[str, str, float]]:
    header, body = read_table_rows(path, max_body_rows=max_rows)
    normalized = [cell.strip().lower() for cell in header]
    if "depth" not in normalized or "count" not in normalized:
        raise ValueError(f"Coverage stats must contain depth and count columns: {path}")
    depth_index = normalized.index("depth")
    count_index = normalized.index("count")
    rows: list[tuple[str, str, float]] = []
    for row_number, row in enumerate(body, start=2):
        if max(depth_index, count_index) >= len(row):
            raise ValueError(f"Coverage row {row_number} is missing depth or count: {path}")
        depth = row[depth_index].strip()
        count_text = row[count_index].strip()
        if not depth or not count_text:
            raise ValueError(f"Coverage row {row_number} has an empty depth or count: {path}")
        try:
            count = float(count_text)
        except ValueError as exc:
            raise ValueError(f"Coverage row {row_number} has a non-numeric count: {count_text}") from exc
        if not math.isfinite(count) or count < 0:
            raise ValueError(f"Coverage row {row_number} count must be finite and nonnegative: {count_text}")
        rows.append((depth, count_text, count))
    return rows


class QCDashboardNode(ReportingNode):
    """Render common QC metrics with strict JSON and coverage parsing."""

    NODE_ID = "qc_dashboard"
    DISPLAY_NAME = "QC Dashboard"
    DESCRIPTION = "Generate QC dashboards from alignment, variant, coverage, and custom statistics."
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
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/json.html"
    UPSTREAM_SOURCE = "Lib/json; Lib/csv.py; Lib/html/__init__.py; Lib/math.py"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"run_name": ("STRING", {"default": "Run"})},
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

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        theme = str(inputs.get("theme", "light") or "light").strip().lower()
        if theme not in {"light", "dark"}:
            return f"Unsupported QC dashboard theme: {theme}"
        return True

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        run_name = str(kwargs.get("run_name", "Run") or "Run")
        title = str(kwargs.get("title", "QC Dashboard") or "QC Dashboard")
        theme = str(kwargs.get("theme", "light") or "light").strip().lower()

        fastqc_dir = _optional_path(kwargs.get("fastqc_dir", ""), label="FastQC input", directory=True)
        alignment_stats = _optional_path(kwargs.get("alignment_stats", ""), label="Alignment stats")
        insert_size = _optional_path(kwargs.get("insert_size", ""), label="Insert-size stats")
        variant_stats = _optional_path(kwargs.get("variant_stats", ""), label="Variant stats")
        coverage_stats = _optional_path(kwargs.get("coverage_stats", ""), label="Coverage stats")

        metrics: dict[str, str] = {}
        if alignment_stats is not None:
            metrics.update(_parse_flagstat_metrics(alignment_stats))
        if variant_stats is not None:
            metrics.update(_parse_variant_metrics(variant_stats))
        metrics.update(_parse_custom_metrics(str(kwargs.get("custom_metrics", "") or "")))
        _add_read_retention(metrics)

        coverage = _coverage_rows(coverage_stats) if coverage_stats is not None else []
        max_count = max((row[2] for row in coverage), default=0.0)
        tokens = theme_tokens(theme)
        metric_cards = "".join(
            '<article class="metric-card">'
            f'<div class="metric-label">{html.escape(key)}</div>'
            f'<div class="metric-value">{html.escape(value)}</div>'
            "</article>"
            for key, value in metrics.items()
        )
        if not metric_cards:
            metric_cards = '<p class="empty-state">No summary metrics were available for this run.</p>'

        coverage_section = ""
        if coverage:
            bars = "".join(
                '<div class="coverage-row" '
                f'data-depth="{html.escape(depth, quote=True)}" '
                f'data-count="{html.escape(count_text, quote=True)}">'
                f'<span class="coverage-depth">{html.escape(depth)}</span>'
                '<span class="coverage-track">'
                f'<span class="coverage-bar" style="width:{(count / max_count * 100) if max_count else 0:.2f}%"></span>'
                "</span>"
                f'<span class="coverage-count">{html.escape(count_text)}</span>'
                "</div>"
                for depth, count_text, count in coverage
            )
            coverage_section = (
                '<section class="dashboard-panel"><h2>Coverage Depth Distribution</h2>'
                f'<div class="coverage-chart">{bars}</div></section>'
            )

        source_items = "".join(
            f"<li>{html.escape(label)}: {html.escape(path.name)}</li>"
            for label, path in [
                ("FastQC directory", fastqc_dir),
                ("Alignment stats", alignment_stats),
                ("Insert size", insert_size),
                ("Variant stats", variant_stats),
                ("Coverage stats", coverage_stats),
            ]
            if path is not None
        )
        sources_section = (
            f'<section class="dashboard-panel"><h2>Input Sources</h2><ul>{source_items}</ul></section>'
            if source_items
            else ""
        )
        document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
:root {{ color-scheme: {theme}; }}
body {{ margin: 0; background: {tokens["bg"]}; color: {tokens["text"]}; font-family: system-ui, sans-serif; }}
.dashboard-container {{ max-width: 1240px; margin: 0 auto; padding: 28px; }}
header {{ text-align: center; border-bottom: 1px solid {tokens["border"]}; padding-bottom: 18px; margin-bottom: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 30px; }}
h2 {{ margin: 0 0 14px; font-size: 18px; }}
.subtitle {{ color: {tokens["muted"]}; font-size: 14px; }}
.metrics-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 14px; margin-bottom: 22px; }}
.metric-card, .dashboard-panel {{ background: {tokens["section"]}; border: 1px solid {tokens["border"]}; border-radius: 8px; padding: 18px; }}
.metric-label {{ color: {tokens["muted"]}; font-size: 12px; text-transform: uppercase; }}
.metric-value {{ color: {tokens["accent"]}; font-size: 24px; font-weight: 700; margin-top: 6px; }}
.empty-state {{ color: {tokens["muted"]}; margin: 0; }}
.dashboard-panel {{ margin: 18px 0; }}
.coverage-chart {{ display: grid; gap: 8px; }}
.coverage-row {{ display: grid; grid-template-columns: 70px 1fr 70px; gap: 10px; align-items: center; font-size: 13px; }}
.coverage-track {{ height: 14px; background: {tokens["bg"]}; border: 1px solid {tokens["border"]}; border-radius: 999px; overflow: hidden; }}
.coverage-bar {{ display: block; height: 100%; background: {tokens["accent"]}; }}
.coverage-depth, .coverage-count {{ color: {tokens["muted"]}; }}
ul {{ margin: 0; padding-left: 20px; }}
</style>
</head>
<body>
<main class="dashboard-container">
<header><h1>{html.escape(title)}</h1><div class="subtitle">{html.escape(run_name)} | Generated by BioNodulo</div></header>
<section class="metrics-row">{metric_cards}</section>
{coverage_section}{sources_section}
</main>
</body>
</html>
"""
        output_path = node_output_path(context, self.NODE_ID, "qc_dashboard.html")
        output_path.write_text(document, encoding="utf-8")
        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="QC Dashboard")
        return {"outputs": {"qc_dashboard": str(output_path)}}
