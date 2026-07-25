from __future__ import annotations

from pathlib import Path

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.environments.manifest import workflow_to_packages
from bionodulo.nodes.builtin.trimming_family import CutadaptNode, TrimGaloreNode, TrimmomaticNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_trim_galore_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["trim_galore"]
    assert node_info["display_name"] == "Trim Galore"
    assert node_info["category"] == "trimming"
    assert node_info["description"].startswith("Adapter and quality trimming")
    assert node_info["output"] == ["FASTQ_LIST", "FILE_LIST", "FILE_LIST"]
    assert node_info["output_name"] == ["trimmed_reads", "fastqc_report", "trimming_reports"]
    assert node_info["required_executables"] == ["trim_galore", "cutadapt", "fastqc"]
    assert node_info["required_conda_packages"] == ["trim-galore", "cutadapt", "fastqc"]
    assert "bisulfite" in node_info["search_aliases"]
    assert "rrbs" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"reads", "threads"}
    assert set(inputs["optional"]) == {
        "paired",
        "quality",
        "length",
        "clip_r1",
        "clip_r2",
        "three_prime_clip_r1",
        "three_prime_clip_r2",
        "rrbs",
        "non_directional",
        "gzip",
        "fastqc",
    }


def test_trim_galore_renders_paired_bisulfite_command() -> None:
    node_class = _node_class("trim_galore")

    cmd = node_class.render_command({
        "reads": ["reads_1.fq", "reads_2.fq"],
        "threads": 4,
        "paired": True,
        "quality": 20,
        "length": 30,
        "clip_r1": 10,
        "clip_r2": 10,
        "three_prime_clip_r1": 5,
        "three_prime_clip_r2": 5,
        "rrbs": True,
        "non_directional": True,
        "gzip": True,
        "fastqc": True,
        "output": "/tmp/run/trim_galore",
    })

    assert cmd == [
        "trim_galore",
        "--paired",
        "--cores",
        "4",
        "--quality",
        "20",
        "--length",
        "30",
        "--clip_R1",
        "10",
        "--clip_R2",
        "10",
        "--three_prime_clip_R1",
        "5",
        "--three_prime_clip_R2",
        "5",
        "--rrbs",
        "--non_directional",
        "--gzip",
        "--fastqc",
        "-o",
        "/tmp/run/trim_galore",
        "reads_1.fq",
        "reads_2.fq",
    ]


def test_trim_galore_renders_single_end_command_and_preserves_explicit_zero_cutoffs() -> None:
    node_class = _node_class("trim_galore")

    cmd = node_class.render_command({
        "reads": "reads.fq.gz",
        "threads": 1,
        "paired": False,
        "quality": 0,
        "length": 0,
        "clip_r1": 0,
        "clip_r2": 0,
        "three_prime_clip_r1": 0,
        "three_prime_clip_r2": 0,
        "rrbs": False,
        "non_directional": False,
        "gzip": False,
        "fastqc": False,
        "output": "/tmp/run/trim_galore",
    })

    assert "--paired" not in cmd
    assert cmd[cmd.index("--quality") + 1] == "0"
    assert cmd[cmd.index("--length") + 1] == "0"
    assert "--clip_R1" not in cmd
    assert "--clip_R2" not in cmd
    assert "--three_prime_clip_R1" not in cmd
    assert "--three_prime_clip_R2" not in cmd
    assert "--rrbs" not in cmd
    assert "--non_directional" not in cmd
    assert "--gzip" not in cmd
    assert "--fastqc" not in cmd
    assert cmd == [
        "trim_galore",
        "--cores",
        "1",
        "--quality",
        "0",
        "--length",
        "0",
        "-o",
        "/tmp/run/trim_galore",
        "reads.fq.gz",
    ]


def test_trim_galore_plans_paired_trimmed_reads_and_report() -> None:
    node_class = _node_class("trim_galore")

    outputs = node_class.PLAN_OUTPUTS(
        {
            "reads": ["reads_1.fq.gz", "reads_2.fq.gz"],
            "paired": True,
            "threads": 1,
            "fastqc": True,
        },
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/trim_galore/reads_1_val_1.fq.gz",
        "/tmp/run/trim_galore/reads_2_val_2.fq.gz",
        "/tmp/run/trim_galore/reads_1_val_1_fastqc.html",
        "/tmp/run/trim_galore/reads_2_val_2_fastqc.html",
        "/tmp/run/trim_galore/reads_1.fq.gz_trimming_report.txt",
        "/tmp/run/trim_galore/reads_2.fq.gz_trimming_report.txt",
    ]


def test_trim_galore_plans_single_end_trimmed_read_and_report() -> None:
    node_class = _node_class("trim_galore")

    outputs = node_class.PLAN_OUTPUTS(
        {"reads": "sample.fastq.gz", "paired": False, "threads": 1},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/trim_galore/sample_trimmed.fq.gz",
        "/tmp/run/trim_galore/sample.fastq.gz_trimming_report.txt",
    ]


