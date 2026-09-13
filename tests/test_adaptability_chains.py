"""Aim B adaptability: one typed graph, interchangeable tool chains.

The dossier strand is "reconfigure an analysis for a different tool chain
without new code". Two structurally different RNA-seq counting chains run
over the SAME contract dimensions (sort_order, strandedness,
normalization_state), with every edge wired to the real registered port
names of the node classes:

* chain A (HISAT2 head, samtools view converter)::

    unstranded_library_reads -> hisat2_align -> samtools_view
        -> samtools_sort -> featurecounts

* chain B (STAR head, Galaxy SAM-to-BAM converter)::

    unstranded_library_reads -> star_align -> sam_to_bam
        -> samtools_sort -> featurecounts

The bundled contract library annotates chain A's nodes but not STAR, and
its HISAT2 contract conservatively reports strandedness=unknown (an
unannotated library). This file therefore composes a library with extra
NodeSemanticContract entries exactly the way tests/test_semantic_contracts.py
does: a synthetic unstranded-library reads producer (the emulation of a
library prep with known protocol) and a propagating HISAT2 contract, plus
a STAR contract keyed to STARAlignNode's real ports (reads/index in,
alignment out).

The planted error is the documented silent-halving failure mode [E8][E11]:
featureCounts ``-s 2`` (reverse) counting an unstranded library. The claim
under test is that the contract system catches the SAME planted error in
BOTH chains - identical enforcement regardless of tool chain is the
adaptability claim.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.semantic_contracts import (
    Guarantee,
    NodeSemanticContract,
    SemanticContractLibrary,
)
from bionodulo.workflow.semantic_checks import check_workflow_semantics

_INDEX_PATH = (
    Path(__file__).resolve().parent.parent / "bionodulo" / "nodes" / "node_index.json"
)

#: The real-node contracts added by this file (the synthetic reads producer
#: has no registered node class by design).
_ALTERNATIVE_CONTRACT_TYPES = ("hisat2_align", "star_align")


def _library() -> SemanticContractLibrary:
    """Bundled library + the chain-B/star and annotated-library contracts.

    The bundled HISAT2 contract is replaced (not duplicated: the library
    rejects duplicate node types) by a variant that propagates the
    annotated library strandedness through the aligner - the honest expert
    model of an annotated run, since an aligner does not alter library
    strandedness.
    """
    bundled = SemanticContractLibrary.bundled()
    hisat2_propagating = NodeSemanticContract(
        node_type="hisat2_align",
        notes="As bundled, but strandedness propagates from the annotated library.",
        inputs={"reads": [], "index": []},
        outputs={
            "alignment": [
                Guarantee(dimension="sort_order", op="set", value="unsorted"),
                Guarantee(dimension="reference_assembly", op="unknown"),
                Guarantee(dimension="strandedness", op="propagate"),
            ]
        },
    )
    star_align = NodeSemanticContract(
        node_type="star_align",
        notes="STAR emits unsorted SAM; library strandedness passes through.",
        inputs={"reads": [], "index": []},
        outputs={
            "alignment": [
                Guarantee(dimension="sort_order", op="set", value="unsorted"),
                Guarantee(dimension="strandedness", op="propagate"),
            ]
        },
    )
    unstranded_library_reads = NodeSemanticContract(
        node_type="unstranded_library_reads",
        notes="Synthetic emulation of an RNA-seq library prep with known "
        "unstranded protocol (the state a run manifest or infer_experiment "
        "would establish).",
        outputs={
            "reads": [Guarantee(dimension="strandedness", op="set", value="unstranded")]
        },
    )
    contracts = tuple(
        contract
        for contract in bundled.contracts
        if contract.node_type != "hisat2_align"
    )
    return SemanticContractLibrary(
        dimensions=bundled.dimensions,
        contracts=(
            *contracts,
            hisat2_propagating,
            star_align,
            unstranded_library_reads,
        ),
        coercions=bundled.coercions,
    )


# --------------------------------------------------------------------------
# Registry cross-validation (tests/test_semantic_contracts.py pattern)


def _node_class(node_type: str) -> Any:
    index = json.loads(_INDEX_PATH.read_text(encoding="utf-8"))
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
    return candidates[0]


def _declared_ports(node_cls: Any) -> tuple[set[str], set[str]]:
    raw_inputs = node_cls.INPUT_TYPES
    input_types = raw_inputs() if callable(raw_inputs) else (raw_inputs or {})
    input_ports: set[str] = set()
    for section in ("required", "optional", "hidden"):
        input_ports.update((input_types.get(section) or {}).keys())
    return input_ports, set(node_cls.RETURN_NAMES or ())


def test_alternative_chain_contracts_use_real_registered_ports() -> None:
    """A contract keyed to a port the node does not have is silently inert;
    the chain-B contracts must match STARAlignNode's and HISAT2AlignNode's
    real ports (reads/index inputs, alignment output)."""
    library = _library()
    for contract in library.contracts:
        if contract.node_type not in _ALTERNATIVE_CONTRACT_TYPES:
            continue
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


# --------------------------------------------------------------------------
# The two chains


def _workflow(
    nodes: list[dict], edges: list[dict]
) -> dict:
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


def _hisat2_chain(strand_specificity: int) -> dict:
    return _workflow(
        [
            _node("lib", "unstranded_library_reads"),
            _node("align", "hisat2_align"),
            _node("view", "samtools_view"),
            _node("sort", "samtools_sort"),
            _node("counts", "featurecounts", {"strand_specificity": strand_specificity}),
        ],
        [
            _edge("e1", "lib", "reads", "align", "reads"),
            _edge("e2", "align", "alignment", "view", "alignment"),
            _edge("e3", "view", "bam", "sort", "alignment"),
            _edge("e4", "sort", "sorted_bam", "counts", "alignment"),
        ],
    )


def _star_chain(strand_specificity: int) -> dict:
    return _workflow(
        [
            _node("lib", "unstranded_library_reads"),
            _node("align", "star_align"),
            _node("convert", "sam_to_bam"),
            _node("sort", "samtools_sort"),
            _node("counts", "featurecounts", {"strand_specificity": strand_specificity}),
        ],
        [
            _edge("e1", "lib", "reads", "align", "reads"),
            _edge("e2", "align", "alignment", "convert", "input"),
            _edge("e3", "convert", "output1", "sort", "alignment"),
            _edge("e4", "sort", "sorted_bam", "counts", "alignment"),
        ],
    )


_CHAINS = {"hisat2": _hisat2_chain, "star": _star_chain}


# --------------------------------------------------------------------------
# (a) correct configuration: both chains check clean


@pytest.mark.parametrize("chain", ["hisat2", "star"], ids=["hisat2_chain", "star_chain"])
def test_alternative_chains_pass_when_configured_correctly(chain: str) -> None:
    """-s 0 (unstranded counting of an unstranded library) is correct in both
    tool chains: zero violations, and the SAME contract dimensions are
    tracked through both graphs."""
    result = check_workflow_semantics(_CHAINS[chain](0), _library())
    assert result.ok
    assert result.violations == []
    assert result.node_states["sort"]["sorted_bam"]["sort_order"] == "coordinate"
    assert result.node_states["sort"]["sorted_bam"]["strandedness"] == "unstranded"
    assert result.node_states["counts"]["counts"]["normalization_state"] == "raw_counts"


# --------------------------------------------------------------------------
# (b) the planted error: -s 2 on unstranded data [E8][E11]


@pytest.mark.parametrize("chain", ["hisat2", "star"], ids=["hisat2_chain", "star_chain"])
def test_planted_strandedness_error_is_caught_in_both_chains(chain: str) -> None:
    """featureCounts -s 2 (reverse) fed by a producer guaranteeing unstranded
    data violates the strandedness contract in BOTH tool chains, with the
    same blame, observed, and required values - the adaptability claim."""
    result = check_workflow_semantics(_CHAINS[chain](2), _library())
    assert not result.ok
    assert len(result.violations) == 1
    violation = result.violations[0]
    assert violation.dimension == "strandedness"
    assert violation.observed_value == "unstranded"
    assert violation.required_value == "reverse"
    assert violation.producer_node == "sort"
    assert violation.consumer_node == "counts"
    assert "guarantees strandedness=unstranded" in violation.explanation()
    # A known-wrong strandedness is never auto-repaired [E57].
    assert not [s for s in result.suggestions if s.dimension == "strandedness"]
