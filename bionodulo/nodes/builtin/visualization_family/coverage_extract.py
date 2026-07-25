"""Extract coverage bins for :mod:`coverage_plot` in its pinned env.

This module intentionally has a tiny stdlib-only outer interface.  It is
launched by ``CoveragePlotNode`` through ``ExecutionContext.run_command`` so
the workflow's prepared Python environment, rather than the worker's base
interpreter, supplies pysam or pyBigWig.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _parse_region(value: str) -> tuple[str, int, int]:
    chromosome, span = value.strip().replace(",", "").split(":", 1)
    start_text, end_text = span.split("-", 1)
    start, end = int(start_text), int(end_text)
    if not chromosome or start < 0 or end <= start:
        raise ValueError("region must use chrom:start-end with end > start")
    return chromosome, start, end


def _bam_bins(
    path: Path,
    region: tuple[str, int, int],
    window_size: int,
    index_path: Path | None,
    reference_path: Path | None,
) -> list[dict[str, object]]:
    try:
        import pysam  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pysam is required for BAM/CRAM coverage") from exc
    chromosome, region_start, region_end = region
    kwargs: dict[str, str] = {}
    if index_path is not None:
        kwargs["index_filename"] = str(index_path)
    if reference_path is not None:
        kwargs["reference_filename"] = str(reference_path)
    rows: list[dict[str, object]] = []
    with pysam.AlignmentFile(str(path), "rb", **kwargs) as alignment:
        for start in range(region_start, region_end, max(window_size, 1)):
            end = min(start + max(window_size, 1), region_end)
            total = 0
            for pileup in alignment.pileup(chromosome, start, end, truncate=True):
                total += pileup.nsegments
            rows.append(
                {
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "coverage": total / max(1, end - start),
                }
            )
    return rows


def _bigwig_bins(
    path: Path,
    region: tuple[str, int, int],
    window_size: int,
) -> list[dict[str, object]]:
    try:
        import pyBigWig  # type: ignore[import-not-found]
    except ImportError as exc:
        raise RuntimeError("pyBigWig is required for BigWig coverage") from exc
    chromosome, region_start, region_end = region
    rows: list[dict[str, object]] = []
    handle = pyBigWig.open(str(path))
    try:
        for start in range(region_start, region_end, max(window_size, 1)):
            end = min(start + max(window_size, 1), region_end)
            value = handle.stats(chromosome, start, end, type="mean")[0]
            rows.append(
                {
                    "chromosome": chromosome,
                    "start": start,
                    "end": end,
                    "coverage": 0.0 if value is None else max(0.0, float(value)),
                }
            )
    finally:
        handle.close()
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--region", required=True)
    parser.add_argument("--window-size", required=True, type=int)
    parser.add_argument("--index", type=Path)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not args.input.is_file():
        raise FileNotFoundError(f"coverage input not found: {args.input}")
    region = _parse_region(args.region)
    suffixes = {suffix.lower() for suffix in args.input.suffixes}
    if suffixes & {".bam", ".cram"}:
        rows = _bam_bins(args.input, region, args.window_size, args.index, args.reference)
    elif suffixes & {".bw", ".bigwig"}:
        rows = _bigwig_bins(args.input, region, args.window_size)
    else:
        raise ValueError(f"unsupported extraction input: {args.input}")
    if not rows:
        raise ValueError("coverage extractor produced no bins")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(rows, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
