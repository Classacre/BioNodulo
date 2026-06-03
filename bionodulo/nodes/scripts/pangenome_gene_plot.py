"""Create a lightweight SVG summary plot for Panaroo presence/absence matrices."""
from __future__ import annotations

import argparse
import csv
from pathlib import Path


def _presence_counts(matrix_path: Path) -> list[tuple[str, int]]:
    with matrix_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle, delimiter="\t")
        header = next(reader, [])
        sample_count = max(len(header) - 1, 1)
        counts: list[tuple[str, int]] = []
        for index, row in enumerate(reader, start=1):
            if not row:
                continue
            gene = row[0] or f"gene_{index}"
            present = sum(1 for value in row[1:] if value not in {"", "0", "False", "false", "NA"})
            counts.append((gene, present))
        if not counts:
            return [("no_genes", 0)]
        return [(gene, min(count, sample_count)) for gene, count in counts]


def write_svg(matrix_path: Path, output_path: Path) -> None:
    counts = _presence_counts(matrix_path)
    top_counts = counts[:50]
    max_count = max((count for _, count in top_counts), default=1) or 1
    width = 900
    bar_height = 14
    row_gap = 6
    left_margin = 190
    top_margin = 36
    height = top_margin + len(top_counts) * (bar_height + row_gap) + 24

    rows = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<text x="24" y="24" font-family="sans-serif" font-size="16" font-weight="700">Gene presence summary</text>',
    ]
    for index, (gene, count) in enumerate(top_counts):
        y = top_margin + index * (bar_height + row_gap)
        bar_width = int((width - left_margin - 60) * count / max_count)
        rows.extend([
            f'<text x="24" y="{y + 11}" font-family="sans-serif" font-size="11" fill="#2f3a45">{gene[:24]}</text>',
            f'<rect x="{left_margin}" y="{y}" width="{bar_width}" height="{bar_height}" fill="#328d7a"/>',
            f'<text x="{left_margin + bar_width + 8}" y="{y + 11}" font-family="sans-serif" font-size="11" fill="#2f3a45">{count}</text>',
        ])
    rows.append("</svg>")
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    write_svg(args.input, args.output)


if __name__ == "__main__":
    main()
