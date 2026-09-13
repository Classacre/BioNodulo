#!/usr/bin/env python
"""End-to-end contract-system demo on real nodes, run locally.

Exercises the full thesis loop (dossier sections 8.1-8.2) on genuine node
types and genuine semantics: samtools index requires a coordinate-sorted
BAM, and the planted workflow skips sorting. The loop is detect (per-edge
check with blame), explain (dimension-attributed violation), repair
(auto-insert the cheapest legal coercion), re-check, structurally validate
against the live 979-node registry, and no-execute preview through the
engine's dry run.

Usage:
    python scripts/run_contract_demo.py          # full loop
    python scripts/run_contract_demo.py --quiet  # machine-readable tail
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bionodulo.nodes.registry import NodeRegistry  # noqa: E402
from bionodulo.nodes.semantic_contracts import SemanticContractLibrary  # noqa: E402
from bionodulo.workflow.semantic_checks import (  # noqa: E402
    apply_suggestions,
    check_workflow_semantics,
)
from bionodulo.workflow.validation import validate_workflow  # noqa: E402


def planted_workflow() -> dict:
    """A realistic mistake: align, convert, and index without sorting."""
    return {
        "version": "2.0",
        "name": "contract-demo-planted",
        "nodes": [
            {"id": "reads", "type": "input_fastq", "params": {
                "sample_name": "demo",
                "reads": ["https://raw.githubusercontent.com/nf-core/test-datasets/72a702d346833d5523bc40d032323ea548603b00/testdata/GSE110004/SRR6357072_1.fastq.gz"],
            }},
            {"id": "ref", "type": "input_fasta", "params": {
                "reference": "https://ftp.ncbi.nlm.nih.gov/genomes/all/GCF/000/146/045/GCF_000146045.2_R64/GCF_000146045.2_R64_genomic.fna.gz",
            }},
            {"id": "build", "type": "hisat2_build", "params": {"threads": 4}},
            {"id": "align", "type": "hisat2_align", "params": {"threads": 4}},
            {"id": "tobam", "type": "sam_to_bam", "params": {"addref_select": "cached"}},
            {"id": "bai", "type": "samtools_index", "params": {}},
        ],
        "edges": [
            {"id": "e0", "from": {"node": "ref", "output": "reference"},
             "to": {"node": "build", "input": "reference"}},
            {"id": "e1", "from": {"node": "reads", "output": "reads"},
             "to": {"node": "align", "input": "reads"}},
            {"id": "e1b", "from": {"node": "build", "output": "index"},
             "to": {"node": "align", "input": "index"}},
            {"id": "e2", "from": {"node": "align", "output": "alignment"},
             "to": {"node": "tobam", "input": "input"}},
            {"id": "e3", "from": {"node": "tobam", "output": "output1"},
             "to": {"node": "bai", "input": "bam"}},
        ],
    }


def clean_workflow() -> dict:
    return {
        "version": "2.0",
        "name": "contract-demo-clean",
        "nodes": [
            {"id": "align", "type": "hisat2_align", "params": {}},
            {"id": "tobam", "type": "sam_to_bam", "params": {}},
            {"id": "sort", "type": "samtools_sort", "params": {}},
            {"id": "bai", "type": "samtools_index", "params": {}},
        ],
        "edges": [
            {"id": "e1", "from": {"node": "align", "output": "alignment"},
             "to": {"node": "tobam", "input": "input"}},
            {"id": "e2", "from": {"node": "tobam", "output": "output1"},
             "to": {"node": "sort", "input": "alignment"}},
            {"id": "e3", "from": {"node": "sort", "output": "sorted_bam"},
             "to": {"node": "bai", "input": "bam"}},
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    def say(message: str) -> None:
        if not args.quiet:
            print(message, flush=True)

    library = SemanticContractLibrary.bundled()
    workflow = planted_workflow()

    say("=== 1. planted workflow (align -> convert -> index, sorting skipped) ===")
    result = check_workflow_semantics(workflow, library)
    say(f"check: {result.summary()}")
    for violation in result.violations:
        say(f"  violation: {violation.explanation()}")
    for suggestion in result.suggestions:
        say(f"  suggestion: {suggestion.explanation}")
    if not result.violations:
        print(json.dumps({"stage": "detect", "ok": False, "reason": "no violation detected"}))
        return 1

    say("=== 2. auto-repair: insert the cheapest legal coercion ===")
    repaired = apply_suggestions(workflow, result)
    recheck = check_workflow_semantics(repaired, library)
    say(f"recheck after repair: {recheck.summary()}")
    if not recheck.ok:
        print(json.dumps({"stage": "repair", "ok": False, "reason": "still violated"}))
        return 1

    say("=== 3. structural validation against the live registry (979 nodes) ===")
    registry = NodeRegistry.create_isolated()
    loaded = registry.load_builtin_nodes()
    validation = validate_workflow(repaired, registry)
    say(f"registry loaded {loaded} nodes; validation valid={validation.valid}")
    if not validation.valid:
        for error in validation.errors:
            say(f"  error: {error}")
        return 1

    say("=== 4. engine dry run (planned commands, outputs, environments) ===")
    from types import SimpleNamespace

    from bionodulo.execution.executor import WorkflowExecutor

    async def _dry() -> dict:
        executor = WorkflowExecutor(
            workspace_dir=REPO_ROOT / "reports" / "contract_demo",
            cache_dir=REPO_ROOT / "reports" / "contract_demo" / "cache",
            registry=registry,
            settings=SimpleNamespace(
                execution=SimpleNamespace(
                    max_workers=1, env_isolation="off", content_hashing="off"
                ),
                api_secrets={},
            ),
        )
        return await executor.dry_run("contract-demo", repaired)

    dry = asyncio.run(_dry())
    say(f"dry run status: {dry.get('status')}")
    nodes = dry.get("nodes") or {}
    for node_id, preview in (nodes.items() if isinstance(nodes, dict) else []):
        command = (preview or {}).get("command") or (preview or {}).get("planned_command")
        if command:
            say(f"  {node_id}: {str(command)[:110]}")

    say("=== 5. clean control workflow ===")
    control = check_workflow_semantics(clean_workflow(), library)
    say(f"clean workflow: {control.summary()}")

    print(
        json.dumps(
            {
                "stage": "done",
                "ok": True,
                "planted_violations": len(result.violations),
                "blame": {
                    "dimension": result.violations[0].dimension,
                    "producer": result.violations[0].producer_node,
                    "consumer": result.violations[0].consumer_node,
                    "observed": result.violations[0].observed_value,
                    "required": result.violations[0].required_value,
                },
                "coercion_inserted": result.suggestions[0].converter_node_type if result.suggestions else None,
                "repaired_ok": recheck.ok,
                "structural_validation": validation.valid,
                "dry_run_status": dry.get("status"),
                "clean_control_ok": control.ok,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
