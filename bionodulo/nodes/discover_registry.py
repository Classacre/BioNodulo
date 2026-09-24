"""CLI for complete, evidence-only bio.tools executable-source discovery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from bionodulo.nodes.generation.discovery import (
    discover_iuc_with_official_parser,
    discover_registry,
    inventory_iuc_repository,
    verified_registry_accessions,
    write_discovery_summary,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--iuc-repository", type=Path)
    parser.add_argument("--iuc-revision")
    parser.add_argument("--iuc-source-url", default="https://github.com/galaxyproject/tools-iuc")
    parser.add_argument("--parse-iuc-official", action="store_true")
    parser.add_argument("--iuc-staging", type=Path)
    args = parser.parse_args(argv)
    if (args.iuc_repository is None) != (args.iuc_revision is None):
        parser.error("--iuc-repository and --iuc-revision must be supplied together")
    if args.parse_iuc_official and (args.iuc_repository is None or args.iuc_staging is None):
        parser.error("--parse-iuc-official requires --iuc-repository, --iuc-revision, and --iuc-staging")
    iuc = None
    if args.iuc_repository is not None:
        iuc = inventory_iuc_repository(
            args.iuc_repository,
            revision=args.iuc_revision,
            source_url=args.iuc_source_url,
        )
    summary = discover_registry(args.snapshot, args.manifest, args.output, iuc=iuc)
    if args.parse_iuc_official:
        assert iuc is not None and args.iuc_repository is not None and args.iuc_staging is not None
        summary["official_galaxy_parser"] = discover_iuc_with_official_parser(
            iuc,
            args.iuc_repository,
            args.iuc_staging,
            args.output,
            registry_accessions=verified_registry_accessions(args.snapshot, args.manifest),
        )
        write_discovery_summary(args.output, summary)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
