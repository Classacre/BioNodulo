from __future__ import annotations

import importlib

from scripts.gen_node_index import build_index


EXPECTED_OWNERS = {
    "aggregate": "aggregate",
    "normalize_data": "normalize_data",
    "pivot_table": "pivot_table",
    "reshape_table": "pivot_table",
    "sample_subset": "sample_subset",
    "split_file": "split_file",
}

SOURCE_COMMITS = {
    "aggregate": "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d",
    "normalize_data": "b99776d746d22e3ec343bb88b86a3341fb31ad80",
    "pivot_table": "9c56cf0fe43457732e2496ad4445d9348da75a64",
    "reshape_table": "9c56cf0fe43457732e2496ad4445d9348da75a64",
    "sample_subset": "3e6970cfcdac1ac2c452aa94f5190ba61ba3ce6d",
    "split_file": "b43aa78217410abe83d886821c8b8194734ece88",
}


def test_native_data_operations_have_focused_pinned_owners() -> None:
    index = build_index()

    for node_id, module_name in EXPECTED_OWNERS.items():
        owner_name = f"bionodulo.nodes.builtin.data_transform_family.{module_name}"
        assert index[node_id] == owner_name
        owner = importlib.import_module(owner_name)
        node_class = next(
            value
            for value in vars(owner).values()
            if isinstance(value, type)
            and value.__module__ == owner_name
            and getattr(value, "NODE_ID", None) == node_id
        )
        assert node_class.PRODUCT_SOURCE_COMMIT == SOURCE_COMMITS[node_id]
        assert node_class.REQUIRED_EXECUTABLES == []
        assert node_class.REQUIRED_CONDA_PACKAGES == []
        assert node_class.ENVIRONMENT == {"python": "3.12.13", "stdlib_only": True}
        assert node_class.VERSION == "1.0.0"


def test_legacy_imports_resolve_to_focused_classes() -> None:
    for node_id, module_name in EXPECTED_OWNERS.items():
        facade_name = {
            "aggregate": "aggregate",
            "normalize_data": "normalize_data",
            "pivot_table": "pivot_table",
            "reshape_table": "pivot_table",
            "sample_subset": "sample_subset",
            "split_file": "split_file",
        }[node_id]
        facade = importlib.import_module(f"bionodulo.nodes.builtin.{facade_name}")
        owner = importlib.import_module(
            f"bionodulo.nodes.builtin.data_transform_family.{module_name}"
        )
        node_class = next(
            value
            for value in vars(owner).values()
            if isinstance(value, type)
            and value.__module__ == owner.__name__
            and getattr(value, "NODE_ID", None) == node_id
        )
        assert node_class in vars(facade).values()
