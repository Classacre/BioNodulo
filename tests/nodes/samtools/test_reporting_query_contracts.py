from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.samtools_family.adapter import _flag_sum
from bionodulo.nodes.registry import NodeRegistry


def _node(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get(node_id)
    assert node is not None
    return node


def test_samtools_flag_masks_follow_bam_str2flag_syntax() -> None:
    # The pinned tools accept symbolic names and 0x/0-prefixed masks, and
    # combine repeated values as a bitwise mask rather than decimal addition.
    assert _flag_sum("READ2,REVERSE") == 0x90
    assert _flag_sum(["0x40", "010"]) == 0x48
    assert _flag_sum(["DUP", 0x400]) == 0x400

    with pytest.raises(ValueError, match="unsupported SAM flag"):
        _flag_sum("not-a-flag")


def test_bedcov_exposes_documented_depth_count_and_header_options() -> None:
    node = _node("samtools_bedcov")
    command = node.render_command(
        {
            "input_bed": "targets.bed",
            "input_bams": ["reads.bam"],
            "bam_indexes": ["reads.bam.bai"],
            "max_depth": 1000,
            "depth_thresh": 20,
            "read_count": True,
            "header": True,
        }
    )
    assert command == [
        "samtools",
        "bedcov",
        "-d",
        "20",
        "--max-depth",
        "1000",
        "-c",
        "-H",
        "-X",
        "targets.bed",
        "reads.bam",
        "reads.bam.bai",
    ]


def test_coverage_renders_source_supported_filters_and_keeps_sibling_index_contract() -> None:
    node = _node("samtools_coverage")
    inputs = {
        "input_bams": ["reads.bam"],
        "bam_indexes": ["reads.bam.bai"],
        "region": "chr1:1-20",
        "max_depth": 500,
        "min_depth": 2,
        "plot_depth": True,
        "ascii": True,
        "output": "/work/coverage",
    }
    assert node.VALIDATE_INPUTS(inputs) is True
    command = node.render_command(inputs)
    assert ["-d", "500"] == command[command.index("-d") : command.index("-d") + 2]
    assert "--min-depth" in command
    assert "-D" in command and "-A" in command
    assert "-X" not in command  # coverage.c has no custom-index option
    assert command[-3:] == ["-o", "/work/coverage/coverage.txt", "reads.bam"]

    default_histogram = node.render_command({"input_bams": ["reads.bam"], "histogram": True})
    assert default_histogram[default_histogram.index("-w") + 1] == "50"

    tabular = node.render_command({"input_bams": ["reads.bam"], "no_header": True})
    assert "-H" in tabular

    invalid_coverage = node.VALIDATE_INPUTS(
        {**inputs, "bam_indexes": ["/elsewhere/reads.bam.bai"]}
    )
    assert invalid_coverage is not True


def test_coverage_rejects_ignored_values_and_applies_bins_to_implied_histograms() -> None:
    node = _node("samtools_coverage")

    assert node.VALIDATE_INPUTS({"input_bams": ["reads.bam"], "min_depth": 0}) is not True
    assert node.VALIDATE_INPUTS({"input_bams": ["reads.bam"], "n_bins": 20}) is not True
    assert (
        node.VALIDATE_INPUTS(
            {"input_bams": ["reads.bam"], "plot_depth": True, "no_header": True}
        )
        is not True
    )

    plot_command = node.render_command(
        {"input_bams": ["reads.bam"], "plot_depth": True, "n_bins": 20}
    )
    assert ["-D", "-w", "20"] == plot_command[
        plot_command.index("-D") : plot_command.index("-D") + 3
    ]

    ascii_command = node.render_command(
        {"input_bams": ["reads.bam"], "ascii": True, "n_bins": 30}
    )
    assert ["-A", "-w", "30"] == ascii_command[
        ascii_command.index("-A") : ascii_command.index("-A") + 3
    ]


def test_depth_intersects_bed_and_region_as_supported_by_upstream() -> None:
    node = _node("samtools_depth")
    inputs = {
        "input_bams": ["reads.bam"],
        "bam_indexes": ["custom.bai"],
        "input_bed": "targets.bed",
        "region": "chr1:1-20",
    }
    assert node.VALIDATE_INPUTS(inputs) is True
    command = node.render_command(inputs)
    assert command[2:6] == ["-b", "targets.bed", "-r", "chr1:1-20"]


def test_depth_rejects_the_source_ignored_legacy_maxdepth_option() -> None:
    node = _node("samtools_depth")
    validation = node.VALIDATE_INPUTS({"input_bams": ["reads.bam"], "maxdepth": 100})
    assert validation == (
        "maxdepth is ignored by samtools depth 1.23.1; use samtools mpileup to cap depth"
    )


def test_idxstats_accepts_the_custom_index_location_supported_by_x() -> None:
    node = _node("samtools_idxstats")
    inputs = {
        "input": "/data/reads.bam",
        "bam_index": "/indexes/reads.bai",
        "threads": 2,
    }
    assert node.VALIDATE_INPUTS(inputs) is True
    assert node.render_command(inputs)[-3:] == [
        "-X",
        "/data/reads.bam",
        "/indexes/reads.bai",
    ]


def test_mpileup_reference_and_fai_are_optional_but_pairing_is_fail_closed() -> None:
    node = _node("samtools_mpileup")
    no_reference = {"input_bams": ["reads.bam"]}
    assert node.VALIDATE_INPUTS(no_reference) is True
    assert node.render_command(no_reference)[:2] == ["samtools", "mpileup"]
    assert "--output" in node.render_command(no_reference)

    with_reference = {
        **no_reference,
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "ignore_read_groups": True,
    }
    assert node.VALIDATE_INPUTS(with_reference) is True
    command = node.render_command(with_reference)
    assert command[:4] == ["samtools", "mpileup", "-f", "ref.fa"]
    assert "-R" in command

    missing_reference_index = node.VALIDATE_INPUTS({**no_reference, "reference": "ref.fa"})
    index_without_reference = node.VALIDATE_INPUTS({**no_reference, "reference_index": "ref.fa.fai"})
    assert missing_reference_index is not True
    assert index_without_reference is not True


def test_reporting_nodes_keep_pinned_authority_and_stdout_or_file_contracts(tmp_path: Path) -> None:
    for node_id, source, stdout_index in (
        ("samtools_bedcov", "bedcov.c", 0),
        ("samtools_depth", "bam2depth.c", 0),
        ("samtools_idxstats", "bam_index.c", 0),
        ("samtools_stats", "stats.c", 0),
        ("samtools_mpileup", "bam_plcmd.c", None),
        ("samtools_consensus", "bam_consensus.c", 0),
    ):
        node = _node(node_id)
        assert node.VERSION == "1.23.1"
        assert node.GIT_COMMIT == "6efb9b6da35224cf804921dedecf9fb8f411365d"
        assert node.UPSTREAM_SOURCE == source
        assert node.PLAN_OUTPUTS({}, tmp_path)[0].parent.name == node_id
        assert node.STDOUT_OUTPUT_INDEX == stdout_index
