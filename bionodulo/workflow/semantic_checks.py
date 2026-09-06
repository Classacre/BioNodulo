"""Per-edge semantic contract checking over a BioNodulo workflow graph.

Implements the design of dossier section 8.2: forward state propagation
(each node applies its guarantee transforms, Liquid-style contract
transformers [S23]), per-edge subsumption checks with blame-explained
rejection [S24], and legal-coercion search with auto-insertion of the
cheapest converter (the deployed Galaxy and Blender precedent [S5][S51]).

The checker is deliberately tolerant of the two edge shapes found in the
wild (nested ``{"from": {"node", "output"}, "to": {...}}`` template form and
the flat ``from_node``/``to_node`` API form) and of nodes without contracts
(gradual typing: unknown state is warned about, never rejected [S26]).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bionodulo.nodes.semantic_contracts import (
    UNKNOWN,
    Clause,
    CoercionRule,
    Guarantee,
    NodeSemanticContract,
    SemanticContractLibrary,
)


# --------------------------------------------------------------------------
# Workflow helpers


def _edge_endpoints(edge: dict[str, Any]) -> tuple[str, str, str, str] | None:
    """Return (source_node, source_output, target_node, target_input)."""
    source = edge.get("from") if isinstance(edge.get("from"), dict) else None
    target = edge.get("to") if isinstance(edge.get("to"), dict) else None
    if source is not None and target is not None:
        return (
            source.get("node", ""),
            source.get("output", ""),
            target.get("node", ""),
            target.get("input", ""),
        )
    if "from_node" in edge or "fromNode" in edge:
        return (
            edge.get("from_node") or edge.get("fromNode") or "",
            edge.get("from_output") or edge.get("fromOutput") or "",
            edge.get("to_node") or edge.get("toNode") or "",
            edge.get("to_input") or edge.get("toInput") or "",
        )
    return None


def _topological_order(nodes: dict[str, dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    """Kahn ordering over the node graph; cycles fall back to declaration order."""
    incoming: dict[str, list[str]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        endpoints = _edge_endpoints(edge)
        if endpoints is None:
            continue
        source, _, target, _ = endpoints
        if source in incoming and target in incoming:
            incoming[target].append(source)
    ready = [node_id for node_id, parents in incoming.items() if not parents]
    order: list[str] = []
    remaining = {node_id: set(parents) for node_id, parents in incoming.items()}
    while ready:
        node_id = ready.pop(0)
        order.append(node_id)
        for child, parents in remaining.items():
            if node_id in parents:
                parents.discard(node_id)
                if not parents and child not in order and child not in ready:
                    ready.append(child)
    for node_id in nodes:  # cycle remnants keep declaration order
        if node_id not in order:
            order.append(node_id)
    return order


# --------------------------------------------------------------------------
# Results


@dataclass
class SuggestedFix:
    """A legal coercion that would repair one violated edge."""

    edge_id: str
    rule: CoercionRule
    dimension: str
    from_value: str
    to_value: str
    explanation: str

    @property
    def converter_node_type(self) -> str:
        return self.rule.converter_node_type


@dataclass
class Violation:
    """A blame-attributed contract failure on one edge [S24]."""

    edge_id: str
    dimension: str
    producer_node: str
    producer_guarantee: str
    consumer_node: str
    consumer_assumption: str
    observed_value: str | None = None
    required_value: str | None = None

    def explanation(self) -> str:
        return (
            f"Edge {self.edge_id} violates the {self.dimension} contract: "
            f"node '{self.producer_node}' guarantees {self.dimension}="
            f"{self.observed_value}, but node '{self.consumer_node}' assumes "
            f"{self.dimension}={self.required_value}."
        )


@dataclass
class SemanticCheckResult:
    ok: bool = True
    violations: list[Violation] = field(default_factory=list)
    suggestions: list[SuggestedFix] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    node_states: dict[str, dict[str, dict[str, str]]] = field(default_factory=dict)

    def summary(self) -> str:
        if self.ok and not self.warnings:
            return "semantic contracts satisfied"
        parts = [f"{len(self.violations)} violation(s), {len(self.suggestions)} suggestion(s)"]
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return ", ".join(parts)


# --------------------------------------------------------------------------
# Checking


def _merge_states(
    states: list[dict[str, str]], node_id: str, result: SemanticCheckResult
) -> dict[str, str]:
    """Merge inbound states; disagreeing known values on one dimension is a
    conflict (two producers guaranteeing different assemblies)."""
    merged: dict[str, str] = {}
    for state in states:
        for dimension, value in state.items():
            existing = merged.get(dimension)
            if existing is None or existing == UNKNOWN:
                merged[dimension] = value
            elif value != UNKNOWN and value != existing:
                result.violations.append(
                    Violation(
                        edge_id="graph",
                        dimension=dimension,
                        producer_node=node_id,
                        producer_guarantee=existing,
                        consumer_node=node_id,
                        consumer_assumption=value,
                        observed_value=existing,
                        required_value=value,
                    )
                )
                result.ok = False
    return merged


def _apply_guarantees(
    contract: NodeSemanticContract,
    merged_input_state: dict[str, str],
    node_params: dict[str, Any],
    guarantee_key: str,
) -> dict[str, str]:
    state = dict(merged_input_state)
    for guarantee in contract.outputs.get(guarantee_key, []):
        state[guarantee.dimension] = _resolve_guarantee(
            guarantee, merged_input_state, node_params
        )
    return state


def _resolve_guarantee(
    guarantee: Guarantee, input_state: dict[str, str], node_params: dict[str, Any]
) -> str:
    if guarantee.op == "set":
        return guarantee.value or UNKNOWN
    if guarantee.op == "unknown":
        return UNKNOWN
    if guarantee.op == "param_map":
        raw = (node_params or {}).get(guarantee.param)
        if raw is None:
            return UNKNOWN
        return guarantee.param_map.get(str(raw), UNKNOWN)
    # propagate
    return input_state.get(guarantee.dimension, UNKNOWN)


def _find_coercion(
    library: SemanticContractLibrary,
    dimension: str,
    observed: str | None,
    required: str,
) -> CoercionRule | None:
    for rule in library.coercions_for(dimension):
        if rule.detection:
            continue
        if rule.from_value == observed and rule.to_value == required:
            return rule
    return None


def _find_detection(
    library: SemanticContractLibrary, dimension: str, observed: str | None
) -> CoercionRule | None:
    if observed not in (None, UNKNOWN):
        return None
    rules = [rule for rule in library.coercions_for(dimension) if rule.detection]
    return min(rules, key=lambda rule: rule.cost) if rules else None


def check_workflow_semantics(
    workflow: dict[str, Any],
    library: SemanticContractLibrary | None = None,
) -> SemanticCheckResult:
    """Propagate semantic state through the graph and check every edge."""
    if library is None:
        library = SemanticContractLibrary.bundled()
    result = SemanticCheckResult()

    nodes_raw = workflow.get("nodes", [])
    if isinstance(nodes_raw, dict):
        nodes = {node_id: (node if isinstance(node, dict) else {}) for node_id, node in nodes_raw.items()}
    else:
        nodes = {node["id"]: node for node in nodes_raw if isinstance(node, dict) and node.get("id")}
    edges = [
        edge if isinstance(edge, dict) else dict(edge)
        for edge in workflow.get("edges", [])
    ]

    order = _topological_order(nodes, edges)
    states: dict[str, dict[str, dict[str, str]]] = {}

    for node_id in order:
        node = nodes.get(node_id, {})
        node_type = node.get("type", "")
        params = node.get("params", {}) if isinstance(node.get("params"), dict) else {}
        contract = library.contract_for(node_type)

        # Resolve inbound states from already-computed predecessors
        # (topological order guarantees they exist).
        incoming: list[tuple[dict[str, Any], dict[str, str]]] = []
        for edge in edges:
            endpoints = _edge_endpoints(edge)
            if endpoints is None:
                continue
            source, source_output, target, target_input = endpoints
            if target != node_id or source not in states:
                continue
            output_state = states[source].get(source_output)
            if output_state is not None:
                incoming.append((edge, output_state))

        merged = _merge_states(
            [state for _, state in incoming], node_id, result
        )
        if contract is None:
            states[node_id] = {}
            if node_type:
                result.warnings.append(
                    f"node '{node_id}' (type {node_type}) has no semantic contract;"
                    " its data state is unknown"
                )
            continue

        # Check assumptions on every incoming edge, with blame and coercions.
        for edge, output_state in incoming:
            endpoints = _edge_endpoints(edge)
            if endpoints is None:
                continue
            source, _, _, target_input = endpoints
            clauses = contract.inputs.get(target_input, [])
            for template_clause in clauses:
                clause = template_clause.resolve_required(params)
                if clause.operator == "any":
                    continue
                if clause.accepts(output_state.get(clause.dimension)):
                    continue
                observed = output_state.get(clause.dimension)
                if observed in (None, UNKNOWN):
                    detection = _find_detection(library, clause.dimension, observed)
                    if detection is not None:
                        result.suggestions.append(
                            SuggestedFix(
                                edge_id=edge.get("id", f"{source}->{node_id}"),
                                rule=detection,
                                dimension=clause.dimension,
                                from_value=UNKNOWN,
                                to_value=UNKNOWN,
                                explanation=(
                                    f"Node '{node_id}' assumes {clause.describe()} but the"
                                    f" state from '{source}' is unknown; a runtime"
                                    f" detection step ({detection.converter_node_type})"
                                    " can resolve it before execution."
                                ),
                            )
                        )
                    else:
                        result.warnings.append(
                            f"edge into '{node_id}' port {target_input}:"
                            f" {clause.dimension} is unknown and cannot be checked"
                        )
                    continue
                violation = Violation(
                    edge_id=edge.get("id", f"{source}->{node_id}"),
                    dimension=clause.dimension,
                    producer_node=source,
                    producer_guarantee=observed or "unknown",
                    consumer_node=node_id,
                    consumer_assumption=clause.value or "",
                    observed_value=observed,
                    required_value=clause.value,
                )
                result.violations.append(violation)
                result.ok = False
                coercion = _find_coercion(library, clause.dimension, observed, clause.value or "")
                if coercion is not None:
                    result.suggestions.append(
                        SuggestedFix(
                            edge_id=violation.edge_id,
                            rule=coercion,
                            dimension=clause.dimension,
                            from_value=observed or "",
                            to_value=clause.value or "",
                            explanation=(
                                f"Insert {coercion.converter_node_type} to convert"
                                f" {clause.dimension} from {observed} to {clause.value}."
                                + (f" Requires: {', '.join(coercion.requires)}." if coercion.requires else "")
                            ),
                        )
                    )

        # Produce output states.
        node_states: dict[str, dict[str, str]] = {}
        for output_port, guarantees in contract.outputs.items():
            if not guarantees:
                node_states[output_port] = dict(merged)
                continue
            node_states[output_port] = _apply_guarantees(
                contract, merged, params, output_port
            )
        states[node_id] = node_states

    result.node_states = states
    return result


# --------------------------------------------------------------------------
# Auto-fix insertion


def _make_edge(
    edge: dict[str, Any], *, source: str, source_output: str, target: str, target_input: str
) -> dict[str, Any]:
    """Clone the edge shape of the original workflow with new endpoints."""
    if isinstance(edge.get("from"), dict):
        return {
            "id": f"{source}-to-{target}",
            "from": {"node": source, "output": source_output},
            "to": {"node": target, "input": target_input},
        }
    return {
        "id": f"{source}-to-{target}",
        "from_node": source,
        "from_output": source_output,
        "to_node": target,
        "to_input": target_input,
    }


def apply_suggestions(
    workflow: dict[str, Any],
    result: SemanticCheckResult,
    *,
    only_edges: set[str] | None = None,
) -> dict[str, Any]:
    """Insert converter nodes for non-detection suggestions and rewire edges.

    Detection suggestions (runtime checks that resolve unknown state) are
    reported but not auto-inserted, because they need reference data such as
    a gene model BED and belong in the user's judgement.
    """
    workflow = dict(workflow)
    nodes = list(workflow.get("nodes", []))
    edges = [dict(edge) if isinstance(edge, dict) else dict(edge) for edge in workflow.get("edges", [])]
    nodes_is_dict = isinstance(workflow.get("nodes"), dict)
    node_map = (
        {node_id: dict(node) for node_id, node in nodes.items()} if nodes_is_dict
        else {node["id"]: dict(node) for node in nodes if isinstance(node, dict) and node.get("id")}
    )

    inserted = 0
    for suggestion in result.suggestions:
        if suggestion.rule.detection:
            continue
        if only_edges is not None and suggestion.edge_id not in only_edges:
            continue
        target_index = next(
            (i for i, edge in enumerate(edges) if edge.get("id") == suggestion.edge_id), None
        )
        if target_index is None:
            continue
        edge = edges[target_index]
        endpoints = _edge_endpoints(edge)
        if endpoints is None:
            continue
        source, source_output, target, target_input = endpoints
        converter_id = f"auto_{suggestion.rule.converter_node_type}_{inserted + 1}"
        inserted += 1
        node_map[converter_id] = {
            "id": converter_id,
            "type": suggestion.rule.converter_node_type,
            "params": dict(suggestion.rule.params),
            "position": {"x": 0.0, "y": 0.0},
        }
        edges[target_index] = _make_edge(
            edge,
            source=source,
            source_output=source_output,
            target=converter_id,
            target_input=suggestion.rule.converter_input_port,
        )
        edges.append(
            _make_edge(
                edge,
                source=converter_id,
                source_output=suggestion.rule.converter_output_port,
                target=target,
                target_input=target_input,
            )
        )

    workflow["edges"] = edges
    workflow["nodes"] = node_map if nodes_is_dict else list(node_map.values())
    return workflow
