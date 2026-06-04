"""Visualization nodes for BioNodulo workflows."""
from __future__ import annotations

import binascii
import csv
import html
import json
import math
import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


SUPPORTED_IMAGE_FORMATS = ("png", "svg")
VOLCANO_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
MA_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
SCATTER_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
LINE_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
BAR_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
HEATMAP_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
MANHATTAN_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
COVERAGE_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
VCF_STATS_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
FOREST_OUTPUT_FORMATS = SUPPORTED_IMAGE_FORMATS + ("html",)
DEFAULT_DPI = 120
DEFAULT_UP_COLOR = "#E74C3C"
DEFAULT_DOWN_COLOR = "#3498DB"
DEFAULT_NS_COLOR = "#95A5A6"
REGULATION_ORDER = {"Down": 0, "NS": 1, "Up": 2}


@dataclass(frozen=True)
class VolcanoPoint:
    """A parsed and classified differential-expression result row."""

    gene: str
    logfc: float
    pvalue: float
    neg_log_p: float
    regulation: str


@dataclass(frozen=True)
class MAPoint:
    """A parsed and classified MA plot row."""

    gene: str
    mean: float
    log_mean: float
    logfc: float
    pvalue: float
    significant: bool


@dataclass(frozen=True)
class ScatterPoint:
    """A parsed scatter plot row."""

    x: float
    y: float
    color_value: str
    size_value: float | None


@dataclass(frozen=True)
class BarDatum:
    """A parsed bar chart row."""

    category: str
    value: float
    group: str


@dataclass(frozen=True)
class ForestPlotRow:
    """A parsed forest plot study or pooled estimate row."""

    label: str
    effect: float
    lower: float
    upper: float
    weight: float | None
    pooled: bool


@dataclass(frozen=True)
class LineSeries:
    """A parsed line chart series."""

    name: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class HeatmapMatrix:
    """A parsed numeric matrix for heatmap rendering."""

    row_labels: tuple[str, ...]
    column_labels: tuple[str, ...]
    values: tuple[tuple[float | None, ...], ...]


@dataclass(frozen=True)
class ManhattanPoint:
    """A parsed GWAS association point for Manhattan plots."""

    chromosome: str
    position: float
    pvalue: float
    neg_log_p: float
    snp: str


@dataclass(frozen=True)
class CoverageBin:
    """A genomic coverage segment or binned coverage interval."""

    chromosome: str
    start: int
    end: int
    coverage: float


@dataclass
class TreeNode:
    """A parsed Newick tree node."""

    name: str = ""
    length: float = 0.0
    children: list["TreeNode"] | None = None

    @property
    def is_leaf(self) -> bool:
        return not self.children


@dataclass(frozen=True)
class VCFRecord:
    """A parsed VCF variant record."""

    chromosome: str
    position: int
    ref: str
    alts: tuple[str, ...]
    quality: float | None
    depth: float | None


@dataclass(frozen=True)
class VCFStats:
    """Summary statistics for a VCF file."""

    variant_types: dict[str, int]
    total_variants: int
    transitions: int
    transversions: int
    titv_ratio: float | None
    qualities: tuple[float, ...]
    depths: tuple[float, ...]
    chromosome_counts: dict[str, int]


@dataclass(frozen=True)
class CircosChromosome:
    """A chromosome sector for Circos-style plots."""

    name: str
    start: int
    end: int

    @property
    def length(self) -> int:
        return max(1, self.end - self.start)


@dataclass(frozen=True)
class CircosInterval:
    """A genomic interval track item for Circos-style plots."""

    chromosome: str
    start: int
    end: int
    label: str
    value: float | None = None


@dataclass(frozen=True)
class CircosVariant:
    """A variant marker for Circos-style plots."""

    chromosome: str
    position: int
    identifier: str


@dataclass(frozen=True)
class IGVVariant:
    """A variant marker for IGV-style snapshots."""

    chromosome: str
    position: int
    identifier: str
    variant_type: str


@dataclass(frozen=True)
class IGVAnnotation:
    """A gene or feature interval for IGV-style snapshots."""

    chromosome: str
    start: int
    end: int
    name: str
    strand: str


@dataclass(frozen=True)
class PlotBounds:
    x_min: float
    x_max: float
    y_max: float
    threshold_y: float


@dataclass(frozen=True)
class MABounds:
    x_min: float
    x_max: float
    y_min: float
    y_max: float


@dataclass(frozen=True)
class XYBounds:
    x_min: float
    x_max: float
    y_min: float
    y_max: float


