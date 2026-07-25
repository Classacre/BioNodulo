"""Statistical normalization node for tabular data."""
from __future__ import annotations

import csv
import math
import statistics
from pathlib import Path
from typing import Any

from .adapter import PythonDataTransformNode


class NormalizeDataNode(PythonDataTransformNode):
    """Apply statistical normalization to numeric table columns."""

    NODE_ID = "normalize_data"
    DISPLAY_NAME = "Normalize Data"
    CATEGORY = "data_transform"
    DESCRIPTION = (
        "Apply statistical normalization to numeric table data: min-max, z-score, "
        "MAD z-score, quantile, log transforms, CPM, TPM-like scaling, and CLR."
    )
    SEARCH_ALIASES = [
        "normalize",
        "standardize",
        "scale",
        "z-score",
        "min-max",
        "quantile normalize",
        "log transform",
        "cpm",
        "tpm",
        "clr",
        "centered log ratio",
    ]
    RETURN_TYPES = ("CSV",)
    RETURN_NAMES = ("normalized_table",)
    REQUIRES_EXTERNAL_TOOLS = False
    VERSION = "1.0.0"
    PRODUCT_SOURCE_COMMIT = "45518cfd3754b40ae44304bd65bc17d5ee6e2816"
    PRODUCT_SOURCE_PATH = "bionodulo/nodes/builtin/data_transform_family/normalize_data.py"
    PRODUCT_SOURCE_SYMBOL = "NormalizeDataNode"
    GIT_URL = "https://github.com/Classacre/BioNodulo.git"
    GIT_COMMIT = PRODUCT_SOURCE_COMMIT
    SOURCE_URL = (
        f"https://github.com/Classacre/BioNodulo/blob/{PRODUCT_SOURCE_COMMIT}/"
        f"{PRODUCT_SOURCE_PATH}"
    )
    UPSTREAM_SOURCE = f"{PRODUCT_SOURCE_PATH}:{PRODUCT_SOURCE_SYMBOL}"
    DOCUMENTATION_URL = "https://docs.python.org/3.12/library/statistics.html"
    RUNTIME_DOCUMENTATION_URLS = (
        DOCUMENTATION_URL,
        "https://docs.python.org/3.12/library/math.html",
        "https://docs.python.org/3.12/library/csv.html",
    )
    SOURCE_AUTHORITIES = {
        "product_contract": SOURCE_URL,
        "python_statistics_runtime": RUNTIME_DOCUMENTATION_URLS[0],
        "python_math_runtime": RUNTIME_DOCUMENTATION_URLS[1],
        "python_csv_runtime": RUNTIME_DOCUMENTATION_URLS[2],
    }
    EXIT_SEMANTICS = (
        "This in-process node has no subprocess exit code; unsupported modes, malformed numeric "
        "values, invalid domains, missing columns, and file I/O errors raise before success."
    )

    _METHODS = [
        "min_max",
        "z_score",
        "z_score_mad",
        "quantile",
        "log2",
        "log10",
        "log1p",
        "cpm",
        "tpm_from_counts",
        "clr",
    ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "table": ("FILE", {"description": "CSV or TSV table with numeric data"}),
                "method": ("STRING", {"default": "z_score", "options": cls._METHODS}),
            },
            "optional": {
                "id_columns": ("STRING", {"default": ""}),
                "axis": ("STRING", {"default": "columns", "options": ["columns", "rows"]}),
                "pseudocount": ("FLOAT", {"default": 1.0, "min": 0.0, "max": 1000.0}),
                "min_max_range": ("STRING", {"default": "0,1"}),
                "output_type": ("STRING", {"default": "AUTO", "options": ["AUTO", "CSV", "TSV"]}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        context = kwargs.pop("context", None)
        input_path = Path(str(kwargs["table"]))
        input_delim = "," if input_path.suffix.lower() == ".csv" else "\t"
        fieldnames, rows = self._read_table(input_path, input_delim)
        method = str(kwargs.get("method", "z_score") or "z_score")
        if method not in self._METHODS:
            raise ValueError(f"Unsupported normalization method: {method}")

        id_columns = self._split_csv(str(kwargs.get("id_columns", "")))
        missing_ids = [column for column in id_columns if column not in fieldnames]
        if missing_ids:
            raise ValueError(f"ID column(s) not found: {', '.join(missing_ids)}")
        numeric_columns = [column for column in fieldnames if column not in id_columns]
        matrix = [[self._as_number(row.get(column, "")) for column in numeric_columns] for row in rows]
        axis = str(kwargs.get("axis", "columns") or "columns")

        if method == "min_max":
            normalised = self._min_max(matrix, axis, str(kwargs.get("min_max_range", "0,1") or "0,1"))
        elif method == "z_score":
            normalised = self._z_score(matrix, axis)
        elif method == "z_score_mad":
            normalised = self._z_score_mad(matrix, axis)
        elif method == "quantile":
            normalised = self._quantile(matrix)
        elif method in {"log2", "log10", "log1p"}:
            normalised = self._log_transform(matrix, method, float(kwargs.get("pseudocount", 1.0) or 0.0))
        elif method == "cpm":
            normalised = self._cpm(matrix)
        elif method == "tpm_from_counts":
            normalised = self._tpm_like(matrix)
        elif method == "clr":
            normalised = self._clr(matrix, axis, float(kwargs.get("pseudocount", 1.0) or 1.0))
        else:
            raise ValueError(f"Unsupported normalization method: {method}")

        output_rows = []
        for row_index, row in enumerate(rows):
            output_row: dict[str, Any] = {column: row.get(column, "") for column in id_columns}
            for column_index, column in enumerate(numeric_columns):
                output_row[column] = normalised[row_index][column_index]
            output_rows.append(output_row)

        output_delim, extension = self._output_format(str(kwargs.get("output_type", "AUTO") or "AUTO"), input_path)
        output_path = self._output_dir(context) / f"{input_path.stem}.norm_{method}{extension}"
        self._write_table(output_path, id_columns + numeric_columns, output_rows, output_delim)
        return (str(output_path),)

    @staticmethod
    def _read_table(path: Path, delimiter: str) -> tuple[list[str], list[dict[str, str]]]:
        with path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter=delimiter)
            if reader.fieldnames is None:
                raise ValueError(f"Table has no header row: {path}")
            return list(reader.fieldnames), [dict(row) for row in reader]

    @staticmethod
    def _write_table(path: Path, fieldnames: list[str], rows: list[dict[str, Any]], delimiter: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames, delimiter=delimiter, extrasaction="ignore")
            writer.writeheader()
            for row in rows:
                writer.writerow({field: NormalizeDataNode._format_scalar(row.get(field, "")) for field in fieldnames})

    @classmethod
    def _min_max(cls, matrix: list[list[float]], axis: str, range_value: str) -> list[list[float]]:
        target_min, target_max = [float(part.strip()) for part in range_value.split(",", 1)]
        return cls._apply_axis(matrix, axis, lambda values: cls._scale_min_max(values, target_min, target_max))

    @classmethod
    def _z_score(cls, matrix: list[list[float]], axis: str) -> list[list[float]]:
        return cls._apply_axis(matrix, axis, cls._scale_z_score)

    @classmethod
    def _z_score_mad(cls, matrix: list[list[float]], axis: str) -> list[list[float]]:
        return cls._apply_axis(matrix, axis, cls._scale_mad)

    @staticmethod
    def _quantile(matrix: list[list[float]]) -> list[list[float]]:
        if not matrix:
            return []
        columns = list(zip(*matrix))
        sorted_columns = [sorted(column) for column in columns]
        rank_means = [
            sum(sorted_column[rank] for sorted_column in sorted_columns) / len(sorted_columns)
            for rank in range(len(matrix))
        ]
        normalised_columns: list[list[float]] = []
        for column in columns:
            order = sorted(range(len(column)), key=lambda index: column[index])
            output = [0.0] * len(column)
            for rank, row_index in enumerate(order):
                output[row_index] = rank_means[rank]
            normalised_columns.append(output)
        return [list(row) for row in zip(*normalised_columns)]

    @staticmethod
    def _log_transform(matrix: list[list[float]], method: str, pseudocount: float) -> list[list[float]]:
        result: list[list[float]] = []
        for row in matrix:
            if method == "log1p":
                result.append([math.log1p(value) for value in row])
            elif method == "log2":
                result.append([math.log2(value + pseudocount) for value in row])
            elif method == "log10":
                result.append([math.log10(value + pseudocount) for value in row])
        return result

    @staticmethod
    def _cpm(matrix: list[list[float]]) -> list[list[float]]:
        if not matrix:
            return []
        column_sums = [sum(row[index] for row in matrix) or 1.0 for index in range(len(matrix[0]))]
        return [
            [value / column_sums[index] * 1_000_000 for index, value in enumerate(row)]
            for row in matrix
        ]

    @classmethod
    def _tpm_like(cls, matrix: list[list[float]]) -> list[list[float]]:
        cpm = cls._cpm(matrix)
        if not cpm:
            return []
        column_sums = [sum(row[index] for row in cpm) or 1.0 for index in range(len(cpm[0]))]
        return [
            [value / column_sums[index] * 1_000_000 for index, value in enumerate(row)]
            for row in cpm
        ]

    @classmethod
    def _clr(cls, matrix: list[list[float]], axis: str, pseudocount: float) -> list[list[float]]:
        adjusted = [[value if value > 0 else pseudocount for value in row] for row in matrix]
        return cls._apply_axis(adjusted, axis, cls._scale_clr)

    @staticmethod
    def _apply_axis(
        matrix: list[list[float]],
        axis: str,
        transform: Any,
    ) -> list[list[float]]:
        if not matrix:
            return []
        if axis == "columns":
            return [transform(row) for row in matrix]
        if axis == "rows":
            columns = list(zip(*matrix))
            transformed_columns = [transform(list(column)) for column in columns]
            return [list(row) for row in zip(*transformed_columns)]
        raise ValueError(f"Unsupported normalization axis: {axis}")

    @staticmethod
    def _scale_min_max(values: list[float], target_min: float, target_max: float) -> list[float]:
        source_min = min(values)
        source_max = max(values)
        if source_max == source_min:
            return [target_min for _value in values]
        return [
            ((value - source_min) / (source_max - source_min)) * (target_max - target_min) + target_min
            for value in values
        ]

    @staticmethod
    def _scale_z_score(values: list[float]) -> list[float]:
        mean = sum(values) / len(values)
        if len(values) <= 1:
            return [0.0 for _value in values]
        std = statistics.stdev(values)
        if std == 0:
            return [0.0 for _value in values]
        return [(value - mean) / std for value in values]

    @staticmethod
    def _scale_mad(values: list[float]) -> list[float]:
        median = statistics.median(values)
        deviations = [abs(value - median) for value in values]
        mad = statistics.median(deviations) * 1.4826
        if mad == 0:
            return [0.0 for _value in values]
        return [(value - median) / mad for value in values]

    @staticmethod
    def _scale_clr(values: list[float]) -> list[float]:
        logs = [math.log(value) for value in values]
        mean_log = sum(logs) / len(logs)
        return [log_value - mean_log for log_value in logs]

    @staticmethod
    def _split_csv(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]

    @staticmethod
    def _as_number(value: str) -> float:
        return float(str(value).strip())

    @staticmethod
    def _format_scalar(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, float):
            if math.isfinite(value) and value.is_integer():
                return str(int(value))
            return str(value)
        return str(value)

    @classmethod
    def _output_dir(cls, context: Any) -> Path:
        base = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = base / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    @staticmethod
    def _output_format(output_type: str, input_path: Path) -> tuple[str, str]:
        normalized = output_type.upper()
        if normalized == "CSV":
            return ",", ".csv"
        if normalized == "TSV":
            return "\t", ".tsv"
        if normalized == "AUTO":
            return (",", ".csv") if input_path.suffix.lower() == ".csv" else ("\t", ".tsv")
        raise ValueError(f"Unsupported output_type: {output_type}")
