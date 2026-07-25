#!/usr/bin/env python3
"""Remove host-specific vcf2bff metadata and emit deterministic NDJSON."""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path
from typing import Any, TextIO


RUNTIME_KEYS = {
    "cwd",
    "filein",
    "fileout",
    "hostname",
    "ncpuhost",
    "projectDir",
    "user",
}


def _open_input(path: Path) -> TextIO:
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return path.open(encoding="utf-8")


def canonicalize(record: dict[str, Any]) -> dict[str, Any]:
    runtime = record.get("_info", {}).get("vcf2bff")
    if isinstance(runtime, dict):
        for key in RUNTIME_KEYS:
            runtime.pop(key, None)
    return record


def main() -> int:
    source, destination = map(Path, sys.argv[1:3])
    with _open_input(source) as input_handle, destination.open("w", encoding="utf-8", newline="\n") as output_handle:
        for line in input_handle:
            if not line.strip():
                continue
            record = canonicalize(json.loads(line))
            output_handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")))
            output_handle.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
