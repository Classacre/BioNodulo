from __future__ import annotations

import math

import pytest

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_utility_primitive_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "string_primitive": ("String", "primitive", ["STRING"], ["value"]),
        "integer_primitive": ("Integer", "primitive", ["INT"], ["value"]),
        "float_primitive": ("Float", "primitive", ["FLOAT"], ["value"]),
        "boolean_primitive": ("Boolean", "primitive", ["BOOLEAN"], ["value"]),
        "math": ("Math", "utils", ["FLOAT", "INT"], ["float_result", "int_result"]),
        "compare": ("Compare", "utils", ["BOOLEAN"], ["result"]),
        "constants": ("Constants", "primitive", ["FLOAT", "INT", "STRING"], ["float_value", "int_value", "name"]),
        "seed": ("Seed", "primitive", ["INT"], ["seed"]),
    }

    for node_id, (display_name, category, outputs, output_names) in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == display_name
        assert node_info["category"] == category
        assert node_info["output"] == outputs
        assert node_info["output_name"] == output_names
        assert node_info["search_aliases"]
        assert node_info["required_executables"] == []
        assert node_info["required_conda_packages"] == []


@pytest.mark.asyncio
async def test_primitive_value_nodes_return_typed_values() -> None:
    assert await _node_class("string_primitive")().run(value=42) == ("42",)
    assert await _node_class("integer_primitive")().run(value="12") == (12,)
    assert await _node_class("float_primitive")().run(value="12.5") == (12.5,)
    assert await _node_class("boolean_primitive")().run(value=True) == (True,)
    assert await _node_class("boolean_primitive")().run(value="false") == (False,)


@pytest.mark.asyncio
async def test_math_node_performs_arithmetic_and_rejects_divide_by_zero() -> None:
    node = _node_class("math")()

    assert await node.run(operation="multiply", a=3, b=2.5) == (7.5, 7)
    assert await node.run(operation="power", a=2, b=8) == (256.0, 256)

    with pytest.raises(ValueError, match="Division by zero"):
        await node.run(operation="divide", a=5, b=0)


@pytest.mark.asyncio
async def test_compare_and_constants_nodes_support_workflow_thresholds() -> None:
    assert await _node_class("compare")().run(operation=">=", a=30.0, b=20.0) == (True,)

    float_value, int_value, name = await _node_class("constants")().run(constant="HG38_SIZE")
    assert float_value == 3_209_286_105.0
    assert int_value == 3_209_286_105
    assert name == "HG38_SIZE"

    pi_float, pi_int, pi_name = await _node_class("constants")().run(constant="PI")
    assert math.isclose(pi_float, math.pi)
    assert pi_int == 3
    assert pi_name == "PI"


@pytest.mark.asyncio
async def test_seed_node_supports_fixed_increment_and_random_cache_busting() -> None:
    node_class = _node_class("seed")

    assert await node_class().run(mode="fixed", seed=2_147_483_647, increment=2) == (1,)

    random_seed = (await node_class().run(mode="random", seed=42))[0]
    assert 0 <= random_seed <= 2_147_483_647
    assert node_class.IS_CHANGED({"mode": "random", "seed": 42}) != node_class.IS_CHANGED({"mode": "random", "seed": 42})