@dataclass(frozen=True)
class PlotLayout:
    width: int
    height: int
    left: int
    right: int
    top: int
    bottom: int

    @property
    def plot_width(self) -> int:
        return max(1, self.width - self.left - self.right)

    @property
    def plot_height(self) -> int:
        return max(1, self.height - self.top - self.bottom)


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _coerce_float(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    return float(value)


def _coerce_int(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    return int(value)


def _normalise_hex_color(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if len(text) == 4 and text.startswith("#"):
        chars = text[1:]
        if all(ch in "0123456789abcdefABCDEF" for ch in chars):
            return "#" + "".join(ch * 2 for ch in chars).upper()
    if len(text) == 7 and text.startswith("#"):
        chars = text[1:]
        if all(ch in "0123456789abcdefABCDEF" for ch in chars):
            return "#" + chars.upper()
    return default


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = _normalise_hex_color(color, DEFAULT_NS_COLOR)
    return (
        int(color[1:3], 16),
        int(color[3:5], 16),
        int(color[5:7], 16),
    )


def _resolve_delimiter(value: Any, sample: str) -> str:
    text = str(value or "auto").strip().lower()
    if text in {"\\t", "tab", "tsv"}:
        return "\t"
    if text in {",", "comma", "csv"}:
        return ","
    if text in {";", "semicolon"}:
        return ";"
    if text and text not in {"auto", "detect"}:
        return text[0]

    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;").delimiter
    except csv.Error:
        return "\t" if sample.count("\t") >= sample.count(",") else ","


def _parse_float(value: Any) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.upper() in {"NA", "N/A", "NAN", "NULL", "."}:
        return None
    try:
        number = float(text)
    except ValueError:
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def _read_result_rows(
    path: Path,
    *,
    delimiter: Any,
    logfc_column: str,
    pvalue_column: str,
    gene_column: str,
) -> list[tuple[str, float, float]]:
    if not path.exists():
        raise FileNotFoundError(f"Results table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Results table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [logfc_column, pvalue_column]
        if gene_column:
            required_columns.append(gene_column)
        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        logfc_index = column_index[logfc_column]
        pvalue_index = column_index[pvalue_column]
        gene_index = column_index.get(gene_column) if gene_column else None
        rows: list[tuple[str, float, float]] = []

        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            logfc = _parse_float(row[logfc_index] if logfc_index < len(row) else None)
            pvalue = _parse_float(row[pvalue_index] if pvalue_index < len(row) else None)
            if logfc is None or pvalue is None:
                continue
            if gene_index is not None and gene_index < len(row):
                gene = row[gene_index].strip()
            else:
                gene = f"row_{row_number}"
            rows.append((gene, logfc, pvalue))

    if not rows:
        raise ValueError(
            f"No numeric rows found for columns '{logfc_column}' and '{pvalue_column}'"
        )
    return rows


def _read_scatter_rows(
    path: Path,
    *,
    delimiter: Any,
    x_column: str,
    y_column: str,
    color_column: str,
    size_column: str,
) -> list[ScatterPoint]:
    if not path.exists():
        raise FileNotFoundError(f"Input table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Input table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [x_column, y_column]
        if color_column:
            required_columns.append(color_column)
        if size_column:
            required_columns.append(size_column)
        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        x_index = column_index[x_column]
        y_index = column_index[y_column]
        color_index = column_index.get(color_column) if color_column else None
        size_index = column_index.get(size_column) if size_column else None
        rows: list[ScatterPoint] = []

        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            x = _parse_float(row[x_index] if x_index < len(row) else None)
            y = _parse_float(row[y_index] if y_index < len(row) else None)
            if x is None or y is None:
                continue
            color_value = ""
            if color_index is not None and color_index < len(row):
                color_value = row[color_index].strip()
            size_value = None
            if size_index is not None and size_index < len(row):
                size_value = _parse_float(row[size_index])
            rows.append(
                ScatterPoint(
                    x=x,
                    y=y,
                    color_value=color_value,
                    size_value=size_value,
                )
            )

    if not rows:
        raise ValueError(f"No numeric rows found for columns '{x_column}' and '{y_column}'")
    return rows


def _read_bar_rows(
    path: Path,
    *,
    delimiter: Any,
    x_column: str,
    y_column: str,
    group_column: str,
) -> list[BarDatum]:
    if not path.exists():
        raise FileNotFoundError(f"Input table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Input table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [x_column, y_column]
        if group_column:
            required_columns.append(group_column)
        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        category_index = column_index[x_column]
        value_index = column_index[y_column]
        group_index = column_index.get(group_column) if group_column else None
        rows: list[BarDatum] = []

        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            value = _parse_float(row[value_index] if value_index < len(row) else None)
            if value is None:
                continue
            category = row[category_index].strip() if category_index < len(row) else f"row_{row_number}"
            group = row[group_index].strip() if group_index is not None and group_index < len(row) else ""
            rows.append(BarDatum(category=category or f"row_{row_number}", value=value, group=group))

    if not rows:
        raise ValueError(f"No numeric rows found for columns '{x_column}' and '{y_column}'")
    return rows


def _truthy_cell(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"1", "true", "t", "yes", "y", "pooled", "overall", "summary"}


def _read_forest_rows(
    path: Path,
    *,
    delimiter: Any,
    label_column: str,
    effect_column: str,
    lower_column: str,
    upper_column: str,
    se_column: str,
    weight_column: str,
    pooled_column: str,
) -> list[ForestPlotRow]:
    if not path.exists():
        raise FileNotFoundError(f"Forest plot table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Forest plot table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [label_column, effect_column]
        has_interval_columns = bool(lower_column and upper_column and lower_column in header and upper_column in header)
        has_se_column = bool(se_column and se_column in header)
        if not has_interval_columns and not has_se_column:
            if lower_column:
                required_columns.append(lower_column)
            if upper_column:
                required_columns.append(upper_column)
            if se_column:
                required_columns.append(se_column)
        if weight_column:
            required_columns.append(weight_column)
        if pooled_column:
            required_columns.append(pooled_column)

        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        label_index = column_index[label_column]
        effect_index = column_index[effect_column]
        lower_index = column_index.get(lower_column) if lower_column else None
        upper_index = column_index.get(upper_column) if upper_column else None
        se_index = column_index.get(se_column) if se_column else None
        weight_index = column_index.get(weight_column) if weight_column else None
        pooled_index = column_index.get(pooled_column) if pooled_column else None
        rows: list[ForestPlotRow] = []

        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue

            effect = _parse_float(row[effect_index] if effect_index < len(row) else None)
            if effect is None:
                continue

            lower: float | None = None
            upper: float | None = None
            if lower_index is not None and upper_index is not None:
                lower = _parse_float(row[lower_index] if lower_index < len(row) else None)
                upper = _parse_float(row[upper_index] if upper_index < len(row) else None)
            if (lower is None or upper is None) and se_index is not None:
                se = _parse_float(row[se_index] if se_index < len(row) else None)
                if se is not None and se >= 0:
                    lower = effect - 1.96 * se
                    upper = effect + 1.96 * se

            if lower is None or upper is None:
                continue
            if lower > upper:
                lower, upper = upper, lower

            label = row[label_index].strip() if label_index < len(row) else ""
            weight = None
            if weight_index is not None and weight_index < len(row):
                weight = _parse_float(row[weight_index])
            pooled = False
            if pooled_index is not None and pooled_index < len(row):
                pooled = _truthy_cell(row[pooled_index])
            elif "pooled" in label.lower() or "overall" in label.lower():
                pooled = True

            rows.append(
                ForestPlotRow(
                    label=label or f"row_{row_number}",
                    effect=effect,
                    lower=lower,
                    upper=upper,
                    weight=weight,
                    pooled=pooled,
                )
            )

    if not rows:
        interval_text = (
            f"'{lower_column}' and '{upper_column}'"
            if lower_column and upper_column
            else f"standard error column '{se_column}'"
        )
        raise ValueError(
            f"No numeric rows found for columns '{effect_column}' and {interval_text}"
        )
    return rows


def _read_line_series(
    path: Path,
    *,
    delimiter: Any,
    x_column: str,
    y_columns: list[str],
) -> list[LineSeries]:
    if not path.exists():
        raise FileNotFoundError(f"Input table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Input table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [x_column, *y_columns]
        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        x_index = column_index[x_column]
        y_indexes = {name: column_index[name] for name in y_columns}
        series_points: dict[str, list[tuple[float, float]]] = {name: [] for name in y_columns}

        for row in reader:
            if not row or all(not cell.strip() for cell in row):
                continue
            x = _parse_float(row[x_index] if x_index < len(row) else None)
            if x is None:
                continue
            for y_column, y_index in y_indexes.items():
                y = _parse_float(row[y_index] if y_index < len(row) else None)
                if y is not None:
                    series_points[y_column].append((x, y))

    series = [
        LineSeries(name=name, points=tuple(points))
        for name, points in series_points.items()
        if points
    ]
    if not series:
        raise ValueError(
            f"No numeric rows found for x column '{x_column}' and y columns: "
            f"{', '.join(y_columns)}"
        )
    return series


def _read_heatmap_matrix(path: Path, *, delimiter: Any) -> HeatmapMatrix:
    if not path.exists():
        raise FileNotFoundError(f"Heatmap matrix not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Heatmap matrix is empty") from exc

        header = [name.strip() for name in raw_header]
        if len(header) < 2:
            raise ValueError("Heatmap matrix requires one row-label column and at least one numeric column")
        column_labels = tuple(label or f"column_{idx}" for idx, label in enumerate(header[1:], start=1))
        row_labels: list[str] = []
        values: list[tuple[float | None, ...]] = []
        numeric_count = 0

        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            label = row[0].strip() if row else ""
            row_values: list[float | None] = []
            for column_index in range(1, len(header)):
                value = _parse_float(row[column_index] if column_index < len(row) else None)
                if value is not None:
                    numeric_count += 1
                row_values.append(value)
            row_labels.append(label or f"row_{row_number}")
            values.append(tuple(row_values))

    if not row_labels:
        raise ValueError("Heatmap matrix has no data rows")
    if numeric_count == 0:
        raise ValueError("No numeric heatmap cells found")
    return HeatmapMatrix(
        row_labels=tuple(row_labels),
        column_labels=column_labels,
        values=tuple(values),
    )


def _normalise_chromosome(value: Any) -> str:
    text = str(value or "").strip()
    if text.lower().startswith("chr"):
        text = text[3:]
    return text or "unknown"


def _read_manhattan_points(
    path: Path,
    *,
    delimiter: Any,
    chr_column: str,
    pos_column: str,
    pvalue_column: str,
    snp_column: str,
) -> list[ManhattanPoint]:
    if not path.exists():
        raise FileNotFoundError(f"GWAS results table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("GWAS results table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [chr_column, pos_column, pvalue_column]
        if snp_column:
            required_columns.append(snp_column)
        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        chr_index = column_index[chr_column]
        pos_index = column_index[pos_column]
        pvalue_index = column_index[pvalue_column]
        snp_index = column_index.get(snp_column) if snp_column else None
        points: list[ManhattanPoint] = []

        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            position = _parse_float(row[pos_index] if pos_index < len(row) else None)
            pvalue = _parse_float(row[pvalue_index] if pvalue_index < len(row) else None)
            if position is None or pvalue is None or pvalue <= 0:
                continue
            chromosome = _normalise_chromosome(row[chr_index] if chr_index < len(row) else "")
            snp = ""
            if snp_index is not None and snp_index < len(row):
                snp = row[snp_index].strip()
            points.append(
                ManhattanPoint(
                    chromosome=chromosome,
                    position=position,
                    pvalue=pvalue,
                    neg_log_p=-math.log10(pvalue),
                    snp=snp or f"row_{row_number}",
                )
            )

    if not points:
        raise ValueError(
            f"No numeric positive rows found for columns '{pos_column}' and '{pvalue_column}'"
        )
    return points


def _read_ma_rows(
    path: Path,
    *,
    delimiter: Any,
    mean_column: str,
    logfc_column: str,
    pvalue_column: str,
    gene_column: str,
) -> list[tuple[str, float, float, float]]:
    if not path.exists():
        raise FileNotFoundError(f"Results table not found: {path}")

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        resolved_delimiter = _resolve_delimiter(delimiter, sample)
        reader = csv.reader(handle, delimiter=resolved_delimiter)
        try:
            raw_header = next(reader)
        except StopIteration as exc:
            raise ValueError("Results table is empty") from exc

        header = [name.strip() for name in raw_header]
        required_columns = [mean_column, logfc_column, pvalue_column]
        if gene_column:
            required_columns.append(gene_column)
        missing = [column for column in required_columns if column not in header]
        if missing:
            missing_text = ", ".join(missing)
            available_text = ", ".join(header) if header else "<none>"
            raise ValueError(
                f"Column(s) not found: {missing_text}. Available columns: {available_text}"
            )

        column_index = {name: idx for idx, name in enumerate(header)}
        mean_index = column_index[mean_column]
        logfc_index = column_index[logfc_column]
        pvalue_index = column_index[pvalue_column]
        gene_index = column_index.get(gene_column) if gene_column else None
        rows: list[tuple[str, float, float, float]] = []

        for row_number, row in enumerate(reader, start=2):
            if not row or all(not cell.strip() for cell in row):
                continue
            mean = _parse_float(row[mean_index] if mean_index < len(row) else None)
            logfc = _parse_float(row[logfc_index] if logfc_index < len(row) else None)
            pvalue = _parse_float(row[pvalue_index] if pvalue_index < len(row) else None)
            if mean is None or logfc is None or pvalue is None or mean <= 0:
                continue
            if gene_index is not None and gene_index < len(row):
                gene = row[gene_index].strip()
            else:
                gene = f"row_{row_number}"
            rows.append((gene, mean, logfc, pvalue))

    if not rows:
        raise ValueError(
            f"No numeric positive rows found for columns '{mean_column}', "
            f"'{logfc_column}', and '{pvalue_column}'"
        )
    return rows


def _classify_points(
    rows: list[tuple[str, float, float]],
    *,
    logfc_threshold: float,
    pvalue_threshold: float,
) -> list[VolcanoPoint]:
    positive_pvalues = [pvalue for _, _, pvalue in rows if pvalue > 0]
    if positive_pvalues:
        floor = max(min(positive_pvalues) * 0.1, 1e-300)
    else:
        floor = 1e-300

    points: list[VolcanoPoint] = []
    for gene, logfc, pvalue in rows:
        plot_pvalue = pvalue if pvalue > 0 else floor
        neg_log_p = -math.log10(plot_pvalue)
        if logfc > logfc_threshold and pvalue < pvalue_threshold:
            regulation = "Up"
        elif logfc < -logfc_threshold and pvalue < pvalue_threshold:
            regulation = "Down"
        else:
            regulation = "NS"
        points.append(
            VolcanoPoint(
                gene=gene,
                logfc=logfc,
                pvalue=pvalue,
                neg_log_p=neg_log_p,
                regulation=regulation,
            )
        )
    return points


def _classify_ma_points(
    rows: list[tuple[str, float, float, float]],
    *,
    logfc_threshold: float,
    pvalue_threshold: float,
) -> list[MAPoint]:
    points: list[MAPoint] = []
    for gene, mean, logfc, pvalue in rows:
        significant = abs(logfc) > logfc_threshold and pvalue < pvalue_threshold
        points.append(
            MAPoint(
                gene=gene,
                mean=mean,
                log_mean=math.log10(mean),
                logfc=logfc,
                pvalue=pvalue,
                significant=significant,
            )
        )
    return points


def _plot_bounds(
    points: list[VolcanoPoint],
    *,
    logfc_threshold: float,
    pvalue_threshold: float,
) -> PlotBounds:
    x_abs = max(
        [abs(point.logfc) for point in points] + [abs(logfc_threshold), 1.0]
    )
    threshold_y = -math.log10(pvalue_threshold)
    y_max = max([point.neg_log_p for point in points] + [threshold_y, 1.0])
    return PlotBounds(
        x_min=-(x_abs * 1.12),
        x_max=x_abs * 1.12,
        y_max=y_max * 1.12,
        threshold_y=threshold_y,
    )


def _ma_bounds(points: list[MAPoint], *, logfc_threshold: float) -> MABounds:
    x_values = [point.log_mean for point in points]
    x_min = min(x_values)
    x_max = max(x_values)
    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    else:
        x_pad = (x_max - x_min) * 0.06
        x_min -= x_pad
        x_max += x_pad

    y_abs = max([abs(point.logfc) for point in points] + [abs(logfc_threshold), 1.0])
    y_abs *= 1.12
    return MABounds(x_min=x_min, x_max=x_max, y_min=-y_abs, y_max=y_abs)


def _xy_bounds(points: list[ScatterPoint]) -> XYBounds:
    x_values = [point.x for point in points]
    y_values = [point.y for point in points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)

    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    else:
        x_pad = (x_max - x_min) * 0.08
        x_min -= x_pad
        x_max += x_pad

    if math.isclose(y_min, y_max):
        y_min -= 0.5
        y_max += 0.5
    else:
        y_pad = (y_max - y_min) * 0.08
        y_min -= y_pad
        y_max += y_pad

    return XYBounds(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)


def _line_bounds(series: list[LineSeries]) -> XYBounds:
    x_values = [x for item in series for x, _ in item.points]
    y_values = [y for item in series for _, y in item.points]
    x_min = min(x_values)
    x_max = max(x_values)
    y_min = min(y_values)
    y_max = max(y_values)

    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    else:
        x_pad = (x_max - x_min) * 0.08
        x_min -= x_pad
        x_max += x_pad

    if math.isclose(y_min, y_max):
        y_min -= 0.5
        y_max += 0.5
    else:
        y_pad = (y_max - y_min) * 0.08
        y_min -= y_pad
        y_max += y_pad

    return XYBounds(x_min=x_min, x_max=x_max, y_min=y_min, y_max=y_max)


def _forest_bounds(rows: list[ForestPlotRow], *, reference: float) -> tuple[float, float]:
    x_min = min([row.lower for row in rows] + [reference])
    x_max = max([row.upper for row in rows] + [reference])
    if math.isclose(x_min, x_max):
        x_min -= 0.5
        x_max += 0.5
    else:
        pad = (x_max - x_min) * 0.10
        x_min -= pad
        x_max += pad
    return x_min, x_max


def _pixel_dimensions(width: Any, height: Any, dpi: Any) -> tuple[int, int]:
    width_value = max(_coerce_float(width, 8.0), 1.0)
    height_value = max(_coerce_float(height, 6.0), 1.0)
    dpi_value = min(max(_coerce_int(dpi, DEFAULT_DPI), 30), 600)

    width_px = width_value * dpi_value if width_value <= 50 else width_value
    height_px = height_value * dpi_value if height_value <= 50 else height_value
    return (
        min(max(int(round(width_px)), 320), 4096),
        min(max(int(round(height_px)), 240), 4096),
    )


def _layout(width: int, height: int) -> PlotLayout:
    return PlotLayout(
        width=width,
        height=height,
        left=max(64, int(width * 0.08)),
        right=max(28, int(width * 0.03)),
        top=max(56, int(height * 0.09)),
        bottom=max(58, int(height * 0.10)),
    )


def _project_x(value: float, bounds: PlotBounds, layout: PlotLayout) -> float:
    span = bounds.x_max - bounds.x_min
    return layout.left + ((value - bounds.x_min) / span) * layout.plot_width


def _project_y(value: float, bounds: PlotBounds, layout: PlotLayout) -> float:
    return layout.top + (1.0 - (value / bounds.y_max)) * layout.plot_height


def _project_ma_x(value: float, bounds: MABounds, layout: PlotLayout) -> float:
    span = bounds.x_max - bounds.x_min
    return layout.left + ((value - bounds.x_min) / span) * layout.plot_width


def _project_ma_y(value: float, bounds: MABounds, layout: PlotLayout) -> float:
    span = bounds.y_max - bounds.y_min
    return layout.top + (1.0 - ((value - bounds.y_min) / span)) * layout.plot_height


def _project_xy_x(value: float, bounds: XYBounds, layout: PlotLayout) -> float:
    span = bounds.x_max - bounds.x_min
    return layout.left + ((value - bounds.x_min) / span) * layout.plot_width


def _project_xy_y(value: float, bounds: XYBounds, layout: PlotLayout) -> float:
    span = bounds.y_max - bounds.y_min
    return layout.top + (1.0 - ((value - bounds.y_min) / span)) * layout.plot_height


def _project_forest_x(value: float, bounds: tuple[float, float], layout: PlotLayout) -> float:
    low, high = bounds
    span = high - low
    return layout.left + ((value - low) / span) * layout.plot_width


def _colour_map(up_color: str, down_color: str, ns_color: str) -> dict[str, str]:
    return {"Up": up_color, "Down": down_color, "NS": ns_color}


def _categorical_palette(values: list[str]) -> dict[str, str]:
    palette = [
        "#2563EB",
        "#DC2626",
        "#16A34A",
        "#9333EA",
        "#EA580C",
        "#0891B2",
        "#BE123C",
        "#4D7C0F",
    ]
    categories = sorted({value or "Unlabelled" for value in values})
    return {category: palette[index % len(palette)] for index, category in enumerate(categories)}


def _scatter_color_data(
    points: list[ScatterPoint],
    *,
    color_column: str,
) -> tuple[str, dict[str, str] | None, tuple[float, float] | None]:
    if not color_column:
        return "none", None, None
    values = [point.color_value for point in points]
    numeric_values = [_parse_float(value) for value in values]
    if all(value is not None for value in numeric_values) and len(set(values)) > 8:
        numbers = [float(value) for value in numeric_values if value is not None]
        return "numeric", None, (min(numbers), max(numbers))
    return "categorical", _categorical_palette(values), None


def _scatter_point_color(
    point: ScatterPoint,
    *,
    color_mode: str,
    category_colours: dict[str, str] | None,
    numeric_range: tuple[float, float] | None,
) -> str:
    if color_mode == "categorical" and category_colours:
        return category_colours.get(point.color_value or "Unlabelled", "#2563EB")
    if color_mode == "numeric" and numeric_range:
        value = _parse_float(point.color_value)
        if value is None:
            return "#2563EB"
        low, high = numeric_range
        ratio = 0.5 if math.isclose(low, high) else (value - low) / (high - low)
        ratio = _clamp(ratio, 0.0, 1.0)
        r = int(37 + ratio * (220 - 37))
        g = int(99 + ratio * (38 - 99))
        b = int(235 + ratio * (38 - 235))
        return f"#{r:02X}{g:02X}{b:02X}"
    return "#2563EB"


def _scatter_radius(
    point: ScatterPoint,
    *,
    point_size: int,
    size_range: tuple[float, float] | None,
) -> float:
    base = max(2.0, min(float(point_size), 200.0) ** 0.5)
    if point.size_value is None or size_range is None:
        return _clamp(base, 3.0, 10.0)
    low, high = size_range
    ratio = 0.5 if math.isclose(low, high) else (point.size_value - low) / (high - low)
    return 3.0 + _clamp(ratio, 0.0, 1.0) * 7.0


def _scatter_size_range(points: list[ScatterPoint]) -> tuple[float, float] | None:
    values = [point.size_value for point in points if point.size_value is not None]
    if not values:
        return None
    return (min(values), max(values))


def _regression_line(points: list[ScatterPoint]) -> tuple[float, float] | None:
    if len(points) < 2:
        return None
    n = float(len(points))
    sum_x = sum(point.x for point in points)
    sum_y = sum(point.y for point in points)
    sum_xx = sum(point.x * point.x for point in points)
    sum_xy = sum(point.x * point.y for point in points)
    denominator = n * sum_xx - sum_x * sum_x
    if math.isclose(denominator, 0.0):
        return None
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n
    return slope, intercept


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            ordered.append(value)
    return ordered


def _bar_categories(rows: list[BarDatum]) -> list[str]:
    return _ordered_unique([row.category for row in rows])


def _bar_groups(rows: list[BarDatum]) -> list[str]:
    groups = _ordered_unique([row.group or "Value" for row in rows])
    return groups or ["Value"]


def _bar_value_range(rows: list[BarDatum]) -> tuple[float, float]:
    values = [row.value for row in rows]
    low = min(values + [0.0])
    high = max(values + [0.0])
    if math.isclose(low, high):
        return (min(0.0, low - 1.0), max(1.0, high + 1.0))
    pad = (high - low) * 0.08
    return (low - pad, high + pad)


def _bar_colour(color: str, group_index: int) -> str:
    default_palette = [
        "#2563EB",
        "#DC2626",
        "#16A34A",
        "#9333EA",
        "#EA580C",
        "#0891B2",
    ]
    normalized = _normalise_hex_color(color, "")
    if normalized:
        return normalized
    if color.lower() in {"steelblue", "default", "tab10", "set1", "set2"}:
        return default_palette[group_index % len(default_palette)]
        return default_palette[group_index % len(default_palette)]


def _line_colour(palette: str, series_index: int) -> str:
    palettes = {
        "default": [
            "#2563EB",
            "#DC2626",
            "#16A34A",
            "#9333EA",
            "#EA580C",
            "#0891B2",
        ],
        "tab10": [
            "#1F77B4",
            "#FF7F0E",
            "#2CA02C",
            "#D62728",
            "#9467BD",
            "#8C564B",
            "#E377C2",
            "#7F7F7F",
            "#BCBD22",
            "#17BECF",
        ],
        "set2": [
            "#66C2A5",
            "#FC8D62",
            "#8DA0CB",
            "#E78AC3",
            "#A6D854",
            "#FFD92F",
            "#E5C494",
            "#B3B3B3",
        ],
    }
    normalized = _normalise_hex_color(palette, "")
    if normalized:
        return normalized
    colours = palettes.get(str(palette or "").strip().lower(), palettes["default"])
    return colours[series_index % len(colours)]


def _heatmap_numeric_values(matrix: HeatmapMatrix) -> list[float]:
    return [value for row in matrix.values for value in row if value is not None]


def _standardise_values(values: list[float | None]) -> list[float | None]:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return values
    mean = sum(numeric) / len(numeric)
    variance = sum((value - mean) ** 2 for value in numeric) / len(numeric)
    stdev = variance ** 0.5
    if math.isclose(stdev, 0.0):
        return [0.0 if value is not None else None for value in values]
    return [((value - mean) / stdev) if value is not None else None for value in values]


def _scale_heatmap_matrix(matrix: HeatmapMatrix, scale: str) -> HeatmapMatrix:
    mode = str(scale or "none").strip().lower()
    if mode == "none":
        return matrix
    if mode == "row":
        return HeatmapMatrix(
            row_labels=matrix.row_labels,
            column_labels=matrix.column_labels,
            values=tuple(tuple(_standardise_values(list(row))) for row in matrix.values),
        )
    if mode == "column":
        rows = [list(row) for row in matrix.values]
        columns = [
            _standardise_values([row[column_index] for row in rows])
            for column_index in range(len(matrix.column_labels))
        ]
        scaled_rows = []
        for row_index in range(len(matrix.row_labels)):
            scaled_rows.append(tuple(column[row_index] for column in columns))
        return HeatmapMatrix(
            row_labels=matrix.row_labels,
            column_labels=matrix.column_labels,
            values=tuple(scaled_rows),
        )
    raise ValueError(f"Unsupported heatmap scale: {scale}")


def _heatmap_order(matrix: HeatmapMatrix, *, cluster_rows: bool, cluster_cols: bool) -> tuple[list[int], list[int]]:
    row_order = list(range(len(matrix.row_labels)))
    col_order = list(range(len(matrix.column_labels)))
    if cluster_rows:
        row_order.sort(
            key=lambda index: (
                sum(value for value in matrix.values[index] if value is not None)
                / max(1, sum(1 for value in matrix.values[index] if value is not None)),
                matrix.row_labels[index],
            )
        )
    if cluster_cols:
        col_order.sort(
            key=lambda index: (
                sum(row[index] for row in matrix.values if row[index] is not None)
                / max(1, sum(1 for row in matrix.values if row[index] is not None)),
                matrix.column_labels[index],
            )
        )
    return row_order, col_order


def _interpolate_rgb(
    start: tuple[int, int, int],
    end: tuple[int, int, int],
    ratio: float,
) -> tuple[int, int, int]:
    clamped = _clamp(ratio, 0.0, 1.0)
    return (
        int(round(start[0] + (end[0] - start[0]) * clamped)),
        int(round(start[1] + (end[1] - start[1]) * clamped)),
        int(round(start[2] + (end[2] - start[2]) * clamped)),
    )


def _rgb_to_hex(colour: tuple[int, int, int]) -> str:
    return f"#{colour[0]:02X}{colour[1]:02X}{colour[2]:02X}"


def _heatmap_cell_colour(value: float | None, *, low: float, high: float, colormap: str) -> str:
    if value is None:
        return "#E5E7EB"
    ratio = 0.5 if math.isclose(low, high) else (value - low) / (high - low)
    palette = str(colormap or "RdYlBu_r").strip().lower()
    if palette in {"viridis", "magma"}:
        stops = [(68, 1, 84), (59, 82, 139), (33, 145, 140), (94, 201, 98), (253, 231, 37)]
    elif palette in {"blues", "blue"}:
        stops = [(239, 246, 255), (147, 197, 253), (37, 99, 235), (30, 64, 175)]
    elif palette in {"redblue", "rdbu", "rdylbu_r", "rdbu_r"}:
        stops = [(49, 54, 149), (116, 173, 209), (255, 255, 191), (244, 109, 67), (165, 0, 38)]
    else:
        stops = [(49, 54, 149), (116, 173, 209), (255, 255, 191), (244, 109, 67), (165, 0, 38)]
    scaled = _clamp(ratio, 0.0, 1.0) * (len(stops) - 1)
    start_index = min(int(math.floor(scaled)), len(stops) - 2)
    local_ratio = scaled - start_index
    return _rgb_to_hex(_interpolate_rgb(stops[start_index], stops[start_index + 1], local_ratio))


def _chromosome_sort_key(value: str) -> tuple[int, int | str]:
    upper = value.upper()
    if upper == "X":
        return (0, 23)
    if upper == "Y":
        return (0, 24)
    if upper in {"M", "MT"}:
        return (0, 25)
    try:
        return (0, int(upper))
    except ValueError:
        return (1, upper)


def _manhattan_chromosomes(points: list[ManhattanPoint]) -> list[str]:
    return sorted({point.chromosome for point in points}, key=_chromosome_sort_key)


def _manhattan_plot_points(
    points: list[ManhattanPoint],
) -> tuple[list[tuple[ManhattanPoint, float]], dict[str, float], float]:
    chromosomes = _manhattan_chromosomes(points)
    plot_points: list[tuple[ManhattanPoint, float]] = []
    chromosome_centres: dict[str, float] = {}
    offset = 0.0
    gap = 1.0
    for chromosome in chromosomes:
        chromosome_points = sorted(
            [point for point in points if point.chromosome == chromosome],
            key=lambda point: point.position,
        )
        if not chromosome_points:
            continue
        max_position = max(point.position for point in chromosome_points)
        for point in chromosome_points:
            plot_points.append((point, offset + point.position))
        chromosome_centres[chromosome] = offset + max_position / 2.0
        offset += max_position + gap
    return plot_points, chromosome_centres, max(offset, 1.0)


def _manhattan_bounds(
    points: list[ManhattanPoint],
    *,
    significance_threshold: float,
    suggestive_threshold: float,
) -> PlotBounds:
    _, _, x_max = _manhattan_plot_points(points)
    threshold_y = -math.log10(significance_threshold)
    suggestive_y = -math.log10(suggestive_threshold)
    y_max = max([point.neg_log_p for point in points] + [threshold_y, suggestive_y, 1.0])
    return PlotBounds(
        x_min=0.0,
        x_max=x_max,
        y_max=y_max * 1.12,
        threshold_y=threshold_y,
    )


def _manhattan_colour(chr_colors: str, chromosome_index: int) -> str:
    defaults = ["#3498DB", "#2ECC71"]
    colours = [
        _normalise_hex_color(item.strip(), "")
        for item in str(chr_colors or "").split(",")
        if item.strip()
    ]
    colours = [colour for colour in colours if colour]
    if not colours:
        colours = defaults
    return colours[chromosome_index % len(colours)]


def _parse_region(region: str) -> tuple[str, int, int]:
    text = str(region or "").strip().replace(",", "")
    if ":" not in text or "-" not in text:
        raise ValueError("Region must use chrom:start-end format")
    chromosome, span = text.split(":", 1)
    start_text, end_text = span.split("-", 1)
    chromosome = chromosome.strip()
    if not chromosome:
        raise ValueError("Region must include a chromosome")
    try:
        start = int(start_text)
        end = int(end_text)
    except ValueError as exc:
        raise ValueError("Region coordinates must be integers") from exc
    if start < 0 or end <= start:
        raise ValueError("Region end must be greater than start")
    return chromosome, start, end


def _append_coverage_bin(
    bins: list[CoverageBin],
    *,
    chromosome: str,
    start: int,
    end: int,
    coverage: float,
    region: tuple[str, int, int],
) -> None:
    region_chromosome, region_start, region_end = region
    if chromosome != region_chromosome or end <= region_start or start >= region_end:
        return
    clipped_start = max(start, region_start)
    clipped_end = min(end, region_end)
    if clipped_end <= clipped_start:
        return
    bins.append(
        CoverageBin(
            chromosome=chromosome,
            start=clipped_start,
            end=clipped_end,
            coverage=max(0.0, coverage),
        )
    )


def _read_coverage_table(path: Path, *, region: tuple[str, int, int]) -> list[CoverageBin]:
    if not path.exists():
        raise FileNotFoundError(f"Coverage input not found: {path}")

    chromosome, region_start, region_end = region
    bins: list[CoverageBin] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        sample = handle.read(4096)
        handle.seek(0)
        first_data = ""
        for line in sample.splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith(("#", "track", "browser")):
                first_data = stripped
                break
        first_cells = first_data.replace(",", "\t").split()
        has_header = len(first_cells) >= 4 and _parse_float(first_cells[1]) is None

        if has_header:
            resolved_delimiter = _resolve_delimiter("auto", sample)
            reader = csv.DictReader(handle, delimiter=resolved_delimiter)
            if not reader.fieldnames:
                raise ValueError("Coverage table is empty")
            field_map = {name.lower().strip(): name for name in reader.fieldnames}
            chrom_field = field_map.get("chrom") or field_map.get("chromosome") or field_map.get("chr")
            start_field = field_map.get("start")
            end_field = field_map.get("end") or field_map.get("stop")
            cov_field = (
                field_map.get("coverage")
                or field_map.get("depth")
                or field_map.get("value")
                or field_map.get("score")
            )
            if not chrom_field or not start_field or not end_field or not cov_field:
                raise ValueError("Coverage table requires chromosome, start, end, and coverage columns")
            for row in reader:
                row_chromosome = str(row.get(chrom_field, "")).strip()
                start_value = _parse_float(row.get(start_field))
                end_value = _parse_float(row.get(end_field))
                coverage_value = _parse_float(row.get(cov_field))
                if start_value is None or end_value is None or coverage_value is None:
                    continue
                _append_coverage_bin(
                    bins,
                    chromosome=row_chromosome,
                    start=int(start_value),
                    end=int(end_value),
                    coverage=coverage_value,
                    region=region,
                )
        else:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line or line.startswith(("#", "track", "browser")):
                    continue
                cells = line.replace(",", "\t").split()
                if len(cells) < 4:
                    raise ValueError(f"Coverage row {line_number} must have at least 4 columns")
                start_value = _parse_float(cells[1])
                end_value = _parse_float(cells[2])
                coverage_value = _parse_float(cells[3])
                if start_value is None or end_value is None or coverage_value is None:
                    continue
                _append_coverage_bin(
                    bins,
                    chromosome=cells[0].strip(),
                    start=int(start_value),
                    end=int(end_value),
                    coverage=coverage_value,
                    region=region,
                )

    if not bins:
        raise ValueError(f"No coverage rows overlap {chromosome}:{region_start}-{region_end}")
    return bins


def _read_bam_coverage(path: Path, *, region: tuple[str, int, int], window_size: int) -> list[CoverageBin]:
    try:
        import pysam  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Reading BAM/CRAM coverage requires the optional 'pysam' package") from exc

    chromosome, region_start, region_end = region
    window = max(window_size, 1)
    bins: list[CoverageBin] = []
    with pysam.AlignmentFile(str(path), "rb") as alignment:
        for start in range(region_start, region_end, window):
            end = min(start + window, region_end)
            total = 0
            for pileup in alignment.pileup(chromosome, start, end, truncate=True):
                total += pileup.nsegments
            bins.append(
                CoverageBin(
                    chromosome=chromosome,
                    start=start,
                    end=end,
                    coverage=total / max(1, end - start),
                )
            )
    return bins


def _read_bigwig_coverage(path: Path, *, region: tuple[str, int, int], window_size: int) -> list[CoverageBin]:
    try:
        import pyBigWig  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("Reading BigWig coverage requires the optional 'pyBigWig' package") from exc

    chromosome, region_start, region_end = region
    window = max(window_size, 1)
    bins: list[CoverageBin] = []
    handle = pyBigWig.open(str(path))
    try:
        for start in range(region_start, region_end, window):
            end = min(start + window, region_end)
            value = handle.stats(chromosome, start, end, type="mean")[0]
            bins.append(
                CoverageBin(
                    chromosome=chromosome,
                    start=start,
                    end=end,
                    coverage=0.0 if value is None else max(0.0, float(value)),
                )
            )
    finally:
        handle.close()
    return bins


def _bin_coverage_rows(
    rows: list[CoverageBin],
    *,
    region: tuple[str, int, int],
    window_size: int,
) -> list[CoverageBin]:
    chromosome, region_start, region_end = region
    window = max(window_size, 1)
    if window <= 1:
        return rows

    binned: list[CoverageBin] = []
    for start in range(region_start, region_end, window):
        end = min(start + window, region_end)
        weighted_total = 0.0
        covered_bases = 0
        for row in rows:
            overlap_start = max(start, row.start)
            overlap_end = min(end, row.end)
            if overlap_end <= overlap_start:
                continue
            overlap = overlap_end - overlap_start
            weighted_total += row.coverage * overlap
            covered_bases += overlap
        coverage = weighted_total / covered_bases if covered_bases else 0.0
        binned.append(CoverageBin(chromosome=chromosome, start=start, end=end, coverage=coverage))
    return binned


def _read_coverage_bins(
    path: Path,
    *,
    region: tuple[str, int, int],
    window_size: int,
) -> list[CoverageBin]:
    suffixes = {suffix.lower() for suffix in path.suffixes}
    if suffixes & {".bam", ".cram"}:
        if not path.exists():
            raise FileNotFoundError(f"Coverage input not found: {path}")
        return _read_bam_coverage(path, region=region, window_size=window_size)
    if suffixes & {".bw", ".bigwig"}:
        if not path.exists():
            raise FileNotFoundError(f"Coverage input not found: {path}")
        return _read_bigwig_coverage(path, region=region, window_size=window_size)
    return _bin_coverage_rows(
        _read_coverage_table(path, region=region),
        region=region,
        window_size=window_size,
    )


def _coverage_bounds(bins: list[CoverageBin], region: tuple[str, int, int]) -> PlotBounds:
    _, region_start, region_end = region
    y_max = max([item.coverage for item in bins] + [1.0])
    return PlotBounds(
        x_min=float(region_start),
        x_max=float(region_end),
        y_max=y_max * 1.12,
        threshold_y=0.0,
    )


def _parse_newick_file(path: Path) -> TreeNode:
    if not path.exists():
        raise FileNotFoundError(f"Phylogenetic tree file not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        raise ValueError("Phylogenetic tree file is empty")
    root, index = _parse_newick_subtree(text, 0)
    while index < len(text) and text[index].isspace():
        index += 1
    if index < len(text) and text[index] == ";":
        index += 1
    while index < len(text) and text[index].isspace():
        index += 1
    if index != len(text):
        raise ValueError("Unexpected trailing Newick content")
    return root


def _parse_newick_subtree(text: str, index: int) -> tuple[TreeNode, int]:
    index = _skip_newick_ws(text, index)
    if index >= len(text):
        raise ValueError("Unexpected end of Newick tree")

    children: list[TreeNode] | None = None
    if text[index] == "(":
        index += 1
        children = []
        while True:
            child, index = _parse_newick_subtree(text, index)
            children.append(child)
            index = _skip_newick_ws(text, index)
            if index >= len(text):
                raise ValueError("Unterminated Newick subtree")
            if text[index] == ",":
                index += 1
                continue
            if text[index] == ")":
                index += 1
                break
            raise ValueError(f"Unexpected Newick character: {text[index]!r}")

    name, index = _read_newick_token(text, index)
    length = 0.0
    index = _skip_newick_ws(text, index)
    if index < len(text) and text[index] == ":":
        index += 1
        length_text, index = _read_newick_token(text, index)
        try:
            length = float(length_text) if length_text else 0.0
        except ValueError as exc:
            raise ValueError(f"Invalid Newick branch length: {length_text}") from exc
    return TreeNode(name=name, length=max(length, 0.0), children=children), index


def _skip_newick_ws(text: str, index: int) -> int:
    while index < len(text) and text[index].isspace():
        index += 1
    return index


def _read_newick_token(text: str, index: int) -> tuple[str, int]:
    index = _skip_newick_ws(text, index)
    if index < len(text) and text[index] in {"'", '"'}:
        quote = text[index]
        index += 1
        start = index
        while index < len(text) and text[index] != quote:
            index += 1
        token = text[start:index]
        return token.strip(), min(index + 1, len(text))

    start = index
    while index < len(text) and text[index] not in ",():;":
        index += 1
    return text[start:index].strip(), index


def _tree_leaves(root: TreeNode) -> list[TreeNode]:
    if root.is_leaf:
        return [root]
    leaves: list[TreeNode] = []
    for child in root.children or []:
        leaves.extend(_tree_leaves(child))
    return leaves


def _assign_tree_coordinates(
    root: TreeNode,
    *,
    layout: PlotLayout,
) -> tuple[dict[int, tuple[float, float]], float]:
    leaves = _tree_leaves(root)
    leaf_positions = {
        id(leaf): layout.top + (index + 1) * layout.plot_height / (len(leaves) + 1)
        for index, leaf in enumerate(leaves)
    }
    max_depth = _tree_max_depth(root, 0.0)
    scale = layout.plot_width / max(max_depth, 1.0)
    positions: dict[int, tuple[float, float]] = {}

    def visit(node: TreeNode, depth: float) -> float:
        x = layout.left + depth * scale
        if node.is_leaf:
            y = leaf_positions[id(node)]
        else:
            child_ys = [visit(child, depth + child.length) for child in node.children or []]
            y = sum(child_ys) / max(1, len(child_ys))
        positions[id(node)] = (x, y)
        return y

    visit(root, 0.0)
    return positions, max_depth


def _tree_max_depth(node: TreeNode, depth: float) -> float:
    if node.is_leaf:
        return depth
    return max(_tree_max_depth(child, depth + child.length) for child in node.children or [])


def _tree_edges(root: TreeNode) -> list[tuple[TreeNode, TreeNode]]:
    edges: list[tuple[TreeNode, TreeNode]] = []
    for child in root.children or []:
        edges.append((root, child))
        edges.extend(_tree_edges(child))
    return edges


def _tree_internal_nodes(root: TreeNode) -> list[TreeNode]:
    nodes: list[TreeNode] = []
    if not root.is_leaf:
        nodes.append(root)
        for child in root.children or []:
            nodes.extend(_tree_internal_nodes(child))
    return nodes


def _bootstrap_value(name: str) -> float | None:
    value = _parse_float(name)
    if value is None:
        return None
    return value


def _polar_tree_positions(
    root: TreeNode,
    *,
    layout: PlotLayout,
) -> tuple[dict[int, tuple[float, float]], tuple[float, float]]:
    leaves = _tree_leaves(root)
    max_depth = _tree_max_depth(root, 0.0)
    centre_x = layout.left + layout.plot_width / 2
    centre_y = layout.top + layout.plot_height / 2
    radius_max = min(layout.plot_width, layout.plot_height) * 0.42
    leaf_angles = {
        id(leaf): (-math.pi / 2) + (2 * math.pi * index / max(1, len(leaves)))
        for index, leaf in enumerate(leaves)
    }
    positions: dict[int, tuple[float, float]] = {}

    def visit(node: TreeNode, depth: float) -> float:
        if node.is_leaf:
            angle = leaf_angles[id(node)]
        else:
            child_angles = [visit(child, depth + child.length) for child in node.children or []]
            sin_sum = sum(math.sin(angle) for angle in child_angles)
            cos_sum = sum(math.cos(angle) for angle in child_angles)
            angle = math.atan2(sin_sum, cos_sum)
        radius = 0.0 if math.isclose(max_depth, 0.0) else (depth / max_depth) * radius_max
        positions[id(node)] = (
            centre_x + math.cos(angle) * radius,
            centre_y + math.sin(angle) * radius,
        )
        return angle

    visit(root, 0.0)
    return positions, (centre_x, centre_y)


def _read_vcf_records(path: Path) -> list[VCFRecord]:
    if not path.exists():
        raise FileNotFoundError(f"VCF file not found: {path}")

    records: list[VCFRecord] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("##"):
                continue
            if line.startswith("#CHROM"):
                continue
            if line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 8:
                raise ValueError(f"VCF row {line_number} must have at least 8 columns")
            quality = _parse_float(fields[5])
            depth = _vcf_depth(fields[7], fields[8:] if len(fields) > 8 else [])
            try:
                position = int(fields[1])
            except ValueError as exc:
                raise ValueError(f"Invalid VCF position on row {line_number}: {fields[1]}") from exc
            records.append(
                VCFRecord(
                    chromosome=fields[0],
                    position=position,
                    ref=fields[3].upper(),
                    alts=tuple(alt.upper() for alt in fields[4].split(",") if alt and alt != "."),
                    quality=quality,
                    depth=depth,
                )
            )

    if not records:
        raise ValueError("No VCF variant records found")
    return records


def _vcf_depth(info: str, sample_fields: list[str]) -> float | None:
    for entry in str(info or "").split(";"):
        if entry.startswith("DP="):
            value = _parse_float(entry.split("=", 1)[1].split(",")[0])
            if value is not None:
                return value
    if len(sample_fields) >= 2:
        keys = sample_fields[0].split(":")
        values = sample_fields[1].split(":")
        if "DP" in keys:
            index = keys.index("DP")
            if index < len(values):
                return _parse_float(values[index])
    return None


def _variant_type(ref: str, alt: str) -> str:
    if len(ref) == 1 and len(alt) == 1:
        return "SNP"
    if len(alt) > len(ref):
        return "INS"
    if len(alt) < len(ref):
        return "DEL"
    if len(ref) == len(alt) and len(ref) > 1:
        return "MNP"
    return "OTHER"


def _vcf_stats(records: list[VCFRecord]) -> VCFStats:
    transitions = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}
    variant_types = {"SNP": 0, "INS": 0, "DEL": 0, "MNP": 0, "MIXED": 0, "OTHER": 0}
    qualities: list[float] = []
    depths: list[float] = []
    chromosome_counts: dict[str, int] = {}
    ti = 0
    tv = 0

    for record in records:
        chromosome_counts[record.chromosome] = chromosome_counts.get(record.chromosome, 0) + 1
        if record.quality is not None:
            qualities.append(record.quality)
        if record.depth is not None:
            depths.append(record.depth)
        if len(record.alts) != 1:
            variant_types["MIXED"] += 1
            continue
        alt = record.alts[0]
        kind = _variant_type(record.ref, alt)
        variant_types[kind] = variant_types.get(kind, 0) + 1
        if kind == "SNP":
            if (record.ref, alt) in transitions:
                ti += 1
            else:
                tv += 1

    ratio = round(ti / tv, 3) if tv else None
    return VCFStats(
        variant_types=variant_types,
        total_variants=len(records),
        transitions=ti,
        transversions=tv,
        titv_ratio=ratio,
        qualities=tuple(qualities),
        depths=tuple(depths),
        chromosome_counts=chromosome_counts,
    )


def _vcf_stats_json(stats: VCFStats) -> dict[str, Any]:
    qualities = list(stats.qualities)
    depths = list(stats.depths)
    return {
        "variant_types": stats.variant_types,
        "total_variants": stats.total_variants,
        "transitions": stats.transitions,
        "transversions": stats.transversions,
        "titv_ratio": stats.titv_ratio,
        "quality_stats": _numeric_summary(qualities),
        "depth_stats": _numeric_summary(depths),
        "chromosome_counts": stats.chromosome_counts,
    }


def _numeric_summary(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)
    mid = len(ordered) // 2
    median = ordered[mid] if len(ordered) % 2 else (ordered[mid - 1] + ordered[mid]) / 2
    return {
        "min": min(values),
        "max": max(values),
        "mean": sum(values) / len(values),
        "median": median,
    }


def _histogram(values: tuple[float, ...], bins: int, low: float | None, high: float | None) -> list[tuple[float, float, int]]:
    if not values:
        return []
    minimum = min(values) if low is None else low
    maximum = max(values) if high is None else high
    if math.isclose(minimum, maximum):
        maximum = minimum + 1.0
    count = max(1, min(int(bins), 200))
    width = (maximum - minimum) / count
    buckets = [[minimum + index * width, minimum + (index + 1) * width, 0] for index in range(count)]
    for value in values:
        if value < minimum or value > maximum:
            continue
        index = min(count - 1, int((value - minimum) / width))
        buckets[index][2] += 1
    return [(start, end, bucket_count) for start, end, bucket_count in buckets]


def _read_circos_chromosomes(path: Path) -> list[CircosChromosome]:
    if not path.exists():
        raise FileNotFoundError(f"Chromosome sizes file not found: {path}")
    chromosomes: list[CircosChromosome] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            cells = line.replace(",", "\t").split()
            if len(cells) < 3:
                raise ValueError(f"Chromosome sizes row {line_number} must have at least 3 columns")
            start_value = _parse_float(cells[1])
            end_value = _parse_float(cells[2])
            if start_value is None or end_value is None:
                raise ValueError(f"Chromosome sizes row {line_number} has non-numeric coordinates")
            start = int(start_value)
            end = int(end_value)
            if end <= start:
                raise ValueError(f"Chromosome sizes row {line_number} end must be greater than start")
            chromosomes.append(CircosChromosome(name=cells[0], start=start, end=end))
    if not chromosomes:
        raise ValueError("No chromosome sizes found")
    return chromosomes


def _read_circos_intervals(path_value: Any, *, value_column: bool = False) -> list[CircosInterval]:
    path_text = str(path_value or "").strip()
    if not path_text:
        return []
    path = Path(path_text)
    if not path.exists():
        raise FileNotFoundError(f"Circos track file not found: {path}")
    intervals: list[CircosInterval] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            cells = line.replace(",", "\t").split()
            if len(cells) < 3:
                raise ValueError(f"Circos interval row {line_number} must have at least 3 columns")
            start_value = _parse_float(cells[1])
            end_value = _parse_float(cells[2])
            if start_value is None or end_value is None:
                continue
            label = cells[3] if len(cells) > 3 else f"{cells[0]}:{int(start_value)}-{int(end_value)}"
            value = _parse_float(cells[3]) if value_column and len(cells) > 3 else None
            intervals.append(
                CircosInterval(
                    chromosome=cells[0],
                    start=int(start_value),
                    end=int(end_value),
                    label=label,
                    value=value,
                )
            )
    return intervals


def _read_circos_variants(path_value: Any) -> list[CircosVariant]:
    path_text = str(path_value or "").strip()
    if not path_text:
        return []
    path = Path(path_text)
    records = _read_vcf_records(path)
    variants: list[CircosVariant] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        record_index = 0
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            record = records[record_index]
            record_index += 1
            identifier = fields[2] if len(fields) > 2 and fields[2] != "." else f"{record.chromosome}:{record.position}"
            variants.append(CircosVariant(record.chromosome, record.position, identifier))
    return variants


def _circos_sector_angles(
    chromosomes: list[CircosChromosome],
    *,
    outer_gap: float,
) -> dict[str, tuple[float, float]]:
    total_length = sum(chromosome.length for chromosome in chromosomes)
    gap = math.radians(max(0.0, outer_gap))
    available = max(0.1, (2 * math.pi) - gap * len(chromosomes))
    current = -math.pi / 2
    sectors: dict[str, tuple[float, float]] = {}
    for chromosome in chromosomes:
        span = available * chromosome.length / total_length
        sectors[chromosome.name] = (current, current + span)
        current += span + gap
    return sectors


def _circos_angle(
    chromosome: CircosChromosome,
    sectors: dict[str, tuple[float, float]],
    position: int,
) -> float:
    start_angle, end_angle = sectors[chromosome.name]
    ratio = (position - chromosome.start) / chromosome.length
    return start_angle + _clamp(ratio, 0.0, 1.0) * (end_angle - start_angle)


def _circos_point(cx: float, cy: float, radius: float, angle: float) -> tuple[float, float]:
    return cx + math.cos(angle) * radius, cy + math.sin(angle) * radius


def _circos_arc_path(cx: float, cy: float, radius: float, start_angle: float, end_angle: float) -> str:
    start_x, start_y = _circos_point(cx, cy, radius, start_angle)
    end_x, end_y = _circos_point(cx, cy, radius, end_angle)
    large_arc = 1 if abs(end_angle - start_angle) > math.pi else 0
    return f"M {start_x:.2f} {start_y:.2f} A {radius:.2f} {radius:.2f} 0 {large_arc} 1 {end_x:.2f} {end_y:.2f}"


def _chromosome_by_name(chromosomes: list[CircosChromosome]) -> dict[str, CircosChromosome]:
    return {chromosome.name: chromosome for chromosome in chromosomes}


def _require_track_file(path_value: Any) -> Path:
    path = Path(str(path_value or ""))
    if not path.exists():
        raise FileNotFoundError(f"IGV track file not found: {path}")
    return path


def _read_igv_variants(path_value: Any, *, region: tuple[str, int, int]) -> list[IGVVariant]:
    if not str(path_value or "").strip():
        return []
    path = _require_track_file(path_value)
    chromosome, start, end = region
    variants: list[IGVVariant] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) < 8 or fields[0] != chromosome:
                continue
            try:
                position = int(fields[1])
            except ValueError:
                continue
            if position < start or position > end:
                continue
            ref = fields[3].upper()
            alt = fields[4].split(",", 1)[0].upper()
            identifier = fields[2] if fields[2] != "." else f"{fields[0]}:{position}"
            variants.append(
                IGVVariant(
                    chromosome=fields[0],
                    position=position,
                    identifier=identifier,
                    variant_type=_variant_type(ref, alt),
                )
            )
    return variants


def _read_igv_annotations(path_value: Any, *, region: tuple[str, int, int]) -> list[IGVAnnotation]:
    if not str(path_value or "").strip():
        return []
    path = _require_track_file(path_value)
    chromosome, region_start, region_end = region
    annotations: list[IGVAnnotation] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) >= 9:
                chrom = fields[0]
                feature_type = fields[2]
                start_text = fields[3]
                end_text = fields[4]
                strand = fields[6] if len(fields) > 6 else "."
                name = _gtf_attribute(fields[8], "gene_id") or _gtf_attribute(fields[8], "Name") or feature_type
            elif len(fields) >= 3:
                chrom = fields[0]
                start_text = fields[1]
                end_text = fields[2]
                strand = fields[5] if len(fields) > 5 else "."
                name = fields[3] if len(fields) > 3 else f"feature_{line_number}"
            else:
                continue
            if chrom != chromosome:
                continue
            start_value = _parse_float(start_text)
            end_value = _parse_float(end_text)
            if start_value is None or end_value is None:
                continue
            feature_start = int(start_value)
            feature_end = int(end_value)
            if feature_end < region_start or feature_start > region_end:
                continue
            annotations.append(
                IGVAnnotation(
                    chromosome=chrom,
                    start=max(feature_start, region_start),
                    end=min(feature_end, region_end),
                    name=name,
                    strand=strand,
                )
            )
    return annotations


def _gtf_attribute(attributes: str, key: str) -> str:
    for part in attributes.split(";"):
        text = part.strip()
        if not text:
            continue
        if text.startswith(key + " "):
            return text[len(key) :].strip().strip('"')
        if text.startswith(key + "="):
            return text.split("=", 1)[1].strip().strip('"')
    return ""


def _read_igv_coverage(path_value: Any, *, region: tuple[str, int, int], window: int) -> list[CoverageBin]:
    if not str(path_value or "").strip():
        return []
    path = _require_track_file(path_value)
    return _read_coverage_bins(path, region=region, window_size=max(window, 1))


def _line_dasharray(line_style: str) -> str:
    style = str(line_style or "solid").strip().lower()
    if style == "dashed":
        return ' stroke-dasharray="8 5"'
    if style == "dotted":
        return ' stroke-dasharray="2 5"'
    if style == "dashdot":
        return ' stroke-dasharray="8 4 2 4"'
    return ""


def _bar_project_y(value: float, value_min: float, value_max: float, layout: PlotLayout) -> float:
    span = value_max - value_min
    return layout.top + (1.0 - ((value - value_min) / span)) * layout.plot_height


def _bar_project_x(value: float, value_min: float, value_max: float, layout: PlotLayout) -> float:
    span = value_max - value_min
    return layout.left + ((value - value_min) / span) * layout.plot_width


def _render_svg(
    path: Path,
    *,
    points: list[VolcanoPoint],
    bounds: PlotBounds,
    layout: PlotLayout,
    logfc_threshold: float,
    title: str,
    label_top_n: int,
    colours: dict[str, str],
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    threshold_y = _project_y(bounds.threshold_y, bounds, layout)
    left_threshold_x = _project_x(-logfc_threshold, bounds, layout)
    right_threshold_x = _project_x(logfc_threshold, bounds, layout)
    zero_x = _project_x(0.0, bounds, layout)

    labels = [
        point
        for point in sorted(points, key=lambda item: item.neg_log_p, reverse=True)
        if point.regulation != "NS" and point.gene
    ][: max(label_top_n, 0)]
    labelled = {id(point) for point in labels}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
        f'<line x1="{zero_x:.2f}" y1="{y0}" x2="{zero_x:.2f}" y2="{y1}" '
        'stroke="#CBD5E1" stroke-width="1"/>',
        f'<line x1="{left_threshold_x:.2f}" y1="{y0}" x2="{left_threshold_x:.2f}" y2="{y1}" '
        'stroke="#64748B" stroke-width="1" stroke-dasharray="6 5"/>',
        f'<line x1="{right_threshold_x:.2f}" y1="{y0}" x2="{right_threshold_x:.2f}" y2="{y1}" '
        'stroke="#64748B" stroke-width="1" stroke-dasharray="6 5"/>',
        f'<line x1="{x0}" y1="{threshold_y:.2f}" x2="{x1}" y2="{threshold_y:.2f}" '
        'stroke="#64748B" stroke-width="1" stroke-dasharray="6 5"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827">log2 fold change</text>',
        f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827" '
        'transform="rotate(-90 22 '
        f'{(y0 + y1) / 2:.1f})">-log10(p-value)</text>',
        f'<text x="{x0}" y="{layout.height - 40}" text-anchor="start" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.x_min:.2g}</text>",
        f'<text x="{x1}" y="{layout.height - 40}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.x_max:.2g}</text>",
        f'<text x="{x0 - 8}" y="{y0 + 4}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.y_max:.2g}</text>",
    ]

    for point in sorted(points, key=lambda item: REGULATION_ORDER[item.regulation]):
        x = _project_x(point.logfc, bounds, layout)
        y = _project_y(point.neg_log_p, bounds, layout)
        colour = colours[point.regulation]
        gene_attr = html.escape(point.gene, quote=True)
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{colour}" '
            'fill-opacity="0.82" stroke="#ffffff" stroke-width="0.8" '
            f'data-regulation="{point.regulation}" data-gene="{gene_attr}">'
            f"<title>{html.escape(point.gene)}: logFC {point.logfc:.3g}, "
            f"p {point.pvalue:.3g}</title></circle>"
        )

        if id(point) in labelled:
            label_x = min(max(x + 7, x0 + 4), x1 - 48)
            label_y = min(max(y - 7, y0 + 12), y1 - 4)
            parts.append(
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" '
                'font-family="Arial, sans-serif" font-size="11" fill="#111827">'
                f"{html.escape(point.gene)}</text>"
            )

    legend_x = x1 - 145
    legend_y = y0 + 16
    for index, label in enumerate(("Up", "Down", "NS")):
        y = legend_y + index * 18
        parts.append(
            f'<circle cx="{legend_x}" cy="{y}" r="4.5" fill="{colours[label]}"/>'
            f'<text x="{legend_x + 10}" y="{y + 4}" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#334155">{label}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _set_pixel(
    pixels: bytearray,
    width: int,
    height: int,
    x: int,
    y: int,
    colour: tuple[int, int, int],
) -> None:
    if x < 0 or y < 0 or x >= width or y >= height:
        return
    offset = (y * width + x) * 3
    pixels[offset:offset + 3] = bytes(colour)


def _draw_line(
    pixels: bytearray,
    width: int,
    height: int,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    colour: tuple[int, int, int],
) -> None:
    dx = abs(x1 - x0)
    sx = 1 if x0 < x1 else -1
    dy = -abs(y1 - y0)
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    while True:
        _set_pixel(pixels, width, height, x0, y0, colour)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x0 += sx
        if e2 <= dx:
            err += dx
            y0 += sy


def _draw_circle(
    pixels: bytearray,
    width: int,
    height: int,
    cx: int,
    cy: int,
    radius: int,
    colour: tuple[int, int, int],
) -> None:
    radius_sq = radius * radius
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius_sq:
                _set_pixel(pixels, width, height, x, y, colour)


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def _write_png(path: Path, width: int, height: int, pixels: bytearray) -> None:
    scanlines = bytearray()
    row_width = width * 3
    for y in range(height):
        scanlines.append(0)
        start = y * row_width
        scanlines.extend(pixels[start:start + row_width])

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    data = (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", ihdr)
        + _png_chunk(b"IDAT", zlib.compress(bytes(scanlines), level=6))
        + _png_chunk(b"IEND", b"")
    )
    path.write_bytes(data)


def _render_png(
    path: Path,
    *,
    points: list[VolcanoPoint],
    bounds: PlotBounds,
    layout: PlotLayout,
    logfc_threshold: float,
    colours: dict[str, str],
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    threshold = (100, 116, 139)
    frame = (203, 213, 225)

    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)

    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    zero_x = int(round(_project_x(0.0, bounds, layout)))
    left_threshold_x = int(round(_project_x(-logfc_threshold, bounds, layout)))
    right_threshold_x = int(round(_project_x(logfc_threshold, bounds, layout)))
    threshold_y = int(round(_project_y(bounds.threshold_y, bounds, layout)))
    _draw_line(pixels, layout.width, layout.height, zero_x, y0, zero_x, y1, frame)
    _draw_line(pixels, layout.width, layout.height, left_threshold_x, y0, left_threshold_x, y1, threshold)
    _draw_line(pixels, layout.width, layout.height, right_threshold_x, y0, right_threshold_x, y1, threshold)
    _draw_line(pixels, layout.width, layout.height, x0, threshold_y, x1, threshold_y, threshold)

    rgb_colours = {label: _hex_to_rgb(colour) for label, colour in colours.items()}
    for point in sorted(points, key=lambda item: REGULATION_ORDER[item.regulation]):
        x = int(round(_project_x(point.logfc, bounds, layout)))
        y = int(round(_project_y(point.neg_log_p, bounds, layout)))
        _draw_circle(pixels, layout.width, layout.height, x, y, 4, rgb_colours[point.regulation])

    _write_png(path, layout.width, layout.height, pixels)


def _render_volcano_html(
    path: Path,
    *,
    points: list[VolcanoPoint],
    bounds: PlotBounds,
    layout: PlotLayout,
    logfc_threshold: float,
    title: str,
    label_top_n: int,
    colours: dict[str, str],
) -> None:
    traces = []
    for label in ("Up", "Down", "NS"):
        group = [point for point in points if point.regulation == label]
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": label,
            "x": [point.logfc for point in group],
            "y": [point.neg_log_p for point in group],
            "text": [
                (
                    f"{html.escape(point.gene)}<br>"
                    f"log2 fold change: {point.logfc:.6g}<br>"
                    f"p-value: {point.pvalue:.6g}"
                )
                for point in group
            ],
            "hovertemplate": "%{text}<extra></extra>",
            "marker": {
                "color": colours[label],
                "size": 9,
                "opacity": 0.82,
                "line": {"color": "#ffffff", "width": 0.8},
            },
        })

    labels = [
        point
        for point in sorted(points, key=lambda item: item.neg_log_p, reverse=True)
        if point.regulation != "NS" and point.gene
    ][: max(label_top_n, 0)]
    if labels:
        traces.append({
            "type": "scatter",
            "mode": "text",
            "name": "Labels",
            "showlegend": False,
            "x": [point.logfc for point in labels],
            "y": [point.neg_log_p for point in labels],
            "text": [point.gene for point in labels],
            "textposition": "top right",
            "hoverinfo": "skip",
            "textfont": {"color": "#111827", "size": 11},
        })

    plot_layout = {
        "title": {"text": title},
        "xaxis": {
            "title": "log2 fold change",
            "range": [bounds.x_min, bounds.x_max],
            "zeroline": True,
            "zerolinecolor": "#CBD5E1",
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "yaxis": {
            "title": "-log10(p-value)",
            "range": [0, bounds.y_max],
            "zeroline": False,
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "shapes": [
            {
                "type": "line",
                "xref": "x",
                "yref": "paper",
                "x0": -logfc_threshold,
                "x1": -logfc_threshold,
                "y0": 0,
                "y1": 1,
                "line": {"color": "#64748B", "width": 1, "dash": "dash"},
            },
            {
                "type": "line",
                "xref": "x",
                "yref": "paper",
                "x0": logfc_threshold,
                "x1": logfc_threshold,
                "y0": 0,
                "y1": 1,
                "line": {"color": "#64748B", "width": 1, "dash": "dash"},
            },
            {
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": bounds.threshold_y,
                "y1": bounds.threshold_y,
                "line": {"color": "#64748B", "width": 1, "dash": "dash"},
            },
        ],
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "hovermode": "closest",
        "showlegend": True,
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "volcano_plot"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_ma_svg(
    path: Path,
    *,
    points: list[MAPoint],
    bounds: MABounds,
    layout: PlotLayout,
    logfc_threshold: float,
    title: str,
    label_top_n: int,
    significant_color: str,
    ns_color: str,
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    zero_y = _project_ma_y(0.0, bounds, layout)
    up_threshold_y = _project_ma_y(logfc_threshold, bounds, layout)
    down_threshold_y = _project_ma_y(-logfc_threshold, bounds, layout)

    labels = [
        point
        for point in sorted(points, key=lambda item: abs(item.logfc), reverse=True)
        if point.significant and point.gene
    ][: max(label_top_n, 0)]
    labelled = {id(point) for point in labels}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
        f'<line x1="{x0}" y1="{zero_y:.2f}" x2="{x1}" y2="{zero_y:.2f}" '
        'stroke="#111827" stroke-width="1.2"/>',
        f'<line x1="{x0}" y1="{up_threshold_y:.2f}" x2="{x1}" y2="{up_threshold_y:.2f}" '
        'stroke="#64748B" stroke-width="1" stroke-dasharray="6 5"/>',
        f'<line x1="{x0}" y1="{down_threshold_y:.2f}" x2="{x1}" y2="{down_threshold_y:.2f}" '
        'stroke="#64748B" stroke-width="1" stroke-dasharray="6 5"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827">Mean expression (log10 scale)</text>',
        f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827" '
        'transform="rotate(-90 22 '
        f'{(y0 + y1) / 2:.1f})">Log2 Fold Change</text>',
        f'<text x="{x0}" y="{layout.height - 40}" text-anchor="start" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"10^{bounds.x_min:.2g}</text>",
        f'<text x="{x1}" y="{layout.height - 40}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"10^{bounds.x_max:.2g}</text>",
        f'<text x="{x0 - 8}" y="{y0 + 4}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.y_max:.2g}</text>",
    ]

    for point in sorted(points, key=lambda item: item.significant):
        x = _project_ma_x(point.log_mean, bounds, layout)
        y = _project_ma_y(point.logfc, bounds, layout)
        colour = significant_color if point.significant else ns_color
        significant_text = "true" if point.significant else "false"
        gene_attr = html.escape(point.gene, quote=True)
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="4.8" fill="{colour}" '
            'fill-opacity="0.82" stroke="#ffffff" stroke-width="0.8" '
            f'data-significant="{significant_text}" data-gene="{gene_attr}">'
            f"<title>{html.escape(point.gene)}: mean {point.mean:.3g}, "
            f"logFC {point.logfc:.3g}, p {point.pvalue:.3g}</title></circle>"
        )
        if id(point) in labelled:
            label_x = min(max(x + 7, x0 + 4), x1 - 48)
            label_y = min(max(y - 7, y0 + 12), y1 - 4)
            parts.append(
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" '
                'font-family="Arial, sans-serif" font-size="11" fill="#111827">'
                f"{html.escape(point.gene)}</text>"
            )

    legend_x = x1 - 165
    legend_y = y0 + 16
    for index, (label, colour) in enumerate(
        (("Significant", significant_color), ("Not significant", ns_color))
    ):
        y = legend_y + index * 18
        parts.append(
            f'<circle cx="{legend_x}" cy="{y}" r="4.5" fill="{colour}"/>'
            f'<text x="{legend_x + 10}" y="{y + 4}" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#334155">{label}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_ma_png(
    path: Path,
    *,
    points: list[MAPoint],
    bounds: MABounds,
    layout: PlotLayout,
    logfc_threshold: float,
    significant_color: str,
    ns_color: str,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    threshold = (100, 116, 139)
    frame = (203, 213, 225)

    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)

    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    zero_y = int(round(_project_ma_y(0.0, bounds, layout)))
    up_threshold_y = int(round(_project_ma_y(logfc_threshold, bounds, layout)))
    down_threshold_y = int(round(_project_ma_y(-logfc_threshold, bounds, layout)))
    _draw_line(pixels, layout.width, layout.height, x0, zero_y, x1, zero_y, axis)
    _draw_line(pixels, layout.width, layout.height, x0, up_threshold_y, x1, up_threshold_y, threshold)
    _draw_line(pixels, layout.width, layout.height, x0, down_threshold_y, x1, down_threshold_y, threshold)

    significant_rgb = _hex_to_rgb(significant_color)
    ns_rgb = _hex_to_rgb(ns_color)
    for point in sorted(points, key=lambda item: item.significant):
        x = int(round(_project_ma_x(point.log_mean, bounds, layout)))
        y = int(round(_project_ma_y(point.logfc, bounds, layout)))
        _draw_circle(pixels, layout.width, layout.height, x, y, 4, significant_rgb if point.significant else ns_rgb)

    _write_png(path, layout.width, layout.height, pixels)


def _render_ma_html(
    path: Path,
    *,
    points: list[MAPoint],
    bounds: MABounds,
    layout: PlotLayout,
    logfc_threshold: float,
    title: str,
    label_top_n: int,
    significant_color: str,
    ns_color: str,
) -> None:
    traces = []
    for label, significant, colour in (
        ("Significant", True, significant_color),
        ("Not significant", False, ns_color),
    ):
        group = [point for point in points if point.significant is significant]
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": label,
            "x": [point.log_mean for point in group],
            "y": [point.logfc for point in group],
            "text": [
                (
                    f"{html.escape(point.gene)}<br>"
                    f"mean expression: {point.mean:.6g}<br>"
                    f"log2 fold change: {point.logfc:.6g}<br>"
                    f"p-value: {point.pvalue:.6g}"
                )
                for point in group
            ],
            "hovertemplate": "%{text}<extra></extra>",
            "marker": {
                "color": colour,
                "size": 9,
                "opacity": 0.82,
                "line": {"color": "#ffffff", "width": 0.8},
            },
        })

    labels = [
        point
        for point in sorted(points, key=lambda item: abs(item.logfc), reverse=True)
        if point.significant and point.gene
    ][: max(label_top_n, 0)]
    if labels:
        traces.append({
            "type": "scatter",
            "mode": "text",
            "name": "Labels",
            "showlegend": False,
            "x": [point.log_mean for point in labels],
            "y": [point.logfc for point in labels],
            "text": [point.gene for point in labels],
            "textposition": "top right",
            "hoverinfo": "skip",
            "textfont": {"color": "#111827", "size": 11},
        })

    plot_layout = {
        "title": {"text": title},
        "xaxis": {
            "title": "Mean expression (log10 scale)",
            "range": [bounds.x_min, bounds.x_max],
            "zeroline": False,
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "yaxis": {
            "title": "Log2 Fold Change",
            "range": [bounds.y_min, bounds.y_max],
            "zeroline": True,
            "zerolinecolor": "#111827",
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "shapes": [
            {
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": logfc_threshold,
                "y1": logfc_threshold,
                "line": {"color": "#64748B", "width": 1, "dash": "dash"},
            },
            {
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": -logfc_threshold,
                "y1": -logfc_threshold,
                "line": {"color": "#64748B", "width": 1, "dash": "dash"},
            },
        ],
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "hovermode": "closest",
        "showlegend": True,
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "ma_plot"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_scatter_svg(
    path: Path,
    *,
    points: list[ScatterPoint],
    bounds: XYBounds,
    layout: PlotLayout,
    title: str,
    xlabel: str,
    ylabel: str,
    color_column: str,
    point_size: int,
    alpha: float,
    regression: bool,
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    color_mode, category_colours, numeric_range = _scatter_color_data(
        points,
        color_column=color_column,
    )
    size_range = _scatter_size_range(points)
    opacity = _clamp(alpha, 0.1, 1.0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
        f'font-family="Arial, sans-serif" font-size="14" fill="#111827">{html.escape(xlabel)}</text>',
        f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827" '
        'transform="rotate(-90 22 '
        f'{(y0 + y1) / 2:.1f})">{html.escape(ylabel)}</text>',
        f'<text x="{x0}" y="{layout.height - 40}" text-anchor="start" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.x_min:.2g}</text>",
        f'<text x="{x1}" y="{layout.height - 40}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.x_max:.2g}</text>",
        f'<text x="{x0 - 8}" y="{y0 + 4}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.y_max:.2g}</text>",
    ]

    if regression:
        fitted = _regression_line(points)
        if fitted is not None:
            slope, intercept = fitted
            y_start = slope * bounds.x_min + intercept
            y_end = slope * bounds.x_max + intercept
            parts.append(
                f'<line class="regression-line" x1="{_project_xy_x(bounds.x_min, bounds, layout):.2f}" '
                f'y1="{_project_xy_y(y_start, bounds, layout):.2f}" '
                f'x2="{_project_xy_x(bounds.x_max, bounds, layout):.2f}" '
                f'y2="{_project_xy_y(y_end, bounds, layout):.2f}" '
                'stroke="#DC2626" stroke-width="2" stroke-dasharray="7 5"/>'
            )

    for point in points:
        x = _project_xy_x(point.x, bounds, layout)
        y = _project_xy_y(point.y, bounds, layout)
        colour = _scatter_point_color(
            point,
            color_mode=color_mode,
            category_colours=category_colours,
            numeric_range=numeric_range,
        )
        radius = _scatter_radius(point, point_size=point_size, size_range=size_range)
        category_attr = html.escape(point.color_value or "Unlabelled", quote=True)
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{colour}" '
            f'fill-opacity="{opacity:.2f}" stroke="#ffffff" stroke-width="0.8" '
            f'data-category="{category_attr}">'
            f"<title>x {point.x:.3g}, y {point.y:.3g}"
            + (f", {html.escape(color_column)} {html.escape(point.color_value)}" if color_column else "")
            + "</title></circle>"
        )

    if color_mode == "categorical" and category_colours:
        legend_x = x1 - 165
        legend_y = y0 + 16
        for index, (label, colour) in enumerate(category_colours.items()):
            if index >= 8:
                break
            y = legend_y + index * 18
            parts.append(
                f'<circle cx="{legend_x}" cy="{y}" r="4.5" fill="{colour}"/>'
                f'<text x="{legend_x + 10}" y="{y + 4}" font-family="Arial, sans-serif" '
                f'font-size="11" fill="#334155">{html.escape(label)}</text>'
            )
    elif color_mode == "numeric" and numeric_range:
        legend_x = x1 - 150
        legend_y = y0 + 16
        parts.append(
            f'<text x="{legend_x}" y="{legend_y}" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#334155">{html.escape(color_column)}</text>'
        )
        parts.append(
            f'<text x="{legend_x}" y="{legend_y + 16}" font-family="Arial, sans-serif" '
            f'font-size="10" fill="#475569">{numeric_range[0]:.2g} to {numeric_range[1]:.2g}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_scatter_png(
    path: Path,
    *,
    points: list[ScatterPoint],
    bounds: XYBounds,
    layout: PlotLayout,
    color_column: str,
    point_size: int,
    regression: bool,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)
    regression_rgb = (220, 38, 38)

    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)

    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    if regression:
        fitted = _regression_line(points)
        if fitted is not None:
            slope, intercept = fitted
            y_start = slope * bounds.x_min + intercept
            y_end = slope * bounds.x_max + intercept
            _draw_line(
                pixels,
                layout.width,
                layout.height,
                int(round(_project_xy_x(bounds.x_min, bounds, layout))),
                int(round(_project_xy_y(y_start, bounds, layout))),
                int(round(_project_xy_x(bounds.x_max, bounds, layout))),
                int(round(_project_xy_y(y_end, bounds, layout))),
                regression_rgb,
            )

    color_mode, category_colours, numeric_range = _scatter_color_data(
        points,
        color_column=color_column,
    )
    size_range = _scatter_size_range(points)
    for point in points:
        x = int(round(_project_xy_x(point.x, bounds, layout)))
        y = int(round(_project_xy_y(point.y, bounds, layout)))
        colour = _hex_to_rgb(
            _scatter_point_color(
                point,
                color_mode=color_mode,
                category_colours=category_colours,
                numeric_range=numeric_range,
            )
        )
        radius = int(round(_scatter_radius(point, point_size=point_size, size_range=size_range)))
        _draw_circle(pixels, layout.width, layout.height, x, y, radius, colour)

    _write_png(path, layout.width, layout.height, pixels)


def _json_for_script(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True).replace("</", "<\\/")


def _scatter_hover_text(point: ScatterPoint, *, color_column: str, size_column: str) -> str:
    parts = [f"x: {point.x:.6g}", f"y: {point.y:.6g}"]
    if color_column:
        parts.append(f"{color_column}: {point.color_value or 'Unlabelled'}")
    if size_column and point.size_value is not None:
        parts.append(f"{size_column}: {point.size_value:.6g}")
    return "<br>".join(html.escape(part) for part in parts)


def _scatter_marker_payload(
    points: list[ScatterPoint],
    *,
    color_column: str,
    point_size: int,
    alpha: float,
    color_mode: str,
    category_colours: dict[str, str] | None,
    numeric_range: tuple[float, float] | None,
    size_range: tuple[float, float] | None,
) -> dict[str, Any]:
    marker: dict[str, Any] = {
        "size": [
            round(_scatter_radius(point, point_size=point_size, size_range=size_range) * 2.0, 2)
            for point in points
        ],
        "opacity": _clamp(alpha, 0.1, 1.0),
        "line": {"color": "#ffffff", "width": 0.8},
    }
    if color_mode == "numeric" and numeric_range:
        marker["color"] = [_parse_float(point.color_value) for point in points]
        marker["colorscale"] = "Viridis"
        marker["colorbar"] = {"title": color_column}
        marker["cmin"], marker["cmax"] = numeric_range
    else:
        marker["color"] = [
            _scatter_point_color(
                point,
                color_mode=color_mode,
                category_colours=category_colours,
                numeric_range=numeric_range,
            )
            for point in points
        ]
    return marker


def _scatter_html_traces(
    *,
    points: list[ScatterPoint],
    bounds: XYBounds,
    color_column: str,
    size_column: str,
    point_size: int,
    alpha: float,
    regression: bool,
) -> list[dict[str, Any]]:
    color_mode, category_colours, numeric_range = _scatter_color_data(
        points,
        color_column=color_column,
    )
    size_range = _scatter_size_range(points)
    traces: list[dict[str, Any]] = []

    if color_mode == "categorical" and category_colours:
        for category, colour in category_colours.items():
            category_points = [
                point for point in points if (point.color_value or "Unlabelled") == category
            ]
            traces.append({
                "type": "scatter",
                "mode": "markers",
                "name": category,
                "x": [point.x for point in category_points],
                "y": [point.y for point in category_points],
                "text": [
                    _scatter_hover_text(point, color_column=color_column, size_column=size_column)
                    for point in category_points
                ],
                "hovertemplate": "%{text}<extra></extra>",
                "marker": {
                    "color": colour,
                    "size": [
                        round(_scatter_radius(point, point_size=point_size, size_range=size_range) * 2.0, 2)
                        for point in category_points
                    ],
                    "opacity": _clamp(alpha, 0.1, 1.0),
                    "line": {"color": "#ffffff", "width": 0.8},
                },
            })
    else:
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": "Points",
            "x": [point.x for point in points],
            "y": [point.y for point in points],
            "text": [
                _scatter_hover_text(point, color_column=color_column, size_column=size_column)
                for point in points
            ],
            "hovertemplate": "%{text}<extra></extra>",
            "marker": _scatter_marker_payload(
                points,
                color_column=color_column,
                point_size=point_size,
                alpha=alpha,
                color_mode=color_mode,
                category_colours=category_colours,
                numeric_range=numeric_range,
                size_range=size_range,
            ),
        })

    if regression:
        fitted = _regression_line(points)
        if fitted is not None:
            slope, intercept = fitted
            traces.append({
                "type": "scatter",
                "mode": "lines",
                "name": "Regression",
                "x": [bounds.x_min, bounds.x_max],
                "y": [
                    slope * bounds.x_min + intercept,
                    slope * bounds.x_max + intercept,
                ],
                "line": {"color": "#DC2626", "width": 2, "dash": "dash"},
                "hoverinfo": "skip",
            })

    return traces


def _render_scatter_html(
    path: Path,
    *,
    points: list[ScatterPoint],
    bounds: XYBounds,
    layout: PlotLayout,
    title: str,
    xlabel: str,
    ylabel: str,
    color_column: str,
    size_column: str,
    point_size: int,
    alpha: float,
    regression: bool,
) -> None:
    traces = _scatter_html_traces(
        points=points,
        bounds=bounds,
        color_column=color_column,
        size_column=size_column,
        point_size=point_size,
        alpha=alpha,
        regression=regression,
    )
    plot_layout = {
        "title": {"text": title},
        "xaxis": {"title": xlabel, "range": [bounds.x_min, bounds.x_max], "zeroline": False},
        "yaxis": {"title": ylabel, "range": [bounds.y_min, bounds.y_max], "zeroline": False},
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "hovermode": "closest",
        "showlegend": bool(color_column),
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "scatter_plot"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_line_svg(
    path: Path,
    *,
    series: list[LineSeries],
    bounds: XYBounds,
    layout: PlotLayout,
    title: str,
    xlabel: str,
    ylabel: str,
    palette: str,
    line_style: str,
    marker: str,
    show_grid: bool,
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    dasharray = _line_dasharray(line_style)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
    ]

    if show_grid:
        for step in range(1, 5):
            x = x0 + (layout.plot_width * step / 5)
            y = y0 + (layout.plot_height * step / 5)
            parts.append(
                f'<line class="grid-line" x1="{x:.2f}" y1="{y0}" x2="{x:.2f}" y2="{y1}" '
                'stroke="#E2E8F0" stroke-width="1"/>'
            )
            parts.append(
                f'<line class="grid-line" x1="{x0}" y1="{y:.2f}" x2="{x1}" y2="{y:.2f}" '
                'stroke="#E2E8F0" stroke-width="1"/>'
            )

    parts.extend(
        [
            f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
            f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
            f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
            f'font-family="Arial, sans-serif" font-size="14" fill="#111827">{html.escape(xlabel)}</text>',
            f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="14" fill="#111827" '
            'transform="rotate(-90 22 '
            f'{(y0 + y1) / 2:.1f})">{html.escape(ylabel)}</text>',
            f'<text x="{x0}" y="{layout.height - 40}" text-anchor="start" '
            'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
            f"{bounds.x_min:.2g}</text>",
            f'<text x="{x1}" y="{layout.height - 40}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
            f"{bounds.x_max:.2g}</text>",
            f'<text x="{x0 - 8}" y="{y0 + 4}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
            f"{bounds.y_max:.2g}</text>",
        ]
    )

    marker_name = str(marker or "none").strip().lower()
    for series_index, item in enumerate(series):
        colour = _line_colour(palette, series_index)
        ordered_points = sorted(item.points, key=lambda point: point[0])
        point_text = " ".join(
            f"{_project_xy_x(x, bounds, layout):.2f},{_project_xy_y(y, bounds, layout):.2f}"
            for x, y in ordered_points
        )
        series_attr = html.escape(item.name, quote=True)
        parts.append(
            f'<polyline class="line-series" data-series="{series_attr}" points="{point_text}" '
            f'fill="none" stroke="{colour}" stroke-width="2.4" stroke-linecap="round" '
            f'stroke-linejoin="round"{dasharray}/>'
        )

        if marker_name != "none":
            for x, y in ordered_points:
                px = _project_xy_x(x, bounds, layout)
                py = _project_xy_y(y, bounds, layout)
                if marker_name == "s":
                    parts.append(
                        f'<rect class="line-marker" data-series="{series_attr}" x="{px - 3.5:.2f}" '
                        f'y="{py - 3.5:.2f}" width="7" height="7" fill="{colour}" '
                        'stroke="#ffffff" stroke-width="0.8"/>'
                    )
                elif marker_name == "^":
                    parts.append(
                        f'<polygon class="line-marker" data-series="{series_attr}" '
                        f'points="{px:.2f},{py - 4:.2f} {px - 4:.2f},{py + 4:.2f} {px + 4:.2f},{py + 4:.2f}" '
                        f'fill="{colour}" stroke="#ffffff" stroke-width="0.8"/>'
                    )
                else:
                    parts.append(
                        f'<circle class="line-marker" data-series="{series_attr}" cx="{px:.2f}" '
                        f'cy="{py:.2f}" r="4" fill="{colour}" stroke="#ffffff" stroke-width="0.8"/>'
                    )

    legend_x = x1 - 165
    legend_y = y0 + 16
    for series_index, item in enumerate(series[:8]):
        y = legend_y + series_index * 18
        colour = _line_colour(palette, series_index)
        parts.append(
            f'<line x1="{legend_x - 8}" y1="{y - 3}" x2="{legend_x + 4}" y2="{y - 3}" '
            f'stroke="{colour}" stroke-width="2.4"{dasharray}/>'
            f'<text x="{legend_x + 10}" y="{y}" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#334155">{html.escape(item.name)}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_line_png(
    path: Path,
    *,
    series: list[LineSeries],
    bounds: XYBounds,
    layout: PlotLayout,
    palette: str,
    marker: str,
    show_grid: bool,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)
    grid = (226, 232, 240)

    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)

    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    if show_grid:
        for step in range(1, 5):
            x = int(round(x0 + (layout.plot_width * step / 5)))
            y = int(round(y0 + (layout.plot_height * step / 5)))
            _draw_line(pixels, layout.width, layout.height, x, y0, x, y1, grid)
            _draw_line(pixels, layout.width, layout.height, x0, y, x1, y, grid)

    marker_name = str(marker or "none").strip().lower()
    for series_index, item in enumerate(series):
        colour = _hex_to_rgb(_line_colour(palette, series_index))
        ordered_points = sorted(item.points, key=lambda point: point[0])
        projected = [
            (
                int(round(_project_xy_x(x, bounds, layout))),
                int(round(_project_xy_y(y, bounds, layout))),
            )
            for x, y in ordered_points
        ]
        for point_index in range(1, len(projected)):
            x_start, y_start = projected[point_index - 1]
            x_end, y_end = projected[point_index]
            _draw_line(pixels, layout.width, layout.height, x_start, y_start, x_end, y_end, colour)
        if marker_name != "none":
            for x, y in projected:
                _draw_circle(pixels, layout.width, layout.height, x, y, 4, colour)

    _write_png(path, layout.width, layout.height, pixels)


def _plotly_dash(line_style: str) -> str:
    style = str(line_style or "solid").strip().lower()
    return {
        "dashed": "dash",
        "dotted": "dot",
        "dashdot": "dashdot",
    }.get(style, "solid")


def _plotly_marker_symbol(marker: str) -> str:
    marker_name = str(marker or "none").strip()
    return {
        "o": "circle",
        "s": "square",
        "^": "triangle-up",
        "D": "diamond",
        "*": "star",
    }.get(marker_name, "circle")


def _render_line_html(
    path: Path,
    *,
    series: list[LineSeries],
    bounds: XYBounds,
    layout: PlotLayout,
    title: str,
    xlabel: str,
    ylabel: str,
    palette: str,
    line_style: str,
    marker: str,
    show_grid: bool,
) -> None:
    marker_name = str(marker or "none").strip()
    mode = "lines+markers" if marker_name != "none" else "lines"
    traces = []
    for series_index, item in enumerate(series):
        ordered_points = sorted(item.points, key=lambda point: point[0])
        traces.append({
            "type": "scatter",
            "mode": mode,
            "name": item.name,
            "x": [point[0] for point in ordered_points],
            "y": [point[1] for point in ordered_points],
            "line": {
                "color": _line_colour(palette, series_index),
                "width": 2.4,
                "dash": _plotly_dash(line_style),
            },
            "marker": {
                "color": _line_colour(palette, series_index),
                "size": 8,
                "symbol": _plotly_marker_symbol(marker_name),
                "line": {"color": "#ffffff", "width": 0.8},
            },
            "hovertemplate": f"{html.escape(item.name)}<br>{html.escape(xlabel)}: %{{x}}"
            f"<br>{html.escape(ylabel)}: %{{y}}<extra></extra>",
        })

    plot_layout = {
        "title": {"text": title},
        "xaxis": {
            "title": xlabel,
            "range": [bounds.x_min, bounds.x_max],
            "zeroline": False,
            "showgrid": show_grid,
            "gridcolor": "#E2E8F0",
        },
        "yaxis": {
            "title": ylabel,
            "range": [bounds.y_min, bounds.y_max],
            "zeroline": False,
            "showgrid": show_grid,
            "gridcolor": "#E2E8F0",
        },
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "hovermode": "x unified",
        "showlegend": True,
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "line_chart"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_heatmap_svg(
    path: Path,
    *,
    matrix: HeatmapMatrix,
    layout: PlotLayout,
    title: str,
    colormap: str,
    show_rownames: bool,
    show_colnames: bool,
    vmin: float | None,
    vmax: float | None,
    cluster_rows: bool,
    cluster_cols: bool,
) -> None:
    row_order, col_order = _heatmap_order(
        matrix,
        cluster_rows=cluster_rows,
        cluster_cols=cluster_cols,
    )
    numeric = _heatmap_numeric_values(matrix)
    low = vmin if vmin is not None else min(numeric)
    high = vmax if vmax is not None else max(numeric)
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    cell_width = layout.plot_width / max(1, len(col_order))
    cell_height = layout.plot_height / max(1, len(row_order))

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
    ]

    for display_row, row_index in enumerate(row_order):
        row_label = matrix.row_labels[row_index]
        cell_y = y0 + display_row * cell_height
        if show_rownames:
            parts.append(
                f'<text x="{x0 - 8}" y="{cell_y + cell_height / 2 + 4:.2f}" '
                'text-anchor="end" font-family="Arial, sans-serif" font-size="11" '
                f'fill="#475569">{html.escape(row_label)}</text>'
            )
        for display_col, col_index in enumerate(col_order):
            col_label = matrix.column_labels[col_index]
            value = matrix.values[row_index][col_index]
            cell_x = x0 + display_col * cell_width
            colour = _heatmap_cell_colour(value, low=low, high=high, colormap=colormap)
            value_text = "" if value is None else f"{value:.6g}"
            parts.append(
                f'<rect class="heatmap-cell" x="{cell_x:.2f}" y="{cell_y:.2f}" '
                f'width="{max(cell_width, 0.5):.2f}" height="{max(cell_height, 0.5):.2f}" '
                f'fill="{colour}" stroke="#ffffff" stroke-width="0.6" '
                f'data-row="{html.escape(row_label, quote=True)}" '
                f'data-column="{html.escape(col_label, quote=True)}" '
                f'data-value="{html.escape(value_text, quote=True)}">'
                f"<title>{html.escape(row_label)} / {html.escape(col_label)}: "
                f"{html.escape(value_text or 'NA')}</title></rect>"
            )

    if show_colnames:
        for display_col, col_index in enumerate(col_order):
            col_label = matrix.column_labels[col_index]
            cell_x = x0 + display_col * cell_width
            label_x = cell_x + cell_width / 2
            label_y = min(layout.height - 24, y1 + 18)
            if cell_width < 48:
                parts.append(
                    f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="end" '
                    'font-family="Arial, sans-serif" font-size="10" fill="#475569" '
                    f'transform="rotate(-45 {label_x:.2f} {label_y:.2f})">{html.escape(col_label)}</text>'
                )
            else:
                parts.append(
                    f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="middle" '
                    'font-family="Arial, sans-serif" font-size="11" '
                    f'fill="#475569">{html.escape(col_label)}</text>'
                )

    legend_x = max(x0, x1 - 160)
    legend_y = max(24, layout.top - 34)
    legend_width = 120
    for step in range(20):
        ratio = step / 19
        colour = _heatmap_cell_colour(low + (high - low) * ratio, low=low, high=high, colormap=colormap)
        parts.append(
            f'<rect x="{legend_x + step * (legend_width / 20):.2f}" y="{legend_y}" '
            f'width="{legend_width / 20 + 0.5:.2f}" height="8" fill="{colour}"/>'
        )
    parts.append(
        f'<text x="{legend_x}" y="{legend_y + 22}" text-anchor="start" '
        f'font-family="Arial, sans-serif" font-size="10" fill="#475569">{low:.2g}</text>'
        f'<text x="{legend_x + legend_width}" y="{legend_y + 22}" text-anchor="end" '
        f'font-family="Arial, sans-serif" font-size="10" fill="#475569">{high:.2g}</text>'
    )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_heatmap_png(
    path: Path,
    *,
    matrix: HeatmapMatrix,
    layout: PlotLayout,
    colormap: str,
    vmin: float | None,
    vmax: float | None,
    cluster_rows: bool,
    cluster_cols: bool,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    frame = (203, 213, 225)
    row_order, col_order = _heatmap_order(
        matrix,
        cluster_rows=cluster_rows,
        cluster_cols=cluster_cols,
    )
    numeric = _heatmap_numeric_values(matrix)
    low = vmin if vmin is not None else min(numeric)
    high = vmax if vmax is not None else max(numeric)
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    cell_width = layout.plot_width / max(1, len(col_order))
    cell_height = layout.plot_height / max(1, len(row_order))

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)

    for display_row, row_index in enumerate(row_order):
        cell_y0 = int(round(y0 + display_row * cell_height))
        cell_y1 = int(round(y0 + (display_row + 1) * cell_height))
        for display_col, col_index in enumerate(col_order):
            cell_x0 = int(round(x0 + display_col * cell_width))
            cell_x1 = int(round(x0 + (display_col + 1) * cell_width))
            value = matrix.values[row_index][col_index]
            colour = _hex_to_rgb(_heatmap_cell_colour(value, low=low, high=high, colormap=colormap))
            for y in range(cell_y0, cell_y1 + 1):
                for x in range(cell_x0, cell_x1 + 1):
                    _set_pixel(pixels, layout.width, layout.height, x, y, colour)

    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, frame)
    _write_png(path, layout.width, layout.height, pixels)


def _plotly_heatmap_colorscale(colormap: str) -> str:
    palette = str(colormap or "RdYlBu_r").strip().lower()
    if palette in {"viridis"}:
        return "Viridis"
    if palette in {"magma"}:
        return "Magma"
    if palette in {"blues", "blue"}:
        return "Blues"
    if palette in {"redblue", "rdbu", "rdbu_r"}:
        return "RdBu"
    if palette in {"rdylbu_r"}:
        return "RdYlBu"
    return "RdYlBu"


def _render_heatmap_html(
    path: Path,
    *,
    matrix: HeatmapMatrix,
    layout: PlotLayout,
    title: str,
    colormap: str,
    show_rownames: bool,
    show_colnames: bool,
    vmin: float | None,
    vmax: float | None,
    cluster_rows: bool,
    cluster_cols: bool,
) -> None:
    row_order, col_order = _heatmap_order(
        matrix,
        cluster_rows=cluster_rows,
        cluster_cols=cluster_cols,
    )
    numeric = _heatmap_numeric_values(matrix)
    low = vmin if vmin is not None else min(numeric)
    high = vmax if vmax is not None else max(numeric)
    row_labels = [matrix.row_labels[index] for index in row_order]
    column_labels = [matrix.column_labels[index] for index in col_order]
    values = [
        [matrix.values[row_index][col_index] for col_index in col_order]
        for row_index in row_order
    ]
    hover_text = [
        [
            (
                f"{html.escape(matrix.row_labels[row_index])}<br>"
                f"{html.escape(matrix.column_labels[col_index])}: "
                f"{matrix.values[row_index][col_index]:.6g}"
            )
            if matrix.values[row_index][col_index] is not None
            else (
                f"{html.escape(matrix.row_labels[row_index])}<br>"
                f"{html.escape(matrix.column_labels[col_index])}: NA"
            )
            for col_index in col_order
        ]
        for row_index in row_order
    ]
    traces = [{
        "type": "heatmap",
        "x": column_labels,
        "y": row_labels,
        "z": values,
        "text": hover_text,
        "hovertemplate": "%{text}<extra></extra>",
        "colorscale": _plotly_heatmap_colorscale(colormap),
        "zmin": low,
        "zmax": high,
        "colorbar": {"title": "Value"},
        "xgap": 1,
        "ygap": 1,
    }]
    plot_layout = {
        "title": {"text": title},
        "xaxis": {"showticklabels": show_colnames, "side": "bottom"},
        "yaxis": {"showticklabels": show_rownames, "autorange": "reversed"},
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "heatmap"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_manhattan_svg(
    path: Path,
    *,
    points: list[ManhattanPoint],
    bounds: PlotBounds,
    layout: PlotLayout,
    significance_threshold: float,
    suggestive_threshold: float,
    title: str,
    chr_colors: str,
    sig_color: str,
    point_size: int,
    label_top_n: int,
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    plot_points, chromosome_centres, _ = _manhattan_plot_points(points)
    chromosomes = _manhattan_chromosomes(points)
    chromosome_index = {chromosome: index for index, chromosome in enumerate(chromosomes)}
    sig_y = _project_y(-math.log10(significance_threshold), bounds, layout)
    sug_y = _project_y(-math.log10(suggestive_threshold), bounds, layout)
    radius = _clamp(float(point_size), 1.0, 50.0) ** 0.5 + 1.0
    sig_colour = _normalise_hex_color(sig_color, DEFAULT_UP_COLOR)
    labels = sorted(points, key=lambda point: point.neg_log_p, reverse=True)[: max(label_top_n, 0)]
    labelled = {id(point) for point in labels}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
        f'<line class="genome-wide-threshold" x1="{x0}" y1="{sig_y:.2f}" x2="{x1}" y2="{sig_y:.2f}" '
        'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="7 5"/>',
        f'<line class="suggestive-threshold" x1="{x0}" y1="{sug_y:.2f}" x2="{x1}" y2="{sug_y:.2f}" '
        'stroke="#F59E0B" stroke-width="1" stroke-dasharray="6 5"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827">Chromosome</text>',
        f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827" '
        'transform="rotate(-90 22 '
        f'{(y0 + y1) / 2:.1f})">-log10(p-value)</text>',
        f'<text x="{x0 - 8}" y="{y0 + 4}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.y_max:.2g}</text>",
    ]

    for chromosome, centre in chromosome_centres.items():
        x = _project_x(centre, bounds, layout)
        parts.append(
            f'<text x="{x:.2f}" y="{layout.height - 40}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="11" '
            f'fill="#475569">{html.escape(chromosome)}</text>'
        )

    for point, plot_x in plot_points:
        x = _project_x(plot_x, bounds, layout)
        y = _project_y(point.neg_log_p, bounds, layout)
        is_significant = point.pvalue < significance_threshold
        colour = sig_colour if is_significant else _manhattan_colour(
            chr_colors,
            chromosome_index[point.chromosome],
        )
        significant_text = "true" if is_significant else "false"
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{colour}" '
            'fill-opacity="0.82" stroke="#ffffff" stroke-width="0.4" '
            f'data-chromosome="{html.escape(point.chromosome, quote=True)}" '
            f'data-snp="{html.escape(point.snp, quote=True)}" '
            f'data-significant="{significant_text}">'
            f"<title>{html.escape(point.snp)} chr{html.escape(point.chromosome)}:"
            f"{point.position:g} p {point.pvalue:.3g}</title></circle>"
        )
        if id(point) in labelled:
            label_x = min(max(x + 7, x0 + 4), x1 - 54)
            label_y = min(max(y - 7, y0 + 12), y1 - 4)
            parts.append(
                f'<text x="{label_x:.2f}" y="{label_y:.2f}" '
                'font-family="Arial, sans-serif" font-size="11" fill="#111827">'
                f"{html.escape(point.snp)}</text>"
            )

    legend_x = x1 - 190
    legend_y = y0 + 18
    parts.append(
        f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x + 18}" y2="{legend_y}" '
        'stroke="#DC2626" stroke-width="1.2" stroke-dasharray="7 5"/>'
        f'<text x="{legend_x + 24}" y="{legend_y + 4}" font-family="Arial, sans-serif" '
        f'font-size="10" fill="#334155">Genome-wide {significance_threshold:.0e}</text>'
    )
    parts.append(
        f'<line x1="{legend_x}" y1="{legend_y + 18}" x2="{legend_x + 18}" y2="{legend_y + 18}" '
        'stroke="#F59E0B" stroke-width="1" stroke-dasharray="6 5"/>'
        f'<text x="{legend_x + 24}" y="{legend_y + 22}" font-family="Arial, sans-serif" '
        f'font-size="10" fill="#334155">Suggestive {suggestive_threshold:.0e}</text>'
    )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_manhattan_html(
    path: Path,
    *,
    points: list[ManhattanPoint],
    bounds: PlotBounds,
    layout: PlotLayout,
    significance_threshold: float,
    suggestive_threshold: float,
    title: str,
    chr_colors: str,
    sig_color: str,
    point_size: int,
    label_top_n: int,
) -> None:
    plot_points, chromosome_centres, _ = _manhattan_plot_points(points)
    chromosomes = _manhattan_chromosomes(points)
    chromosome_index = {chromosome: index for index, chromosome in enumerate(chromosomes)}
    sig_colour = _normalise_hex_color(sig_color, DEFAULT_UP_COLOR)
    radius = _clamp(float(point_size), 1.0, 50.0) ** 0.5 + 3.0
    labels = sorted(points, key=lambda point: point.neg_log_p, reverse=True)[: max(label_top_n, 0)]
    labelled = {id(point) for point in labels}

    traces = [{
        "type": "scattergl",
        "mode": "markers",
        "name": "Associations",
        "x": [plot_x for _, plot_x in plot_points],
        "y": [point.neg_log_p for point, _ in plot_points],
        "customdata": [[point.snp, point.chromosome, point.position] for point, _ in plot_points],
        "text": [
            (
                f"{html.escape(point.snp)}<br>"
                f"chr{html.escape(point.chromosome)}:{point.position:g}<br>"
                f"p-value: {point.pvalue:.6g}"
            )
            for point, _ in plot_points
        ],
        "hovertemplate": "%{text}<extra></extra>",
        "marker": {
            "color": [
                sig_colour
                if point.pvalue < significance_threshold
                else _manhattan_colour(chr_colors, chromosome_index[point.chromosome])
                for point, _ in plot_points
            ],
            "size": radius,
            "opacity": 0.82,
            "line": {"color": "#ffffff", "width": 0.4},
        },
        "showlegend": False,
    }]

    if labels:
        label_positions = {
            id(point): plot_x
            for point, plot_x in plot_points
            if id(point) in labelled
        }
        traces.append({
            "type": "scatter",
            "mode": "text",
            "name": "Labels",
            "showlegend": False,
            "x": [label_positions[id(point)] for point in labels],
            "y": [point.neg_log_p for point in labels],
            "text": [point.snp for point in labels],
            "textposition": "top right",
            "hoverinfo": "skip",
            "textfont": {"color": "#111827", "size": 11},
        })

    significance_y = -math.log10(significance_threshold)
    suggestive_y = -math.log10(suggestive_threshold)
    plot_layout = {
        "title": {"text": title},
        "xaxis": {
            "title": "Chromosome",
            "range": [bounds.x_min, bounds.x_max],
            "tickmode": "array",
            "tickvals": [chromosome_centres[chromosome] for chromosome in chromosomes],
            "ticktext": chromosomes,
            "showgrid": False,
            "zeroline": False,
        },
        "yaxis": {
            "title": "-log10(p-value)",
            "range": [0, bounds.y_max],
            "zeroline": False,
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "shapes": [
            {
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": significance_y,
                "y1": significance_y,
                "line": {"color": "#DC2626", "width": 1.2, "dash": "dash"},
            },
            {
                "type": "line",
                "xref": "paper",
                "yref": "y",
                "x0": 0,
                "x1": 1,
                "y0": suggestive_y,
                "y1": suggestive_y,
                "line": {"color": "#F59E0B", "width": 1, "dash": "dash"},
            },
        ],
        "annotations": [
            {
                "text": "Genome-wide",
                "xref": "paper",
                "yref": "y",
                "x": 1,
                "y": significance_y,
                "xanchor": "right",
                "yanchor": "bottom",
                "showarrow": False,
                "font": {"color": "#991B1B", "size": 11},
            },
            {
                "text": "Suggestive",
                "xref": "paper",
                "yref": "y",
                "x": 1,
                "y": suggestive_y,
                "xanchor": "right",
                "yanchor": "bottom",
                "showarrow": False,
                "font": {"color": "#92400E", "size": 11},
            },
        ],
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "hovermode": "closest",
        "showlegend": False,
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "manhattan_plot"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_coverage_svg(
    path: Path,
    *,
    bins: list[CoverageBin],
    bounds: PlotBounds,
    layout: PlotLayout,
    title: str,
    fill_color: str,
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    chromosome = bins[0].chromosome
    colour = _normalise_hex_color(fill_color, "#2563EB")

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827">'
        f"{html.escape(chromosome)} position</text>",
        f'<text x="22" y="{(y0 + y1) / 2:.1f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827" '
        f'transform="rotate(-90 22 {(y0 + y1) / 2:.1f})">Coverage</text>',
        f'<text x="{x0 - 8}" y="{y0 + 4}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds.y_max:.2g}</text>",
    ]

    for item in bins:
        x_start = _project_x(float(item.start), bounds, layout)
        x_end = _project_x(float(item.end), bounds, layout)
        y = _project_y(item.coverage, bounds, layout)
        rect_width = max(1.0, x_end - x_start)
        rect_height = max(0.5, y1 - y)
        parts.append(
            f'<rect class="coverage-segment" x="{x_start:.2f}" y="{y:.2f}" '
            f'width="{rect_width:.2f}" height="{rect_height:.2f}" fill="{colour}" '
            'fill-opacity="0.78" '
            f'data-chromosome="{html.escape(item.chromosome, quote=True)}" '
            f'data-start="{item.start}" data-end="{item.end}" '
            f'data-coverage="{item.coverage:.6g}">'
            f"<title>{html.escape(item.chromosome)}:{item.start}-{item.end} "
            f"coverage {item.coverage:.3g}</title></rect>"
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_coverage_png(
    path: Path,
    *,
    bins: list[CoverageBin],
    bounds: PlotBounds,
    layout: PlotLayout,
    fill_color: str,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)
    colour = _hex_to_rgb(_normalise_hex_color(fill_color, "#2563EB"))
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)
    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    for item in bins:
        x_start = int(round(_project_x(float(item.start), bounds, layout)))
        x_end = int(round(_project_x(float(item.end), bounds, layout)))
        y_value = int(round(_project_y(item.coverage, bounds, layout)))
        for y in range(max(y0, y_value), y1 + 1):
            for x in range(max(x0, x_start), min(x1, max(x_start, x_end)) + 1):
                _set_pixel(pixels, layout.width, layout.height, x, y, colour)

    _write_png(path, layout.width, layout.height, pixels)


def _render_coverage_html(
    path: Path,
    *,
    bins: list[CoverageBin],
    bounds: PlotBounds,
    layout: PlotLayout,
    title: str,
    fill_color: str,
) -> None:
    colour = _normalise_hex_color(fill_color, "#2563EB")
    chromosome = bins[0].chromosome
    traces = [{
        "type": "bar",
        "name": "Coverage",
        "x": [(item.start + item.end) / 2 for item in bins],
        "y": [item.coverage for item in bins],
        "width": [max(1, item.end - item.start) for item in bins],
        "text": [f"{item.chromosome}:{item.start}-{item.end}" for item in bins],
        "customdata": [
            [item.chromosome, item.start, item.end, item.coverage]
            for item in bins
        ],
        "hovertemplate": (
            "%{customdata[0]}:%{customdata[1]}-%{customdata[2]}<br>"
            "coverage: %{customdata[3]}<extra></extra>"
        ),
        "marker": {
            "color": colour,
            "opacity": 0.78,
            "line": {"color": "#ffffff", "width": 0.4},
        },
    }]
    plot_layout = {
        "title": {"text": title},
        "xaxis": {
            "title": f"{chromosome} position",
            "range": [bounds.x_min, bounds.x_max],
            "showgrid": True,
            "gridcolor": "#E2E8F0",
            "zeroline": False,
        },
        "yaxis": {
            "title": "Coverage",
            "range": [0, bounds.y_max],
            "zeroline": False,
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "bargap": 0,
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "showlegend": False,
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "coverage_plot"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _render_tree_svg(
    path: Path,
    *,
    root: TreeNode,
    tree_layout: str,
    show_bootstrap: bool,
    bootstrap_threshold: float,
    branch_width: float,
    tip_label_size: int,
    color_branches: bool,
    title: str,
    layout: PlotLayout,
) -> None:
    positions, _ = (
        _polar_tree_positions(root, layout=layout)
        if tree_layout in {"circular", "radial"}
        else _assign_tree_coordinates(root, layout=layout)
    )
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
    ]

    for parent, child in _tree_edges(root):
        parent_x, parent_y = positions[id(parent)]
        child_x, child_y = positions[id(child)]
        support = _bootstrap_value(child.name)
        colour = "#111827"
        if color_branches and support is not None:
            colour = "#16A34A" if support >= bootstrap_threshold else "#DC2626"
        if tree_layout == "rectangular":
            parts.append(
                f'<path class="tree-branch" d="M {parent_x:.2f} {parent_y:.2f} '
                f'L {parent_x:.2f} {child_y:.2f} L {child_x:.2f} {child_y:.2f}" '
                f'fill="none" stroke="{colour}" stroke-width="{max(branch_width, 0.5):.2f}"/>'
            )
        else:
            parts.append(
                f'<line class="tree-branch" x1="{parent_x:.2f}" y1="{parent_y:.2f}" '
                f'x2="{child_x:.2f}" y2="{child_y:.2f}" stroke="{colour}" '
                f'stroke-width="{max(branch_width, 0.5):.2f}"/>'
            )

    for node in _tree_internal_nodes(root):
        support = _bootstrap_value(node.name)
        if not show_bootstrap or support is None or support < bootstrap_threshold:
            continue
        x, y = positions[id(node)]
        parts.append(
            f'<text class="tree-bootstrap" x="{x + 5:.2f}" y="{y - 5:.2f}" '
            'font-family="Arial, sans-serif" font-size="10" fill="#475569" '
            f'data-bootstrap="{support:g}">{support:g}</text>'
        )

    for leaf in _tree_leaves(root):
        x, y = positions[id(leaf)]
        if tree_layout == "rectangular":
            label_x = min(x + 8, x1 - 4)
            anchor = "start"
        else:
            centre_x = layout.left + layout.plot_width / 2
            label_x = x + (8 if x >= centre_x else -8)
            anchor = "start" if x >= centre_x else "end"
        parts.append(
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.6" fill="#2563EB"/>'
            f'<text class="tree-tip" x="{label_x:.2f}" y="{y + 4:.2f}" '
            f'text-anchor="{anchor}" font-family="Arial, sans-serif" '
            f'font-size="{max(tip_label_size, 4)}" fill="#111827" '
            f'data-tip="{html.escape(leaf.name, quote=True)}">{html.escape(leaf.name)}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_tree_png(
    path: Path,
    *,
    root: TreeNode,
    tree_layout: str,
    branch_width: float,
    color_branches: bool,
    bootstrap_threshold: float,
    layout: PlotLayout,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)
    positions, _ = (
        _polar_tree_positions(root, layout=layout)
        if tree_layout in {"circular", "radial"}
        else _assign_tree_coordinates(root, layout=layout)
    )
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)
    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    line_width = max(1, int(round(branch_width)))
    for parent, child in _tree_edges(root):
        parent_x, parent_y = positions[id(parent)]
        child_x, child_y = positions[id(child)]
        support = _bootstrap_value(child.name)
        colour = (17, 24, 39)
        if color_branches and support is not None:
            colour = (22, 163, 74) if support >= bootstrap_threshold else (220, 38, 38)
        if tree_layout == "rectangular":
            segments = [
                (parent_x, parent_y, parent_x, child_y),
                (parent_x, child_y, child_x, child_y),
            ]
        else:
            segments = [(parent_x, parent_y, child_x, child_y)]
        for x_a, y_a, x_b, y_b in segments:
            for offset in range(-(line_width // 2), line_width // 2 + 1):
                _draw_line(
                    pixels,
                    layout.width,
                    layout.height,
                    int(round(x_a)),
                    int(round(y_a + offset)),
                    int(round(x_b)),
                    int(round(y_b + offset)),
                    colour,
                )

    for leaf in _tree_leaves(root):
        x, y = positions[id(leaf)]
        _draw_circle(pixels, layout.width, layout.height, int(round(x)), int(round(y)), 3, (37, 99, 235))

    _write_png(path, layout.width, layout.height, pixels)


def _panel_grid(layout: PlotLayout) -> list[tuple[float, float, float, float]]:
    gap_x = max(24.0, layout.plot_width * 0.04)
    gap_y = max(34.0, layout.plot_height * 0.08)
    panel_width = (layout.plot_width - gap_x) / 2
    panel_height = (layout.plot_height - gap_y) / 2
    return [
        (layout.left, layout.top, panel_width, panel_height),
        (layout.left + panel_width + gap_x, layout.top, panel_width, panel_height),
        (layout.left, layout.top + panel_height + gap_y, panel_width, panel_height),
        (layout.left + panel_width + gap_x, layout.top + panel_height + gap_y, panel_width, panel_height),
    ]


def _render_vcf_stats_svg(
    path: Path,
    *,
    stats: VCFStats,
    title: str,
    quality_bins: int,
    min_quality: float,
    max_quality: float | None,
    layout: PlotLayout,
) -> None:
    panels = _panel_grid(layout)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
    ]

    _append_vcf_bar_panel_svg(
        parts,
        panels[0],
        title="Variant Types",
        items=[(key, value) for key, value in stats.variant_types.items() if value > 0],
        bar_class="variant-type-bar",
        data_name="type",
        colour="#2563EB",
    )
    histogram = _histogram(
        stats.qualities,
        quality_bins,
        min_quality if min_quality > 0 else None,
        max_quality,
    )
    _append_vcf_histogram_panel_svg(parts, panels[1], histogram, title="Quality Distribution")
    _append_vcf_bar_panel_svg(
        parts,
        panels[2],
        title=f"Ti/Tv Ratio: {stats.titv_ratio:g}" if stats.titv_ratio is not None else "Ti/Tv Ratio: N/A",
        items=[("Transitions", stats.transitions), ("Transversions", stats.transversions)],
        bar_class="titv-bar",
        data_name="kind",
        colour="#16A34A",
    )
    _append_vcf_bar_panel_svg(
        parts,
        panels[3],
        title="Variants per Chromosome",
        items=sorted(stats.chromosome_counts.items(), key=lambda item: _chromosome_sort_key(item[0].removeprefix("chr").removeprefix("CHR"))),
        bar_class="chromosome-count-bar",
        data_name="chromosome",
        colour="#9333EA",
    )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _append_vcf_bar_panel_svg(
    parts: list[str],
    panel: tuple[float, float, float, float],
    *,
    title: str,
    items: list[tuple[str, int]],
    bar_class: str,
    data_name: str,
    colour: str,
) -> None:
    x, y, width, height = panel
    parts.append(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{x + width / 2:.2f}" y="{y + 20:.2f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="13" font-weight="700" '
        f'fill="#111827">{html.escape(title)}</text>'
    )
    if not items:
        parts.append(
            f'<text x="{x + width / 2:.2f}" y="{y + height / 2:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="12" fill="#64748B">No data</text>'
        )
        return
    max_value = max([value for _, value in items] + [1])
    chart_x = x + 34
    chart_y = y + 36
    chart_width = width - 48
    chart_height = height - 66
    bar_band = chart_width / max(1, len(items))
    for index, (label, value) in enumerate(items):
        bar_height = 0 if max_value == 0 else (value / max_value) * chart_height
        bar_width = max(3.0, bar_band * 0.62)
        bar_x = chart_x + index * bar_band + (bar_band - bar_width) / 2
        bar_y = chart_y + chart_height - bar_height
        parts.append(
            f'<rect class="{bar_class}" x="{bar_x:.2f}" y="{bar_y:.2f}" '
            f'width="{bar_width:.2f}" height="{bar_height:.2f}" fill="{colour}" '
            f'data-{data_name}="{html.escape(label, quote=True)}" data-count="{value}">'
            f"<title>{html.escape(label)}: {value}</title></rect>"
        )
        parts.append(
            f'<text x="{bar_x + bar_width / 2:.2f}" y="{chart_y + chart_height + 14:.2f}" '
            'text-anchor="middle" font-family="Arial, sans-serif" font-size="10" '
            f'fill="#475569">{html.escape(label)}</text>'
        )


def _append_vcf_histogram_panel_svg(
    parts: list[str],
    panel: tuple[float, float, float, float],
    histogram: list[tuple[float, float, int]],
    *,
    title: str,
) -> None:
    x, y, width, height = panel
    parts.append(
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>'
    )
    parts.append(
        f'<text x="{x + width / 2:.2f}" y="{y + 20:.2f}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="13" font-weight="700" '
        f'fill="#111827">{html.escape(title)}</text>'
    )
    if not histogram:
        parts.append(
            f'<text x="{x + width / 2:.2f}" y="{y + height / 2:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="12" fill="#64748B">No quality scores</text>'
        )
        return
    max_count = max([count for _, _, count in histogram] + [1])
    chart_x = x + 34
    chart_y = y + 36
    chart_width = width - 48
    chart_height = height - 66
    bar_width = chart_width / max(1, len(histogram))
    for index, (start, end, count) in enumerate(histogram):
        bar_height = 0 if max_count == 0 else (count / max_count) * chart_height
        bar_x = chart_x + index * bar_width
        bar_y = chart_y + chart_height - bar_height
        parts.append(
            f'<rect class="quality-bin" x="{bar_x:.2f}" y="{bar_y:.2f}" '
            f'width="{max(1.0, bar_width - 1):.2f}" height="{bar_height:.2f}" fill="#0891B2" '
            f'data-start="{start:.6g}" data-end="{end:.6g}" data-count="{count}">'
            f"<title>QUAL {start:.3g}-{end:.3g}: {count}</title></rect>"
        )


def _render_vcf_stats_png(
    path: Path,
    *,
    stats: VCFStats,
    quality_bins: int,
    min_quality: float,
    max_quality: float | None,
    layout: PlotLayout,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    panels = _panel_grid(layout)
    _draw_panel_bars_png(
        pixels,
        layout,
        panels[0],
        [(key, value) for key, value in stats.variant_types.items() if value > 0],
        (37, 99, 235),
    )
    _draw_panel_histogram_png(
        pixels,
        layout,
        panels[1],
        _histogram(stats.qualities, quality_bins, min_quality if min_quality > 0 else None, max_quality),
        (8, 145, 178),
    )
    _draw_panel_bars_png(
        pixels,
        layout,
        panels[2],
        [("Transitions", stats.transitions), ("Transversions", stats.transversions)],
        (22, 163, 74),
    )
    _draw_panel_bars_png(
        pixels,
        layout,
        panels[3],
        sorted(stats.chromosome_counts.items(), key=lambda item: _chromosome_sort_key(item[0].removeprefix("chr").removeprefix("CHR"))),
        (147, 51, 234),
    )
    _write_png(path, layout.width, layout.height, pixels)


def _render_vcf_stats_html(
    path: Path,
    *,
    stats: VCFStats,
    title: str,
    quality_bins: int,
    min_quality: float,
    max_quality: float | None,
    layout: PlotLayout,
) -> None:
    variant_items = [(key, value) for key, value in stats.variant_types.items() if value > 0]
    quality_histogram = _histogram(
        stats.qualities,
        quality_bins,
        min_quality if min_quality > 0 else None,
        max_quality,
    )
    chromosome_items = sorted(
        stats.chromosome_counts.items(),
        key=lambda item: _chromosome_sort_key(item[0].removeprefix("chr").removeprefix("CHR")),
    )
    traces = [
        {
            "type": "bar",
            "name": "Variant Types",
            "x": [label for label, _ in variant_items],
            "y": [value for _, value in variant_items],
            "marker": {"color": "#2563EB"},
            "hovertemplate": "%{x}: %{y}<extra></extra>",
            "xaxis": "x",
            "yaxis": "y",
        },
        {
            "type": "bar",
            "name": "Quality Distribution",
            "x": [(start + end) / 2 for start, end, _ in quality_histogram],
            "y": [count for _, _, count in quality_histogram],
            "width": [max(0.1, end - start) for start, end, _ in quality_histogram],
            "customdata": [[start, end, count] for start, end, count in quality_histogram],
            "marker": {"color": "#0891B2"},
            "hovertemplate": "QUAL %{customdata[0]:.3g}-%{customdata[1]:.3g}: %{customdata[2]}<extra></extra>",
            "xaxis": "x2",
            "yaxis": "y2",
        },
        {
            "type": "bar",
            "name": "Ti/Tv Ratio",
            "x": ["Transitions", "Transversions"],
            "y": [stats.transitions, stats.transversions],
            "marker": {"color": "#16A34A"},
            "hovertemplate": "%{x}: %{y}<extra></extra>",
            "xaxis": "x3",
            "yaxis": "y3",
        },
        {
            "type": "bar",
            "name": "Variants per Chromosome",
            "x": [label for label, _ in chromosome_items],
            "y": [value for _, value in chromosome_items],
            "marker": {"color": "#9333EA"},
            "hovertemplate": "%{x}: %{y}<extra></extra>",
            "xaxis": "x4",
            "yaxis": "y4",
        },
    ]
    titv_title = (
        f"Ti/Tv Ratio: {stats.titv_ratio:g}"
        if stats.titv_ratio is not None
        else "Ti/Tv Ratio: N/A"
    )
    plot_layout = {
        "title": {"text": title},
        "grid": {"rows": 2, "columns": 2, "pattern": "independent"},
        "xaxis": {"title": "Variant type", "domain": [0, 0.47]},
        "yaxis": {"title": "Count", "domain": [0.56, 1]},
        "xaxis2": {"title": "QUAL", "domain": [0.53, 1]},
        "yaxis2": {"title": "Count", "domain": [0.56, 1]},
        "xaxis3": {"title": "Kind", "domain": [0, 0.47]},
        "yaxis3": {"title": "Count", "domain": [0, 0.44]},
        "xaxis4": {"title": "Chromosome", "domain": [0.53, 1]},
        "yaxis4": {"title": "Count", "domain": [0, 0.44]},
        "annotations": [
            {"text": "Variant Types", "xref": "paper", "yref": "paper", "x": 0.235, "y": 1.06, "showarrow": False, "font": {"size": 13}},
            {"text": "Quality Distribution", "xref": "paper", "yref": "paper", "x": 0.765, "y": 1.06, "showarrow": False, "font": {"size": 13}},
            {"text": titv_title, "xref": "paper", "yref": "paper", "x": 0.235, "y": 0.48, "showarrow": False, "font": {"size": 13}},
            {"text": "Variants per Chromosome", "xref": "paper", "yref": "paper", "x": 0.765, "y": 0.48, "showarrow": False, "font": {"size": 13}},
        ],
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "showlegend": False,
        "bargap": 0.12,
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "vcf_stats"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _draw_panel_frame(pixels: bytearray, layout: PlotLayout, panel: tuple[float, float, float, float]) -> tuple[int, int, int, int]:
    x, y, width, height = panel
    x0 = int(round(x))
    y0 = int(round(y))
    x1 = int(round(x + width))
    y1 = int(round(y + height))
    background = (248, 250, 252)
    frame = (203, 213, 225)
    for py in range(y0, y1 + 1):
        for px in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, px, py, background)
    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, frame)
    return x0, y0, x1, y1


def _draw_panel_bars_png(
    pixels: bytearray,
    layout: PlotLayout,
    panel: tuple[float, float, float, float],
    items: list[tuple[str, int]],
    colour: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = _draw_panel_frame(pixels, layout, panel)
    if not items:
        return
    chart_x0 = x0 + 34
    chart_y0 = y0 + 36
    chart_x1 = x1 - 14
    chart_y1 = y1 - 30
    max_value = max([value for _, value in items] + [1])
    band = (chart_x1 - chart_x0) / max(1, len(items))
    for index, (_, value) in enumerate(items):
        bar_height = 0 if max_value == 0 else int(round((value / max_value) * (chart_y1 - chart_y0)))
        bar_width = max(2, int(round(band * 0.62)))
        rect_x0 = int(round(chart_x0 + index * band + (band - bar_width) / 2))
        rect_x1 = rect_x0 + bar_width
        rect_y0 = chart_y1 - bar_height
        for py in range(rect_y0, chart_y1 + 1):
            for px in range(rect_x0, rect_x1 + 1):
                _set_pixel(pixels, layout.width, layout.height, px, py, colour)


def _draw_panel_histogram_png(
    pixels: bytearray,
    layout: PlotLayout,
    panel: tuple[float, float, float, float],
    histogram: list[tuple[float, float, int]],
    colour: tuple[int, int, int],
) -> None:
    x0, y0, x1, y1 = _draw_panel_frame(pixels, layout, panel)
    if not histogram:
        return
    chart_x0 = x0 + 34
    chart_y0 = y0 + 36
    chart_x1 = x1 - 14
    chart_y1 = y1 - 30
    max_count = max([count for _, _, count in histogram] + [1])
    band = (chart_x1 - chart_x0) / max(1, len(histogram))
    for index, (_, _, count) in enumerate(histogram):
        bar_height = 0 if max_count == 0 else int(round((count / max_count) * (chart_y1 - chart_y0)))
        rect_x0 = int(round(chart_x0 + index * band))
        rect_x1 = int(round(chart_x0 + (index + 1) * band - 1))
        rect_y0 = chart_y1 - bar_height
        for py in range(rect_y0, chart_y1 + 1):
            for px in range(rect_x0, rect_x1 + 1):
                _set_pixel(pixels, layout.width, layout.height, px, py, colour)


def _render_circos_svg(
    path: Path,
    *,
    chromosomes: list[CircosChromosome],
    genes: list[CircosInterval],
    variants: list[CircosVariant],
    cnvs: list[CircosInterval],
    title: str,
    outer_gap: float,
    layout: PlotLayout,
) -> None:
    cx = layout.width / 2
    cy = layout.height / 2 + 12
    outer_radius = min(layout.plot_width, layout.plot_height) * 0.44
    gene_radius = outer_radius - 32
    variant_radius = outer_radius - 58
    cnv_radius = outer_radius - 84
    sectors = _circos_sector_angles(chromosomes, outer_gap=outer_gap)
    chromosome_map = _chromosome_by_name(chromosomes)
    colours = ["#2563EB", "#16A34A", "#9333EA", "#EA580C", "#0891B2", "#BE123C"]

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
    ]

    for index, chromosome in enumerate(chromosomes):
        start_angle, end_angle = sectors[chromosome.name]
        colour = colours[index % len(colours)]
        parts.append(
            f'<path class="circos-chromosome" d="{_circos_arc_path(cx, cy, outer_radius, start_angle, end_angle)}" '
            f'fill="none" stroke="{colour}" stroke-width="18" stroke-linecap="round" '
            f'data-chromosome="{html.escape(chromosome.name, quote=True)}" '
            f'data-start="{chromosome.start}" data-end="{chromosome.end}">'
            f"<title>{html.escape(chromosome.name)} {chromosome.start}-{chromosome.end}</title></path>"
        )
        label_angle = (start_angle + end_angle) / 2
        label_x, label_y = _circos_point(cx, cy, outer_radius + 28, label_angle)
        parts.append(
            f'<text x="{label_x:.2f}" y="{label_y:.2f}" text-anchor="middle" '
            'font-family="Arial, sans-serif" font-size="11" fill="#334155">'
            f"{html.escape(chromosome.name)}</text>"
        )

    for gene in genes:
        chromosome = chromosome_map.get(gene.chromosome)
        if chromosome is None:
            continue
        start_angle = _circos_angle(chromosome, sectors, gene.start)
        end_angle = _circos_angle(chromosome, sectors, gene.end)
        parts.append(
            f'<path class="circos-gene" d="{_circos_arc_path(cx, cy, gene_radius, start_angle, end_angle)}" '
            'fill="none" stroke="#16A34A" stroke-width="10" stroke-linecap="round" '
            f'data-chromosome="{html.escape(gene.chromosome, quote=True)}" '
            f'data-gene="{html.escape(gene.label, quote=True)}">'
            f"<title>{html.escape(gene.label)} {gene.chromosome}:{gene.start}-{gene.end}</title></path>"
        )

    for variant in variants:
        chromosome = chromosome_map.get(variant.chromosome)
        if chromosome is None:
            continue
        angle = _circos_angle(chromosome, sectors, variant.position)
        x1, y1 = _circos_point(cx, cy, variant_radius - 8, angle)
        x2, y2 = _circos_point(cx, cy, variant_radius + 10, angle)
        parts.append(
            f'<line class="circos-variant" x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" '
            'stroke="#DC2626" stroke-width="2.2" stroke-linecap="round" '
            f'data-chromosome="{html.escape(variant.chromosome, quote=True)}" '
            f'data-position="{variant.position}" data-id="{html.escape(variant.identifier, quote=True)}">'
            f"<title>{html.escape(variant.identifier)} {variant.chromosome}:{variant.position}</title></line>"
        )

    for interval in cnvs:
        chromosome = chromosome_map.get(interval.chromosome)
        if chromosome is None:
            continue
        start_angle = _circos_angle(chromosome, sectors, interval.start)
        end_angle = _circos_angle(chromosome, sectors, interval.end)
        colour = "#DC2626" if (interval.value or 0.0) >= 0 else "#2563EB"
        parts.append(
            f'<path class="circos-cnv" d="{_circos_arc_path(cx, cy, cnv_radius, start_angle, end_angle)}" '
            f'fill="none" stroke="{colour}" stroke-width="9" stroke-linecap="round" '
            f'data-chromosome="{html.escape(interval.chromosome, quote=True)}" '
            f'data-value="{0.0 if interval.value is None else interval.value:.6g}">'
            f"<title>{html.escape(interval.chromosome)}:{interval.start}-{interval.end} "
            f"CNV {0.0 if interval.value is None else interval.value:.3g}</title></path>"
        )

    legend_x = layout.left
    legend_y = layout.height - layout.bottom + 24
    for index, (label, colour) in enumerate(
        [("Genes", "#16A34A"), ("Variants", "#DC2626"), ("CNV gain/loss", "#9333EA")]
    ):
        x = legend_x + index * 120
        parts.append(
            f'<line x1="{x}" y1="{legend_y}" x2="{x + 20}" y2="{legend_y}" '
            f'stroke="{colour}" stroke-width="5" stroke-linecap="round"/>'
            f'<text x="{x + 28}" y="{legend_y + 4}" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#334155">{html.escape(label)}</text>'
        )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_circos_png(
    path: Path,
    *,
    chromosomes: list[CircosChromosome],
    genes: list[CircosInterval],
    variants: list[CircosVariant],
    cnvs: list[CircosInterval],
    outer_gap: float,
    layout: PlotLayout,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    cx = layout.width / 2
    cy = layout.height / 2 + 12
    outer_radius = min(layout.plot_width, layout.plot_height) * 0.44
    gene_radius = outer_radius - 32
    variant_radius = outer_radius - 58
    cnv_radius = outer_radius - 84
    sectors = _circos_sector_angles(chromosomes, outer_gap=outer_gap)
    chromosome_map = _chromosome_by_name(chromosomes)
    colours = [(37, 99, 235), (22, 163, 74), (147, 51, 234), (234, 88, 12), (8, 145, 178), (190, 18, 60)]

    for index, chromosome in enumerate(chromosomes):
        start_angle, end_angle = sectors[chromosome.name]
        _draw_arc_pixels(
            pixels,
            layout,
            cx,
            cy,
            outer_radius,
            start_angle,
            end_angle,
            9,
            colours[index % len(colours)],
        )

    for gene in genes:
        chromosome = chromosome_map.get(gene.chromosome)
        if chromosome is None:
            continue
        _draw_arc_pixels(
            pixels,
            layout,
            cx,
            cy,
            gene_radius,
            _circos_angle(chromosome, sectors, gene.start),
            _circos_angle(chromosome, sectors, gene.end),
            6,
            (22, 163, 74),
        )

    for variant in variants:
        chromosome = chromosome_map.get(variant.chromosome)
        if chromosome is None:
            continue
        angle = _circos_angle(chromosome, sectors, variant.position)
        x1, y1 = _circos_point(cx, cy, variant_radius - 8, angle)
        x2, y2 = _circos_point(cx, cy, variant_radius + 10, angle)
        _draw_line(pixels, layout.width, layout.height, int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)), (220, 38, 38))

    for interval in cnvs:
        chromosome = chromosome_map.get(interval.chromosome)
        if chromosome is None:
            continue
        colour = (220, 38, 38) if (interval.value or 0.0) >= 0 else (37, 99, 235)
        _draw_arc_pixels(
            pixels,
            layout,
            cx,
            cy,
            cnv_radius,
            _circos_angle(chromosome, sectors, interval.start),
            _circos_angle(chromosome, sectors, interval.end),
            5,
            colour,
        )

    _write_png(path, layout.width, layout.height, pixels)


def _draw_arc_pixels(
    pixels: bytearray,
    layout: PlotLayout,
    cx: float,
    cy: float,
    radius: float,
    start_angle: float,
    end_angle: float,
    thickness: int,
    colour: tuple[int, int, int],
) -> None:
    steps = max(12, int(abs(end_angle - start_angle) * radius / 2))
    for step in range(steps + 1):
        angle = start_angle + (end_angle - start_angle) * step / steps
        x, y = _circos_point(cx, cy, radius, angle)
        _draw_circle(pixels, layout.width, layout.height, int(round(x)), int(round(y)), thickness, colour)


def _igv_project_x(position: int, region: tuple[str, int, int], layout: PlotLayout) -> float:
    _, start, end = region
    return layout.left + ((position - start) / max(1, end - start)) * layout.plot_width


def _igv_track_layout(layout: PlotLayout, track_count: int) -> list[tuple[float, float, float, float]]:
    gap = 18.0
    available = layout.plot_height - gap * max(0, track_count - 1)
    track_height = max(28.0, available / max(1, track_count))
    return [
        (float(layout.left), layout.top + index * (track_height + gap), float(layout.plot_width), track_height)
        for index in range(track_count)
    ]


def _render_igv_svg(
    path: Path,
    *,
    region: tuple[str, int, int],
    coverage: list[CoverageBin],
    variants: list[IGVVariant],
    annotations: list[IGVAnnotation],
    title: str,
    layout: PlotLayout,
) -> None:
    tracks: list[tuple[str, str]] = []
    if coverage:
        tracks.append(("coverage", "Coverage"))
    if variants:
        tracks.append(("variants", "Variants"))
    if annotations:
        tracks.append(("annotations", "Annotations"))
    track_boxes = _igv_track_layout(layout, len(tracks))
    chromosome, start, end = region
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<text x="{layout.width / 2:.1f}" y="{layout.top - 8}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="12" fill="#475569">'
        f"{html.escape(chromosome)}:{start}-{end}</text>",
    ]

    for (track_key, track_label), (x, y, width, height) in zip(tracks, track_boxes):
        parts.append(
            f'<rect class="igv-track" x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1" '
            f'data-track="{track_key}"/>'
        )
        parts.append(
            f'<text x="{x - 8:.2f}" y="{y + height / 2 + 4:.2f}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="11" fill="#334155">'
            f"{html.escape(track_label)}</text>"
        )
        if track_key == "coverage":
            _append_igv_coverage_svg(parts, coverage, region, layout, y, height)
        elif track_key == "variants":
            _append_igv_variants_svg(parts, variants, region, layout, y, height)
        elif track_key == "annotations":
            _append_igv_annotations_svg(parts, annotations, region, layout, y, height)

    axis_y = layout.height - layout.bottom + 18
    parts.append(
        f'<line x1="{layout.left}" y1="{axis_y}" x2="{layout.width - layout.right}" y2="{axis_y}" '
        'stroke="#111827" stroke-width="1"/>'
        f'<text x="{layout.left}" y="{axis_y + 16}" text-anchor="start" font-family="Arial, sans-serif" '
        f'font-size="10" fill="#475569">{start}</text>'
        f'<text x="{layout.width - layout.right}" y="{axis_y + 16}" text-anchor="end" '
        f'font-family="Arial, sans-serif" font-size="10" fill="#475569">{end}</text>'
    )
    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _append_igv_coverage_svg(
    parts: list[str],
    coverage: list[CoverageBin],
    region: tuple[str, int, int],
    layout: PlotLayout,
    y: float,
    height: float,
) -> None:
    max_cov = max([item.coverage for item in coverage] + [1.0])
    baseline = y + height - 8
    for item in coverage:
        x0 = _igv_project_x(item.start, region, layout)
        x1 = _igv_project_x(item.end, region, layout)
        bar_height = (item.coverage / max_cov) * max(1.0, height - 18)
        parts.append(
            f'<rect class="igv-coverage-bin" x="{x0:.2f}" y="{baseline - bar_height:.2f}" '
            f'width="{max(1.0, x1 - x0):.2f}" height="{bar_height:.2f}" fill="#475569" '
            f'data-coverage="{item.coverage:.6g}"/>'
        )


def _append_igv_variants_svg(
    parts: list[str],
    variants: list[IGVVariant],
    region: tuple[str, int, int],
    layout: PlotLayout,
    y: float,
    height: float,
) -> None:
    for variant in variants:
        x = _igv_project_x(variant.position, region, layout)
        parts.append(
            f'<line class="igv-variant" x1="{x:.2f}" y1="{y + 8:.2f}" x2="{x:.2f}" y2="{y + height - 8:.2f}" '
            'stroke="#DC2626" stroke-width="2" stroke-linecap="round" '
            f'data-id="{html.escape(variant.identifier, quote=True)}" '
            f'data-position="{variant.position}" data-type="{variant.variant_type}">'
            f"<title>{html.escape(variant.identifier)} {variant.chromosome}:{variant.position}</title></line>"
        )


def _append_igv_annotations_svg(
    parts: list[str],
    annotations: list[IGVAnnotation],
    region: tuple[str, int, int],
    layout: PlotLayout,
    y: float,
    height: float,
) -> None:
    baseline = y + height / 2
    for annotation in annotations:
        x0 = _igv_project_x(annotation.start, region, layout)
        x1 = _igv_project_x(annotation.end, region, layout)
        colour = "#2563EB" if annotation.strand != "-" else "#16A34A"
        parts.append(
            f'<rect class="igv-gene" x="{x0:.2f}" y="{baseline - 8:.2f}" '
            f'width="{max(2.0, x1 - x0):.2f}" height="16" rx="2" fill="{colour}" '
            f'data-gene="{html.escape(annotation.name, quote=True)}" '
            f'data-strand="{html.escape(annotation.strand, quote=True)}">'
            f"<title>{html.escape(annotation.name)} {annotation.chromosome}:{annotation.start}-{annotation.end}</title></rect>"
        )


def _render_igv_png(
    path: Path,
    *,
    region: tuple[str, int, int],
    coverage: list[CoverageBin],
    variants: list[IGVVariant],
    annotations: list[IGVAnnotation],
    layout: PlotLayout,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    tracks: list[str] = []
    if coverage:
        tracks.append("coverage")
    if variants:
        tracks.append("variants")
    if annotations:
        tracks.append("annotations")
    track_boxes = _igv_track_layout(layout, len(tracks))
    frame = (203, 213, 225)
    background = (248, 250, 252)
    for track_key, (x, y, width, height) in zip(tracks, track_boxes):
        x0 = int(round(x))
        y0 = int(round(y))
        x1 = int(round(x + width))
        y1 = int(round(y + height))
        for py in range(y0, y1 + 1):
            for px in range(x0, x1 + 1):
                _set_pixel(pixels, layout.width, layout.height, px, py, background)
        _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
        _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
        _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, frame)
        _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, frame)
        if track_key == "coverage":
            _draw_igv_coverage_png(pixels, layout, coverage, region, y, height)
        elif track_key == "variants":
            _draw_igv_variants_png(pixels, layout, variants, region, y, height)
        elif track_key == "annotations":
            _draw_igv_annotations_png(pixels, layout, annotations, region, y, height)
    _write_png(path, layout.width, layout.height, pixels)


def _draw_igv_coverage_png(
    pixels: bytearray,
    layout: PlotLayout,
    coverage: list[CoverageBin],
    region: tuple[str, int, int],
    y: float,
    height: float,
) -> None:
    max_cov = max([item.coverage for item in coverage] + [1.0])
    baseline = int(round(y + height - 8))
    for item in coverage:
        x0 = int(round(_igv_project_x(item.start, region, layout)))
        x1 = int(round(_igv_project_x(item.end, region, layout)))
        bar_height = int(round((item.coverage / max_cov) * max(1.0, height - 18)))
        for py in range(baseline - bar_height, baseline + 1):
            for px in range(x0, max(x0, x1) + 1):
                _set_pixel(pixels, layout.width, layout.height, px, py, (71, 85, 105))


def _draw_igv_variants_png(
    pixels: bytearray,
    layout: PlotLayout,
    variants: list[IGVVariant],
    region: tuple[str, int, int],
    y: float,
    height: float,
) -> None:
    for variant in variants:
        x = int(round(_igv_project_x(variant.position, region, layout)))
        _draw_line(pixels, layout.width, layout.height, x, int(round(y + 8)), x, int(round(y + height - 8)), (220, 38, 38))


def _draw_igv_annotations_png(
    pixels: bytearray,
    layout: PlotLayout,
    annotations: list[IGVAnnotation],
    region: tuple[str, int, int],
    y: float,
    height: float,
) -> None:
    baseline = int(round(y + height / 2))
    for annotation in annotations:
        x0 = int(round(_igv_project_x(annotation.start, region, layout)))
        x1 = int(round(_igv_project_x(annotation.end, region, layout)))
        colour = (37, 99, 235) if annotation.strand != "-" else (22, 163, 74)
        for py in range(baseline - 8, baseline + 9):
            for px in range(x0, max(x0, x1) + 1):
                _set_pixel(pixels, layout.width, layout.height, px, py, colour)


def _render_manhattan_png(
    path: Path,
    *,
    points: list[ManhattanPoint],
    bounds: PlotBounds,
    layout: PlotLayout,
    significance_threshold: float,
    suggestive_threshold: float,
    chr_colors: str,
    sig_color: str,
    point_size: int,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)
    sig_rgb = _hex_to_rgb(_normalise_hex_color(sig_color, DEFAULT_UP_COLOR))
    plot_points, _, _ = _manhattan_plot_points(points)
    chromosomes = _manhattan_chromosomes(points)
    chromosome_index = {chromosome: index for index, chromosome in enumerate(chromosomes)}
    radius = max(2, int(round(_clamp(float(point_size), 1.0, 50.0) ** 0.5)))

    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)

    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)
    sig_y = int(round(_project_y(-math.log10(significance_threshold), bounds, layout)))
    sug_y = int(round(_project_y(-math.log10(suggestive_threshold), bounds, layout)))
    _draw_line(pixels, layout.width, layout.height, x0, sig_y, x1, sig_y, (220, 38, 38))
    _draw_line(pixels, layout.width, layout.height, x0, sug_y, x1, sug_y, (245, 158, 11))

    for point, plot_x in plot_points:
        x = int(round(_project_x(plot_x, bounds, layout)))
        y = int(round(_project_y(point.neg_log_p, bounds, layout)))
        colour = sig_rgb if point.pvalue < significance_threshold else _hex_to_rgb(
            _manhattan_colour(chr_colors, chromosome_index[point.chromosome])
        )
        _draw_circle(pixels, layout.width, layout.height, x, y, radius, colour)

    _write_png(path, layout.width, layout.height, pixels)


def _render_bar_svg(
    path: Path,
    *,
    rows: list[BarDatum],
    layout: PlotLayout,
    title: str,
    orientation: str,
    color: str,
    show_values: bool,
) -> None:
    categories = _bar_categories(rows)
    groups = _bar_groups(rows)
    value_min, value_max = _bar_value_range(rows)
    grouped = {(row.category, row.group or "Value"): row.value for row in rows}
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    zero_y = _bar_project_y(0.0, value_min, value_max, layout)
    zero_x = _bar_project_x(0.0, value_min, value_max, layout)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
    ]

    if orientation == "horizontal":
        category_band = layout.plot_height / max(1, len(categories))
        group_band = category_band / max(1, len(groups))
        bar_height = max(2.0, group_band * 0.72)
        parts.append(
            f'<line x1="{zero_x:.2f}" y1="{y0}" x2="{zero_x:.2f}" y2="{y1}" '
            'stroke="#111827" stroke-width="1.4"/>'
        )
        parts.append(
            f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>'
        )
        for cat_index, category in enumerate(categories):
            base_y = y0 + cat_index * category_band
            parts.append(
                f'<text x="{x0 - 8}" y="{base_y + category_band / 2 + 4:.2f}" '
                'text-anchor="end" font-family="Arial, sans-serif" font-size="11" '
                f'fill="#475569">{html.escape(category)}</text>'
            )
            for group_index, group in enumerate(groups):
                value = grouped.get((category, group))
                if value is None:
                    continue
                x_value = _bar_project_x(value, value_min, value_max, layout)
                rect_x = min(zero_x, x_value)
                rect_width = abs(x_value - zero_x)
                rect_y = base_y + group_index * group_band + (group_band - bar_height) / 2
                colour = _bar_colour(color, group_index)
                parts.append(
                    f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{rect_width:.2f}" '
                    f'height="{bar_height:.2f}" fill="{colour}" fill-opacity="0.86" '
                    f'data-category="{html.escape(category, quote=True)}" '
                    f'data-group="{html.escape(group, quote=True)}" data-value="{value:.6g}"/>'
                )
                if show_values:
                    label_x = x_value + (4 if value >= 0 else -4)
                    anchor = "start" if value >= 0 else "end"
                    parts.append(
                        f'<text x="{label_x:.2f}" y="{rect_y + bar_height / 2 + 4:.2f}" '
                        f'text-anchor="{anchor}" font-family="Arial, sans-serif" '
                        f'font-size="10" fill="#334155">{value:g}</text>'
                    )
    else:
        category_band = layout.plot_width / max(1, len(categories))
        group_band = category_band / max(1, len(groups))
        bar_width = max(2.0, group_band * 0.72)
        parts.append(
            f'<line x1="{x0}" y1="{zero_y:.2f}" x2="{x1}" y2="{zero_y:.2f}" '
            'stroke="#111827" stroke-width="1.4"/>'
        )
        parts.append(
            f'<line x1="{x0}" y1="{y0}" x2="{x0}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>'
        )
        for cat_index, category in enumerate(categories):
            base_x = x0 + cat_index * category_band
            parts.append(
                f'<text x="{base_x + category_band / 2:.2f}" y="{layout.height - 40}" '
                'text-anchor="middle" font-family="Arial, sans-serif" font-size="11" '
                f'fill="#475569">{html.escape(category)}</text>'
            )
            for group_index, group in enumerate(groups):
                value = grouped.get((category, group))
                if value is None:
                    continue
                y_value = _bar_project_y(value, value_min, value_max, layout)
                rect_y = min(zero_y, y_value)
                rect_height = abs(zero_y - y_value)
                rect_x = base_x + group_index * group_band + (group_band - bar_width) / 2
                colour = _bar_colour(color, group_index)
                parts.append(
                    f'<rect x="{rect_x:.2f}" y="{rect_y:.2f}" width="{bar_width:.2f}" '
                    f'height="{rect_height:.2f}" fill="{colour}" fill-opacity="0.86" '
                    f'data-category="{html.escape(category, quote=True)}" '
                    f'data-group="{html.escape(group, quote=True)}" data-value="{value:.6g}"/>'
                )
                if show_values:
                    label_y = y_value - 5 if value >= 0 else y_value + 13
                    parts.append(
                        f'<text x="{rect_x + bar_width / 2:.2f}" y="{label_y:.2f}" '
                        'text-anchor="middle" font-family="Arial, sans-serif" '
                        f'font-size="10" fill="#334155">{value:g}</text>'
                    )

    if len(groups) > 1:
        legend_x = x1 - 145
        legend_y = y0 + 16
        for group_index, group in enumerate(groups):
            y = legend_y + group_index * 18
            parts.append(
                f'<rect x="{legend_x - 5}" y="{y - 8}" width="9" height="9" '
                f'fill="{_bar_colour(color, group_index)}"/>'
                f'<text x="{legend_x + 10}" y="{y}" font-family="Arial, sans-serif" '
                f'font-size="11" fill="#334155">{html.escape(group)}</text>'
            )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_bar_png(
    path: Path,
    *,
    rows: list[BarDatum],
    layout: PlotLayout,
    orientation: str,
    color: str,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)

    categories = _bar_categories(rows)
    groups = _bar_groups(rows)
    grouped = {(row.category, row.group or "Value"): row.value for row in rows}
    value_min, value_max = _bar_value_range(rows)
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)
    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, axis)

    if orientation == "horizontal":
        zero_x = _bar_project_x(0.0, value_min, value_max, layout)
        category_band = layout.plot_height / max(1, len(categories))
        group_band = category_band / max(1, len(groups))
        bar_height = max(2.0, group_band * 0.72)
        _draw_line(pixels, layout.width, layout.height, int(round(zero_x)), y0, int(round(zero_x)), y1, axis)
        for cat_index, category in enumerate(categories):
            base_y = y0 + cat_index * category_band
            for group_index, group in enumerate(groups):
                value = grouped.get((category, group))
                if value is None:
                    continue
                x_value = _bar_project_x(value, value_min, value_max, layout)
                rect_x0 = int(round(min(zero_x, x_value)))
                rect_x1 = int(round(max(zero_x, x_value)))
                rect_y0 = int(round(base_y + group_index * group_band + (group_band - bar_height) / 2))
                rect_y1 = int(round(rect_y0 + bar_height))
                colour = _hex_to_rgb(_bar_colour(color, group_index))
                for y in range(rect_y0, rect_y1 + 1):
                    for x in range(rect_x0, rect_x1 + 1):
                        _set_pixel(pixels, layout.width, layout.height, x, y, colour)
    else:
        zero_y = _bar_project_y(0.0, value_min, value_max, layout)
        category_band = layout.plot_width / max(1, len(categories))
        group_band = category_band / max(1, len(groups))
        bar_width = max(2.0, group_band * 0.72)
        _draw_line(pixels, layout.width, layout.height, x0, int(round(zero_y)), x1, int(round(zero_y)), axis)
        for cat_index, category in enumerate(categories):
            base_x = x0 + cat_index * category_band
            for group_index, group in enumerate(groups):
                value = grouped.get((category, group))
                if value is None:
                    continue
                y_value = _bar_project_y(value, value_min, value_max, layout)
                rect_y0 = int(round(min(zero_y, y_value)))
                rect_y1 = int(round(max(zero_y, y_value)))
                rect_x0 = int(round(base_x + group_index * group_band + (group_band - bar_width) / 2))
                rect_x1 = int(round(rect_x0 + bar_width))
                colour = _hex_to_rgb(_bar_colour(color, group_index))
                for y in range(rect_y0, rect_y1 + 1):
                    for x in range(rect_x0, rect_x1 + 1):
                        _set_pixel(pixels, layout.width, layout.height, x, y, colour)

    _write_png(path, layout.width, layout.height, pixels)


