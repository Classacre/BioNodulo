"""Tests for the semantic contract schema and per-edge checker.

Grounded in dossier sections 8.1 and 8.2. Every scenario mirrors a
documented failure mode: strandedness mismatches silently halving counts
[E8][E11], sort-order requirements, reference-build conflicts, and gradual
unknowns resolved by runtime detection [E9][E10].
"""

from __future__ import annotations

import pytest

from bionodulo.nodes.semantic_contracts import (
    Clause,
    CoercionRule,
    Guarantee,
    NodeSemanticContract,
    SemanticContractLibrary,
    SemanticDimension,
)
from bionodulo.workflow.semantic_checks import (
    apply_suggestions,
    check_workflow_semantics,
)


def _library() -> SemanticContractLibrary:
    return SemanticContractLibrary.bundled()


# --------------------------------------------------------------------------
# Schema


def test_dimensions_must_include_unknown() -> None:
    with pytest.raises(ValueError, match="must include 'unknown'"):
        SemanticDimension(name="bad", values=("a", "b"))


def test_clause_value_must_be_dimension_member() -> None:
    library = _library()
    contract = NodeSemanticContract(
        node_type="broken",
        inputs={"alignment": [Clause(dimension="sort_order", value="sideways")]},
    )
    with pytest.raises(ValueError, match="not a member"):
        SemanticContractLibrary(
            dimensions=library.dimensions, contracts=(contract,)
        )


def test_detection_rule_cannot_rewrite_known_state() -> None:
    library = _library()
    with pytest.raises(ValueError, match="detection rules must target"):
        SemanticContractLibrary(
            dimensions=library.dimensions,
            coercions=(
                CoercionRule(
                    id="bad_detect",
                    dimension="strandedness",
                    from_value="forward",
                    to_value="reverse",
                    converter_node_type="rseqc_infer_experiment",
                    converter_input_port="input",
                    converter_output_port="infer_experiment",
                    detection=True,
                ),
            ),
        )


def test_bundled_library_loads_and_validates() -> None:
    library = _library()
    assert library.dimensions
    assert library.contract_for("samtools_sort") is not None
    assert library.contract_for("does_not_exist") is None


# --------------------------------------------------------------------------
# Registry cross-validation: contract ports must match real node ports


def _node_class(node_type: str):
    """Import the registered node class and return it."""
    import importlib
    import inspect
    import json
    from pathlib import Path

    index = json.loads(
        (
            Path(__file__).resolve().parent.parent
            / "bionodulo"
            / "nodes"
            / "node_index.json"
        ).read_text(encoding="utf-8")
    )
    module_path = index.get(node_type)
    assert module_path, f"node type {node_type} is not in the registry index"
    module = importlib.import_module(module_path)
    candidates = [
        member
        for _, member in inspect.getmembers(module, inspect.isclass)
        if member.__module__ == module.__name__
        and hasattr(member, "RETURN_NAMES")
        and hasattr(member, "INPUT_TYPES")
    ]
    assert candidates, f"no node class with ports defined in {module_path}"
    node_cls = candidates[0]
    return node_cls


def _declared_ports(node_cls) -> tuple[set[str], set[str]]:
    raw_inputs = node_cls.INPUT_TYPES
    input_types = raw_inputs() if callable(raw_inputs) else (raw_inputs or {})
    input_ports = set()
    for section in ("required", "optional", "hidden"):
        input_ports.update((input_types.get(section) or {}).keys())
    return input_ports, set(node_cls.RETURN_NAMES or ())


def test_seed_contract_ports_match_registered_nodes() -> None:
    """A contract keyed to a port the node does not have is silently inert;
    this test makes that class of bug impossible to ship."""
    library = _library()
    for contract in library.contracts:
        node_cls = _node_class(contract.node_type)
        input_ports, output_ports = _declared_ports(node_cls)
        for port in contract.inputs:
            assert port in input_ports, (
                f"{contract.node_type} contract input port '{port}' is not a"
                " registered input port"
            )
        for port in contract.outputs:
            assert port in output_ports, (
                f"{contract.node_type} contract output port '{port}' is not a"
                " registered output port"
            )


