#!/usr/bin/env python
"""Compare two verified bio.tools snapshots and report what changed.

Answers the playbook requirement to "compare additions, updates, removals, and
absent pages on later syncs" without silently rewriting history. Both snapshots
are ordered by lower-cased accession, so this is a streaming merge join: memory
stays bounded regardless of registry size.

Every record's exact JSON is hashed, so "changed" means the registry content for
that accession differs, not merely that a timestamp moved.

Usage:
    python scripts/diff_registry_snapshots.py \
        --base-dir reports/biotools_registry/current \
        --target-dir reports/biotools_registry/resync \
        --output reports/biotools_registry/snapshot-diff.json
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def record_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_manifest(snapshot_dir: Path) -> dict:
    manifest = json.loads((snapshot_dir / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("complete"):
        raise ValueError(f"{snapshot_dir} is not a complete verified snapshot")
    digest = hashlib.sha256()
    with (snapshot_dir / "registry.jsonl").open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    if digest.hexdigest() != manifest["sha256"]:
        raise ValueError(f"{snapshot_dir} registry.jsonl does not match its manifest hash")
    return manifest


def iterate(snapshot_dir: Path):
    """Yield (casefolded_id, accession, raw_json) in snapshot order."""
    with (snapshot_dir / "registry.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            record = json.loads(line)
            accession = record["biotoolsID"]
            yield accession.lower(), accession, line


def diff(base_dir: Path, target_dir: Path) -> dict:
    base_manifest = load_manifest(base_dir)
    target_manifest = load_manifest(target_dir)

    additions: list[dict] = []
    removals: list[dict] = []
    changed: list[dict] = []
    unchanged = 0
    base_count = 0
    target_count = 0

    base_iter = iterate(base_dir)
    target_iter = iterate(target_dir)
    base_item = next(base_iter, None)
    target_item = next(target_iter, None)

    while base_item is not None or target_item is not None:
        if base_item is None:
            key, accession, raw = target_item
            additions.append({"biotools_id": accession, "raw_sha256": record_hash(raw)})
            target_count += 1
            target_item = next(target_iter, None)
        elif target_item is None:
            key, accession, raw = base_item
            removals.append({"biotools_id": accession, "raw_sha256": record_hash(raw)})
            base_count += 1
            base_item = next(base_iter, None)
        else:
            base_key, base_accession, base_raw = base_item
            target_key, target_accession, target_raw = target_item
            if base_key < target_key:
                removals.append({"biotools_id": base_accession, "raw_sha256": record_hash(base_raw)})
                base_count += 1
                base_item = next(base_iter, None)
            elif base_key > target_key:
                additions.append({"biotools_id": target_accession, "raw_sha256": record_hash(target_raw)})
                target_count += 1
                target_item = next(target_iter, None)
            else:
                base_hash = record_hash(base_raw)
                target_hash = record_hash(target_raw)
                if base_hash != target_hash:
                    changed.append({
                        "biotools_id": target_accession,
                        "base_sha256": base_hash,
                        "target_sha256": target_hash,
                    })
                else:
                    unchanged += 1
                base_count += 1
                target_count += 1
                base_item = next(base_iter, None)
                target_item = next(target_iter, None)

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "base": {
            "dir": str(base_dir).replace("\\", "/"),
            "started_at": base_manifest["started_at"],
            "completed_at": base_manifest["completed_at"],
            "reported_count": base_manifest["records"],
            "sha256": base_manifest["sha256"],
            "pages": base_manifest["pages"],
        },
        "target": {
            "dir": str(target_dir).replace("\\", "/"),
            "started_at": target_manifest["started_at"],
            "completed_at": target_manifest["completed_at"],
            "reported_count": target_manifest["records"],
            "sha256": target_manifest["sha256"],
            "pages": target_manifest["pages"],
        },
        "counts": {
            "base_records": base_count,
            "target_records": target_count,
            "additions": len(additions),
            "removals": len(removals),
            "changed": len(changed),
            "unchanged": unchanged,
            "net_change": target_count - base_count,
        },
        "additions": additions,
        "removals": removals,
        "changed": changed,
        "scope": (
            "Metadata comparison only. A removal here means the accession is absent from the "
            "later snapshot, not that the software was retracted. A change means the record JSON "
            "differs, not that the tool's behaviour changed."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-dir", type=Path, required=True)
    parser.add_argument("--target-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = diff(args.base_dir, args.target_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(json.dumps(report["counts"], indent=2))
    print(f"wrote {args.output}")


if __name__ == "__main__":
    main()
