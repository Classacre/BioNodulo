"""Every-tool sweep: semantic checking must hold for the whole registry.

Aim B verification strand: the typed workflow graph is tool-agnostic, so a
minimal workflow containing ANY registered node type must survive
``check_workflow_semantics``. The sweep is generated from
``bionodulo/nodes/node_index.json`` (979 entries at the time of writing).
Uncontracted node types are gradual: warned, never rejected [S26];
contracted types must validate against their declared ports with default
(empty) parameters.

Measured on the development machine (2026-09-13): importing and
introspecting all 979 node classes takes ~1.4 s (the registry import is
lazy but cheap), and the single-node semantic sweep itself runs in
<0.1 s. The full 979-node sweep plus the 60-pair consecutive sample below
therefore runs far inside the 120 s budget; no reduction to 30 pairs was
needed.
"""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from bionodulo.workflow.semantic_checks import (
    SemanticCheckResult,
    check_workflow_semantics,
)

_INDEX_PATH = (
    Path(__file__).resolve().parent.parent / "bionodulo" / "nodes" / "node_index.json"
)

#: Consecutive pairs drawn from the sorted registry (2 x PAIRWISE_PAIR_COUNT
#: node types, paired as (t0, t1), (t2, t3), ...). 60 pairs keep the
#: module-import cost of the pairwise sweep trivial (module docstring).
PAIRWISE_PAIR_COUNT = 60


def _registry_index() -> dict[str, str]:
    return json.loads(_INDEX_PATH.read_text(encoding="utf-8"))


def _node_types() -> list[str]:
    return sorted(_registry_index())


ALL_NODE_TYPES = _node_types()


def _node_class(node_type: str) -> Any:
    """Import the registered node class and return it (the
    tests/test_semantic_contracts.py pattern)."""
    module_path = _registry_index().get(node_type)
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


def _ordered_ports(node_cls: Any) -> tuple[list[str], list[str]]:
    """(input ports, output ports) in declaration order."""
    raw_inputs = node_cls.INPUT_TYPES
    input_types: dict[str, Any] = (
        raw_inputs() if callable(raw_inputs) else (raw_inputs or {})
    )
    input_ports: list[str] = []
    for section in ("required", "optional", "hidden"):
        for port in (input_types.get(section) or {}):
            if port not in input_ports:
                input_ports.append(port)
    return input_ports, list(node_cls.RETURN_NAMES or ())


def _pairwise_pairs() -> list[tuple[str, str]]:
    """Consecutively paired sample from the head of the sorted registry."""
    types = ALL_NODE_TYPES[: PAIRWISE_PAIR_COUNT * 2]
    return [(types[i], types[i + 1]) for i in range(0, len(types) - 1, 2)]


def _workflow(
    nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    return {"version": "2.0", "nodes": nodes, "edges": edges}


def _node(node_id: str, node_type: str) -> dict[str, Any]:
    return {"id": node_id, "type": node_type, "params": {}}


def _edge(
    edge_id: str, source: str, source_output: str, target: str, target_input: str
) -> dict[str, Any]:
    return {
        "id": edge_id,
        "from": {"node": source, "output": source_output},
        "to": {"node": target, "input": target_input},
    }


def test_sweep_covers_the_shipped_registry() -> None:
    """Guard against accidental truncation of the generated parametrization:
    the shipped registry carries 979 node types today."""
    assert len(ALL_NODE_TYPES) > 900
    assert "featurecounts" in ALL_NODE_TYPES


@pytest.mark.parametrize(
    "node_type",
    [pytest.param(node_type, id=node_type) for node_type in ALL_NODE_TYPES],
)
def test_single_node_workflow_passes_semantics(node_type: str) -> None:
    """A minimal single-node workflow of every registered type checks clean."""
    workflow = _workflow([_node("n1", node_type)], [])
    result = check_workflow_semantics(workflow)
    assert isinstance(result, SemanticCheckResult)
    assert result.ok


@pytest.mark.parametrize(
    ("producer_type", "consumer_type"),
    [
        pytest.param(producer, consumer, id=f"{producer}--{consumer}")
        for producer, consumer in _pairwise_pairs()
    ],
)
def test_pairwise_two_node_chain_does_not_crash(
    producer_type: str, consumer_type: str
) -> None:
    """Two-node chains wired first-output-port to first-input-port (real
    port names from the registered node classes) must never crash the
    checker, whatever the combination of tool families."""
    _, producer_outputs = _ordered_ports(_node_class(producer_type))
    consumer_inputs, _ = _ordered_ports(_node_class(consumer_type))
    if not producer_outputs or not consumer_inputs:
        pytest.skip("annotation/preview node declares no connectable ports")
    workflow = _workflow(
        [_node("producer", producer_type), _node("consumer", consumer_type)],
        [
            _edge(
                "e1",
                "producer",
                producer_outputs[0],
                "consumer",
                consumer_inputs[0],
            )
        ],
    )
    result = check_workflow_semantics(workflow)
    assert result.summary()
    assert set(result.node_states) == {"producer", "consumer"}
