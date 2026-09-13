#!/usr/bin/env python
"""Link BioNodulo node types to bio.tools registry records and EDAM terms.

Queries https://bio.tools/api/tool/{biotoolsID} for each node type in the
provided families (or an explicit list), records biotoolsID, tool version,
EDAM topics, operations, and per-function input/output data and format terms
into ``bionodulo/nodes/generated/biotools_links.json``.

This is the identification and selection substrate for contract inference
(dossier sections 3.1 and 8.3): the FAIR-in-practice lifecycle stages
[G15], the nf-core precedent of embedding bio.tools identifiers with lint
able to re-derive them [G23]. Run periodically; diff-friendly JSON output.

Usage:
    python scripts/link_biotools.py --families samtools_family rna_seq_family
    python scripts/link_biotools.py --types samtools_view featurecounts
    python scripts/link_biotools.py --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
NODE_METADATA_PATH = REPO_ROOT / "bionodulo" / "nodes" / "node_metadata.json"
NODE_INDEX_PATH = REPO_ROOT / "bionodulo" / "nodes" / "node_index.json"
OUTPUT_PATH = REPO_ROOT / "bionodulo" / "nodes" / "generated" / "biotools_links.json"

BIOTOOLS_API = "https://bio.tools/api/tool/{tool_id}?format=json"
REQUEST_DELAY_SECONDS = 0.5  # be a polite API citizen

# Node types whose biotoolsID cannot be derived from the family or node id.
EXPLICIT_IDS: dict[str, str] = {
    "featurecounts": "featurecounts",
    "samtools_view": "samtools",
    "samtools_sort": "samtools",
    "samtools_index": "samtools",
    "samtools_flagstat": "samtools",
    "samtools_bam_to_cram": "samtools",
    "samtools_cram_to_bam": "samtools",
    "sam_to_bam": "samtools",
    "bam_to_sam": "samtools",
    "hisat2_align": "hisat2",
    "hisat2_build": "hisat2",
    "bwa_mem": "bwa",
    "bwa_mem2": "bwa-mem2",
    "fastqc": "fastqc",
    "multiqc": "multiqc",
}


def _family_of(node_id: str, index: dict[str, str]) -> str | None:
    module = index.get(node_id, "")
    if "builtin." not in module:
        return None
    tail = module.split("builtin.", 1)[1]
    return tail.split(".", 1)[0] if "." in tail else None


def _edam_uris(terms: list | None) -> list[str]:
    if not terms:
        return []
    uris: set[str] = set()
    for term in terms:
        if isinstance(term, str):
            if term.startswith("http"):
                uris.add(term)
            continue
        if isinstance(term, dict):
            uri = term.get("uri") or term.get("term")
            if uri:
                uris.add(uri)
    return sorted(uris)


def fetch_tool(biotools_id: str) -> dict | None:
    url = BIOTOOLS_API.format(tool_id=biotools_id)
    request = urllib.request.Request(url, headers={"User-Agent": "bionodulo-linker/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
        print(f"  ! {biotools_id}: {error}", file=sys.stderr)
        return None


def summarize(record: dict) -> dict:
    functions = []
    for function in record.get("function", []) or []:
        inputs = []
        for item in function.get("input", []) or []:
            inputs.append(
                {
                    "data": _edam_uris(item.get("data")),
                    "formats": _edam_uris(item.get("format")),
                }
            )
        outputs = []
        for item in function.get("output", []) or []:
            outputs.append(
                {
                    "data": _edam_uris(item.get("data")),
                    "formats": _edam_uris(item.get("format")),
                }
            )
        functions.append(
            {
                "operations": _edam_uris(function.get("function")),
                "inputs": inputs,
                "outputs": outputs,
            }
        )
    return {
        "biotoolsID": record.get("biotoolsID"),
        "biotoolsCURIE": record.get("biotoolsCURIE"),
        "name": record.get("name"),
        "toolType": record.get("toolType", []),
        "topic": _edam_uris(record.get("topic")),
        "description": (record.get("description") or "")[:300],
        "homepage": record.get("homepage"),
        "documentation": next(
            (
                link.get("url")
                for link in record.get("link", []) or []
                if link.get("type") == "documentation"
            ),
            None,
        ),
        "license": record.get("license"),
        "version": record.get("version", [])[-6:],
        "functions": functions,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--families", nargs="*", default=[])
    parser.add_argument("--types", nargs="*", default=[])
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    index = json.loads(NODE_INDEX_PATH.read_text(encoding="utf-8"))
    targets: list[str] = []
    if args.types:
        targets.extend(args.types)
    for family in args.families:
        targets.extend(
            node_id for node_id in index if _family_of(node_id, index) == family
        )
    if not targets and not args.types and not args.families:
        targets = sorted(EXPLICIT_IDS)
    if args.limit:
        targets = targets[: args.limit]
    targets = [node_id for node_id in dict.fromkeys(targets) if node_id in index]
    print(f"linking {len(targets)} node types to bio.tools")

    links: dict[str, dict] = {}
    for node_id in targets:
        biotools_id = EXPLICIT_IDS.get(node_id)
        if biotools_id is None:
            biotools_id = node_id.split("_")[0] if "_" in node_id else node_id
        print(f"  {node_id} -> bio.tools:{biotools_id}")
        if args.dry_run:
            links[node_id] = {"biotools_id": biotools_id, "queried": False}
            continue
        record = fetch_tool(biotools_id)
        if record is None or record.get("biotoolsID") is None:
            links[node_id] = {"biotools_id": biotools_id, "queried": True, "found": False}
            continue
        links[node_id] = {"biotools_id": biotools_id, "queried": True, "found": True, **summarize(record)}
        time.sleep(REQUEST_DELAY_SECONDS)

    payload = {
        "schema_version": "0.1",
        "source": "https://bio.tools/api",
        "linked_node_types": len(links),
        "found": sum(1 for entry in links.values() if entry.get("found")),
        "links": dict(sorted(links.items())),
    }
    if args.dry_run:
        print(json.dumps(payload, indent=2)[:2000])
        return 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {args.output} ({payload['found']}/{payload['linked_node_types']} found)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
