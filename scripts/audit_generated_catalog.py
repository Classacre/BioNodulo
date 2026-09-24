"""Validate every generated CWL document and probe every declared runtime.

This audit does not execute the biological command or claim scientific coverage.
Full stdout/stderr and a result for every catalog entry are retained.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bionodulo.nodes.contract.model import NodeSpec
from bionodulo.nodes.cwl_reference_runtime import verify_reference_runtime
from bionodulo.nodes.generate_registry import atomic_json


async def audit(catalog: Path, output: Path):
    records = []
    output.mkdir(parents=True, exist_ok=True)
    for value in json.loads(catalog.read_text())["specs"]:
        spec = NodeSpec.model_validate_json(json.dumps(value))
        item = {"node_id": spec.identity.machine_id, "source_uri": spec.cwl_reference.source_uri,
                "accession": spec.cwl_reference.biotools_accession, "contract_digest": spec.contract_digest()}
        target = output / spec.identity.machine_id
        target.mkdir(exist_ok=True)
        descriptor = target / "source.cwl"
        descriptor.write_text(spec.cwl_reference.source_text, encoding="utf-8", newline="")
        try:
            result = subprocess.run([os.environ["BIONODULO_CWLTOOL"], "--skip-schemas", "--validate", str(descriptor)],
                                    capture_output=True, timeout=60)
            (target / "validation.stdout.log").write_bytes(result.stdout)
            (target / "validation.stderr.log").write_bytes(result.stderr)
            item["descriptor_validation"] = "passed" if result.returncode == 0 else "failed"
            item["validation_exit_code"] = result.returncode
        except Exception as error:
            item["descriptor_validation"] = "failed"
            item["validation_error"] = f"{type(error).__name__}: {error}"
        try:
            item["runtime_receipt"] = await verify_reference_runtime(spec, workspace_dir=output)
            item["runtime_readiness"] = "passed"
        except Exception as error:
            item["runtime_readiness"] = "failed"
            item["runtime_error"] = f"{type(error).__name__}: {error}"
        records.append(item)
        atomic_json(output / "audit.json", {"catalog": str(catalog), "nodes": len(records),
            "descriptor_validation": dict(Counter(item["descriptor_validation"] for item in records)),
            "runtime_readiness": dict(Counter(item["runtime_readiness"] for item in records)),
            "scope": "CWL syntax and runtime identity only; no biological execution or scientific validation", "records": records})
        print(json.dumps({key: value for key, value in item.items() if key != "runtime_receipt"}), flush=True)
    return int(any(item["descriptor_validation"] != "passed" or item["runtime_readiness"] != "passed" for item in records))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(audit(args.catalog, args.output)))
