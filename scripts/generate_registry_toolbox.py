"""Generate every verified bio.tools record as a lazy toolbox node definition."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bionodulo.nodes.registry_catalog import DEFAULT_CATALOG, generate_catalog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_CATALOG)
    args = parser.parse_args()
    print(json.dumps(generate_catalog(args.snapshot, args.manifest, args.output), indent=2))


if __name__ == "__main__":
    main()
