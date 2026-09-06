"""Workflow Run RO-Crate export with BioNodulo semantic contract records.

Implements dossier sections 4.2 and 8.4: the crate conforms to the Workflow
Run Crate family profiles (declared in ``conformsTo``), records per-tool
``CreateAction`` executions, and layers the BioNodulo terms namespace
(``https://w3id.org/ro/terms/bionodulo#``) for ``SemanticState`` and
``ContractCheck`` entities, which no current profile records [P3][P4][P5].
The extension mechanism (a terms context plus additional properties on
existing entities) follows accepted precedents [P8][P12][P34].

The emitter is dependency-free: it writes JSON-LD directly so provenance
export never gains a runtime dependency. Validation with ro-crate-validator
[P28] is a CI concern, not an import-time one.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bionodulo.nodes.semantic_contracts import UNKNOWN

RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
WORKFLOW_RUN_TERMS_CONTEXT = "https://w3id.org/ro/terms/workflow-run/context"
BIONODULO_TERMS_NAMESPACE = "https://w3id.org/ro/terms/bionodulo#"
BIONODULO_PROFILE = "https://w3id.org/ro/terms/bionodulo/profile/0.1"
WORKFLOW_RUN_CRATE_PROFILE = "https://w3id.org/ro/wfrun/workflow/0.5"
PROVENANCE_RUN_CRATE_PROFILE = "https://w3id.org/ro/wfrun/provenance/0.5"

_BIONODULO_PREFIX = "bionodulo:"


def _entity(entity_id: str, entity_type: str | list[str], **props: Any) -> dict[str, Any]:
    entity: dict[str, Any] = {"@id": entity_id, "@type": entity_type}
    for key, value in props.items():
        if value is None:
            continue
        entity[key] = value
    return entity


def _ref(entity_id: str) -> dict[str, str]:
    return {"@id": entity_id}


def _state_entity(
    state_id: str, state: dict[str, str]
) -> dict[str, Any]:
    """A reusable SemanticState contextual entity.

    Assembly values are opaque identifiers here (registry enums); richer
    crates would use Identifiers.org URIs [dossier 4.2].
    """
    properties = []
    for dimension, value in sorted(state.items()):
        if value == UNKNOWN:
            continue
        properties.append(
            {"@type": "PropertyValue", "name": dimension, "value": value}
        )
    return _entity(
        state_id,
        "bionodulo:SemanticState",
        **{_BIONODULO_PREFIX + "stateProperty": properties},
    )


def build_run_crate(
    workflow: dict[str, Any],
    *,
    run_summary: dict[str, Any] | None = None,
    node_metadata: dict[str, dict[str, Any]] | None = None,
    semantic_result: Any | None = None,
    agent_name: str = "BioNodulo",
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Build a ro-crate-metadata.json payload for one workflow (run).

    ``workflow`` is a BioNodulo workflow dict (nodes + edges, either edge
    shape). ``run_summary`` optionally carries per-node execution records:
    ``{"nodes": {"<id>": {"status": "...", "start_time": ..., "end_time": ...,
    "command": ...}}}``. ``semantic_result`` is a
    :class:`~bionodulo.workflow.semantic_checks.SemanticCheckResult`; its
    resolved states become ``bionodulo:hasSemanticState`` on outputs and its
    violations become failed ``ContractCheck`` records on the consuming
    action.
    """
    run_summary = run_summary or {}
    node_metadata = node_metadata or {}
    timestamp = (generated_at or datetime.now(timezone.utc)).isoformat()
    workflow_name = workflow.get("name") or "BioNodulo workflow"

    graph: list[dict[str, Any]] = []
    workflow_file_id = "workflow/bionodulo-workflow.json"

    # Metadata file descriptor + root dataset [P1].
    graph.append(
        _entity(
            "ro-crate-metadata.json",
            "CreativeWork",
            about=_ref("./"),
            conformsTo={"@id": "https://w3id.org/ro/crate/1.1"},
        )
    )
    graph.append(
        _entity(
            "./",
            "Dataset",
            name=f"{workflow_name} (BioNodulo run crate)",
            description=(
                "BioNodulo workflow run with semantic contract records."
            ),
            dateModified=timestamp,
            conformsTo=[
                _ref(WORKFLOW_RUN_CRATE_PROFILE),
                _ref(PROVENANCE_RUN_CRATE_PROFILE),
                _ref(BIONODULO_PROFILE),
            ],
            mainEntity=_ref(workflow_file_id),
        )
    )
    # Profile entities so conformsTo references resolve [P2].
    for profile_id, profile_name in (
        (WORKFLOW_RUN_CRATE_PROFILE, "Workflow Run Crate 0.5"),
        (PROVENANCE_RUN_CRATE_PROFILE, "Provenance Run Crate 0.5"),
        (BIONODULO_PROFILE, "BioNodulo Semantic Run Crate profile 0.1"),
    ):
        graph.append(
            _entity(
                profile_id,
                ["CreativeWork", "Profile"],
                name=profile_name,
            )
        )

    # The workflow itself as main entity [P6].
    graph.append(
        _entity(
            workflow_file_id,
            ["File", "SoftwareSourceCode", "ComputationalWorkflow"],
            name=workflow_name,
            programmingLanguage="BioNodulo",
            encodingFormat="application/json",
        )
    )

    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        node_list = [
            {"id": node_id, **(node if isinstance(node, dict) else {})}
            for node_id, node in nodes.items()
        ]
    else:
        node_list = [node for node in nodes if isinstance(node, dict) and node.get("id")]

    check_records: dict[str, list[dict[str, Any]]] = {}
    if semantic_result is not None:
        for violation in getattr(semantic_result, "violations", []):
            check_records.setdefault(violation.consumer_node, []).append(
                _entity(
                    f"#check-{violation.edge_id}-{violation.dimension}",
                    "bionodulo:ContractCheck",
                    **{
                        _BIONODULO_PREFIX + "dimension": violation.dimension,
                        _BIONODULO_PREFIX + "expected": {
                            "@type": "PropertyValue",
                            "name": violation.dimension,
                            "value": violation.required_value,
                        },
                        _BIONODULO_PREFIX + "observed": {
                            "@type": "PropertyValue",
                            "name": violation.dimension,
                            "value": violation.observed_value,
                        },
                        _BIONODULO_PREFIX + "satisfiedBy": _ref(
                            BIONODULO_TERMS_NAMESPACE + "Violated"
                        ),
                        "description": violation.explanation(),
                    },
                )
            )

    mentions: list[dict[str, str]] = []
    for node in node_list:
        node_id = node["id"]
        node_type = node.get("type", node_id)
        meta = node_metadata.get(node_type, {})
        tool_ref = _ref(f"#tool-{node_type}")
        graph.append(
            _entity(
                f"#tool-{node_type}",
                "SoftwareApplication",
                name=meta.get("display_name") or node_type,
                softwareVersion=str(meta.get("version") or meta.get("git_commit") or "unknown"),
                url=meta.get("documentation_url"),
            )
        )
        run_info = (run_summary.get("nodes") or {}).get(node_id, {})
        action_props: dict[str, Any] = {
            "instrument": tool_ref,
            "actionStatus": run_info.get(
                "status", "PotentialActionStatus"
            ),
            "startTime": run_info.get("start_time"),
            "endTime": run_info.get("end_time"),
            "description": run_info.get("command"),
            "object": _ref(workflow_file_id),
        }
        checks = check_records.get(node_id)
        if checks:
            action_props[_BIONODULO_PREFIX + "hasContractCheck"] = [
                _ref(check["@id"]) for check in checks
            ]
            graph.extend(checks)
        graph.append(_entity(f"#run-{node_id}", "CreateAction", **action_props))
        mentions.append(_ref(f"#run-{node_id}"))

        if semantic_result is not None:
            states = (getattr(semantic_result, "node_states", {}) or {}).get(node_id, {})
            for output_port, state in states.items():
                known = {
                    dimension: value
                    for dimension, value in state.items()
                    if value != UNKNOWN
                }
                if not known:
                    continue
                state_id = f"#state-{node_id}-{output_port}"
                graph.append(_state_entity(state_id, known))
                graph.append(
                    _entity(
                        f"#output-{node_id}-{output_port}",
                        "File",
                        name=f"{node_id}:{output_port}",
                        **{_BIONODULO_PREFIX + "hasSemanticState": _ref(state_id)},
                    )
                )

    root = graph[1]
    root["mentions"] = mentions

    return {
        "@context": [
            RO_CRATE_CONTEXT,
            WORKFLOW_RUN_TERMS_CONTEXT,
            {"bionodulo": BIONODULO_TERMS_NAMESPACE},
        ],
        "@graph": graph,
    }


def write_run_crate(
    directory: str | Path,
    workflow: dict[str, Any],
    **kwargs: Any,
) -> Path:
    """Write a crate directory: the workflow file plus its metadata."""
    target = Path(directory)
    target.mkdir(parents=True, exist_ok=True)
    workflow_file = target / "workflow" / "bionodulo-workflow.json"
    workflow_file.parent.mkdir(parents=True, exist_ok=True)
    workflow_file.write_text(
        json.dumps(workflow, indent=2, sort_keys=True), encoding="utf-8"
    )
    crate = build_run_crate(workflow, **kwargs)
    metadata_file = target / "ro-crate-metadata.json"
    metadata_file.write_text(
        json.dumps(crate, indent=2, sort_keys=True), encoding="utf-8"
    )
    return metadata_file