def test_trim_galore_rejects_invalid_paired_reads_and_threads() -> None:
    node_class = _node_class("trim_galore")

    assert node_class.VALIDATE_INPUTS({"reads": ["r1.fq"], "paired": True, "threads": 1}) == "paired mode requires exactly 2 reads."
    assert node_class.VALIDATE_INPUTS({"reads": ["r1.fq", "r2.fq"], "paired": False, "threads": 1}) == "single-end mode requires exactly 1 read."
    assert node_class.VALIDATE_INPUTS({"reads": "r1.fq", "paired": False, "threads": 0}) == "threads must be at least 1."


def test_trim_galore_enforces_documented_mode_dependencies_and_uncompressed_outputs() -> None:
    inputs = TrimGaloreNode.INPUT_TYPES()["optional"]
    assert inputs["paired"][1]["default"] is False
    assert inputs["gzip"][1]["default"] is False
    assert inputs["fastqc"][1]["default"] is False
    assert (
        TrimGaloreNode.VALIDATE_INPUTS({
            "reads": ["r1.fq", "r2.fq"],
            "paired": True,
            "threads": 1,
            "non_directional": True,
        })
        == "non_directional requires rrbs."
    )
    assert (
        TrimGaloreNode.VALIDATE_INPUTS({
            "reads": "r1.fq",
            "paired": False,
            "threads": 1,
            "clip_r2": 2,
        })
        == "read 2 clipping requires paired mode."
    )
    outputs = TrimGaloreNode.PLAN_OUTPUTS(
        {"reads": "sample.fastq", "paired": False, "threads": 1, "gzip": False, "fastqc": False},
        "/tmp/run",
    )
    assert [path.name for path in outputs] == ["sample_trimmed.fq", "sample.fastq_trimming_report.txt"]
    compressed = TrimGaloreNode.PLAN_OUTPUTS(
        {"reads": "sample.fastq.gz", "paired": False, "threads": 1},
        "/tmp/run",
    )
    assert [path.name for path in compressed] == [
        "sample_trimmed.fq.gz",
        "sample.fastq.gz_trimming_report.txt",
    ]


def test_trim_galore_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["trim_galore"] == "trim-galore"
    assert PACKAGE_MIN_VERSIONS["trim-galore"] == "0.6.10"
    assert PACKAGE_MIN_VERSIONS["trimmomatic"] == "0.40"
    assert PACKAGE_MIN_VERSIONS["cutadapt"] == "5.2"

    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    assert workflow_to_packages({"nodes": [{"id": "trim", "type": "trim_galore"}]}, registry) == [
        "cutadapt",
        "fastqc",
        "trim-galore",
    ]


@pytest.mark.parametrize(
    ("node_id", "node_class", "module", "version", "commit"),
    [
        ("trim_galore", TrimGaloreNode, "trim_galore", "0.6.10", "4edff97d22f3837d42a29e4afbfaeb6e07ffb11b"),
        ("trimmomatic", TrimmomaticNode, "trimmomatic", "0.40", "7c9e862f7a050fdde034b63363ed4a99bf70d6b3"),
        ("cutadapt", CutadaptNode, "cutadapt", "5.2", "ef852629f667637439f28761499bb56126e390a1"),
    ],
)
def test_remaining_trimming_nodes_have_focused_pinned_ownership(
    node_id: str,
    node_class: type,
    module: str,
    version: str,
    commit: str,
) -> None:
    assert build_index()[node_id] == f"bionodulo.nodes.builtin.trimming_family.{module}"
    assert node_class.VERSION == version
    assert node_class.GIT_COMMIT == commit
    assert commit in node_class.SOURCE_URL
    assert node_class.UPSTREAM_SOURCE_PATHS
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert node_class.EXIT_SEMANTICS