def test_coercion_converter_ports_match_registered_nodes() -> None:
    library = _library()
    for rule in library.coercions:
        node_cls = _node_class(rule.converter_node_type)
        input_ports, output_ports = _declared_ports(node_cls)
        assert rule.converter_input_port in input_ports, (
            f"coercion {rule.id} input port '{rule.converter_input_port}' is"
            f" not a registered port of {rule.converter_node_type}"
        )
        assert rule.converter_output_port in output_ports, (
            f"coercion {rule.id} output port '{rule.converter_output_port}' is"
            f" not a registered port of {rule.converter_node_type}"
        )


# --------------------------------------------------------------------------
# Propagation and passing checks


def _workflow(nodes: list[dict], edges: list[dict]) -> dict:
    return {"version": "2.0", "nodes": nodes, "edges": edges}


def _node(node_id: str, node_type: str, params: dict | None = None) -> dict:
    return {"id": node_id, "type": node_type, "params": params or {}}


def _edge(
    edge_id: str, source: str, source_output: str, target: str, target_input: str
) -> dict:
    return {
        "id": edge_id,
        "from": {"node": source, "output": source_output},
        "to": {"node": target, "input": target_input},
    }


def test_sort_pipeline_propagates_coordinate_order() -> None:
    workflow = _workflow(
        [
            _node("align", "hisat2_align"),
            _node("view", "samtools_view"),
            _node("sort", "samtools_sort"),
            _node("counts", "featurecounts", {"strand_specificity": 0}),
        ],
        [
            _edge("e1", "align", "alignment", "view", "alignment"),
            _edge("e2", "view", "bam", "sort", "alignment"),
            _edge("e3", "sort", "sorted_bam", "counts", "alignment"),
        ],
    )
    result = check_workflow_semantics(workflow, _library())
    assert result.ok
    assert result.node_states["align"]["alignment"]["sort_order"] == "unsorted"
    assert result.node_states["view"]["bam"]["sort_order"] == "unsorted"
    assert result.node_states["sort"]["sorted_bam"]["sort_order"] == "coordinate"
    # featureCounts emits raw counts [S35].
    assert result.node_states["counts"]["counts"]["normalization_state"] == "raw_counts"


def test_unannotated_nodes_are_gradual_warnings() -> None:
    workflow = _workflow(
        [_node("mystery", "custom_node")],
        [],
    )
    result = check_workflow_semantics(workflow, _library())
    assert result.ok
    assert any("no semantic contract" in warning for warning in result.warnings)


# --------------------------------------------------------------------------
# Violations with blame


def test_strandedness_mismatch_violation_blames_producer_and_consumer() -> None:
    # A reverse-stranded assumption (featureCounts -s 2) fed by a node
    # guaranteeing forward strandedness: the documented silent-halving
    # error [E8][E11].
    library = _library()
    annotated_input = NodeSemanticContract(
        node_type="annotated_aligner",
        inputs={"reads": []},
        outputs={
            "alignment": [
                Guarantee(dimension="strandedness", op="set", value="forward"),
                Guarantee(dimension="sort_order", op="set", value="coordinate"),
            ]
        },
    )
    library = SemanticContractLibrary(
        dimensions=library.dimensions,
        contracts=(*library.contracts, annotated_input),
        coercions=library.coercions,
    )
    workflow = _workflow(
        [
            _node("align", "annotated_aligner"),
            _node("counts", "featurecounts", {"strand_specificity": 2}),
        ],
        [_edge("e1", "align", "alignment", "counts", "alignment")],
    )
    result = check_workflow_semantics(workflow, library)
    assert not result.ok
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.dimension == "strandedness"
    assert violation.producer_node == "align"
    assert violation.consumer_node == "counts"
    assert violation.observed_value == "forward"
    assert violation.required_value == "reverse"
    assert "guarantees strandedness=forward" in violation.explanation()
    # No coercion can legally rewrite a known-wrong strandedness [E57].
    assert not [s for s in result.suggestions if s.dimension == "strandedness"]


