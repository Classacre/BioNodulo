"""Acquire exact typed CWL source links from a hash-verified bio.tools snapshot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bionodulo.nodes.generation.source_links import acquire_typed_cwl


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--max-requests", type=int, default=None)
    args = parser.parse_args()
    summary = acquire_typed_cwl(
        args.snapshot,
        args.manifest,
        args.output,
        timeout=args.timeout,
        delay=args.delay,
        max_requests=args.max_requests,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
