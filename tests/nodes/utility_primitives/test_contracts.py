from __future__ import annotations

import math

import pytest

from bionodulo.nodes.builtin.utility_primitives_family import adapter
from bionodulo.nodes.builtin.utility_primitives_family.float_primitive import FloatPrimitiveNode
from bionodulo.nodes.builtin.utility_primitives_family.integer_primitive import IntegerPrimitiveNode
from bionodulo.nodes.builtin.utility_primitives_family.math_operation import MathNode
from bionodulo.nodes.builtin.utility_primitives_family.range_list import RangeListNode
from bionodulo.nodes.registry import NodeRegistry


EXPECTED_MODULES = {
    node_id: f"bionodulo.nodes.builtin.utility_primitives_family.{module}"
    for node_id, module in {
        "boolean_primitive": "boolean_primitive",
        "compare": "compare",
        "constants": "constants",
        "float_primitive": "float_primitive",
        "integer_primitive": "integer_primitive",
        "math": "math_operation",
        "random_seed": "random_seed",
        "range_list": "range_list",
        "seed": "seed",
        "string_primitive": "string_primitive",
    }.items()
}


def test_utility_primitive_ids_have_one_focused_owner() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert {node_id: registry.get(node_id).__module__ for node_id in EXPECTED_MODULES} == EXPECTED_MODULES
    adapter_classes = [
        value
        for value in vars(adapter).values()
        if isinstance(value, type) and value.__module__ == adapter.__name__
    ]
    assert all(not value.__dict__.get("NODE_ID") for value in adapter_classes)
    assert all(registry.get(node_id).GIT_COMMIT == adapter.BIONODULO_SOURCE_COMMIT for node_id in EXPECTED_MODULES)


@pytest.mark.asyncio
async def test_primitive_numeric_nodes_reject_lossy_or_non_finite_values() -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        await IntegerPrimitiveNode().run(value=1.5)
    with pytest.raises(ValueError, match="between -2147483648"):
        await IntegerPrimitiveNode().run(value=2**31)
    with pytest.raises(ValueError, match="finite"):
        await FloatPrimitiveNode().run(value=math.inf)
    with pytest.raises(ValueError, match="finite real result"):
        await MathNode().run(operation="power", a=10.0, b=1000.0)


@pytest.mark.asyncio
async def test_range_list_fails_before_materializing_unbounded_output() -> None:
    with pytest.raises(ValueError, match="cannot produce more than 1000000"):
        await RangeListNode().run(start=0, stop=adapter.MAX_RANGE_ITEMS + 1, step=1)
