from __future__ import annotations

import importlib
import os
from pathlib import Path
from typing import Any

import pytest

from bionodulo.execution.executor import WorkflowExecutor
from bionodulo.nodes.builtin.bismark_family.adapter import (
    BOWTIE2_INDEX_PARTS,
    bowtie2_index_files,
    validate_prepared_genome,
)
from bionodulo.nodes.builtin.bismark_family.align import BismarkAlignNode
from bionodulo.nodes.builtin.bismark_family.genome_preparation import (
    BismarkGenomePreparationNode,
)
from bionodulo.nodes.builtin.bismark_family.methylation_extractor import (
    BismarkMethylationExtractorNode,
    BismarkMethylationNode,
)
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


PINNED_COMMIT = "e552b8f307a7041bcebed8f8e5a764ebcf7b046c"


def _prepared_genome(folder: Path, *, large: bool = False) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "genome.fa").write_text(">chr1\nACGT\n", encoding="ascii")
    for conversion, stem in (("CT_conversion", "BS_CT"), ("GA_conversion", "BS_GA")):
        directory = folder / "Bisulfite_Genome" / conversion
        directory.mkdir(parents=True, exist_ok=True)
        prefix = directory / stem
        for path in bowtie2_index_files(prefix, large=large):
            path.write_bytes(path.suffix.encode("ascii"))
    return folder


def test_nodes_pin_the_supported_bismark_rust_release() -> None:
    expected = [
        (BismarkGenomePreparationNode, "rust/bismark/src/genome_prep", "bismark_genome_preparation"),
        (BismarkAlignNode, "rust/bismark/src/aligner", "bismark"),
        (BismarkMethylationExtractorNode, "rust/bismark/src/extractor", "bismark_methylation_extractor"),
    ]
    for node, source, executable in expected:
        assert node.VERSION == "3.1.0"
        assert node.GIT_URL == "https://github.com/FelixKrueger/Bismark.git"
        assert node.GIT_COMMIT == PINNED_COMMIT
        assert node.UPSTREAM_TAG == "bismark-rust-v3.1.0"
        assert node.UPSTREAM_SOURCE == source
        assert node.REQUIRED_EXECUTABLES[0] == executable
        assert node.SHELL is False


def test_focused_modules_own_stable_ids_and_legacy_imports_remain_valid() -> None:
    live_index = build_index()
    expected = {
        "bismark_genome_preparation": "bionodulo.nodes.builtin.bismark_family.genome_preparation",
        "bismark_align": "bionodulo.nodes.builtin.bismark_family.align",
        "bismark_methylation_extractor": ("bionodulo.nodes.builtin.bismark_family.methylation_extractor"),
        "bismark_methylation": "bionodulo.nodes.builtin.bismark_family.methylation_extractor",
    }
    assert {node_id: live_index[node_id] for node_id in expected} == expected

    legacy = importlib.import_module("bionodulo.nodes.builtin.epigenomics")
    assert legacy.BismarkGenomePreparationNode is BismarkGenomePreparationNode
    assert legacy.BismarkAlignNode is BismarkAlignNode
    assert legacy.BismarkMethylationExtractorNode is BismarkMethylationExtractorNode
    assert legacy.BismarkMethylationNode is BismarkMethylationNode
    assert issubclass(BismarkMethylationNode, BismarkMethylationExtractorNode)
    assert BismarkMethylationNode.INPUT_TYPES() == BismarkMethylationExtractorNode.INPUT_TYPES()
    assert BismarkMethylationNode.RETURN_TYPES == BismarkMethylationExtractorNode.RETURN_TYPES
    assert BismarkMethylationNode.RETURN_NAMES == BismarkMethylationExtractorNode.RETURN_NAMES
    assert BismarkMethylationNode.GIT_COMMIT == PINNED_COMMIT