def test_conflicting_assembly_states_across_two_producers() -> None:
    library = _library()
    grch37 = NodeSemanticContract(
        node_type="producer37",
        outputs={"alignment": [Guarantee(dimension="reference_assembly", op="set", value="grch37")]},
    )
    grch38 = NodeSemanticContract(
        node_type="producer38",
        outputs={"alignment": [Guarantee(dimension="reference_assembly", op="set", value="grch38")]},
    )
    combiner = NodeSemanticContract(
        node_type="combiner",
        inputs={"left": [], "right": []},
        outputs={"merged": [Guarantee(dimension="reference_assembly", op="propagate")]},
    )
    library = SemanticContractLibrary(
        dimensions=library.dimensions,
        contracts=(*library.contracts, grch37, grch38, combiner),
        coercions=library.coercions,
    )
    workflow = _workflow(
        [
            _node("a", "producer37"),
            _node("b", "producer38"),
            _node("m", "combiner"),
        ],
        [
            _edge("e1", "a", "alignment", "m", "left"),
            _edge("e2", "b", "alignment", "m", "right"),
        ],
    )
    result = check_workflow_semantics(workflow, library)
    assert not result.ok
    assert any(v.dimension == "reference_assembly" for v in result.violations)


# --------------------------------------------------------------------------
# Coercions


def _coord_hungry_library() -> SemanticContractLibrary:
    library = _library()
    consumer = NodeSemanticContract(
        node_type="needs_coordinate",
        inputs={
            "alignment": [Clause(dimension="sort_order", value="coordinate")],
        },
        outputs={"result": []},
    )
    unsorted_producer = NodeSemanticContract(
        node_type="produces_unsorted",
        outputs={
            "alignment": [Guarantee(dimension="sort_order", op="set", value="unsorted")]
        },
    )
    return SemanticContractLibrary(
        dimensions=library.dimensions,
        contracts=(*library.contracts, consumer, unsorted_producer),
        coercions=library.coercions,
    )


def test_unsorted_to_coordinate_suggests_samtools_sort_and_rewires() -> None:
    library = _coord_hungry_library()
    workflow = _workflow(
        [
            _node("align", "produces_unsorted"),
            _node("call", "needs_coordinate"),
        ],
        [_edge("e1", "align", "alignment", "call", "alignment")],
    )
    result = check_workflow_semantics(workflow, library)
    assert not result.ok
    fix = next(s for s in result.suggestions if s.rule.id == "sort_unsorted_to_coordinate")
    assert fix.converter_node_type == "samtools_sort"

    fixed = apply_suggestions(workflow, result)
    assert any(
        node["type"] == "samtools_sort" for node in fixed["nodes"]
    ), "converter node must be inserted"
    assert len(fixed["edges"]) == 2, "original edge must split into two"
    endpoints = {edge["from"]["node"] for edge in fixed["edges"]}
    assert "auto_samtools_sort_1" in endpoints

    # The fixed workflow must now satisfy the contract.
    rechecked = check_workflow_semantics(fixed, library)
    assert rechecked.ok
    assert rechecked.node_states["call"]["result"]["sort_order"] == "coordinate"


def test_unknown_strandedness_suggests_runtime_detection_not_rejection() -> None:
    library = _library()
    workflow = _workflow(
        [
            _node("align", "hisat2_align"),
            _node("counts", "featurecounts", {"strand_specificity": 1}),
        ],
        [_edge("e1", "align", "alignment", "counts", "alignment")],
    )
    result = check_workflow_semantics(workflow, library)
    # Gradual: unknown state never rejects [S26].
    assert result.ok
    detections = [
        s for s in result.suggestions if s.rule.id == "strandedness_unknown_detect"
    ]
    assert detections, "an unknown strandedness should suggest infer_experiment"
    assert "infer_experiment" in detections[0].explanation
    # Detection fixes are never auto-inserted (they need reference data).
    fixed = apply_suggestions(workflow, result)
    assert not any(
        node["type"] == "rseqc_infer_experiment" for node in fixed["nodes"]
    )


def test_flat_edge_shape_is_supported() -> None:
    workflow = {
        "version": "2.0",
        "nodes": [
            _node("align", "hisat2_align"),
            _node("counts", "featurecounts", {"strand_specificity": 0}),
        ],
        "edges": [
            {
                "id": "e1",
                "from_node": "align",
                "from_output": "alignment",
                "to_node": "counts",
                "to_input": "alignment",
            }
        ],
    }
    result = check_workflow_semantics(workflow, _library())
    assert result.ok
    assert result.node_states["counts"]["counts"]["normalization_state"] == "raw_counts"