def _render_bar_html(
    path: Path,
    *,
    rows: list[BarDatum],
    bounds: tuple[float, float],
    layout: PlotLayout,
    title: str,
    orientation: str,
    color: str,
    show_values: bool,
) -> None:
    categories = _bar_categories(rows)
    groups = _bar_groups(rows)
    grouped = {(row.category, row.group or "Value"): row.value for row in rows}
    traces = []
    for group_index, group in enumerate(groups):
        values = [grouped.get((category, group), 0.0) for category in categories]
        trace: dict[str, Any] = {
            "type": "bar",
            "name": group,
            "marker": {"color": _bar_colour(color, group_index), "opacity": 0.86},
            "text": [f"{value:g}" for value in values] if show_values else [],
            "textposition": "auto" if show_values else "none",
            "hovertemplate": (
                "%{y}: %{x}<extra>" + html.escape(group) + "</extra>"
                if orientation == "horizontal"
                else "%{x}: %{y}<extra>" + html.escape(group) + "</extra>"
            ),
        }
        if orientation == "horizontal":
            trace.update({
                "orientation": "h",
                "x": values,
                "y": categories,
            })
        else:
            trace.update({
                "x": categories,
                "y": values,
            })
        traces.append(trace)

    low, high = bounds
    axis_range = [low, high]
    plot_layout = {
        "title": {"text": title},
        "barmode": "group",
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "showlegend": len(groups) > 1,
    }
    if orientation == "horizontal":
        plot_layout["xaxis"] = {"title": "Value", "range": axis_range, "zeroline": True}
        plot_layout["yaxis"] = {"title": ""}
    else:
        plot_layout["xaxis"] = {"title": ""}
        plot_layout["yaxis"] = {"title": "Value", "range": axis_range, "zeroline": True}
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "bar_chart"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _forest_error_array(rows: list[ForestPlotRow], *, side: str) -> list[float]:
    if side == "upper":
        return [round(max(row.upper - row.effect, 0.0), 10) for row in rows]
    return [round(max(row.effect - row.lower, 0.0), 10) for row in rows]


