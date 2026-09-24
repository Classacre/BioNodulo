#!/usr/bin/env python
"""Round-trip fidelity harness: export a workflow, re-import it, score it.

Implements dossier section 5.3. For each export target (Snakemake, Nextflow,
CWL, Galaxy) and each bundled template, the harness computes:

* ``s_nodes``   node-count preservation ratio
* ``s_edges``   exact endpoint/port set Jaccard similarity
* ``s_params``  Jaccard similarity over canonicalized node params
* ``s_labels``  fraction of round-tripped nodes whose type matches an
               original node type (tool-label recall, Dijkman-style label
               matching on exact type equality as the strict end [R36])
* ``f_target``  geometric mean of the above (any zero component drags the
               product to zero, preventing compensation)

plus a categorical loss ledger per target (nodes/edges/params lost) and an
idempotence check (a second export of the round-tripped workflow). The
annotation and provenance components are measured when present and null
otherwise. Unsupported computation counts as failure, never a pruned graph.
The re-export check records success, not byte equality or engine execution.

Usage:
    python scripts/roundtrip_fidelity.py                     # all templates
    python scripts/roundtrip_fidelity.py --templates rna_seq_pipeline
    python scripts/roundtrip_fidelity.py --output reports/fidelity
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable

from bionodulo.converter import (
    export_to_cwl,
    export_to_galaxy,
    export_to_nextflow,
    export_to_snakemake,
    import_from_cwl,
    import_from_galaxy,
    import_from_nextflow,
    import_from_snakemake,
)
from bionodulo.workflow.graph import edge_source, edge_source_port, edge_target, edge_target_port

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO_ROOT / "templates"
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "roundtrip_fidelity"

def _export_cwl(workflow: dict[str, Any]) -> Any:
    return export_to_cwl(workflow)


def _import_cwl(exported: Any, workdir: Path) -> dict[str, Any]:
    if not isinstance(exported, dict):
        raise TypeError("CWL export must be a dict of files")
    for relative_path, content in exported.items():
        target = workdir / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return import_from_cwl(workdir / "workflow.cwl")


TARGETS: dict[str, dict[str, Any]] = {
    "snakemake": {
        "export": export_to_snakemake,
        "import": lambda exported, _workdir: import_from_snakemake(exported),
    },
    "nextflow": {
        "export": export_to_nextflow,
        "import": lambda exported, _workdir: import_from_nextflow(exported),
    },
    "galaxy": {
        "export": export_to_galaxy,
        "import": lambda exported, _workdir: import_from_galaxy(exported),
    },
    "cwl": {"export": _export_cwl, "import": _import_cwl},
}

# Templates whose exportable subgraph is smaller than this are scaffolds:
# their round-trip score is trivially 1.0 and hides real fidelity, so they
# are flagged and excluded from the "meaningful" mean.
MIN_NODES_FOR_SCORING = 3


def _nodes(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        return [
            {"id": node_id, **(node if isinstance(node, dict) else {})}
            for node_id, node in nodes.items()
        ]
    return [node for node in nodes if isinstance(node, dict) and node.get("id")]


def _edges(workflow: dict[str, Any]) -> list[Any]:
    return workflow.get("edges", [])


def _canonical_params(node: dict[str, Any]) -> dict[str, str]:
    params = node.get("params", {})
    if not isinstance(params, dict):
        return {}
    return {str(key): json.dumps(value, sort_keys=True) for key, value in {**params, **node.get("widgets", {})}.items()}


def _ratio(original: int, roundtripped: int) -> float:
    if original == 0:
        return 1.0 if roundtripped == 0 else 0.0
    if roundtripped >= original:
        return original / roundtripped if roundtripped else 0.0
    return roundtripped / original


def score_roundtrip(original: dict[str, Any], roundtripped: dict[str, Any]) -> dict[str, Any]:
    original_nodes = _nodes(original)
    roundtripped_nodes = _nodes(roundtripped)
    original_types = {node.get("type", "") for node in original_nodes}
    roundtripped_types = {node.get("type", "") for node in roundtripped_nodes}

    matched = original_types & roundtripped_types
    s_labels = (
        len(matched) / len(original_types) if original_types else 1.0
    )

    original_params: dict[str, str] = {}
    for node in original_nodes:
        original_params.update(
            {f"{node['id']}.{key}": value for key, value in _canonical_params(node).items()}
        )
    roundtripped_params: dict[str, str] = {}
    for node in roundtripped_nodes:
        roundtripped_params.update(
            {f"{node['id']}.{key}": value for key, value in _canonical_params(node).items()}
        )
    union = set(original_params) | set(roundtripped_params)
    intersection = set(original_params) & set(roundtripped_params)
    value_matches = sum(
        1
        for key in intersection
        if original_params[key] == roundtripped_params[key]
    )
    s_params = (value_matches / len(union)) if union else 1.0

    s_nodes = _ratio(len(original_nodes), len(roundtripped_nodes))
    def edge_set(graph: dict[str, Any]) -> set[tuple[str, str, str, str]]:
        return {(edge_source(edge), edge_source_port(edge), edge_target(edge), edge_target_port(edge)) for edge in _edges(graph)}
    original_edges, restored_edges = edge_set(original), edge_set(roundtripped)
    s_edges = len(original_edges & restored_edges) / len(original_edges | restored_edges) if original_edges | restored_edges else 1.0

    components = {
        "s_nodes": round(s_nodes, 4),
        "s_edges": round(s_edges, 4),
        "s_params": round(s_params, 4),
        "s_labels": round(s_labels, 4),
    }
    def annotations(graph: dict[str, Any], keys: tuple[str, ...]) -> dict[str, str]:
        values = {f"workflow.{key}": json.dumps(graph[key], sort_keys=True) for key in keys if key in graph}
        for node in _nodes(graph):
            values.update({f"{node['id']}.{key}": json.dumps(node[key], sort_keys=True) for key in keys if key in node})
        return values
    for name, keys in (("s_ann", ("semantic_contract", "semantic_state", "semantic_types", "inputs", "outputs")), ("s_provenance", ("provenance", "run_metadata"))):
        before, after = annotations(original, keys), annotations(roundtripped, keys)
        components[name] = sum(after.get(key) == value for key, value in before.items()) / len(before) if before else None
    measured = [value for value in components.values() if value is not None]
    product = math.prod(measured)
    components["f_target"] = round(product ** (1 / len(measured)), 4) if original_nodes else None
    components["unmeasured"] = [name for name, value in components.items() if value is None]
    components["edge_comparison"] = "Exact endpoint IDs and ports; does not infer graph isomorphism after renaming"

    components["ledger"] = {
        "nodes": {
            "original": len(original_nodes),
            "roundtripped": len(roundtripped_nodes),
            "lost": max(0, len(original_nodes) - len(roundtripped_nodes)),
        },
        "edges": {
            "original": len(_edges(original)),
            "roundtripped": len(_edges(roundtripped)),
            "lost": max(0, len(_edges(original)) - len(_edges(roundtripped))),
        },
        "types_lost": sorted(original_types - roundtripped_types),
    }
    return components


def _exportable_subgraph(workflow: dict[str, Any], export: Callable[..., str]) -> tuple[dict[str, Any], list[str]]:
    """Exclude decorative notes only; unsupported computation is a failure."""
    current = json.loads(json.dumps(workflow))
    nodes = _nodes(current)
    current["nodes"] = [node for node in nodes if node.get("type") != "note"]
    kept = {node["id"] for node in current["nodes"]}
    current["edges"] = [edge for edge in _edges(current) if _edge_nodes(edge) <= kept]
    return current, ["note"] if any(node.get("type") == "note" for node in nodes) else []


def _edge_nodes(edge: Any) -> set[str]:
    if not isinstance(edge, dict):
        return set()
    source = edge.get("from") if isinstance(edge.get("from"), dict) else None
    target = edge.get("to") if isinstance(edge.get("to"), dict) else None
    if source and target:
        return {source.get("node", ""), target.get("node", "")}
    return {edge_source(edge), edge_target(edge)}


def evaluate_template(template_path: Path) -> dict[str, Any]:
    workflow = json.loads(template_path.read_text(encoding="utf-8"))
    results: dict[str, Any] = {
        "template": template_path.stem,
        "node_count": len(_nodes(workflow)),
        "targets": {},
    }
    for target, adapter in TARGETS.items():
        export, import_ = adapter["export"], adapter["import"]
        workdir = None
        try:
            comparable, excluded = _exportable_subgraph(workflow, export)
            exported = export(comparable)
            workdir = Path(tempfile.mkdtemp(prefix=f"fidelity-{template_path.stem}-{target}-"))
            roundtripped = import_(exported, workdir)  # noqa: F841 workdir used by adapter
            # Idempotence: exporting the round-tripped workflow must succeed.
            try:
                export(roundtripped)
                idempotent = True
            except Exception:  # noqa: BLE001 - harness reports, never crashes
                idempotent = False
            scoring = score_roundtrip(comparable, roundtripped)
            scoring["idempotent"] = idempotent
            scoring["excluded_node_types"] = excluded
            scoring["scaffold"] = len(_nodes(comparable)) < MIN_NODES_FOR_SCORING
            results["targets"][target] = scoring
        except Exception as error:  # noqa: BLE001 - harness reports, never crashes
            results["targets"][target] = {"error": f"{type(error).__name__}: {error}", "f_target": 0.0, "unsupported_computation_counted_as_failure": True}
        finally:
            if workdir is not None:
                shutil.rmtree(workdir, ignore_errors=True)
    return results


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Round-trip fidelity report",
        "",
        f"Generated: {report['generated_at']}  ",
        f"Templates: {report['template_count']}  ",
        "Metric: f_target is the geometric mean of measured node, edge, parameter,",
        "label, annotation and provenance preservation. Missing annotations are unmeasured.",
        "Unsupported computational nodes score zero; only decorative notes are excluded.",
        "This measures serialization, not execution in an external workflow engine.",
        "",
        "| Template | " + " | ".join(TARGETS) + " |",
        "| --- | " + " | ".join("---" for _ in TARGETS) + " |",
    ]
    for template in report["templates"]:
        cells = []
        for target in TARGETS:
            entry = template["targets"].get(target, {})
            if "error" in entry:
                cells.append(f"error: {entry['error'][:40]}")
            else:
                cells.append(str(entry["f_target"]))
        lines.append(f"| {template['template']} ({template['node_count']}n) | " + " | ".join(cells) + " |")

    lines += ["", "## Per-target averages", "", "| Target | mean f_target | idempotent |", "| --- | --- | --- |"]
    for target in TARGETS:
        scores = [
            t["targets"][target]["f_target"]
            for t in report["templates"]
            if t["targets"].get(target, {}).get("f_target") is not None
        ]
        idempotent = [
            t["targets"][target].get("idempotent", False)
            for t in report["templates"]
            if t["targets"].get(target, {}).get("f_target") is not None
        ]
        mean = round(sum(scores) / len(scores), 4) if scores else None
        fraction = f"{sum(idempotent)}/{len(idempotent)}" if idempotent else "-"
        lines.append(f"| {target} | {mean} | {fraction} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--templates", nargs="*", default=None)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    template_paths = sorted(path for path in TEMPLATES_DIR.glob("*.json") if path.name != "index.json")
    if args.templates:
        wanted = {name if name.endswith(".json") else f"{name}.json" for name in args.templates}
        template_paths = [path for path in template_paths if path.name in wanted]

    import datetime as _dt

    report = {
        "generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "template_count": len(template_paths),
        "templates": [evaluate_template(path) for path in template_paths],
    }

    args.output.mkdir(parents=True, exist_ok=True)
    json_path = args.output / "fidelity.json"
    md_path = args.output / "fidelity.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")

    for target in TARGETS:
        scored = [
            t["targets"][target]
            for t in report["templates"]
            if t["targets"].get(target, {}).get("f_target") is not None
        ]
        meaningful = [entry for entry in scored if "error" not in entry and not entry.get("scaffold")]
        if scored:
            mean = round(sum(e["f_target"] for e in scored) / len(scored), 4)
            meaningful_mean = (
                round(sum(e["f_target"] for e in meaningful) / len(meaningful), 4)
                if meaningful
                else None
            )
            print(
                f"  {target}: mean f_target = {mean} over {len(scored)} templates"
                f" (meaningful, >= {MIN_NODES_FOR_SCORING} exportable nodes:"
                f" {meaningful_mean} over {len(meaningful)})"
            )
        else:
            errors = sum(1 for t in report["templates"] if "error" in t["targets"].get(target, {}))
            print(f"  {target}: no scores ({errors} templates errored)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
