"""Ownership and pinned-authority contracts for the data-transform wave."""

from __future__ import annotations

from bionodulo.nodes.builtin.data_transform_family import (
    AggregateByGroupNode,
    DeduplicateNode,
    ExtractColumnsNode,
    FilterRowsNode,
    FormatConverterNode,
    JoinTablesNode,
    MathExpressionNode,
    MergeTablesNode,
    ReplaceTextNode,
    SetFieldsNode,
    SortFileNode,
    StringFormatNode,
    TSVToFastaNode,
    TransposeTableNode,
)


FAMILY = (
    AggregateByGroupNode,
    DeduplicateNode,
    ExtractColumnsNode,
    FilterRowsNode,
    FormatConverterNode,
    JoinTablesNode,
    MathExpressionNode,
    MergeTablesNode,
    ReplaceTextNode,
    SetFieldsNode,
    SortFileNode,
    StringFormatNode,
    TSVToFastaNode,
    TransposeTableNode,
)


def test_family_has_exact_focused_ownership_and_python_authority() -> None:
    assert {node.NODE_ID for node in FAMILY} == {
        "aggregate_by_group",
        "deduplicate",
        "extract_columns",
        "filter_rows",
        "format_converter",
        "join_tables",
        "math_expression",
        "merge_tables",
        "replace_text",
        "set_fields",
        "sort_file",
        "string_format",
        "transpose_table",
        "tsv_to_fasta",
    }
    assert all(node.GIT_COMMIT == "3bb231a6a5dc02b95658877318bf61501a7209e9" for node in FAMILY)
    assert all(node.ENVIRONMENT == {"python": "3.12.13", "stdlib_only": True} for node in FAMILY)
    assert all(node.__module__.startswith("bionodulo.nodes.builtin.data_transform_family.") for node in FAMILY)


def test_corrected_generic_contracts() -> None:
    assert FormatConverterNode.REQUIRES_EXTERNAL_TOOLS is False
    assert FormatConverterNode.REQUIRED_EXECUTABLES == []
    assert FormatConverterNode.REQUIRED_CONDA_PACKAGES == []
    assert FormatConverterNode.INPUT_TYPES()["required"]["output_format"][0] == ["csv", "tsv", "json"]
    assert "stable" not in SortFileNode.INPUT_TYPES()["optional"]
    assert "report_dups" not in DeduplicateNode.INPUT_TYPES()["optional"]
    assert AggregateByGroupNode.INPUT_TYPES()["optional"]["value_column"][0] == "STRING"
    for node in (
        DeduplicateNode,
        ExtractColumnsNode,
        FilterRowsNode,
        MergeTablesNode,
        SetFieldsNode,
        SortFileNode,
        TransposeTableNode,
    ):
        assert all(output == "FILE" for output in node.RETURN_TYPES)
