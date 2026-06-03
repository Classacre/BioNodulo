"""Summarize Panacus histgrowth tables for BioNodulo pangenome stats nodes."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import TextIO


def _numeric_values(row: dict[str, str]) -> list[float]:
    values: list[float] = []
    for value in row.values():
        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue
    return values


def summarize_table(handle: TextIO, core_threshold: float, shell_threshold: float) -> dict[str, object]:
    rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        return {
            "rows": 0,
            "core_threshold": core_threshold,
            "shell_threshold": shell_threshold,
            "core_features": 0,
            "shell_features": 0,
            "cloud_features": 0,
            "max_observed": 0,
        }

    maxima = [max(_numeric_values(row), default=0.0) for row in rows]
    max_observed = max(maxima, default=0.0)
    denominator = max_observed or 1.0

    core_cutoff = core_threshold * denominator
    shell_cutoff = shell_threshold * denominator
    core_features = sum(1 for value in maxima if value >= core_cutoff)
    shell_features = sum(1 for value in maxima if shell_cutoff <= value < core_cutoff)
    cloud_features = sum(1 for value in maxima if value < shell_cutoff)

    return {
        "rows": len(rows),
        "core_threshold": core_threshold,
        "shell_threshold": shell_threshold,
        "core_features": core_features,
        "shell_features": shell_features,
        "cloud_features": cloud_features,
        "max_observed": max_observed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--core-threshold", required=True, type=float)
    parser.add_argument("--shell-threshold", required=True, type=float)
    args = parser.parse_args()

    with args.input.open("r", encoding="utf-8", newline="") as handle:
        summary = summarize_table(handle, args.core_threshold, args.shell_threshold)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