def test_trimmomatic_pe_contract_has_explicit_adapter_fasta_and_four_outputs(tmp_path: Path) -> None:
    inputs = {
        "reads": ["R1.fastq.gz", "R2.fastq.gz"],
        "threads": 8,
        "adapters": "TruSeq3-PE.fa",
        "leading": 3,
        "trailing": 4,
        "quality": 15,
        "minlen": 36,
        "output": str(tmp_path / "trimmomatic"),
    }
    assert TrimmomaticNode.INPUT_TYPES()["required"]["adapters"][0] == "FILE"
    assert TrimmomaticNode.INPUT_TYPES()["required"]["threads"][1]["default"] == 0
    assert TrimmomaticNode.RETURN_TYPES == ("FASTQ", "FASTQ", "FASTQ", "FASTQ")
    assert TrimmomaticNode.PRESET_SOURCE == "README.md paired-end reference command"
    assert "no implicit trimming-step defaults" in TrimmomaticNode.PRESET_SEMANTICS
    assert TrimmomaticNode.render_command(inputs) == [
        "trimmomatic",
        "PE",
        "-threads",
        "8",
        "R1.fastq.gz",
        "R2.fastq.gz",
        str(tmp_path / "trimmomatic" / "R1_paired.fastq.gz"),
        str(tmp_path / "trimmomatic" / "R1_unpaired.fastq.gz"),
        str(tmp_path / "trimmomatic" / "R2_paired.fastq.gz"),
        str(tmp_path / "trimmomatic" / "R2_unpaired.fastq.gz"),
        "ILLUMINACLIP:TruSeq3-PE.fa:2:30:10",
        "LEADING:3",
        "TRAILING:4",
        "SLIDINGWINDOW:4:15",
        "MINLEN:36",
    ]
    assert [path.name for path in TrimmomaticNode.PLAN_OUTPUTS(inputs, tmp_path)] == list(
        TrimmomaticNode.OUTPUT_FILENAMES
    )
    mapped = TrimmomaticNode.MAP_PLANNED_OUTPUTS(TrimmomaticNode.PLAN_OUTPUTS(inputs, tmp_path))
    assert all(isinstance(path, Path) for path in mapped.values())
    assert TrimmomaticNode.VALIDATE_INPUTS({**inputs, "reads": ["R1.fastq.gz"]}) == (
        "Trimmomatic PE requires exactly two reads."
    )


def test_cutadapt_uses_explicit_adapters_and_documented_string_option_shapes(tmp_path: Path) -> None:
    input_types = CutadaptNode.INPUT_TYPES()
    assert input_types["required"]["threads"][1]["default"] == 1
    assert "default" not in input_types["required"]["adapter_r1"][1]
    assert "default" not in input_types["optional"]["adapter_r2"][1]
    assert input_types["optional"]["minimum_length"][0] == "STRING"
    assert input_types["optional"]["quality_cutoff"][0] == "STRING"

    paired = {
        "reads": ["R1.fastq.gz", "R2.fastq.gz"],
        "threads": 4,
        "adapter_r1": "AGATCGGAAGAGC",
        "adapter_r2": "AGATCGGAAGAGC",
        "minimum_length": "20:24",
        "quality_cutoff": "5,20",
        "output": str(tmp_path / "cutadapt"),
    }
    command = CutadaptNode.render_command(paired)
    assert command == [
        "cutadapt",
        "-a",
        "AGATCGGAAGAGC",
        "-A",
        "AGATCGGAAGAGC",
        "-o",
        str(tmp_path / "cutadapt" / "trimmed_reads.fastq.gz"),
        "-p",
        str(tmp_path / "cutadapt" / "trimmed_reads_2.fastq.gz"),
        "-j",
        "4",
        "-m",
        "20:24",
        "-q",
        "5,20",
        "R1.fastq.gz",
        "R2.fastq.gz",
    ]
    assert [path.name for path in CutadaptNode.PLAN_OUTPUTS(paired, tmp_path)] == [
        "trimmed_reads.fastq.gz",
        "trimmed_reads_2.fastq.gz",
    ]

    single = {
        "reads": ["R1.fastq.gz"],
        "threads": 1,
        "adapter_r1": "AGATCGGAAGAGC",
        "output": str(tmp_path / "cutadapt"),
    }
    single_command = CutadaptNode.render_command(single)
    assert "-A" not in single_command
    assert "-p" not in single_command
    assert "-m" not in single_command
    assert "-q" not in single_command
    assert single_command[single_command.index("-j") + 1] == "1"
    assert [path.name for path in CutadaptNode.PLAN_OUTPUTS(single, tmp_path)] == ["trimmed_reads.fastq.gz"]
    assert CutadaptNode.VALIDATE_INPUTS({**paired, "reads": []}) == (
        "Cutadapt requires exactly one single-end FASTQ or two paired FASTQs."
    )
    paired_without_r2_adapter = {**paired, "adapter_r2": None}
    assert "-A" not in CutadaptNode.render_command(paired_without_r2_adapter)
    assert "-p" in CutadaptNode.render_command(paired_without_r2_adapter)


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"minimum_length": "20:24:30"}, "LEN[:LEN2]"),
        ({"quality_cutoff": "5,20,30"}, "[5-prime,]3-prime"),
        ({"adapter_r2": "AGATCGGAAGAGC"}, "only valid for paired-end"),
    ],
)
def test_cutadapt_rejects_values_outside_the_pinned_cli_grammar(
    updates: dict[str, str],
    message: str,
) -> None:
    inputs = {
        "reads": ["R1.fastq.gz"],
        "threads": 1,
        "adapter_r1": "AGATCGGAAGAGC",
        **updates,
    }
    assert message in str(CutadaptNode.VALIDATE_INPUTS(inputs))
