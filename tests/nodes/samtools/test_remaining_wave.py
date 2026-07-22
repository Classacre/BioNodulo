from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.nodes.builtin.samtools_family.adapter import (
    SAMTOOLS_GIT_COMMIT,
    SAMTOOLS_VERSION,
    TOOLS_IUC_GIT_COMMIT,
)
from bionodulo.nodes.registry import NodeRegistry


REMAINING_IDS = (
    "samtools_merge",
    "samtools_stats",
    "samtools_idxstats",
    "samtools_depth",
    "samtools_coverage",
    "samtools_bedcov",
    "samtools_calmd",
    "samtools_ampliconclip",
    "samtools_fastx",
    "samtools_mpileup",
    "samtools_reheader",
    "samtools_split",
    "samtools_slice_bam",
    "samtools_phase",
    "samtools_consensus",
    "samtools_bam_to_cram",
    "samtools_cram_to_bam",
    "samtools_bam_to_sam",
    "bam_to_sam",
    "samtools_sam_to_bam",
    "sam_to_bam",
)


def _node(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node = registry.get(node_id)
    assert node is not None
    return node


def test_exact_remaining_ids_use_focused_owners_and_pinned_runtime() -> None:
    for node_id in REMAINING_IDS:
        node = _node(node_id)
        assert node.__module__.startswith("bionodulo.nodes.builtin.samtools_family.")
        assert node.RUNTIME_VERSION == SAMTOOLS_VERSION == "1.23.1"
        assert node.RUNTIME_GIT_COMMIT == SAMTOOLS_GIT_COMMIT
        assert node.UPSTREAM_MANPAGE.startswith("doc/samtools-")
        assert node.UPSTREAM_SOURCE.endswith(".c")


def test_galaxy_aliases_pin_wrapper_and_runtime_authorities() -> None:
    for node_id, version, source in (
        ("bam_to_sam", "2.0.7", "tool_collections/samtools/bam_to_sam/bam_to_sam.xml"),
        ("sam_to_bam", "2.1.5", "tool_collections/samtools/sam_to_bam/sam_to_bam.xml"),
    ):
        node = _node(node_id)
        assert node.VERSION == version
        assert node.GIT_COMMIT == TOOLS_IUC_GIT_COMMIT
        assert node.WRAPPER_SOURCE == source
        assert node.RUNTIME_VERSION == "1.23.1"
        assert node.RUNTIME_GIT_COMMIT == SAMTOOLS_GIT_COMMIT


def test_merge_stats_and_idxstats_commands_are_deterministic(tmp_path: Path) -> None:
    merge = _node("samtools_merge")
    assert merge.render_command({"bams": ["a.bam", "b.bam"], "threads": 4, "output": "/work/merge"}) == [
        "samtools",
        "merge",
        "-@",
        "4",
        "-o",
        "/work/merge/merged_bam.bam",
        "a.bam",
        "b.bam",
    ]
    assert merge.VALIDATE_INPUTS({"bams": [], "threads": 4}) is not True

    stats = _node("samtools_stats")
    assert stats.render_command({"bam": "a.bam", "threads": 2, "target_regions": "targets.tsv"}) == [
        "samtools",
        "stats",
        "-@",
        "2",
        "-t",
        "targets.tsv",
        "a.bam",
    ]
    assert stats.STDOUT_OUTPUT_INDEX == 0

    idxstats = _node("samtools_idxstats")
    assert idxstats.render_command({"input": "a.bam", "bam_index": "a.bam.bai", "threads": 5}) == [
        "samtools",
        "idxstats",
        "-@",
        "4",
        "-X",
        "a.bam",
        "a.bam.bai",
    ]
    assert idxstats.VALIDATE_INPUTS({"input": "a.bam", "bam_index": "a.bam.bai", "threads": 1}) is True
    assert idxstats.PLAN_OUTPUTS({}, tmp_path)[0].name == "idxstats.tsv"


def test_depth_coverage_and_bedcov_use_explicit_index_contracts() -> None:
    depth = _node("samtools_depth")
    depth_inputs = {
        "input_bams": ["a.bam", "b.bam"],
        "bam_indexes": ["/idx/a.bai", "/idx/b.bai"],
        "region": "chr1:1-20",
        "required_flags": [2, 64],
        "skipped_flags": [4, 256],
        "header": True,
    }
    assert depth.VALIDATE_INPUTS(depth_inputs) is True
    depth_command = depth.render_command(depth_inputs)
    assert depth_command == [
        "samtools",
        "depth",
        "-r",
        "chr1:1-20",
        "--require-flags",
        "66",
        "-G",
        "260",
        "-H",
        "-X",
        "a.bam",
        "b.bam",
        "/idx/a.bai",
        "/idx/b.bai",
    ]
    assert depth.STDOUT_OUTPUT_INDEX == 0

    coverage = _node("samtools_coverage")
    coverage_inputs = {
        "input_bams": ["a.bam", "b.bam"],
        "bam_indexes": ["a.bam.bai", "b.bam.bai"],
        "region": "chr2:5-50",
        "histogram": True,
        "n_bins": 20,
        "output": "/work/coverage",
    }
    assert coverage.VALIDATE_INPUTS(coverage_inputs) is True
    coverage_command = coverage.render_command(coverage_inputs)
    assert coverage_command[-4:] == [
        "-o",
        "/work/coverage/coverage.txt",
        "a.bam",
        "b.bam",
    ]
    assert coverage_command.index("-r") < coverage_command.index("a.bam")

    bedcov = _node("samtools_bedcov")
    bedcov_inputs = {
        "input_bed": "targets.bed",
        "input_bams": ["a.bam", "b.bam"],
        "bam_indexes": ["/idx/a.bai", "/idx/b.bai"],
        "mapq": 20,
    }
    assert bedcov.VALIDATE_INPUTS(bedcov_inputs) is True
    assert bedcov.render_command(bedcov_inputs) == [
        "samtools",
        "bedcov",
        "-Q",
        "20",
        "-X",
        "targets.bed",
        "a.bam",
        "b.bam",
        "/idx/a.bai",
        "/idx/b.bai",
    ]
    assert bedcov.STDOUT_OUTPUT_INDEX == 0


def test_calmd_and_ampliconclip_match_reference_and_output_contracts() -> None:
    calmd = _node("samtools_calmd")
    inputs = {
        "input": "a.bam",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "threads": 3,
        "calculate_baq": True,
        "modify_quality": True,
        "extended_baq": True,
        "adjust_mq": 50,
        "output": "/work/calmd",
    }
    assert calmd.VALIDATE_INPUTS(inputs) is True
    assert calmd.render_command(inputs) == [
        "samtools",
        "calmd",
        "-r",
        "-A",
        "-E",
        "-C",
        "50",
        "-b",
        "-@",
        "2",
        "a.bam",
        "ref.fa",
        ">",
        "/work/calmd/calmd.bam",
    ]
    assert calmd.SHELL is True
    assert calmd.VALIDATE_INPUTS({**inputs, "adjust_mq": 10}) is not True
    assert calmd.VALIDATE_INPUTS({**inputs, "adjust_mq": 1000}) is True
    assert "--no-PG" in calmd.render_command({**inputs, "no_pg": True})

    clip = _node("samtools_ampliconclip")
    invalid_clip = {
        "input_bed": "primers.bed",
        "input_bam": "a.bam",
        "threads": 2,
        "both_ends": True,
        "strand": True,
    }
    assert clip.VALIDATE_INPUTS(invalid_clip) is not True
    command = clip.render_command(
        {
            "input_bed": "primers.bed",
            "input_bam": "a.bam",
            "threads": 2,
            "strand": True,
            "no_pg": True,
            "output": "/work/clip",
        }
    )
    assert "--primer-counts" in command
    assert "/work/clip/primer_counts.bedgraph" in command
    assert "--strand" in command
    assert "--no-PG" in command
    assert command.count("|") == 3
    assert command[-2:] == ["-o", "/work/clip/clipped.bam"]


def test_fastx_uses_collate_pipeline_and_prepares_fixed_ports(tmp_path: Path) -> None:
    fastx = _node("samtools_fastx")
    inputs = {
        "input": "reads.bam",
        "threads": 4,
        "output_format": "fastq",
        "outputs": ["read1", "read2", "singletons", "nonspecific"],
        "write_index_reads": True,
        "write_i1": True,
        "write_i2": False,
        "index_format": "i8",
        "output": "/work/fastx",
    }
    assert fastx.VALIDATE_INPUTS(inputs) is True
    command = fastx.render_command(inputs)
    assert command[:8] == [
        "samtools",
        "collate",
        "-@",
        "3",
        "-O",
        "-u",
        "reads.bam",
        "|",
    ]
    assert command[-1] == "-"
    assert "--i1" in command
    assert "--i2" not in command
    assert fastx.STDOUT_OUTPUT_INDEX == 0

    outputs = fastx.PLAN_OUTPUTS(inputs, tmp_path)
    fastx.PREPARE_EXECUTION(inputs, outputs)
    assert [path.name for path in outputs] == [
        "reads.fastq",
        "read1.fastq",
        "read2.fastq",
        "singletons.fastq",
        "nonspecific.fastq",
        "index1.fastq",
        "index2.fastq",
    ]
    assert all(path.exists() for path in outputs)

    casava = {
        "input": "reads.bam",
        "threads": 1,
        "output_format": "fastq",
        "illumina_casava": True,
        "index_format": "i8",
        "barcode_tag": "CB",
        "quality_tag": "CY",
    }
    assert fastx.VALIDATE_INPUTS(casava) is True
    casava_command = fastx.render_command(casava)
    assert ["--index-format", "i8"] == casava_command[
        casava_command.index("--index-format") : casava_command.index("--index-format") + 2
    ]
    assert ["--barcode-tag", "CB"] == casava_command[
        casava_command.index("--barcode-tag") : casava_command.index("--barcode-tag") + 2
    ]
    assert ["--quality-tag", "CY"] == casava_command[
        casava_command.index("--quality-tag") : casava_command.index("--quality-tag") + 2
    ]

    assert fastx.VALIDATE_INPUTS({**inputs, "index_format": "i8i8i8"}) is not True
    assert fastx.VALIDATE_INPUTS({**inputs, "write_i2": True, "index_format": "i8"}) is not True
    assert (
        fastx.VALIDATE_INPUTS(
            {
                "input": "reads.bam",
                "threads": 1,
                "output_format": "fastq",
                "index_format": "i8",
            }
        )
        is not True
    )


def test_mpileup_places_options_before_explicit_bam_index_pairs() -> None:
    mpileup = _node("samtools_mpileup")
    inputs = {
        "input_bams": ["a.bam", "b.bam"],
        "bam_indexes": ["/idx/a.bai", "/idx/b.bai"],
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "region": "chr3:1-30",
        "min_bq": 20,
        "output": "/work/mpileup",
    }
    assert mpileup.VALIDATE_INPUTS(inputs) is True
    command = mpileup.render_command(inputs)
    assert command[:4] == ["samtools", "mpileup", "-f", "ref.fa"]
    assert command.index("-r") < command.index("a.bam")
    assert command[-5:] == [
        "-X",
        "a.bam",
        "b.bam",
        "/idx/a.bai",
        "/idx/b.bai",
    ]
    assert command[command.index("--output") + 1] == "/work/mpileup/pileup.pileup"
    assert mpileup.VALIDATE_INPUTS({"input_bams": ["a.bam"], "adjust_mq": 10}) is not True
    assert mpileup.VALIDATE_INPUTS({"input_bams": ["a.bam"], "adjust_mq": 50}) is not True
    assert mpileup.VALIDATE_INPUTS({"input_bams": ["a.bam"], "disable_baq": True}) is not True
    assert mpileup.VALIDATE_INPUTS({"input_bams": ["a.bam"], "redo_baq": True}) is not True
    assert (
        mpileup.VALIDATE_INPUTS(
            {
                **inputs,
                "disable_baq": True,
                "redo_baq": True,
            }
        )
        is not True
    )


def test_reheader_split_and_slice_keep_outputs_inside_declared_paths(tmp_path: Path) -> None:
    reheader = _node("samtools_reheader")
    assert reheader.render_command(
        {
            "input_header": "header.sam",
            "input_file": "a.bam",
            "no_pg": True,
            "output": "/work/reheader",
        }
    ) == [
        "samtools",
        "reheader",
        "--no-PG",
        "header.sam",
        "a.bam",
        ">",
        "/work/reheader/reheadered.bam",
    ]
    assert reheader.SHELL is True

    split = _node("samtools_split")
    split_output = split.PLAN_OUTPUTS({}, tmp_path)[0]
    command = split.render_command({"input_bam": "a.bam", "threads": 1, "output": str(tmp_path / "samtools_split")})
    unaccounted = Path(command[command.index("-u") + 1])
    filename_format = Path(command[command.index("-f") + 1])
    assert split_output == tmp_path / "samtools_split" / "readgroup_bams"
    assert unaccounted.parent == split_output
    assert filename_format.parent == split_output
    assert filename_format.name == "Read_Group_%#.bam"
    assert "%!" not in filename_format.name
    assert "--no-PG" in split.render_command(
        {
            "input_bam": "a.bam",
            "threads": 1,
            "no_pg": True,
            "output": str(tmp_path / "samtools_split"),
        }
    )

    slice_node = _node("samtools_slice_bam")
    slice_inputs = {
        "input_bam": "a.bam",
        "bam_index": "a.bam.bai",
        "slice_method": "manual",
        "regions": ["chr1:1-10", "chr2:20-30"],
        "threads": 2,
        "output": "/work/slice",
    }
    assert slice_node.VALIDATE_INPUTS(slice_inputs) is True
    slice_command = slice_node.render_command(slice_inputs)
    assert slice_command[:7] == [
        "samtools",
        "view",
        "-@",
        "1",
        "-u",
        "-X",
        "a.bam",
    ]
    assert "a.bam.bai" in slice_command
    assert "|" in slice_command
    assert slice_command[-1] == "-"


def test_phase_and_consensus_capture_stdout_and_plan_real_filenames(tmp_path: Path) -> None:
    phase = _node("samtools_phase")
    phase_command = phase.render_command({"input_bam": "a.bam", "drop_ambiguous": True, "output": "/work/phase"})
    assert phase_command[-2:] == ["-A", "a.bam"]
    assert phase.STDOUT_OUTPUT_INDEX == 0
    assert [path.name for path in phase.PLAN_OUTPUTS({}, tmp_path)][-1] == ("phase_wrapper.chimera.bam")

    consensus = _node("samtools_consensus")
    inputs = {
        "input": "a.bam",
        "bam_index": "a.bam.bai",
        "threads": 2,
        "format": "fastq",
        "mode": "bayesian",
        "config": "manual",
        "use_mq": False,
        "region": "chr1:1-10",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
    }
    assert consensus.VALIDATE_INPUTS(inputs) is True
    command = consensus.render_command(inputs)
    assert command[:4] == ["samtools", "consensus", "-f", "fastq"]
    assert "--no-use-MQ" in command
    assert command[-1] == "a.bam"
    assert ">" not in command
    assert consensus.STDOUT_OUTPUT_INDEX == 0
    assert consensus.PLAN_OUTPUTS(inputs, tmp_path)[0].name == "consensus.fastq"


def test_format_conversion_nodes_require_explicit_reference_sidecars() -> None:
    bam_to_cram = _node("samtools_bam_to_cram")
    bam_inputs = {
        "input": "a.bam",
        "bam_index": "a.bam.bai",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "threads": 2,
        "target_region": "region",
        "region_string": "chr1:1-10",
        "output": "/work/bam_to_cram",
    }
    assert bam_to_cram.VALIDATE_INPUTS(bam_inputs) is True
    command = bam_to_cram.render_command(bam_inputs)
    assert "--output-fmt-option" not in command
    assert "-t" not in command
    assert command[-4:] == ["-X", "a.bam", "a.bam.bai", "chr1:1-10"]

    cram_to_bam = _node("samtools_cram_to_bam")
    cram_inputs = {
        "input": "a.cram",
        "cram_index": "a.cram.crai",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "threads": 2,
        "target_region": "region",
        "region_string": "chr2:1-20",
        "output": "/work/cram_to_bam",
    }
    assert cram_to_bam.VALIDATE_INPUTS(cram_inputs) is True
    assert cram_to_bam.render_command(cram_inputs)[-4:] == [
        "-X",
        "a.cram",
        "a.cram.crai",
        "chr2:1-20",
    ]


def test_sam_bam_aliases_preserve_ports_but_use_explicit_fai_inputs() -> None:
    bam_to_sam = _node("samtools_bam_to_sam")
    alias_bam_to_sam = _node("bam_to_sam")
    assert bam_to_sam.render_command({"input": "a.bam", "header": "-H"})[-2:] == [
        "-H",
        "a.bam",
    ]
    assert alias_bam_to_sam.render_command({"input1": "a.bam", "header": "-h", "output": "/work/alias"}) == [
        "samtools",
        "view",
        "-o",
        "/work/alias/output1.sam",
        "-h",
        "a.bam",
    ]

    sam_to_bam = _node("samtools_sam_to_bam")
    inputs = {
        "input": "a.sam",
        "reference": "ref.fa",
        "reference_index": "ref.fa.fai",
        "threads": 1,
        "output": "/work/sam_to_bam",
    }
    assert sam_to_bam.VALIDATE_INPUTS(inputs) is True
    assert sam_to_bam.render_command(inputs)[5:8] == ["-t", "ref.fa.fai", "a.sam"]

    alias = _node("sam_to_bam")
    alias_inputs = {
        "input": "a.sam",
        "addref_select": "history",
        "ref": "ref.fa",
        "ref_index": "ref.fa.fai",
        "threads": 1,
        "output": "/work/alias_sam_to_bam",
    }
    assert alias.VALIDATE_INPUTS(alias_inputs) is True
    alias_command = alias.render_command(alias_inputs)
    assert alias_command[:8] == [
        "samtools",
        "view",
        "-b",
        "-@",
        "0",
        "-t",
        "ref.fa.fai",
        "a.sam",
    ]
    assert "faidx" not in alias_command


@pytest.mark.parametrize(
    ("node_id", "inputs", "needle"),
    [
        (
            "samtools_calmd",
            {
                "input": "a.bam",
                "reference": "ref.fa",
                "reference_index": "wrong.fai",
                "threads": 1,
            },
            "reference_index",
        ),
        (
            "samtools_coverage",
            {"input_bams": ["a.bam"], "region": "chr1"},
            "bam_indexes",
        ),
        (
            "samtools_bedcov",
            {"input_bed": "a.bed", "input_bams": ["a.bam"]},
            "bam_indexes",
        ),
        (
            "samtools_fastx",
            {
                "input": "a.bam",
                "threads": 1,
                "write_index_reads": True,
            },
            "index_format",
        ),
        (
            "samtools_slice_bam",
            {
                "input_bam": "a.bam",
                "bam_index": "a.bam.bai",
                "slice_method": "manual",
                "threads": 1,
            },
            "regions",
        ),
    ],
)
def test_remaining_nodes_fail_closed_on_missing_or_mismatched_contract_inputs(
    node_id: str,
    inputs: dict[str, object],
    needle: str,
) -> None:
    result = _node(node_id).VALIDATE_INPUTS(inputs)
    assert result is not True
    assert needle in str(result)
