from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.variant_family.adapter import VariantCommandNode
from bionodulo.nodes.builtin.variant_family.legacy import _VcfToolsFilterContract
from bionodulo.nodes.builtin.variant_family.vcftools_filter import (
    VCFTOOLS_COMMIT,
    VcfToolsFilterNode,
)


def test_authority_is_pinned_to_vcftools_0_1_17_source() -> None:
    assert VCFTOOLS_COMMIT == "1c53c3c73be141103069965403e655536dda9c87"
    assert VcfToolsFilterNode.VERSION == "0.1.17"
    assert VcfToolsFilterNode.GIT_COMMIT == VCFTOOLS_COMMIT
    assert VcfToolsFilterNode.PINNED_SOURCE_URL.endswith(VCFTOOLS_COMMIT)
    assert VCFTOOLS_COMMIT in VcfToolsFilterNode.DOCUMENTATION_URL
    assert VcfToolsFilterNode.UPSTREAM_MANPAGE == "src/cpp/vcftools.1"
    assert VcfToolsFilterNode.UPSTREAM_PARSER_SOURCE == "src/cpp/parameters.cpp"
    assert VcfToolsFilterNode.UPSTREAM_FILTER_SOURCE == "src/cpp/entry_filters.cpp"
    assert VcfToolsFilterNode.UPSTREAM_OUTPUT_SOURCE == "src/cpp/vcf_file.cpp"
    assert VcfToolsFilterNode.PACKAGE_CONSTRAINTS == ("vcftools==0.1.17",)
    assert VcfToolsFilterNode.CITATION_DOIS == ["10.1093/bioinformatics/btr330"]


def test_focused_owner_has_no_legacy_contract_or_copy_workaround() -> None:
    assert VcfToolsFilterNode.__bases__ == (VariantCommandNode,)
    assert _VcfToolsFilterContract not in VcfToolsFilterNode.__mro__
    assert "run" not in VcfToolsFilterNode.__dict__


def test_ports_match_sequential_plain_or_gzip_vcf_contract() -> None:
    ports = VcfToolsFilterNode.INPUT_TYPES()

    assert ports["required"]["vcf"][0] == ("VCF", "VCF_GZ")
    assert set(ports["optional"]) == {
        "maf",
        "min_qual",
        "min_mean_depth",
        "max_missing",
        "recode_info_all",
    }
    assert all(
        ports["optional"][key][1]["default"] is None
        for key in ("maf", "min_qual", "min_mean_depth", "max_missing")
    )
    assert ports["optional"]["min_qual"][0] == "FLOAT"
    assert ports["optional"]["min_mean_depth"][0] == "FLOAT"
    assert not any("index" in name for group in ports.values() for name in group)


def test_plain_vcf_defaults_emit_no_filters_and_plan_native_output(tmp_path: Path) -> None:
    node_output = tmp_path / VcfToolsFilterNode.NODE_ID
    inputs = {"vcf": "/data/cohort.vcf", "output": node_output}

    assert VcfToolsFilterNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        node_output / "filtered.recode.vcf"
    ]
    assert VcfToolsFilterNode.render_command(inputs) == [
        "vcftools",
        "--vcf",
        "/data/cohort.vcf",
        "--recode",
        "--out",
        str(node_output / "filtered"),
    ]


def test_gzip_vcf_selected_filters_emit_exact_parser_flags(tmp_path: Path) -> None:
    node_output = tmp_path / VcfToolsFilterNode.NODE_ID

    assert VcfToolsFilterNode.render_command(
        {
            "vcf": "/data/cohort.vcf.gz",
            "output": node_output,
            "maf": 0,
            "min_qual": 12.5,
            "min_mean_depth": 7.25,
            "max_missing": 0.9,
            "recode_info_all": True,
        }
    ) == [
        "vcftools",
        "--gzvcf",
        "/data/cohort.vcf.gz",
        "--maf",
        "0",
        "--minQ",
        "12.5",
        "--min-meanDP",
        "7.25",
        "--max-missing",
        "0.9",
        "--recode-INFO-all",
        "--recode",
        "--out",
        str(node_output / "filtered"),
    ]


def test_exposed_numeric_filters_fail_closed_on_invalid_values() -> None:
    invalid = (
        ({"maf": -0.01}, "maf must be at least 0"),
        ({"maf": 1.01}, "maf must be at most 1"),
        ({"max_missing": -0.01}, "max_missing must be at least 0"),
        ({"max_missing": 1.01}, "max_missing must be at most 1"),
        ({"min_qual": -1}, "min_qual must be at least 0"),
        ({"min_mean_depth": -1}, "min_mean_depth must be at least 0"),
        ({"min_qual": float("inf")}, "min_qual must be finite"),
        ({"min_mean_depth": float("nan")}, "min_mean_depth must be finite"),
        ({"maf": True}, "maf must be a number"),
    )

    for update, message in invalid:
        assert VcfToolsFilterNode.VALIDATE_INPUTS(
            {"vcf": "/data/cohort.vcf", **update}
        ) == message

    with pytest.raises(ValueError, match="maf must be at most 1"):
        VcfToolsFilterNode.render_command({"vcf": "/data/cohort.vcf", "maf": 2})


def test_exit_semantics_are_candid_about_upstream_zero_exit_errors() -> None:
    semantics = VcfToolsFilterNode.EXIT_SEMANTICS

    assert "exit 0" in semantics
    assert "exit 76" in semantics
    assert "exit 3" in semantics
    assert "missing filtered.recode.vcf" in semantics
    assert VcfToolsFilterNode.AUDIT_STATUS == "contract-checked-no-external-execution"