def _forest_customdata(rows: list[ForestPlotRow]) -> list[list[Any]]:
    return [
        [
            row.label,
            round(row.effect, 10),
            round(row.lower, 10),
            round(row.upper, 10),
            "n/a" if row.weight is None else round(row.weight, 10),
        ]
        for row in rows
    ]


def _render_forest_html(
    path: Path,
    *,
    rows: list[ForestPlotRow],
    bounds: tuple[float, float],
    layout: PlotLayout,
    title: str,
    x_label: str,
    reference: float,
    show_weights: bool,
) -> None:
    labels = [row.label for row in rows]
    study_rows = [row for row in rows if not row.pooled]
    pooled_rows = [row for row in rows if row.pooled]
    has_weights = any(row.weight is not None for row in rows)
    weight_line = "<br>weight: %{customdata[4]}%" if show_weights and has_weights else ""
    hovertemplate = (
        "<b>%{customdata[0]}</b><br>"
        "effect: %{customdata[1]}<br>"
        "CI: [%{customdata[2]}, %{customdata[3]}]"
        f"{weight_line}<extra></extra>"
    )

    traces: list[dict[str, Any]] = []
    if study_rows:
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": "Study",
            "x": [round(row.effect, 10) for row in study_rows],
            "y": [row.label for row in study_rows],
            "customdata": _forest_customdata(study_rows),
            "hovertemplate": hovertemplate,
            "error_x": {
                "type": "data",
                "symmetric": False,
                "array": _forest_error_array(study_rows, side="upper"),
                "arrayminus": _forest_error_array(study_rows, side="lower"),
                "color": "#334155",
                "thickness": 1.6,
                "width": 6,
            },
            "marker": {
                "color": "#2563EB",
                "size": [round(_forest_marker_radius(row) * 2.0, 2) for row in study_rows],
                "opacity": 0.88,
                "line": {"color": "#ffffff", "width": 1},
            },
        })
    if pooled_rows:
        traces.append({
            "type": "scatter",
            "mode": "markers",
            "name": "Pooled",
            "x": [round(row.effect, 10) for row in pooled_rows],
            "y": [row.label for row in pooled_rows],
            "customdata": _forest_customdata(pooled_rows),
            "hovertemplate": hovertemplate,
            "error_x": {
                "type": "data",
                "symmetric": False,
                "array": _forest_error_array(pooled_rows, side="upper"),
                "arrayminus": _forest_error_array(pooled_rows, side="lower"),
                "color": "#0F172A",
                "thickness": 2.2,
                "width": 7,
            },
            "marker": {
                "color": "#0F172A",
                "symbol": "diamond",
                "size": [round(_forest_marker_radius(row) * 2.4, 2) for row in pooled_rows],
                "opacity": 0.95,
                "line": {"color": "#ffffff", "width": 1},
            },
        })

    plot_layout = {
        "title": {"text": title},
        "xaxis": {
            "title": x_label,
            "range": [bounds[0], bounds[1]],
            "zeroline": False,
            "showgrid": True,
            "gridcolor": "#E2E8F0",
        },
        "yaxis": {
            "title": "",
            "categoryorder": "array",
            "categoryarray": labels,
            "autorange": "reversed",
            "automargin": True,
        },
        "shapes": [{
            "type": "line",
            "xref": "x",
            "yref": "paper",
            "x0": reference,
            "x1": reference,
            "y0": 0,
            "y1": 1,
            "line": {"color": "#64748B", "width": 1, "dash": "dash"},
        }],
        "plot_bgcolor": "#F8FAFC",
        "paper_bgcolor": "#FFFFFF",
        "font": {"family": "Arial, sans-serif", "color": "#111827"},
        "margin": {"l": layout.left, "r": layout.right, "t": layout.top, "b": layout.bottom},
        "hovermode": "closest",
        "showlegend": bool(study_rows and pooled_rows),
    }
    config = {
        "displaylogo": False,
        "responsive": True,
        "toImageButtonOptions": {"format": "png", "filename": "forest_plot"},
    }

    document = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
