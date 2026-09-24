"""RO-Crate run metadata with an experimental semantic-contract extension.

Actual executor records and output hashes are preserved. Static predictions
are distinguished from observed files. Workflow Run/Provenance Run profile
conformance and measured external binary versions are not asserted: their
additional requirements still need standards validation and runtime tracing.
"""

from __future__ import annotations

import json
import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bionodulo.nodes.semantic_contracts import UNKNOWN

RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
WORKFLOW_RUN_TERMS_CONTEXT = "https://w3id.org/ro/terms/workflow-run/context"
BIONODULO_TERMS_NAMESPACE = "https://github.com/Classacre/BioNodulo/terms/experimental#"
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


def _flatten_graph(graph: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """RO-Crate requires contextual entities at top level, linked by @id only."""
    flattened: list[dict[str, Any]] = []
    generated: list[dict[str, Any]] = []

    def value(item: Any) -> Any:
        if isinstance(item, list):
            return [value(member) for member in item]
        if isinstance(item, dict) and "@type" in item:
            entity_id = item.get("@id", f"#inline-property-{len(generated)}")
            entity = {"@id": entity_id, **item}
            generated.append(entity)
            for key in list(entity):
                if not key.startswith("@"):
                    entity[key] = value(entity[key])
            return _ref(entity_id)
        return item

    for entity in graph:
        flattened.append({key: value(item) if not key.startswith("@") else item for key, item in entity.items()})
    return flattened + generated


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
    metadata = run_summary.get("metadata") or run_summary
    runtime_nodes = run_summary.get("node_results") or {}
    run_nodes = metadata.get("nodes") or {}
    semantic_payload = semantic_result.to_dict() if hasattr(semantic_result, "to_dict") else semantic_result or metadata.get("semantics") or {}

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
            datePublished=timestamp,
            license="Reuse terms are unspecified; consult the data custodian.",
            conformsTo=[_ref("https://w3id.org/ro/crate/1.1")],
            **{_BIONODULO_PREFIX + "conformanceStatus": "Experimental extension; Workflow Run and Provenance Run profiles have not been validated"},
            mainEntity=_ref(workflow_file_id),
        )
    )
    # Related profiles are references, not a declaration of conformance.
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
            programmingLanguage=_ref("#bionodulo-language"),
            encodingFormat="application/json",
        )
    )
    graph.append(_entity("#bionodulo-language", "ComputerLanguage", name="BioNodulo workflow JSON"))
    graph.append(_entity("#engine", "SoftwareApplication", name=agent_name))

    nodes = workflow.get("nodes", [])
    if isinstance(nodes, dict):
        node_list = [
            {"id": node_id, **(node if isinstance(node, dict) else {})}
            for node_id, node in nodes.items()
        ]
    else:
        node_list = [node for node in nodes if isinstance(node, dict) and node.get("id")]

    check_records: dict[str, list[dict[str, Any]]] = {}
    for index, check in enumerate(semantic_payload.get("checks", [])):
        check_records.setdefault(check["consumer_node"], []).append(_entity(
            f"#check-{index}", "bionodulo:ContractCheck",
            **{
                _BIONODULO_PREFIX + "dimension": check["dimension"],
                _BIONODULO_PREFIX + "expected": check["expected"],
                _BIONODULO_PREFIX + "observed": check["observed"],
                _BIONODULO_PREFIX + "status": check["status"],
                _BIONODULO_PREFIX + "evidenceKind": "static declared contract",
                "description": f"Edge {check['edge_id']}: {check['status']}",
            },
        ))
    if semantic_result is not None and not semantic_payload.get("checks"):
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
    emitted_tools: set[str] = set()
    emitted_files: dict[str, dict[str, Any]] = {}
    for node in node_list:
        node_id = node["id"]
        node_type = node.get("type", node_id)
        if node_type == "note":
            continue
        meta = node_metadata.get(node_type, {})
        tool_ref = _ref(f"#tool-{node_type}")
        if node_type not in emitted_tools:
            # One tool entity per type; every run of that type references it
            # (duplicate @id values in @graph fail crate validation).
            emitted_tools.add(node_type)
            graph.append(
                _entity(
                    f"#tool-{node_type}",
                    "SoftwareApplication",
                    name=meta.get("display_name") or node_type,
                    softwareVersion=str(meta.get("version") or meta.get("git_commit") or "unknown"),
                    url=meta.get("documentation_url"),
                )
            )
        run_info = {**run_nodes.get(node_id, {}), **runtime_nodes.get(node_id, {})}
        status = run_info.get("status", "PotentialActionStatus")
        action_status = {"completed": "CompletedActionStatus", "cached": "CompletedActionStatus", "failed": "FailedActionStatus", "cancelled": "FailedActionStatus"}.get(status, status if status.endswith("ActionStatus") else "PotentialActionStatus")
        action_props: dict[str, Any] = {
            "instrument": tool_ref,
            "actionStatus": action_status,
            "startTime": run_info.get("start_time"),
            "endTime": run_info.get("end_time"),
            "description": run_info.get("command"),
            "object": _ref(workflow_file_id),
            _BIONODULO_PREFIX + "executionStatus": status,
            "error": run_info.get("error"),
        }
        oci_runs = metadata.get("cwl_oci", {})
        oci_receipt = oci_runs.get(node_id) if isinstance(oci_runs, dict) else None
        if isinstance(oci_receipt, dict):
            for key in (
                "source_uri", "source_sha256", "source_docker_pull", "image_index", "image_platform",
                "cwltool_sha256", "docker_sha256", "nodejs_sha256", "docker_wrapper_sha256",
                "effective_source_sha256", "environment_digest", "contract_digest",
                "resource_cap_cores", "resource_cap_ram_mib",
            ):
                value = oci_receipt.get(key)
                if isinstance(value, str):
                    action_props[_BIONODULO_PREFIX + "oci" + key.title().replace("_", "")] = value
        checks = check_records.get(node_id)
        if checks:
            action_props[_BIONODULO_PREFIX + "hasContractCheck"] = [
                _ref(check["@id"]) for check in checks
            ]
            graph.extend(checks)
        action = _entity(f"#run-{node_id}", "CreateAction", **action_props)
        graph.append(action)
        mentions.append(_ref(f"#run-{node_id}"))

        if semantic_payload:
            states = semantic_payload.get("node_states", {}).get(node_id, {})
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
                        "PropertyValue",
                        name=f"{node_id}:{output_port}",
                        description="Static predicted output state, not proof that a file was produced",
                        **{_BIONODULO_PREFIX + "hasSemanticState": _ref(state_id)},
                    )
                )

        output_refs = []
        for port, raw_path in (run_info.get("outputs") or {}).items():
            if not isinstance(raw_path, str):
                continue
            path = Path(raw_path)
            try:
                if not path.is_file():
                    continue
                file_id = path.resolve().as_uri()
                if file_id not in emitted_files:
                    with path.open("rb") as handle:
                        digest = hashlib.file_digest(handle, "sha256").hexdigest()
                    emitted_files[file_id] = _entity(
                        file_id, "File", name=path.name, contentSize=path.stat().st_size,
                        encodingFormat=mimetypes.guess_type(path.name)[0] or "application/octet-stream",
                        **{_BIONODULO_PREFIX + "sha256": digest},
                    )
                    graph.append(emitted_files[file_id])
                state_id = f"#state-{node_id}-{port}"
                if any(entity["@id"] == state_id for entity in graph):
                    emitted_files[file_id][_BIONODULO_PREFIX + "hasSemanticState"] = _ref(state_id)
                output_refs.append(_ref(file_id))
            except OSError as exc:
                action[_BIONODULO_PREFIX + "artifactReadError"] = str(exc)
        if output_refs:
            action["result"] = output_refs

    root = graph[1]
    root["mentions"] = mentions
    root["hasPart"] = [_ref(workflow_file_id), *[_ref(file_id) for file_id in emitted_files]]
    root[_BIONODULO_PREFIX + "semanticVerification"] = semantic_payload.get("verification", "unverified")
    if run_summary:
        status = run_summary.get("status") or metadata.get("status")
        graph.append(_entity(
            "#workflow-run", "CreateAction", name=workflow_name,
            instrument=_ref(workflow_file_id), agent=_ref("#engine"),
            actionStatus={"completed": "CompletedActionStatus", "failed": "FailedActionStatus", "cancelled": "FailedActionStatus"}.get(status, "PotentialActionStatus"),
            result=[_ref(file_id) for file_id in emitted_files],
        ))
        mentions.append(_ref("#workflow-run"))

    return {
        "@context": [
            RO_CRATE_CONTEXT,
            WORKFLOW_RUN_TERMS_CONTEXT,
            {"bionodulo": BIONODULO_TERMS_NAMESPACE},
        ],
        "@graph": _flatten_graph(graph),
    }


def write_run_crate(
    directory: str | Path,
    workflow: dict[str, Any],
    **kwargs: Any,
) -> Path:
    """Write a crate directory: the workflow file plus its metadata."""
    from bionodulo.core.credentials import redact_tree

    workflow = redact_tree(workflow)
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
