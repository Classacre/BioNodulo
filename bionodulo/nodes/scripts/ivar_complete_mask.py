"""Expand iVar masked primer names to complete amplicon primer sets."""
from __future__ import annotations

import argparse
from pathlib import Path


def complete_mask_file(masked_path: Path, amplicon_info_path: Path) -> list[str]:
    """Expand masked primers in-place to all primers from affected amplicons."""
    masked_primers = masked_path.read_text(encoding="utf-8").strip().split()
    if not masked_primers:
        masked_path.write_text("\n", encoding="utf-8")
        return []

    amplicons = [
        line.strip().split("\t")
        for line in amplicon_info_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expanded: set[str] = set()
    masked_set = set(masked_primers)
    for amplicon in amplicons:
        if masked_set.intersection(amplicon):
            expanded.update(amplicon)

    result = sorted(expanded)
    masked_path.write_text("\t".join(result) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("masked_primers", type=Path)
    parser.add_argument("amplicon_info", type=Path)
    args = parser.parse_args()

    result = complete_mask_file(args.masked_primers, args.amplicon_info)
    if result:
        print()
        print("Removing reads primed with any of:")
        print("\t".join(result))
    else:
        print()
        print("No affected primer binding sites found!")


if __name__ == "__main__":
    main()
