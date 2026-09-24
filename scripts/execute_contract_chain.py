#!/usr/bin/env python
"""Real, local, end-to-end thesis pipeline on public fixture data.

Chain: input TSV -> normalize_data(method=cpm) -> [deseq2].

Three demonstrations in one run:
1. DETECT: the planted workflow feeds a CPM-normalized matrix into DESeq2,
   which assumes raw counts (the documented misuse [S35][E18][S38]); the
   contract check flags it with blame and, correctly, offers no coercion,
   because normalization state cannot be legally converted back.
2. EXECUTE: the normalize_data node is pure Python, so the chain up to the
   violation point runs for real through the engine on the bundled fixture
   (robust_per_subgraph_sample.tsv), producing actual output files.
3. PROVENANCE: the real run plus its semantic states are exported as a
   Workflow Run RO-Crate with ContractCheck records.

Usage:
    python scripts/execute_contract_chain.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from bionodulo.nodes.registry import NodeRegistry  # noqa: E402
from bionodulo.nodes.semantic_contracts import SemanticContractLibrary  # noqa: E402
from bionodulo.workflow.semantic_checks import check_workflow_semantics  # noqa: E402


def counts_fixture() -> Path:
    """A deterministic 40-gene by 6-sample raw count matrix."""
    import random

    fixture = REPO_ROOT / "reports" / "contract_demo" / "counts_fixture.tsv"
    fixture.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(20260913)
    lines = ["gene\tsample_1\tsample_2\tsample_3\tsample_4\tsample_5\tsample_6"]
    for index in range(40):
        base = rng.randint(50, 5000)
        row = [str(base + rng.randint(-40, 40) + (index * 7 if index % 4 == 0 else 0)) for _ in range(6)]
        lines.append(f"gene_{index:03d}\t" + "\t".join(row))
    fixture.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return fixture


def planted_workflow() -> dict:
    fixture = counts_fixture()
    return {
        "version": "2.0",
        "name": "normalization-planted",
        "nodes": [
            {"id": "table", "type": "input_file", "params": {"file": str(fixture)}},
            {"id": "cpm", "type": "normalize_data", "params": {"method": "cpm", "id_columns": "gene"}},
            {"id": "de", "type": "deseq2", "params": {}},
        ],
        "edges": [
            {"id": "e1", "from": {"node": "table", "output": "file"},
             "to": {"node": "cpm", "input": "table"}},
            {"id": "e2", "from": {"node": "cpm", "output": "normalized_table"},
             "to": {"node": "de", "input": "count_matrix"}},
        ],
    }


def executable_workflow() -> dict:
    workflow = planted_workflow()
    workflow["name"] = "normalization-real-run"
    workflow["nodes"] = [n for n in workflow["nodes"] if n["id"] != "de"]
    workflow["edges"] = [e for e in workflow["edges"] if e["to"]["node"] != "de"]
    return workflow


async def run_engine(workflow: dict) -> tuple[dict, Path]:
    from bionodulo.execution.executor import WorkflowExecutor

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    run_dir = REPO_ROOT / "reports" / "contract_demo" / "real_run"
    executor = WorkflowExecutor(
        workspace_dir=run_dir,
        cache_dir=run_dir.parent / "cache",
        registry=registry,
        settings=SimpleNamespace(
            execution=SimpleNamespace(max_workers=1, env_isolation="off", content_hashing="on"),
            api_secrets={},
        ),
    )
    result = await executor.execute("normalization-real", workflow)
    return result, run_dir / "runs" / "normalization-real"


def main() -> int:
    library = SemanticContractLibrary.bundled()

    print("=== 1. DETECT: CPM matrix into a raw-counts consumer ===")
    result = check_workflow_semantics(planted_workflow(), library)
    print(f"check: {result.summary()}")
    for violation in result.violations:
        print(f"  violation: {violation.explanation()}")
    assert result.violations, "planted normalization error must be detected"
    assert not result.suggestions, "normalization state has no legal coercion back to raw counts"
    state = result.node_states["cpm"]["normalized_table"]["normalization_state"]
    print(f"  propagated state: normalize_data(cpm) guarantees normalization_state={state}")

    print("=== 2. EXECUTE: real local run of the chain up to the violation point ===")
    outcome, run_path = asyncio.run(run_engine(executable_workflow()))
    print(f"  run status: {outcome.get('status')}")
    metadata_path = run_path / "run_metadata.json"
    artifacts = []
    if metadata_path.exists():
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        for artifact in metadata.get("artifacts", []):
            size = Path(artifact["path"]).stat().st_size if Path(artifact["path"]).exists() else -1
            artifacts.append({"node": artifact["node_id"], "port": artifact["port"], "bytes": size})
            print(f"  produced: {artifact['node_id']}.{artifact['port']} ({size} bytes)")
    assert outcome.get("status") == "completed", "real execution must complete"

    print("=== 3. PROVENANCE: Workflow Run RO-Crate with the real semantic states ===")
    from bionodulo.provenance.rocrate_export import write_run_crate

    crate_dir = REPO_ROOT / "reports" / "contract_demo" / "crate"
    metadata_file = write_run_crate(
        crate_dir,
        executable_workflow(),
        run_summary={
            "nodes": {
                "table": {"status": "CompletedActionStatus"},
                "cpm": {"status": "CompletedActionStatus"},
            }
        },
        semantic_result=result,
    )
    print(f"  crate metadata: {metadata_file}")
    payload = json.loads(metadata_file.read_text(encoding="utf-8"))
    states = [e for e in payload["@graph"] if e.get("@type") == "bionodulo:SemanticState"]
    print(f"  semantic states recorded in crate: {len(states)}")

    print(json.dumps({
        "stage": "done",
        "ok": True,
        "planted_violations": len(result.violations),
        "dimension": result.violations[0].dimension,
        "observed": result.violations[0].observed_value,
        "required": result.violations[0].required_value,
        "coercion_offered": False,
        "real_run_status": outcome.get("status"),
        "artifacts": artifacts,
        "crate_states": len(states),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