def test_genome_preparation_is_a_bounded_bowtie2_contract(tmp_path: Path) -> None:
    inputs = BismarkGenomePreparationNode.INPUT_TYPES()
    node_output = tmp_path / "bismark_genome_preparation"

    assert set(inputs["required"]) == {"genome_folder"}
    assert set(inputs["optional"]) == {"parallel"}
    assert inputs["optional"]["parallel"][1]["default"] == 1
    assert BismarkGenomePreparationNode.RETURN_NAMES == ("genome_folder",)
    assert BismarkGenomePreparationNode.REQUIRED_EXECUTABLES == [
        "bismark_genome_preparation",
        "bowtie2-build",
    ]
    assert BismarkGenomePreparationNode.PLAN_OUTPUTS({}, tmp_path) == [node_output / "genome"]
    assert BismarkGenomePreparationNode.render_command({"output": node_output}) == [
        "bismark_genome_preparation",
        "--bowtie2",
        str(node_output / "genome"),
    ]
    assert BismarkGenomePreparationNode.render_command({"output": node_output, "parallel": 4}) == [
        "bismark_genome_preparation",
        "--bowtie2",
        "--parallel",
        "4",
        str(node_output / "genome"),
    ]


def test_genome_preparation_stages_only_the_selected_fasta_tier(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    chosen = source / "chr1.fa"
    chosen.write_text(">chr1\nACGT\n", encoding="ascii")
    (source / "ignored.fasta").write_text(">ignored\nA\n", encoding="ascii")
    outputs = BismarkGenomePreparationNode.PLAN_OUTPUTS({}, tmp_path / "run")
    stale = outputs[0] / "Bisulfite_Genome" / "stale.bt2"
    stale.parent.mkdir(parents=True)
    stale.write_text("stale", encoding="ascii")
    inputs: dict[str, Any] = {"genome_folder": source, "parallel": 1}

    BismarkGenomePreparationNode.PREPARE_EXECUTION(inputs, outputs)

    staged = outputs[0] / chosen.name
    assert inputs["genome_folder"] == str(outputs[0])
    assert sorted(path.name for path in outputs[0].iterdir()) == ["chr1.fa"]
    assert os.path.samefile(chosen, staged)
    assert not stale.exists()


def test_genome_preparation_rejects_missing_fasta_and_invalid_parallel(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    valid = tmp_path / "valid"
    valid.mkdir()
    (valid / "genome.fa").write_text(">chr1\nA\n", encoding="ascii")

    assert "not found" in str(
        BismarkGenomePreparationNode.VALIDATE_INPUTS({"genome_folder": tmp_path / "missing", "parallel": 1})
    )
    assert "no top-level FASTA" in str(
        BismarkGenomePreparationNode.VALIDATE_INPUTS({"genome_folder": empty, "parallel": 1})
    )
    assert (
        BismarkGenomePreparationNode.VALIDATE_INPUTS({"genome_folder": valid, "parallel": True})
        == "parallel must be an integer"
    )
    assert (
        BismarkGenomePreparationNode.VALIDATE_INPUTS({"genome_folder": valid, "parallel": 0})
        == "parallel must be at least 1"
    )


@pytest.mark.parametrize("large", [False, True])
def test_prepared_genome_accepts_complete_small_and_large_indexes(
    tmp_path: Path,
    large: bool,
) -> None:
    genome = _prepared_genome(tmp_path / ("large" if large else "small"), large=large)

    artifacts = validate_prepared_genome(genome)

    assert len(artifacts) == 1 + (2 * len(BOWTIE2_INDEX_PARTS))
    assert all(path.is_file() for path in artifacts)


@pytest.mark.parametrize("large", [False, True])
def test_prepared_genome_rejects_zero_byte_index_members(
    tmp_path: Path,
    large: bool,
) -> None:
    genome = _prepared_genome(tmp_path / ("large" if large else "small"), large=large)
    prefix = genome / "Bisulfite_Genome" / "CT_conversion" / "BS_CT"
    bowtie2_index_files(prefix, large=large)[0].write_bytes(b"")

    with pytest.raises(FileNotFoundError, match="is incomplete"):
        validate_prepared_genome(genome)


def test_prepared_genome_rejects_an_incomplete_conversion_index(tmp_path: Path) -> None:
    for conversion, stem in (("CT_conversion", "BS_CT"), ("GA_conversion", "BS_GA")):
        genome = _prepared_genome(tmp_path / conversion)
        Path(genome / "Bisulfite_Genome" / conversion / f"{stem}.rev.2.bt2").unlink()

        with pytest.raises(FileNotFoundError, match="is incomplete"):
            validate_prepared_genome(genome)


@pytest.mark.asyncio
async def test_genome_preparation_fake_execution_returns_a_complete_bundle(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "genome.fa").write_text(">chr1\nACGT\n", encoding="ascii")

    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            self.command = command
            _prepared_genome(Path(command[-1]))
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await BismarkGenomePreparationNode().run(
        genome_folder=source,
        parallel=2,
        context=context,
    )

    expected = tmp_path / "run" / "bismark_genome_preparation" / "genome"
    assert result == (str(expected),)
    assert context.command == [
        "bismark_genome_preparation",
        "--bowtie2",
        "--parallel",
        "2",
        str(expected),
    ]
    validate_prepared_genome(result[0])


@pytest.mark.asyncio
async def test_genome_preparation_fails_closed_on_zero_exit_without_indexes(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    source.mkdir()
    (source / "genome.fa").write_text(">chr1\nACGT\n", encoding="ascii")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, _command: list[str], **_kwargs: Any) -> dict[str, Any]:
            return {"returncode": 0, "stdout": "", "stderr": ""}

    with pytest.raises(FileNotFoundError, match="conversion index directory not found"):
        await BismarkGenomePreparationNode().run(
            genome_folder=source,
            parallel=1,
            context=Context(),
        )


def test_align_contract_exposes_bam_and_the_always_written_report() -> None:
    inputs = BismarkAlignNode.INPUT_TYPES()

    assert set(inputs["required"]) == {"r1", "genome_folder", "parallel_instances"}
    assert set(inputs["optional"]) == {"r2", "non_directional"}
    assert inputs["required"]["parallel_instances"][1]["default"] == 1
    assert inputs["optional"]["non_directional"][1]["default"] is False
    assert BismarkAlignNode.RETURN_TYPES == ("BAM", "TXT")
    assert BismarkAlignNode.RETURN_NAMES == ("aligned_bam", "alignment_report")
    assert BismarkAlignNode.REQUIRED_EXECUTABLES == ["bismark", "bowtie2"]


def test_align_renders_and_plans_exact_single_or_paired_outputs(tmp_path: Path) -> None:
    node_output = tmp_path / "run" / "bismark_align"
    for paired in (False, True):
        inputs: dict[str, Any] = {
            "r1": "sample_R1.fastq.gz",
            "genome_folder": "prepared genome",
            "parallel_instances": 3,
            "non_directional": paired,
            "output": node_output,
        }
        if paired:
            inputs["r2"] = "sample_R2.fastq.gz"

        expected_command = [
            "bismark",
            "--genome",
            "prepared genome",
            "--output_dir",
            str(node_output),
            "--basename",
            "aligned_bam",
            "--parallel",
            "3",
        ]
        if paired:
            expected_command.extend(
                [
                    "--non_directional",
                    "-1",
                    "sample_R1.fastq.gz",
                    "-2",
                    "sample_R2.fastq.gz",
                ]
            )
            expected_outputs = [
                node_output / "aligned_bam_pe.bam",
                node_output / "aligned_bam_PE_report.txt",
            ]
        else:
            expected_command.append("sample_R1.fastq.gz")
            expected_outputs = [
                node_output / "aligned_bam.bam",
                node_output / "aligned_bam_SE_report.txt",
            ]

        assert BismarkAlignNode.render_command(inputs) == expected_command
        assert BismarkAlignNode.PLAN_OUTPUTS(inputs, tmp_path / "run") == expected_outputs
        assert "-p" not in expected_command


def test_align_validation_requires_reads_complete_indexes_and_positive_parallel(
    tmp_path: Path,
) -> None:
    genome = _prepared_genome(tmp_path / "genome")
    r1 = tmp_path / "r1.fastq.gz"
    r1.write_bytes(b"reads")
    inputs: dict[str, Any] = {
        "r1": r1,
        "genome_folder": genome,
        "parallel_instances": 1,
    }
    assert BismarkAlignNode.VALIDATE_INPUTS(inputs) is True

    assert "read file not found" in str(BismarkAlignNode.VALIDATE_INPUTS({**inputs, "r1": tmp_path / "missing.fq"}))
    missing = genome / "Bisulfite_Genome" / "GA_conversion" / "BS_GA.4.bt2"
    missing.unlink()
    assert "is incomplete" in str(BismarkAlignNode.VALIDATE_INPUTS(inputs))
    _prepared_genome(genome)
    assert (
        BismarkAlignNode.VALIDATE_INPUTS({**inputs, "parallel_instances": 0}) == "parallel_instances must be at least 1"
    )


@pytest.mark.asyncio
async def test_align_dry_run_accepts_the_unmaterialized_preparation_output(
    tmp_path: Path,
) -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    workflow = {
        "name": "Bismark dry-run contract",
        "nodes": [
            {
                "id": "prep",
                "type": "bismark_genome_preparation",
                "params": {"genome_folder": "/inputs/genome", "parallel": 1},
            },
            {
                "id": "align",
                "type": "bismark_align",
                "params": {"r1": "/inputs/R1.fastq.gz", "parallel_instances": 1},
            },
        ],
        "edges": [
            {
                "from": {"node": "prep", "output": "genome_folder"},
                "to": {"node": "align", "input": "genome_folder"},
            }
        ],
    }
    executor = WorkflowExecutor(
        workspace_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        registry=registry,
    )

    preview = await executor.dry_run("preview", workflow)

    align = next(node for node in preview["nodes"] if node["node_id"] == "align")
    expected = tmp_path / "runs" / "preview" / "prep" / "bismark_genome_preparation" / "genome"
    assert align["command"][align["command"].index("--genome") + 1] == str(expected)


@pytest.mark.asyncio
async def test_align_fake_execution_returns_the_selected_layout_outputs(
    tmp_path: Path,
) -> None:
    genome = _prepared_genome(tmp_path / "genome")
    r1 = tmp_path / "r1.fastq.gz"
    r2 = tmp_path / "r2.fastq.gz"
    r1.write_bytes(b"r1")
    r2.write_bytes(b"r2")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            output = Path(command[command.index("--output_dir") + 1])
            (output / "aligned_bam_pe.bam").write_bytes(b"bam")
            (output / "aligned_bam_PE_report.txt").write_text("report", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await BismarkAlignNode().run(
        r1=r1,
        r2=r2,
        genome_folder=genome,
        parallel_instances=1,
        context=Context(),
    )

    assert result == (
        str(tmp_path / "run" / "bismark_align" / "aligned_bam_pe.bam"),
        str(tmp_path / "run" / "bismark_align" / "aligned_bam_PE_report.txt"),
    )


def test_extractor_contract_uses_upstream_defaults_and_guaranteed_outputs() -> None:
    inputs = BismarkMethylationExtractorNode.INPUT_TYPES()

    assert set(inputs["required"]) == {"bam", "multicore"}
    assert set(inputs["optional"]) == {
        "cytosine_report",
        "genome_folder",
        "no_overlap",
        "merge_non_cpg",
    }
    assert inputs["required"]["multicore"][1]["default"] == 1
    assert inputs["optional"]["cytosine_report"][1]["default"] is False
    assert inputs["optional"]["no_overlap"][1]["default"] is True
    assert BismarkMethylationExtractorNode.RETURN_TYPES == ("DIRECTORY", "TXT", "TXT")
    assert BismarkMethylationExtractorNode.RETURN_NAMES == (
        "methylation_output",
        "mbias_report",
        "splitting_report",
    )


def test_extractor_renders_exact_output_and_optional_flags(tmp_path: Path) -> None:
    output = tmp_path / "run" / "bismark_methylation_extractor"
    common = {"bam": "aligned_bam_pe.bam", "multicore": 2, "output": output}
    prefix = [
        "bismark_methylation_extractor",
        "--bedGraph",
        "--comprehensive",
        "--gzip",
        "--multicore",
        "2",
        "--output_dir",
        str(output / "methylation_output"),
    ]

    assert BismarkMethylationExtractorNode.render_command(common) == [
        *prefix,
        "aligned_bam_pe.bam",
    ]
    assert BismarkMethylationExtractorNode.render_command(
        {
            **common,
            "cytosine_report": True,
            "genome_folder": "genome",
            "no_overlap": False,
            "merge_non_cpg": True,
        }
    ) == [
        *prefix,
        "--cytosine_report",
        "--genome_folder",
        "genome",
        "--paired-end",
        "--include_overlap",
        "--merge_non_CpG",
        "aligned_bam_pe.bam",
    ]


def test_extractor_plans_upstream_derived_report_names(tmp_path: Path) -> None:
    expected = [
        ("aligned_bam_pe.bam", "aligned_bam_pe.M-bias.txt", "aligned_bam_pe_splitting_report.txt"),
        ("sample.bam.gz", "sample.bam.M-bias.txt", "sample.bam.gz_splitting_report.txt"),
    ]
    output = tmp_path / "bismark_methylation_extractor" / "methylation_output"
    for bam, mbias, splitting in expected:
        assert BismarkMethylationExtractorNode.PLAN_OUTPUTS({"bam": bam}, tmp_path) == [
            output,
            output / mbias,
            output / splitting,
        ]


def test_extractor_requires_a_genome_for_cytosine_report_but_not_a_fai(
    tmp_path: Path,
) -> None:
    bam = tmp_path / "aligned.bam"
    bam.write_bytes(b"bam")
    genome = tmp_path / "genome"
    genome.mkdir()
    (genome / "genome.fa").write_text(">chr1\nACGT\n", encoding="ascii")
    inputs: dict[str, Any] = {
        "bam": bam,
        "multicore": 1,
        "cytosine_report": True,
        "genome_folder": genome,
    }

    assert not (genome / "genome.fa.fai").exists()
    assert BismarkMethylationExtractorNode.VALIDATE_INPUTS(inputs) is True
    assert (
        BismarkMethylationExtractorNode.VALIDATE_INPUTS(
            {key: value for key, value in inputs.items() if key != "genome_folder"}
        )
        == "genome_folder is required when cytosine_report is enabled"
    )
    assert BismarkMethylationExtractorNode.VALIDATE_INPUTS({**inputs, "multicore": 0}) == "multicore must be at least 1"


@pytest.mark.asyncio
async def test_extractor_fake_execution_returns_only_unconditional_artifacts(
    tmp_path: Path,
) -> None:
    bam = tmp_path / "aligned_bam_pe.bam"
    bam.write_bytes(b"bam")

    class Context:
        node_dir = tmp_path / "run"

        async def run_command(self, command: list[str], **_kwargs: Any) -> dict[str, Any]:
            output = Path(command[command.index("--output_dir") + 1])
            output.mkdir()
            (output / "aligned_bam_pe.M-bias.txt").write_text("mbias", encoding="ascii")
            (output / "aligned_bam_pe_splitting_report.txt").write_text("splitting", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await BismarkMethylationExtractorNode().run(
        bam=bam,
        multicore=1,
        context=Context(),
    )
    output = tmp_path / "run" / "bismark_methylation_extractor" / "methylation_output"

    assert result == (
        str(output),
        str(output / "aligned_bam_pe.M-bias.txt"),
        str(output / "aligned_bam_pe_splitting_report.txt"),
    )
    assert not any(output.glob("*.bedGraph.gz"))
