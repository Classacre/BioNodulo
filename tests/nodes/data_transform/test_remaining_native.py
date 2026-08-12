from __future__ import annotations


import pytest

from bionodulo.nodes.builtin.data_transform_family.aggregate import AggregateNode
from bionodulo.nodes.builtin.data_transform_family.normalize_data import NormalizeDataNode
from bionodulo.nodes.builtin.data_transform_family.pivot_table import PivotTableNode, ReshapeTableNode
from bionodulo.nodes.builtin.data_transform_family.sample_subset import SampleSubsetNode
from bionodulo.nodes.builtin.data_transform_family.split_file import SplitFileNode
from bionodulo.nodes.builtin.input_family.sample_sheet import SampleSheetNode
from bionodulo.nodes.builtin.r_family.dataframe_builder import DataFrameBuilderNode

SOURCE_COMMITS = {
    "aggregate": "45518cfd3754b40ae44304bd65bc17d5ee6e2816",
    "normalize_data": "45518cfd3754b40ae44304bd65bc17d5ee6e2816",
    "pivot_table": "45518cfd3754b40ae44304bd65bc17d5ee6e2816",
    "reshape_table": "45518cfd3754b40ae44304bd65bc17d5ee6e2816",
    "sample_subset": "45518cfd3754b40ae44304bd65bc17d5ee6e2816",
    "split_file": "45518cfd3754b40ae44304bd65bc17d5ee6e2816",
    "input_sample_sheet": "827ffffc57530d60becfc66f190c35e79d2df7fc",
    "r_dataframe_builder": "827ffffc57530d60becfc66f190c35e79d2df7fc",
}
VERSIONS = {node_id: "1.0.0" for node_id in SOURCE_COMMITS}
VERSIONS["input_sample_sheet"] = "2.1.0"

NODE_CLASSES = {
    node.NODE_ID: node
    for node in (
        AggregateNode,
        NormalizeDataNode,
        PivotTableNode,
        ReshapeTableNode,
        SampleSubsetNode,
        SplitFileNode,
        SampleSheetNode,
        DataFrameBuilderNode,
    )
}

PORT_CONTRACTS = {
    "aggregate": (
        {"table", "group_columns", "agg_column", "agg_function"},
        {"agg_column_2", "agg_function_2", "output_type"},
        ("CSV",),
        ("aggregated_table",),
    ),
    "normalize_data": (
        {"table", "method"},
        {"id_columns", "axis", "pseudocount", "min_max_range", "output_type"},
        ("CSV",),
        ("normalized_table",),
    ),
    "pivot_table": (
        {"table", "operation"},
        {
            "index_column", "index_columns", "names_from", "columns_column", "values_from",
            "values_column", "fill_value", "id_columns", "id_vars", "value_columns",
            "value_vars", "variable_name", "var_name", "value_name", "agg_func", "delimiter",
            "output_type",
        },
        ("CSV",),
        ("reshaped_table",),
    ),
    "reshape_table": (
        {"table", "direction", "id_vars"},
        {
            "value_vars", "names_to", "values_to", "names_from", "values_from", "fill_value",
            "delimiter", "output_type",
        },
        ("CSV",),
        ("reshaped_table",),
    ),
    "sample_subset": (
        {"file", "n"},
        {"mode", "seed", "stratify_column", "every_n", "output_type"},
        ("FILE",),
        ("subset_file",),
    ),
    "split_file": (
        {"file", "split_mode"},
        {"lines_per_chunk", "split_column", "max_size_mb", "records_per_chunk", "has_header", "output_type"},
        ("DIRECTORY",),
        ("chunks_dir",),
    ),
    "input_sample_sheet": (
        {"sample_sheet"},
        set(),
        ("SAMPLE_SHEET",),
        ("sample_sheet",),
    ),
    "r_dataframe_builder": (
        {"x_column", "x_values", "y_column", "y_values"},
        {"group_column", "group_values"},
        ("CSV",),
        ("csv",),
    ),
}


def test_native_data_operations_preserve_pinned_contract_metadata() -> None:
    for node_id, node_class in NODE_CLASSES.items():
        assert node_class.PRODUCT_SOURCE_COMMIT == SOURCE_COMMITS[node_id]
        assert node_class.GIT_URL == "https://github.com/Classacre/BioNodulo.git"
        assert node_class.GIT_COMMIT == node_class.PRODUCT_SOURCE_COMMIT
        assert node_class.PRODUCT_SOURCE_PATH in node_class.SOURCE_URL
        assert node_class.PRODUCT_SOURCE_COMMIT in node_class.SOURCE_URL
        assert node_class.UPSTREAM_SOURCE == (
            f"{node_class.PRODUCT_SOURCE_PATH}:{node_class.PRODUCT_SOURCE_SYMBOL}"
        )
        assert node_class.SOURCE_AUTHORITIES["product_contract"] == node_class.SOURCE_URL
        assert node_class.DOCUMENTATION_URL.startswith("https://")
        assert node_class.DOCUMENTATION_URL in node_class.RUNTIME_DOCUMENTATION_URLS
        assert node_class.EXIT_SEMANTICS.startswith("This ")
        assert node_class.REQUIRED_EXECUTABLES == []
        assert node_class.REQUIRED_CONDA_PACKAGES == []
        assert node_class.VERSION == VERSIONS[node_id]


@pytest.mark.parametrize("node_id", sorted(PORT_CONTRACTS))
def test_native_data_operation_ports_parameters_outputs_and_errors_are_explicit(node_id: str) -> None:
    node_class = NODE_CLASSES[node_id]
    required, optional, return_types, return_names = PORT_CONTRACTS[node_id]
    inputs = node_class.INPUT_TYPES()

    assert set(inputs["required"]) == required
    assert set(inputs.get("optional", {})) == optional
    assert node_class.RETURN_TYPES == return_types
    assert node_class.RETURN_NAMES == return_names
    assert "raise" in node_class.EXIT_SEMANTICS


def test_native_data_operation_selector_defaults_match_the_implemented_branches() -> None:
    assert AggregateNode.INPUT_TYPES()["required"]["agg_function"][1] == {
        "default": "sum",
        "options": AggregateNode._FUNCTIONS,
    }
    assert NormalizeDataNode.INPUT_TYPES()["required"]["method"][1] == {
        "default": "z_score",
        "options": NormalizeDataNode._METHODS,
    }
    assert PivotTableNode.INPUT_TYPES()["required"]["operation"][1]["options"] == [
        "pivot_wide", "melt_long", "pivot_table_agg",
    ]
    assert ReshapeTableNode.INPUT_TYPES()["required"]["direction"][1] == {
        "default": "long",
        "options": ["long", "wide"],
    }
    assert SampleSubsetNode.INPUT_TYPES()["optional"]["mode"][1]["default"] == "random"
    assert SplitFileNode.INPUT_TYPES()["required"]["split_mode"][1]["options"] == [
        "by_line_count", "by_column_value", "by_file_size", "by_record_count",
    ]
    assert "URL" in SampleSheetNode.INPUT_TYPES()["required"]["sample_sheet"][1]["description"]
    assert DataFrameBuilderNode.INPUT_TYPES()["optional"]["group_column"][1]["default"] == ""