html, body {{ margin: 0; min-height: 100%; background: #ffffff; color: #111827; font-family: Arial, sans-serif; }}
#plot {{ width: 100%; min-height: min(100vh, {layout.height}px); }}
.plot-fallback {{ padding: 16px; color: #475569; font-size: 13px; }}
</style>
</head>
<body>
<div id="plot"></div>
<script>
const data = {_json_for_script(traces)};
const layout = {_json_for_script(plot_layout)};
const config = {_json_for_script(config)};
if (window.Plotly) {{
  Plotly.newPlot("plot", data, layout, config);
}} else {{
  document.getElementById("plot").innerHTML = '<div class="plot-fallback">Plotly could not be loaded.</div>';
}}
</script>
</body>
</html>
"""
    path.write_text(document, encoding="utf-8")


def _forest_marker_radius(row: ForestPlotRow) -> float:
    if row.pooled:
        return 7.0
    if row.weight is None:
        return 5.0
    return 3.8 + math.sqrt(max(row.weight, 0.0)) * 0.35


def _render_forest_svg(
    path: Path,
    *,
    rows: list[ForestPlotRow],
    bounds: tuple[float, float],
    layout: PlotLayout,
    title: str,
    x_label: str,
    reference: float,
    show_weights: bool,
) -> None:
    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom
    reference_x = _project_forest_x(reference, bounds, layout)
    row_step = layout.plot_height / max(1, len(rows))
    label_x = max(12, x0 - 10)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{layout.width}" '
        f'height="{layout.height}" viewBox="0 0 {layout.width} {layout.height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        f'<text x="{layout.width / 2:.1f}" y="{max(24, layout.top - 28)}" '
        'text-anchor="middle" font-family="Arial, sans-serif" font-size="20" '
        f'font-weight="700" fill="#111827">{html.escape(title)}</text>',
        f'<rect x="{x0}" y="{y0}" width="{layout.plot_width}" height="{layout.plot_height}" '
        'fill="#F8FAFC" stroke="#CBD5E1" stroke-width="1"/>',
        f'<line x1="{reference_x:.2f}" y1="{y0}" x2="{reference_x:.2f}" y2="{y1}" '
        'stroke="#64748B" stroke-width="1" stroke-dasharray="6 5" class="forest-reference"/>',
        f'<line x1="{x0}" y1="{y1}" x2="{x1}" y2="{y1}" stroke="#111827" stroke-width="1.5"/>',
        f'<text x="{(x0 + x1) / 2:.1f}" y="{layout.height - 20}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="14" fill="#111827">'
        f"{html.escape(x_label)}</text>",
        f'<text x="{x0}" y="{layout.height - 40}" text-anchor="start" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds[0]:.3g}</text>",
        f'<text x="{reference_x:.2f}" y="{layout.height - 40}" text-anchor="middle" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{reference:g}</text>",
        f'<text x="{x1}" y="{layout.height - 40}" text-anchor="end" '
        'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
        f"{bounds[1]:.3g}</text>",
    ]

    for index, row in enumerate(rows):
        y = y0 + row_step * (index + 0.5)
        if index % 2 == 1:
            parts.append(
                f'<rect x="{x0}" y="{y - row_step / 2:.2f}" width="{layout.plot_width}" '
                f'height="{row_step:.2f}" fill="#EEF2F7" fill-opacity="0.45"/>'
            )

        lower_x = _project_forest_x(row.lower, bounds, layout)
        upper_x = _project_forest_x(row.upper, bounds, layout)
        effect_x = _project_forest_x(row.effect, bounds, layout)
        label_attr = html.escape(row.label, quote=True)
        stroke = "#0F172A" if row.pooled else "#334155"
        fill = "#0F172A" if row.pooled else "#2563EB"
        radius = _forest_marker_radius(row)

        parts.append(
            f'<text x="{label_x}" y="{y + 4:.2f}" text-anchor="end" '
            'font-family="Arial, sans-serif" font-size="12" '
            f'font-weight="{700 if row.pooled else 400}" fill="#111827">'
            f"{html.escape(row.label)}</text>"
        )
        parts.append(
            f'<line x1="{lower_x:.2f}" y1="{y:.2f}" x2="{upper_x:.2f}" y2="{y:.2f}" '
            f'stroke="{stroke}" stroke-width="{2.4 if row.pooled else 1.8}" '
            f'class="forest-ci" data-label="{label_attr}" data-effect="{row.effect:.6g}" '
            f'data-lower="{row.lower:.6g}" data-upper="{row.upper:.6g}"/>'
        )
        parts.append(
            f'<line x1="{lower_x:.2f}" y1="{y - 5:.2f}" x2="{lower_x:.2f}" y2="{y + 5:.2f}" '
            f'stroke="{stroke}" stroke-width="1.4"/>'
        )
        parts.append(
            f'<line x1="{upper_x:.2f}" y1="{y - 5:.2f}" x2="{upper_x:.2f}" y2="{y + 5:.2f}" '
            f'stroke="{stroke}" stroke-width="1.4"/>'
        )

        if row.pooled:
            diamond = (
                f"{effect_x:.2f},{y - radius:.2f} "
                f"{effect_x + radius:.2f},{y:.2f} "
                f"{effect_x:.2f},{y + radius:.2f} "
                f"{effect_x - radius:.2f},{y:.2f}"
            )
            parts.append(
                f'<polygon points="{diamond}" fill="{fill}" stroke="#ffffff" stroke-width="1" '
                f'class="forest-pooled" data-label="{label_attr}" data-effect="{row.effect:.6g}">'
                f"<title>{html.escape(row.label)}: {row.effect:.3g} "
                f"[{row.lower:.3g}, {row.upper:.3g}]</title></polygon>"
            )
        else:
            parts.append(
                f'<circle cx="{effect_x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{fill}" '
                'fill-opacity="0.88" stroke="#ffffff" stroke-width="1" '
                f'class="forest-effect" data-label="{label_attr}" data-effect="{row.effect:.6g}">'
                f"<title>{html.escape(row.label)}: {row.effect:.3g} "
                f"[{row.lower:.3g}, {row.upper:.3g}]</title></circle>"
            )

        if show_weights and row.weight is not None:
            parts.append(
                f'<text x="{x1 + 8}" y="{y + 4:.2f}" text-anchor="start" '
                'font-family="Arial, sans-serif" font-size="11" fill="#475569">'
                f"{row.weight:g}%</text>"
            )

    parts.append("</svg>")
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _render_forest_png(
    path: Path,
    *,
    rows: list[ForestPlotRow],
    bounds: tuple[float, float],
    layout: PlotLayout,
    reference: float,
) -> None:
    pixels = bytearray([255, 255, 255]) * (layout.width * layout.height)
    background = (248, 250, 252)
    axis = (17, 24, 39)
    frame = (203, 213, 225)
    interval = (51, 65, 85)
    marker = (37, 99, 235)
    pooled_marker = (15, 23, 42)

    x0 = layout.left
    x1 = layout.width - layout.right
    y0 = layout.top
    y1 = layout.height - layout.bottom

    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            _set_pixel(pixels, layout.width, layout.height, x, y, background)
    _draw_line(pixels, layout.width, layout.height, x0, y0, x1, y0, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y0, x1, y1, frame)
    _draw_line(pixels, layout.width, layout.height, x1, y1, x0, y1, axis)
    _draw_line(pixels, layout.width, layout.height, x0, y1, x0, y0, frame)

    reference_x = int(round(_project_forest_x(reference, bounds, layout)))
    _draw_line(pixels, layout.width, layout.height, reference_x, y0, reference_x, y1, (100, 116, 139))

    row_step = layout.plot_height / max(1, len(rows))
    for index, row in enumerate(rows):
        y = int(round(y0 + row_step * (index + 0.5)))
        lower_x = int(round(_project_forest_x(row.lower, bounds, layout)))
        upper_x = int(round(_project_forest_x(row.upper, bounds, layout)))
        effect_x = int(round(_project_forest_x(row.effect, bounds, layout)))
        colour = pooled_marker if row.pooled else marker
        line_colour = pooled_marker if row.pooled else interval
        _draw_line(pixels, layout.width, layout.height, lower_x, y, upper_x, y, line_colour)
        _draw_line(pixels, layout.width, layout.height, lower_x, y - 5, lower_x, y + 5, line_colour)
        _draw_line(pixels, layout.width, layout.height, upper_x, y - 5, upper_x, y + 5, line_colour)
        if row.pooled:
            radius = int(round(_forest_marker_radius(row)))
            for dy in range(-radius, radius + 1):
                span = radius - abs(dy)
                _draw_line(
                    pixels,
                    layout.width,
                    layout.height,
                    effect_x - span,
                    y + dy,
                    effect_x + span,
                    y + dy,
                    colour,
                )
        else:
            _draw_circle(
                pixels,
                layout.width,
                layout.height,
                effect_x,
                y,
                int(round(_forest_marker_radius(row))),
                colour,
            )

    _write_png(path, layout.width, layout.height, pixels)


class ForestPlotNode(BaseNode):
    """Create a forest plot from meta-analysis effect estimates."""

    NODE_ID = "forest_plot"
    DISPLAY_NAME = "Forest Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Create forest plots for per-study and pooled meta-analysis effect sizes."
    SEARCH_ALIASES = ["forest", "meta-analysis", "effect size", "confidence interval", "pooled estimate"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("forest_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV/TSV table with study effects and intervals"}),
            },
            "optional": {
                "label_column": ("STRING", {"default": "study"}),
                "study_column": ("STRING", {"default": ""}),
                "effect_column": ("STRING", {"default": "logFC"}),
                "lower_column": ("STRING", {"default": "ci_lower"}),
                "upper_column": ("STRING", {"default": "ci_upper"}),
                "se_column": ("STRING", {"default": "SE"}),
                "weight_column": ("STRING", {"default": ""}),
                "pooled_column": ("STRING", {"default": ""}),
                "title": ("STRING", {"default": "Forest Plot"}),
                "x_label": ("STRING", {"default": "Effect size"}),
                "reference": ("FLOAT", {"default": 0.0}),
                "show_weights": ("BOOLEAN", {"default": True}),
                "format": (list(FOREST_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 6.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in FOREST_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported forest plot format: {output_format}")

        label_column = str(kwargs.get("study_column", "") or "").strip()
        if not label_column:
            label_column = str(kwargs.get("label_column", "study") or "study").strip()
        effect_column = str(kwargs.get("effect_column", "logFC") or "logFC").strip()
        lower_column = str(kwargs.get("lower_column", "ci_lower") or "ci_lower").strip()
        upper_column = str(kwargs.get("upper_column", "ci_upper") or "ci_upper").strip()
        se_column = str(kwargs.get("se_column", "SE") or "SE").strip()
        weight_column = str(kwargs.get("weight_column", "") or "").strip()
        pooled_column = str(kwargs.get("pooled_column", "") or "").strip()
        if not label_column or not effect_column:
            raise ValueError("Forest plot requires label/study and effect columns")

        rows = _read_forest_rows(
            Path(str(kwargs["table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            label_column=label_column,
            effect_column=effect_column,
            lower_column=lower_column,
            upper_column=upper_column,
            se_column=se_column,
            weight_column=weight_column,
            pooled_column=pooled_column,
        )
        reference = _coerce_float(kwargs.get("reference", 0.0), 0.0)
        bounds = _forest_bounds(rows, reference=reference)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 10.0),
            kwargs.get("height", 6.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        layout = PlotLayout(
            width=layout.width,
            height=layout.height,
            left=max(layout.left, 118),
            right=max(layout.right, 78 if any(row.weight is not None for row in rows) else layout.right),
            top=layout.top,
            bottom=layout.bottom,
        )

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"forest_plot.{output_format}"
        if output_format == "svg":
            _render_forest_svg(
                output_path,
                rows=rows,
                bounds=bounds,
                layout=layout,
                title=str(kwargs.get("title", "Forest Plot") or "Forest Plot"),
                x_label=str(kwargs.get("x_label", "Effect size") or "Effect size"),
                reference=reference,
                show_weights=bool(kwargs.get("show_weights", True)),
            )
        elif output_format == "html":
            _render_forest_html(
                output_path,
                rows=rows,
                bounds=bounds,
                layout=layout,
                title=str(kwargs.get("title", "Forest Plot") or "Forest Plot"),
                x_label=str(kwargs.get("x_label", "Effect size") or "Effect size"),
                reference=reference,
                show_weights=bool(kwargs.get("show_weights", True)),
            )
        else:
            _render_forest_png(
                output_path,
                rows=rows,
                bounds=bounds,
                layout=layout,
                reference=reference,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Forest Plot")

        return {"outputs": {"forest_image": str(output_path)}}


class LineChartNode(BaseNode):
    """Create a multi-series line chart from a CSV/TSV table."""

    NODE_ID = "line_chart"
    DISPLAY_NAME = "Line Chart"
    CATEGORY = "visualization"
    DESCRIPTION = "Create line charts for time-series, trajectories, or continuous data."
    SEARCH_ALIASES = ["line", "linechart", "time series", "trend", "trajectory", "expression profile"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("chart_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV/TSV table with numeric X and Y columns"}),
                "x_column": ("STRING", {"default": ""}),
                "y_columns": ("STRING", {"default": ""}),
            },
            "optional": {
                "title": ("STRING", {"default": "Line Chart"}),
                "xlabel": ("STRING", {"default": ""}),
                "ylabel": ("STRING", {"default": ""}),
                "palette": ("STRING", {"default": "tab10"}),
                "line_style": ("STRING", {"default": "solid", "options": ["solid", "dashed", "dotted", "dashdot"]}),
                "marker": ("STRING", {"default": "none", "options": ["none", "o", "s", "^", "D", "*"]}),
                "show_grid": ("BOOLEAN", {"default": True}),
                "format": (list(LINE_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 6.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in LINE_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported line chart format: {output_format}")

        x_column = str(kwargs.get("x_column", "") or "").strip()
        y_columns = [
            column.strip()
            for column in str(kwargs.get("y_columns", "") or "").split(",")
            if column.strip()
        ]
        if not x_column or not y_columns:
            raise ValueError("Line chart requires x_column and y_columns")

        line_style = str(kwargs.get("line_style", "solid") or "solid").strip().lower()
        if line_style not in {"solid", "dashed", "dotted", "dashdot"}:
            raise ValueError(f"Unsupported line chart line style: {line_style}")
        marker = str(kwargs.get("marker", "none") or "none").strip()
        if marker not in {"none", "o", "s", "^", "D", "*"}:
            raise ValueError(f"Unsupported line chart marker: {marker}")

        series = _read_line_series(
            Path(str(kwargs["table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            x_column=x_column,
            y_columns=y_columns,
        )
        bounds = _line_bounds(series)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 10.0),
            kwargs.get("height", 6.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Line Chart") or "Line Chart")
        xlabel = str(kwargs.get("xlabel", "") or x_column)
        ylabel = str(kwargs.get("ylabel", "") or ", ".join(y_columns))
        palette = str(kwargs.get("palette", "tab10") or "tab10")
        show_grid = bool(kwargs.get("show_grid", True))

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"line_chart.{output_format}"
        if output_format == "svg":
            _render_line_svg(
                output_path,
                series=series,
                bounds=bounds,
                layout=layout,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                palette=palette,
                line_style=line_style,
                marker=marker,
                show_grid=show_grid,
            )
        elif output_format == "html":
            _render_line_html(
                output_path,
                series=series,
                bounds=bounds,
                layout=layout,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                palette=palette,
                line_style=line_style,
                marker=marker,
                show_grid=show_grid,
            )
        else:
            _render_line_png(
                output_path,
                series=series,
                bounds=bounds,
                layout=layout,
                palette=palette,
                marker=marker,
                show_grid=show_grid,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Line Chart")

        return {"outputs": {"chart_image": str(output_path)}}


class HeatmapNode(BaseNode):
    """Create a heatmap from a row-labelled numeric matrix."""

    NODE_ID = "heatmap"
    DISPLAY_NAME = "Heatmap"
    CATEGORY = "visualization"
    DESCRIPTION = "Create matrix heatmaps for expression, correlation, or distance tables."
    SEARCH_ALIASES = ["heatmap", "clustered heatmap", "expression matrix", "correlation matrix", "distance matrix", "pheatmap"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("heatmap_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "matrix": ("FILE", {"description": "CSV/TSV matrix with row labels in the first column"}),
            },
            "optional": {
                "colormap": ("STRING", {"default": "RdYlBu_r"}),
                "cluster_rows": ("BOOLEAN", {"default": True}),
                "cluster_cols": ("BOOLEAN", {"default": True}),
                "scale": ("STRING", {"default": "none", "options": ["none", "row", "column"]}),
                "title": ("STRING", {"default": "Heatmap"}),
                "show_rownames": ("BOOLEAN", {"default": True}),
                "show_colnames": ("BOOLEAN", {"default": True}),
                "vmin": ("FLOAT", {"default": 0.0}),
                "vmax": ("FLOAT", {"default": 0.0}),
                "format": (list(HEATMAP_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 8.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in HEATMAP_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported heatmap format: {output_format}")

        scale = str(kwargs.get("scale", "none") or "none").strip().lower()
        matrix = _scale_heatmap_matrix(
            _read_heatmap_matrix(
                Path(str(kwargs["matrix"])),
                delimiter=kwargs.get("delimiter", "auto"),
            ),
            scale,
        )
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 10.0),
            kwargs.get("height", 8.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        colormap = str(kwargs.get("colormap", "RdYlBu_r") or "RdYlBu_r")
        title = str(kwargs.get("title", "Heatmap") or "Heatmap")
        show_rownames = bool(kwargs.get("show_rownames", True))
        show_colnames = bool(kwargs.get("show_colnames", True))
        vmin_value = _coerce_float(kwargs.get("vmin", 0.0), 0.0)
        vmax_value = _coerce_float(kwargs.get("vmax", 0.0), 0.0)
        vmin = vmin_value if not math.isclose(vmin_value, 0.0) else None
        vmax = vmax_value if not math.isclose(vmax_value, 0.0) else None
        if vmin is not None and vmax is not None and vmin >= vmax:
            raise ValueError("Heatmap vmin must be less than vmax")
        cluster_rows = bool(kwargs.get("cluster_rows", True))
        cluster_cols = bool(kwargs.get("cluster_cols", True))

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"heatmap.{output_format}"
        if output_format == "svg":
            _render_heatmap_svg(
                output_path,
                matrix=matrix,
                layout=layout,
                title=title,
                colormap=colormap,
                show_rownames=show_rownames,
                show_colnames=show_colnames,
                vmin=vmin,
                vmax=vmax,
                cluster_rows=cluster_rows,
                cluster_cols=cluster_cols,
            )
        elif output_format == "html":
            _render_heatmap_html(
                output_path,
                matrix=matrix,
                layout=layout,
                title=title,
                colormap=colormap,
                show_rownames=show_rownames,
                show_colnames=show_colnames,
                vmin=vmin,
                vmax=vmax,
                cluster_rows=cluster_rows,
                cluster_cols=cluster_cols,
            )
        else:
            _render_heatmap_png(
                output_path,
                matrix=matrix,
                layout=layout,
                colormap=colormap,
                vmin=vmin,
                vmax=vmax,
                cluster_rows=cluster_rows,
                cluster_cols=cluster_cols,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Heatmap")

        return {"outputs": {"heatmap_image": str(output_path)}}


class ManhattanPlotNode(BaseNode):
    """Create a GWAS Manhattan plot from association results."""

    NODE_ID = "manhattan_plot"
    DISPLAY_NAME = "Manhattan Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Create GWAS Manhattan plots with chromosome-wide p-values and thresholds."
    SEARCH_ALIASES = ["manhattan", "gwas", "genome-wide", "p-value plot", "association", "snp plot"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("manhattan_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "results_table": ("FILE", {"description": "GWAS table with chromosome, position, and p-value columns"}),
                "chr_column": ("STRING", {"default": "CHR"}),
                "pos_column": ("STRING", {"default": "BP"}),
                "pvalue_column": ("STRING", {"default": "P"}),
            },
            "optional": {
                "snp_column": ("STRING", {"default": ""}),
                "significance_threshold": ("FLOAT", {"default": 5e-8}),
                "suggestive_threshold": ("FLOAT", {"default": 1e-5}),
                "title": ("STRING", {"default": "Manhattan Plot"}),
                "chr_colors": ("STRING", {"default": "#3498DB,#2ECC71"}),
                "sig_color": ("STRING", {"default": DEFAULT_UP_COLOR}),
                "point_size": ("INT", {"default": 8, "min": 1, "max": 50}),
                "label_top_n": ("INT", {"default": 5, "min": 0, "max": 50}),
                "format": (list(MANHATTAN_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 16.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 6.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in MANHATTAN_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported Manhattan plot format: {output_format}")

        chr_column = str(kwargs.get("chr_column", "CHR") or "CHR").strip()
        pos_column = str(kwargs.get("pos_column", "BP") or "BP").strip()
        pvalue_column = str(kwargs.get("pvalue_column", "P") or "P").strip()
        snp_column = str(kwargs.get("snp_column", "") or "").strip()
        if not chr_column or not pos_column or not pvalue_column:
            raise ValueError("Manhattan plot requires chr_column, pos_column, and pvalue_column")

        significance_threshold = _coerce_float(kwargs.get("significance_threshold", 5e-8), 5e-8)
        suggestive_threshold = _coerce_float(kwargs.get("suggestive_threshold", 1e-5), 1e-5)
        if significance_threshold <= 0 or suggestive_threshold <= 0:
            raise ValueError("Manhattan plot thresholds must be greater than zero")

        points = _read_manhattan_points(
            Path(str(kwargs["results_table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            chr_column=chr_column,
            pos_column=pos_column,
            pvalue_column=pvalue_column,
            snp_column=snp_column,
        )
        bounds = _manhattan_bounds(
            points,
            significance_threshold=significance_threshold,
            suggestive_threshold=suggestive_threshold,
        )
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 16.0),
            kwargs.get("height", 6.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Manhattan Plot") or "Manhattan Plot")
        chr_colors = str(kwargs.get("chr_colors", "#3498DB,#2ECC71") or "#3498DB,#2ECC71")
        sig_color = str(kwargs.get("sig_color", DEFAULT_UP_COLOR) or DEFAULT_UP_COLOR)
        point_size = _coerce_int(kwargs.get("point_size", 8), 8)
        label_top_n = _coerce_int(kwargs.get("label_top_n", 5), 5)

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"manhattan_plot.{output_format}"
        if output_format == "svg":
            _render_manhattan_svg(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                significance_threshold=significance_threshold,
                suggestive_threshold=suggestive_threshold,
                title=title,
                chr_colors=chr_colors,
                sig_color=sig_color,
                point_size=point_size,
                label_top_n=label_top_n,
            )
        elif output_format == "html":
            _render_manhattan_html(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                significance_threshold=significance_threshold,
                suggestive_threshold=suggestive_threshold,
                title=title,
                chr_colors=chr_colors,
                sig_color=sig_color,
                point_size=point_size,
                label_top_n=label_top_n,
            )
        else:
            _render_manhattan_png(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                significance_threshold=significance_threshold,
                suggestive_threshold=suggestive_threshold,
                chr_colors=chr_colors,
                sig_color=sig_color,
                point_size=point_size,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Manhattan Plot")

        return {"outputs": {"manhattan_image": str(output_path)}}


class CoveragePlotNode(BaseNode):
    """Create a genomic coverage plot from BAM, BigWig, bedGraph, or coverage tables."""

    NODE_ID = "coverage_plot"
    DISPLAY_NAME = "Coverage Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Render read depth or signal coverage across a genomic interval."
    SEARCH_ALIASES = ["coverage", "read depth", "bam coverage", "bigwig", "bedgraph", "genome browser"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("coverage_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignment": ("FILE", {"description": "BAM/CRAM, BigWig, bedGraph, or coverage table"}),
                "region": ("STRING", {"default": "chr1:1-1000"}),
            },
            "optional": {
                "window_size": ("INT", {"default": 50, "min": 1, "max": 1000000}),
                "title": ("STRING", {"default": "Coverage Plot"}),
                "fill_color": ("STRING", {"default": "#2563EB"}),
                "format": (list(COVERAGE_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 12.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 4.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in COVERAGE_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported coverage plot format: {output_format}")

        region = _parse_region(str(kwargs.get("region", "") or ""))
        window_size = max(_coerce_int(kwargs.get("window_size", 50), 50), 1)
        bins = _read_coverage_bins(
            Path(str(kwargs["alignment"])),
            region=region,
            window_size=window_size,
        )
        bounds = _coverage_bounds(bins, region)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 12.0),
            kwargs.get("height", 4.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Coverage Plot") or "Coverage Plot")
        fill_color = str(kwargs.get("fill_color", "#2563EB") or "#2563EB")

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"coverage_plot.{output_format}"
        if output_format == "svg":
            _render_coverage_svg(
                output_path,
                bins=bins,
                bounds=bounds,
                layout=layout,
                title=title,
                fill_color=fill_color,
            )
        elif output_format == "html":
            _render_coverage_html(
                output_path,
                bins=bins,
                bounds=bounds,
                layout=layout,
                title=title,
                fill_color=fill_color,
            )
        else:
            _render_coverage_png(
                output_path,
                bins=bins,
                bounds=bounds,
                layout=layout,
                fill_color=fill_color,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Coverage Plot")

        return {"outputs": {"coverage_image": str(output_path)}}


class PhylogeneticTreeViewerNode(BaseNode):
    """Render phylogenetic trees from Newick files."""

    NODE_ID = "phylo_tree_viewer"
    DISPLAY_NAME = "Phylogenetic Tree Viewer"
    CATEGORY = "visualization"
    DESCRIPTION = "Render phylogenetic trees from Newick files with bootstrap annotations."
    SEARCH_ALIASES = ["phylogenetic tree", "newick", "tree viewer", "phylogeny", "bootstrap", "cladogram"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("tree_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tree_file": ("FILE", {"description": "Phylogenetic tree in Newick format"}),
            },
            "optional": {
                "layout": ("STRING", {"default": "rectangular", "options": ["rectangular", "circular", "radial"]}),
                "show_bootstrap": ("BOOLEAN", {"default": True}),
                "bootstrap_threshold": ("FLOAT", {"default": 70.0, "min": 0.0, "max": 100.0}),
                "branch_width": ("FLOAT", {"default": 2.0, "min": 0.5, "max": 10.0}),
                "tip_label_size": ("INT", {"default": 10, "min": 4, "max": 24}),
                "color_branches": ("BOOLEAN", {"default": False}),
                "title": ("STRING", {"default": "Phylogenetic Tree"}),
                "format": (list(SUPPORTED_IMAGE_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 12.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 8.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"Unsupported phylogenetic tree format: {output_format}")

        tree_layout = str(kwargs.get("layout", "rectangular") or "rectangular").strip().lower()
        if tree_layout not in {"rectangular", "circular", "radial"}:
            raise ValueError(f"Unsupported phylogenetic tree layout: {tree_layout}")

        root = _parse_newick_file(Path(str(kwargs["tree_file"])))
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 12.0),
            kwargs.get("height", 8.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Phylogenetic Tree") or "Phylogenetic Tree")
        show_bootstrap = bool(kwargs.get("show_bootstrap", True))
        bootstrap_threshold = _coerce_float(kwargs.get("bootstrap_threshold", 70.0), 70.0)
        branch_width = _coerce_float(kwargs.get("branch_width", 2.0), 2.0)
        tip_label_size = _coerce_int(kwargs.get("tip_label_size", 10), 10)
        color_branches = bool(kwargs.get("color_branches", False))

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"phylo_tree.{output_format}"
        if output_format == "svg":
            _render_tree_svg(
                output_path,
                root=root,
                tree_layout=tree_layout,
                show_bootstrap=show_bootstrap,
                bootstrap_threshold=bootstrap_threshold,
                branch_width=branch_width,
                tip_label_size=tip_label_size,
                color_branches=color_branches,
                title=title,
                layout=layout,
            )
        else:
            _render_tree_png(
                output_path,
                root=root,
                tree_layout=tree_layout,
                branch_width=branch_width,
                color_branches=color_branches,
                bootstrap_threshold=bootstrap_threshold,
                layout=layout,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Phylogenetic Tree")

        return {"outputs": {"tree_image": str(output_path)}}


class VCFStatsChartNode(BaseNode):
    """Generate VCF statistics charts and JSON summaries."""

    NODE_ID = "vcf_stats_chart"
    DISPLAY_NAME = "VCF Stats Chart"
    CATEGORY = "visualization"
    DESCRIPTION = "Generate comprehensive VCF statistics charts: variant types, quality, Ti/Tv, and chromosome distribution."
    SEARCH_ALIASES = ["vcf stats", "variant stats", "snp distribution", "vcf quality", "titv ratio", "variant chart"]
    RETURN_TYPES = ("IMAGE", "JSON")
    RETURN_NAMES = ("stats_image", "stats_json")
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": ("FILE", {"description": "VCF file"}),
            },
            "optional": {
                "title": ("STRING", {"default": "VCF Statistics"}),
                "quality_bins": ("INT", {"default": 50, "min": 1, "max": 200}),
                "min_quality": ("FLOAT", {"default": 0.0}),
                "max_quality": ("FLOAT", {"default": 0.0}),
                "format": (list(VCF_STATS_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 16.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 12.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in VCF_STATS_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported VCF stats chart format: {output_format}")

        records = _read_vcf_records(Path(str(kwargs["vcf"])))
        stats = _vcf_stats(records)
        quality_bins = _coerce_int(kwargs.get("quality_bins", 50), 50)
        min_quality = _coerce_float(kwargs.get("min_quality", 0.0), 0.0)
        max_quality_value = _coerce_float(kwargs.get("max_quality", 0.0), 0.0)
        max_quality = max_quality_value if max_quality_value > 0 else None
        if max_quality is not None and min_quality >= max_quality:
            raise ValueError("max_quality must be greater than min_quality")

        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 16.0),
            kwargs.get("height", 12.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "VCF Statistics") or "VCF Statistics")

        out_dir = _node_output_dir(self, context)
        image_path = out_dir / f"vcf_stats.{output_format}"
        json_path = out_dir / "vcf_stats.json"
        json_path.write_text(json.dumps(_vcf_stats_json(stats), indent=2, sort_keys=True) + "\n", encoding="utf-8")

        if output_format == "svg":
            _render_vcf_stats_svg(
                image_path,
                stats=stats,
                title=title,
                quality_bins=quality_bins,
                min_quality=min_quality,
                max_quality=max_quality,
                layout=layout,
            )
        elif output_format == "html":
            _render_vcf_stats_html(
                image_path,
                stats=stats,
                title=title,
                quality_bins=quality_bins,
                min_quality=min_quality,
                max_quality=max_quality,
                layout=layout,
            )
        else:
            _render_vcf_stats_png(
                image_path,
                stats=stats,
                quality_bins=quality_bins,
                min_quality=min_quality,
                max_quality=max_quality,
                layout=layout,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(image_path, label="VCF Stats Chart")

        return {"outputs": {"stats_image": str(image_path), "stats_json": str(json_path)}}


class CircosPlotNode(BaseNode):
    """Create a static Circos-style circular genome plot."""

    NODE_ID = "circos_plot"
    DISPLAY_NAME = "Circos Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Circular genome visualization with chromosome sectors and optional gene, variant, and CNV tracks."
    SEARCH_ALIASES = ["circos", "circular genome", "genome ring", "circular plot", "genome visualization"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("circos_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "chromosome_sizes": ("FILE", {"description": "BED-like file: chromosome, start, end"}),
            },
            "optional": {
                "gene_track": ("FILE", {"default": "", "description": "BED-like gene intervals"}),
                "variant_track": ("FILE", {"default": "", "description": "VCF variant track"}),
                "cnv_track": ("FILE", {"default": "", "description": "CNV intervals: chrom, start, end, log2fc"}),
                "title": ("STRING", {"default": "Circos Plot"}),
                "outer_gap": ("FLOAT", {"default": 2.0, "min": 0.0, "max": 20.0}),
                "format": (list(SUPPORTED_IMAGE_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"Unsupported Circos plot format: {output_format}")

        chromosomes = _read_circos_chromosomes(Path(str(kwargs["chromosome_sizes"])))
        genes = _read_circos_intervals(kwargs.get("gene_track", ""))
        variants = _read_circos_variants(kwargs.get("variant_track", ""))
        cnvs = _read_circos_intervals(kwargs.get("cnv_track", ""), value_column=True)
        outer_gap = _coerce_float(kwargs.get("outer_gap", 2.0), 2.0)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 10.0),
            kwargs.get("height", 10.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Circos Plot") or "Circos Plot")

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"circos_plot.{output_format}"
        if output_format == "svg":
            _render_circos_svg(
                output_path,
                chromosomes=chromosomes,
                genes=genes,
                variants=variants,
                cnvs=cnvs,
                title=title,
                outer_gap=outer_gap,
                layout=layout,
            )
        else:
            _render_circos_png(
                output_path,
                chromosomes=chromosomes,
                genes=genes,
                variants=variants,
                cnvs=cnvs,
                outer_gap=outer_gap,
                layout=layout,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Circos Plot")

        return {"outputs": {"circos_image": str(output_path)}}


class IGVSnapshotNode(BaseNode):
    """Create an IGV-style static genome browser snapshot."""

    NODE_ID = "igv_snapshot"
    DISPLAY_NAME = "IGV Snapshot"
    CATEGORY = "visualization"
    DESCRIPTION = "Generate IGV-style multi-track genome browser snapshots with coverage, variants, and annotations."
    SEARCH_ALIASES = ["igv", "genome browser", "browser view", "genome snapshot", "track viewer", "multi-track"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("snapshot_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "region": ("STRING", {"default": "chr1:1-1000"}),
            },
            "optional": {
                "bam_track": ("FILE", {"default": "", "description": "BAM/CRAM track; requires pysam when used"}),
                "variant_track": ("FILE", {"default": "", "description": "VCF variant track"}),
                "annotation_track": ("FILE", {"default": "", "description": "GTF/GFF/BED annotation track"}),
                "bigwig_track": ("FILE", {"default": "", "description": "BigWig/bedGraph signal track"}),
                "title": ("STRING", {"default": "Genome Browser View"}),
                "track_height": ("INT", {"default": 2, "min": 1, "max": 10}),
                "window": ("INT", {"default": 50, "min": 1, "max": 100000}),
                "format": (list(SUPPORTED_IMAGE_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 18.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in SUPPORTED_IMAGE_FORMATS:
            raise ValueError(f"Unsupported IGV snapshot format: {output_format}")

        region = _parse_region(str(kwargs.get("region", "") or ""))
        window = max(_coerce_int(kwargs.get("window", 50), 50), 1)
        coverage: list[CoverageBin] = []
        bam_track = str(kwargs.get("bam_track", "") or "").strip()
        bigwig_track = str(kwargs.get("bigwig_track", "") or "").strip()
        if bam_track:
            coverage.extend(_read_igv_coverage(bam_track, region=region, window=window))
        if bigwig_track:
            coverage.extend(_read_igv_coverage(bigwig_track, region=region, window=window))
        variants = _read_igv_variants(kwargs.get("variant_track", ""), region=region)
        annotations = _read_igv_annotations(kwargs.get("annotation_track", ""), region=region)
        if not coverage and not variants and not annotations:
            raise ValueError("At least one IGV snapshot track must be provided")

        track_count = sum(1 for items in (coverage, variants, annotations) if items)
        track_height = max(_coerce_int(kwargs.get("track_height", 2), 2), 1)
        height_inches = max(3.0, 1.2 + track_count * track_height)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 18.0),
            height_inches,
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Genome Browser View") or "Genome Browser View")

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"igv_snapshot.{output_format}"
        if output_format == "svg":
            _render_igv_svg(
                output_path,
                region=region,
                coverage=coverage,
                variants=variants,
                annotations=annotations,
                title=title,
                layout=layout,
            )
        else:
            _render_igv_png(
                output_path,
                region=region,
                coverage=coverage,
                variants=variants,
                annotations=annotations,
                layout=layout,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="IGV Snapshot")

        return {"outputs": {"snapshot_image": str(output_path)}}


class BarChartNode(BaseNode):
    """Create a bar chart from a CSV/TSV table."""

    NODE_ID = "bar_chart"
    DISPLAY_NAME = "Bar Chart"
    CATEGORY = "visualization"
    DESCRIPTION = "Create bar charts from CSV/TSV tables with optional grouping and orientation."
    SEARCH_ALIASES = ["bar", "barchart", "column chart", "categorical plot", "counts"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("chart_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV/TSV table with categorical values"}),
                "x_column": ("STRING", {"default": ""}),
                "y_column": ("STRING", {"default": ""}),
            },
            "optional": {
                "group_column": ("STRING", {"default": ""}),
                "title": ("STRING", {"default": "Bar Chart"}),
                "orientation": ("STRING", {"default": "vertical", "options": ["vertical", "horizontal"]}),
                "color": ("STRING", {"default": "steelblue"}),
                "format": (list(BAR_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 6.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "show_values": ("BOOLEAN", {"default": True}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in BAR_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported bar chart format: {output_format}")

        x_column = str(kwargs.get("x_column", "") or "").strip()
        y_column = str(kwargs.get("y_column", "") or "").strip()
        group_column = str(kwargs.get("group_column", "") or "").strip()
        if not x_column or not y_column:
            raise ValueError("Bar chart requires x_column and y_column")
        orientation = str(kwargs.get("orientation", "vertical") or "vertical").strip().lower()
        if orientation not in {"vertical", "horizontal"}:
            raise ValueError(f"Unsupported bar chart orientation: {orientation}")

        rows = _read_bar_rows(
            Path(str(kwargs["table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            x_column=x_column,
            y_column=y_column,
            group_column=group_column,
        )
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 10.0),
            kwargs.get("height", 6.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        title = str(kwargs.get("title", "Bar Chart") or "Bar Chart")
        color = str(kwargs.get("color", "steelblue") or "steelblue")
        show_values = bool(kwargs.get("show_values", True))

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"bar_chart.{output_format}"
        if output_format == "svg":
            _render_bar_svg(
                output_path,
                rows=rows,
                layout=layout,
                title=title,
                orientation=orientation,
                color=color,
                show_values=show_values,
            )
        elif output_format == "html":
            _render_bar_html(
                output_path,
                rows=rows,
                bounds=_bar_value_range(rows),
                layout=layout,
                title=title,
                orientation=orientation,
                color=color,
                show_values=show_values,
            )
        else:
            _render_bar_png(
                output_path,
                rows=rows,
                layout=layout,
                orientation=orientation,
                color=color,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Bar Chart")

        return {"outputs": {"chart_image": str(output_path)}}


class VolcanoPlotNode(BaseNode):
    """Create a volcano plot from differential-expression results."""

    NODE_ID = "volcano_plot"
    DISPLAY_NAME = "Volcano Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Highlight significant genes by log fold change and -log10(p-value)."
    SEARCH_ALIASES = ["volcano", "differential expression", "deseq2", "rna-seq", "plot"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("volcano_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "results_table": ("FILE", {"description": "CSV/TSV table with differential-expression results"}),
                "logfc_column": ("STRING", {"default": "log2FoldChange"}),
                "pvalue_column": ("STRING", {"default": "padj"}),
            },
            "optional": {
                "gene_column": ("STRING", {"default": ""}),
                "logfc_threshold": ("FLOAT", {"default": 1.0, "min": 0.0}),
                "pvalue_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "title": ("STRING", {"default": "Volcano Plot"}),
                "label_top_n": ("INT", {"default": 10, "min": 0, "max": 100}),
                "up_color": ("STRING", {"default": DEFAULT_UP_COLOR}),
                "down_color": ("STRING", {"default": DEFAULT_DOWN_COLOR}),
                "ns_color": ("STRING", {"default": DEFAULT_NS_COLOR}),
                "format": (list(VOLCANO_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 8.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 6.0, "min": 1.0}),
                "dpi": ("INT", {"default": DEFAULT_DPI, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in VOLCANO_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported volcano plot format: {output_format}")

        logfc_column = str(kwargs.get("logfc_column", "log2FoldChange") or "log2FoldChange").strip()
        pvalue_column = str(kwargs.get("pvalue_column", "padj") or "padj").strip()
        gene_column = str(kwargs.get("gene_column", "") or "").strip()
        if not logfc_column or not pvalue_column:
            raise ValueError("Volcano plot requires logfc_column and pvalue_column")

        logfc_threshold = _coerce_float(kwargs.get("logfc_threshold", 1.0), 1.0)
        pvalue_threshold = _coerce_float(kwargs.get("pvalue_threshold", 0.05), 0.05)
        if logfc_threshold < 0:
            raise ValueError("logfc_threshold must be non-negative")
        if pvalue_threshold <= 0:
            raise ValueError("pvalue_threshold must be greater than zero")

        rows = _read_result_rows(
            Path(str(kwargs["results_table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            logfc_column=logfc_column,
            pvalue_column=pvalue_column,
            gene_column=gene_column,
        )
        points = _classify_points(
            rows,
            logfc_threshold=logfc_threshold,
            pvalue_threshold=pvalue_threshold,
        )
        bounds = _plot_bounds(
            points,
            logfc_threshold=logfc_threshold,
            pvalue_threshold=pvalue_threshold,
        )
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 8.0),
            kwargs.get("height", 6.0),
            kwargs.get("dpi", DEFAULT_DPI),
        )
        layout = _layout(width_px, height_px)
        colours = _colour_map(
            _normalise_hex_color(kwargs.get("up_color", DEFAULT_UP_COLOR), DEFAULT_UP_COLOR),
            _normalise_hex_color(kwargs.get("down_color", DEFAULT_DOWN_COLOR), DEFAULT_DOWN_COLOR),
            _normalise_hex_color(kwargs.get("ns_color", DEFAULT_NS_COLOR), DEFAULT_NS_COLOR),
        )

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"volcano_plot.{output_format}"
        title = str(kwargs.get("title", "Volcano Plot") or "Volcano Plot")
        label_top_n = _coerce_int(kwargs.get("label_top_n", 10), 10)
        if output_format == "svg":
            _render_svg(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                logfc_threshold=logfc_threshold,
                title=title,
                label_top_n=label_top_n,
                colours=colours,
            )
        elif output_format == "html":
            _render_volcano_html(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                logfc_threshold=logfc_threshold,
                title=title,
                label_top_n=label_top_n,
                colours=colours,
            )
        else:
            _render_png(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                logfc_threshold=logfc_threshold,
                colours=colours,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Volcano Plot")

        return {"outputs": {"volcano_image": str(output_path)}}


class MAPlotNode(BaseNode):
    """Create an MA plot from differential-expression results."""

    NODE_ID = "ma_plot"
    DISPLAY_NAME = "MA Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Show log fold change against mean expression with significance highlighting."
    SEARCH_ALIASES = ["ma plot", "mean difference", "differential expression", "deseq2", "rna-seq"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("ma_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "results_table": ("FILE", {"description": "CSV/TSV table with differential-expression results"}),
                "mean_column": ("STRING", {"default": "baseMean"}),
                "logfc_column": ("STRING", {"default": "log2FoldChange"}),
                "pvalue_column": ("STRING", {"default": "padj"}),
            },
            "optional": {
                "gene_column": ("STRING", {"default": ""}),
                "logfc_threshold": ("FLOAT", {"default": 1.0, "min": 0.0}),
                "pvalue_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "title": ("STRING", {"default": "MA Plot"}),
                "sig_color": ("STRING", {"default": DEFAULT_UP_COLOR}),
                "ns_color": ("STRING", {"default": DEFAULT_NS_COLOR}),
                "label_top_n": ("INT", {"default": 10, "min": 0, "max": 100}),
                "format": (list(MA_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 10.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 8.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in MA_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported MA plot format: {output_format}")

        mean_column = str(kwargs.get("mean_column", "baseMean") or "baseMean").strip()
        logfc_column = str(kwargs.get("logfc_column", "log2FoldChange") or "log2FoldChange").strip()
        pvalue_column = str(kwargs.get("pvalue_column", "padj") or "padj").strip()
        gene_column = str(kwargs.get("gene_column", "") or "").strip()
        if not mean_column or not logfc_column or not pvalue_column:
            raise ValueError("MA plot requires mean_column, logfc_column, and pvalue_column")

        logfc_threshold = _coerce_float(kwargs.get("logfc_threshold", 1.0), 1.0)
        pvalue_threshold = _coerce_float(kwargs.get("pvalue_threshold", 0.05), 0.05)
        if logfc_threshold < 0:
            raise ValueError("logfc_threshold must be non-negative")
        if pvalue_threshold <= 0:
            raise ValueError("pvalue_threshold must be greater than zero")

        rows = _read_ma_rows(
            Path(str(kwargs["results_table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            mean_column=mean_column,
            logfc_column=logfc_column,
            pvalue_column=pvalue_column,
            gene_column=gene_column,
        )
        points = _classify_ma_points(
            rows,
            logfc_threshold=logfc_threshold,
            pvalue_threshold=pvalue_threshold,
        )
        bounds = _ma_bounds(points, logfc_threshold=logfc_threshold)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 10.0),
            kwargs.get("height", 8.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        significant_color = _normalise_hex_color(kwargs.get("sig_color", DEFAULT_UP_COLOR), DEFAULT_UP_COLOR)
        ns_color = _normalise_hex_color(kwargs.get("ns_color", DEFAULT_NS_COLOR), DEFAULT_NS_COLOR)

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"ma_plot.{output_format}"
        title = str(kwargs.get("title", "MA Plot") or "MA Plot")
        label_top_n = _coerce_int(kwargs.get("label_top_n", 10), 10)
        if output_format == "svg":
            _render_ma_svg(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                logfc_threshold=logfc_threshold,
                title=title,
                label_top_n=label_top_n,
                significant_color=significant_color,
                ns_color=ns_color,
            )
        elif output_format == "html":
            _render_ma_html(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                logfc_threshold=logfc_threshold,
                title=title,
                label_top_n=label_top_n,
                significant_color=significant_color,
                ns_color=ns_color,
            )
        else:
            _render_ma_png(
                output_path,
                points=points,
                bounds=bounds,
                layout=layout,
                logfc_threshold=logfc_threshold,
                significant_color=significant_color,
                ns_color=ns_color,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="MA Plot")

        return {"outputs": {"ma_image": str(output_path)}}


class ScatterPlotNode(BaseNode):
    """Create an XY scatter plot from a CSV/TSV table."""

    NODE_ID = "scatter_plot"
    DISPLAY_NAME = "Scatter Plot"
    CATEGORY = "visualization"
    DESCRIPTION = "Create XY scatter plots with optional color, size, and regression overlays."
    SEARCH_ALIASES = ["scatter", "scatterplot", "correlation", "xy plot", "pca plot", "bubble chart"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("plot_image",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = False

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV/TSV table with numeric X and Y columns"}),
                "x_column": ("STRING", {"default": ""}),
                "y_column": ("STRING", {"default": ""}),
            },
            "optional": {
                "color_column": ("STRING", {"default": ""}),
                "size_column": ("STRING", {"default": ""}),
                "title": ("STRING", {"default": "Scatter Plot"}),
                "xlabel": ("STRING", {"default": ""}),
                "ylabel": ("STRING", {"default": ""}),
                "palette": ("STRING", {"default": "default"}),
                "regression": ("BOOLEAN", {"default": False}),
                "alpha": ("FLOAT", {"default": 0.6, "min": 0.1, "max": 1.0}),
                "point_size": ("INT", {"default": 30, "min": 5, "max": 200}),
                "format": (list(SCATTER_OUTPUT_FORMATS), {"default": "png"}),
                "width": ("FLOAT", {"default": 8.0, "min": 1.0}),
                "height": ("FLOAT", {"default": 7.0, "min": 1.0}),
                "dpi": ("INT", {"default": 150, "min": 30, "max": 600}),
                "delimiter": ("STRING", {"default": "auto"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        output_format = str(kwargs.get("format", "png") or "png").strip().lower()
        if output_format not in SCATTER_OUTPUT_FORMATS:
            raise ValueError(f"Unsupported scatter plot format: {output_format}")

        x_column = str(kwargs.get("x_column", "") or "").strip()
        y_column = str(kwargs.get("y_column", "") or "").strip()
        color_column = str(kwargs.get("color_column", "") or "").strip()
        size_column = str(kwargs.get("size_column", "") or "").strip()
        if not x_column or not y_column:
            raise ValueError("Scatter plot requires x_column and y_column")

        rows = _read_scatter_rows(
            Path(str(kwargs["table"])),
            delimiter=kwargs.get("delimiter", "auto"),
            x_column=x_column,
            y_column=y_column,
            color_column=color_column,
            size_column=size_column,
        )
        bounds = _xy_bounds(rows)
        width_px, height_px = _pixel_dimensions(
            kwargs.get("width", 8.0),
            kwargs.get("height", 7.0),
            kwargs.get("dpi", 150),
        )
        layout = _layout(width_px, height_px)
        point_size = _coerce_int(kwargs.get("point_size", 30), 30)
        alpha = _coerce_float(kwargs.get("alpha", 0.6), 0.6)
        regression = bool(kwargs.get("regression", False))
        title = str(kwargs.get("title", "Scatter Plot") or "Scatter Plot")
        xlabel = str(kwargs.get("xlabel", "") or x_column)
        ylabel = str(kwargs.get("ylabel", "") or y_column)

        out_dir = _node_output_dir(self, context)
        output_path = out_dir / f"scatter_plot.{output_format}"
        if output_format == "svg":
            _render_scatter_svg(
                output_path,
                points=rows,
                bounds=bounds,
                layout=layout,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                color_column=color_column,
                point_size=point_size,
                alpha=alpha,
                regression=regression,
            )
        elif output_format == "html":
            _render_scatter_html(
                output_path,
                points=rows,
                bounds=bounds,
                layout=layout,
                title=title,
                xlabel=xlabel,
                ylabel=ylabel,
                color_column=color_column,
                size_column=size_column,
                point_size=point_size,
                alpha=alpha,
                regression=regression,
            )
        else:
            _render_scatter_png(
                output_path,
                points=rows,
                bounds=bounds,
                layout=layout,
                color_column=color_column,
                point_size=point_size,
                regression=regression,
            )

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(output_path, label="Scatter Plot")

        return {"outputs": {"plot_image": str(output_path)}}
