"""Compact source-contract coverage for the focused RSeQC 5.0.3 family."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin.rseqc_family.adapter import RSeQCCommandNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


OUTPUT = "/work/node"
SOURCE_SHA256 = "869f542e08f50c8874280d58e4f5565857b0aebac66a8eceef3f23016175061e"


CASES: list[tuple[str, dict[str, object], list[str]]] = [
    (
        "rseqc_bam2wig",
        {"input": "a.bam", "bam_index": "a.bam.bai", "chromsize": "chrom.sizes"},
        ["bam2wig.py", "-i", "a.bam", "-s", "chrom.sizes", "-o", f"{OUTPUT}/outfile", "-q", "30"],
    ),
    ("rseqc_bam_stat", {"input": "a.bam"}, ["bam_stat.py", "-i", "a.bam", "-q", "30"]),
    (
        "rseqc_clipping_profile",
        {"input": "a.bam", "layout": "SE"},
        ["clipping_profile.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-q", "30", "-s", "SE"],
    ),
    (
        "rseqc_deletion_profile",
        {"input": "a.bam", "read_align_length": 101},
        ["deletion_profile.py", "-i", "a.bam", "-l", "101", "-o", f"{OUTPUT}/output", "-n", "1000000", "-q", "30"],
    ),
    (
        "rseqc_fpkm_count",
        {"input": "a.bam", "bam_index": "a.bam.bai", "refgene": "genes.bed"},
        ["FPKM_count.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-r", "genes.bed", "-q", "30", "-s", "1"],
    ),
    (
        "rseqc_gene_body_coverage",
        {"input": ["a.bam"], "bam_indexes": ["a.bam.bai"], "refgene": "genes.bed"},
        ["geneBody_coverage.py", "-i", "a.bam", "-r", "genes.bed", "-l", "100", "-f", "pdf", "-o", f"{OUTPUT}/output"],
    ),
    (
        "rseqc_gene_body_coverage2",
        {"input": "a.bw", "refgene": "genes.bed"},
        ["geneBody_coverage2.py", "-i", "a.bw", "-r", "genes.bed", "-o", f"{OUTPUT}/output", "-t", "pdf"],
    ),
    (
        "rseqc_infer_experiment",
        {"input": "a.bam", "refgene": "genes.bed"},
        ["infer_experiment.py", "-i", "a.bam", "-r", "genes.bed", "-s", "200000", "-q", "30"],
    ),
    (
        "rseqc_inner_distance",
        {"input": "a.bam", "refgene": "genes.bed"},
        [
            "inner_distance.py",
            "-i",
            "a.bam",
            "-o",
            f"{OUTPUT}/output",
            "-r",
            "genes.bed",
            "-k",
            "1000000",
            "-l",
            "-250",
            "-u",
            "250",
            "-s",
            "5",
            "-q",
            "30",
        ],
    ),
    (
        "rseqc_insertion_profile",
        {"input": "a.bam", "layout": "SE"},
        ["insertion_profile.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-q", "30", "-s", "SE"],
    ),
    (
        "rseqc_junction_annotation",
        {"input": "a.bam", "refgene": "genes.bed"},
        ["junction_annotation.py", "-i", "a.bam", "-r", "genes.bed", "-o", f"{OUTPUT}/output", "-m", "50", "-q", "30"],
    ),
    (
        "rseqc_junction_saturation",
        {"input": "a.bam", "refgene": "genes.bed"},
        [
            "junction_saturation.py",
            "-i",
            "a.bam",
            "-o",
            f"{OUTPUT}/output",
            "-r",
            "genes.bed",
            "-l",
            "5",
            "-u",
            "100",
            "-s",
            "5",
            "-m",
            "50",
            "-v",
            "1",
            "-q",
            "30",
        ],
    ),
    (
        "rseqc_mismatch_profile",
        {"input": "a.bam", "read_align_length": 101},
        ["mismatch_profile.py", "-i", "a.bam", "-l", "101", "-o", f"{OUTPUT}/output", "-n", "1000000", "-q", "30"],
    ),
    (
        "rseqc_read_distribution",
        {"input": "a.bam", "refgene": "genes.bed"},
        ["read_distribution.py", "-i", "a.bam", "-r", "genes.bed"],
    ),
    (
        "rseqc_read_duplication",
        {"input": "a.bam"},
        ["read_duplication.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-u", "500", "-q", "30"],
    ),
    (
        "rseqc_read_gc",
        {"input": "a.bam"},
        ["read_GC.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-q", "30"],
    ),
    ("rseqc_read_hexamer", {"inputs": ["a.fastq"]}, ["read_hexamer.py", "-i", "a.fastq"]),
    (
        "rseqc_read_nvc",
        {"input": "a.bam"},
        ["read_NVC.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-q", "30"],
    ),
    (
        "rseqc_read_quality",
        {"input": "a.bam"},
        ["read_quality.py", "-i", "a.bam", "-o", f"{OUTPUT}/output", "-r", "1", "-q", "30"],
    ),
    (
        "rseqc_rna_fragment_size",
        {"input": "a.bam", "bam_index": "a.bam.bai", "refgene": "genes.bed"},
        ["RNA_fragment_size.py", "-i", "a.bam", "-r", "genes.bed", "-q", "30", "-n", "3"],
    ),
    (
        "rseqc_rpkm_saturation",
        {"input": "a.bam", "refgene": "genes.bed"},
        [
            "RPKM_saturation.py",
            "-i",
            "a.bam",
            "-o",
            f"{OUTPUT}/output",
            "-r",
            "genes.bed",
            "-l",
            "5",
            "-u",
            "100",
            "-s",
            "5",
            "-c",
            "0.01",
            "-q",
            "30",
        ],
    ),
    (
        "rseqc_tin",
        {"input": ["a.bam"], "bam_indexes": ["a.bam.bai"], "refgene": "genes.bed"},
        ["tin.py", "-i", "a.bam", "-r", "genes.bed", "-c", "10", "-n", "100"],
    ),
]


OUTPUT_FILES: dict[str, list[str]] = {
    "rseqc_bam2wig": ["outfile.wig", "outfile.bw"],
    "rseqc_bam_stat": ["bam_stat.txt"],
    "rseqc_clipping_profile": [
        "output.clipping_profile.xls",
        "output.clipping_profile.r",
        "output.clipping_profile.pdf",
    ],
    "rseqc_deletion_profile": [
        "output.deletion_profile.txt",
        "output.deletion_profile.r",
        "output.deletion_profile.pdf",
    ],
    "rseqc_fpkm_count": ["output.FPKM.xls"],
    "rseqc_gene_body_coverage": [
        "output.geneBodyCoverage.txt",
        "output.geneBodyCoverage.r",
        "output.geneBodyCoverage.curves.pdf",
    ],
    "rseqc_gene_body_coverage2": [
        "output.geneBodyCoverage.txt",
        "output.geneBodyCoverage_plot.r",
        "output.geneBodyCoverage.pdf",
    ],
    "rseqc_infer_experiment": ["infer_experiment.txt"],
    "rseqc_inner_distance": [
        "output.inner_distance.txt",
        "output.inner_distance_freq.txt",
        "output.inner_distance_plot.r",
        "output.inner_distance_plot.pdf",
    ],
    "rseqc_insertion_profile": [
        "output.insertion_profile.xls",
        "output.insertion_profile.r",
        "output.insertion_profile.pdf",
    ],
    "rseqc_junction_annotation": [
        "output.junction.xls",
        "output.junction_plot.r",
        "output.splice_events.pdf",
        "output.splice_junction.pdf",
        "output.junction.bed",
        "output.junction.Interact.bed",
    ],
    "rseqc_junction_saturation": ["output.junctionSaturation_plot.r", "output.junctionSaturation_plot.pdf"],
    "rseqc_mismatch_profile": [
        "output.mismatch_profile.xls",
        "output.mismatch_profile.r",
        "output.mismatch_profile.pdf",
    ],
    "rseqc_read_distribution": ["read_distribution.txt"],
    "rseqc_read_duplication": [
        "output.seq.DupRate.xls",
        "output.pos.DupRate.xls",
        "output.DupRate_plot.r",
        "output.DupRate_plot.pdf",
    ],
    "rseqc_read_gc": ["output.GC.xls", "output.GC_plot.r", "output.GC_plot.pdf"],
    "rseqc_read_hexamer": ["read_hexamer.tsv"],
    "rseqc_read_nvc": ["output.NVC.xls", "output.NVC_plot.r", "output.NVC_plot.pdf"],
    "rseqc_read_quality": ["output.qual.r", "output.qual.boxplot.pdf", "output.qual.heatmap.pdf"],
    "rseqc_rna_fragment_size": ["fragment_sizes.tsv"],
    "rseqc_rpkm_saturation": [
        "output.eRPKM.xls",
        "output.rawCount.xls",
        "output.saturation.r",
        "output.saturation.pdf",
    ],
    "rseqc_tin": ["rseqc_tin"],
}


@pytest.fixture(scope="module")
def registry() -> NodeRegistry:
    result = NodeRegistry.create_isolated()
    result.load_builtin_nodes()
    return result


@pytest.mark.parametrize(("node_id", "inputs", "expected"), CASES, ids=[case[0] for case in CASES])
def test_rseqc_source_order_argv(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
    expected: list[str],
) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    assert node_class.render_command({**inputs, "output": OUTPUT}) == expected


@pytest.mark.parametrize(("node_id", "inputs", "_expected"), CASES, ids=[case[0] for case in CASES])
def test_rseqc_source_output_plans(
    tmp_path: Path,
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
    _expected: list[str],
) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    outputs = node_class.PLAN_OUTPUTS(inputs, tmp_path)
    assert [path.name for path in outputs] == OUTPUT_FILES[node_id]


def test_rseqc_archive_identity_and_environment(registry: NodeRegistry) -> None:
    assert PACKAGE_MIN_VERSIONS["rseqc"] == "5.0.3"
    for node_id, _inputs, _expected in CASES:
        node_class = registry.get(node_id)
        assert node_class is not None
        assert issubclass(node_class, RSeQCCommandNode)
        assert node_class.VERSION == "5.0.3"
        assert node_class.GIT_URL == ""
        assert node_class.GIT_COMMIT == ""
        assert node_class.SOURCE_SHA256 == SOURCE_SHA256
        assert node_class.SOURCE_URL.endswith("RSeQC-5.0.3.tar.gz")
        assert node_class.CATEGORY == "rna_seq"
        assert "rseqc" in node_class.REQUIRED_CONDA_PACKAGES


def test_rseqc_stdout_artifacts_use_runtime_capture(registry: NodeRegistry) -> None:
    stdout_nodes = {
        "rseqc_infer_experiment",
        "rseqc_read_hexamer",
        "rseqc_rna_fragment_size",
        "rseqc_bam_stat",
        "rseqc_read_distribution",
    }
    for node_id in stdout_nodes:
        node_class = registry.get(node_id)
        assert node_class is not None
        assert node_class.STDOUT_OUTPUT_INDEX == 0
        assert node_class.SHELL is False
        assert ">" not in node_class.render_command(
            {
                **next(inputs for current, inputs, _expected in CASES if current == node_id),
                "output": OUTPUT,
            }
        )


@pytest.mark.parametrize(
    ("node_id", "inputs", "index_key"),
    [
        ("rseqc_fpkm_count", {"input": "a.bam", "bam_index": "a.bam.bai", "refgene": "genes.bed"}, "bam_index"),
        ("rseqc_bam2wig", {"input": "a.bam", "bam_index": "a.bam.bai", "chromsize": "chrom.sizes"}, "bam_index"),
        (
            "rseqc_gene_body_coverage",
            {"input": ["a.bam"], "bam_indexes": ["a.bam.bai"], "refgene": "genes.bed"},
            "bam_indexes",
        ),
        ("rseqc_rna_fragment_size", {"input": "a.bam", "bam_index": "a.bam.bai", "refgene": "genes.bed"}, "bam_index"),
        ("rseqc_tin", {"input": ["a.bam"], "bam_indexes": ["a.bam.bai"], "refgene": "genes.bed"}, "bam_indexes"),
    ],
)
def test_indexed_bam_consumers_fail_closed(
    registry: NodeRegistry,
    node_id: str,
    inputs: dict[str, object],
    index_key: str,
) -> None:
    node_class = registry.get(node_id)
    assert node_class is not None
    assert node_class.VALIDATE_INPUTS(inputs) is True
    invalid = dict(inputs)
    invalid[index_key] = ["wrong.bai"] if index_key.endswith("indexes") else "wrong.bai"
    validation = node_class.VALIDATE_INPUTS(invalid)
    assert validation is not True
    assert "sibling" in str(validation) or "index" in str(validation)


def test_layout_dependent_outputs_are_grouped_into_stable_ports(
    tmp_path: Path,
    registry: NodeRegistry,
) -> None:
    bam2wig = registry.get("rseqc_bam2wig")
    clipping = registry.get("rseqc_clipping_profile")
    insertion = registry.get("rseqc_insertion_profile")
    gene_body = registry.get("rseqc_gene_body_coverage")
    assert bam2wig and clipping and insertion and gene_body

    unstranded = bam2wig.PLAN_OUTPUTS({}, tmp_path)
    stranded = bam2wig.PLAN_OUTPUTS({"strand": "1++,1--,2+-,2-+"}, tmp_path)
    assert set(bam2wig.MAP_PLANNED_OUTPUTS(unstranded)) == {"wiggle_tracks", "bigwig_tracks"}
    assert [path.suffix for path in bam2wig.MAP_PLANNED_OUTPUTS(stranded)["wiggle_tracks"]] == [".wig", ".wig"]
    assert [path.suffix for path in bam2wig.MAP_PLANNED_OUTPUTS(stranded)["bigwig_tracks"]] == [".bw", ".bw"]

    for node_class, output_name in (
        (clipping, "clipping_plots"),
        (insertion, "insertion_profile_plots"),
    ):
        assert (
            len(node_class.MAP_PLANNED_OUTPUTS(node_class.PLAN_OUTPUTS({"layout": "SE"}, tmp_path))[output_name]) == 1
        )
        assert (
            len(node_class.MAP_PLANNED_OUTPUTS(node_class.PLAN_OUTPUTS({"layout": "PE"}, tmp_path))[output_name]) == 2
        )

    single = gene_body.PLAN_OUTPUTS({"input": ["a.bam"]}, tmp_path)
    multi = gene_body.PLAN_OUTPUTS({"input": ["a.bam", "b.bam", "c.bam"]}, tmp_path)
    assert len(gene_body.MAP_PLANNED_OUTPUTS(single)["coverage_plots"]) == 1
    assert len(gene_body.MAP_PLANNED_OUTPUTS(multi)["coverage_plots"]) == 2


@pytest.mark.asyncio
async def test_gene_body_coverage_allows_source_skipped_heatmap(
    tmp_path: Path,
    registry: NodeRegistry,
) -> None:
    """RSeQC may omit the heatmap after skipping an unusable BAM."""
    node_class = registry.get("rseqc_gene_body_coverage")
    assert node_class is not None

    class Context:
        node_dir = tmp_path

        async def run_command(self, _command: list[str], **kwargs: Any) -> dict[str, Any]:
            output_dir = Path(str(kwargs["cwd"]))
            (output_dir / "output.geneBodyCoverage.txt").write_text("Percentile\t1\n")
            (output_dir / "output.geneBodyCoverage.r").write_text("# generated\n")
            (output_dir / "output.geneBodyCoverage.curves.pdf").write_bytes(b"curves")
            # The pinned source omits heatMap when fewer than three datasets
            # survive its no-coverage filtering.
            return {"returncode": 0, "stdout": "", "stderr": ""}

    stale_heatmap = tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.heatMap.pdf"
    stale_heatmap.parent.mkdir(parents=True, exist_ok=True)
    stale_heatmap.write_bytes(b"stale")
    result = await node_class().run(
        context=Context(),
        output_dir=tmp_path,
        input=["one.bam", "two.bam", "three.bam"],
        bam_indexes=["one.bam.bai", "two.bam.bai", "three.bam.bai"],
        refgene="genes.bed",
    )
    assert result["outputs"]["coverage_plots"] == [
        str(tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf")
    ]


@pytest.mark.asyncio
async def test_gene_body_coverage_returns_heatmap_when_source_creates_it(
    tmp_path: Path,
    registry: NodeRegistry,
) -> None:
    node_class = registry.get("rseqc_gene_body_coverage")
    assert node_class is not None

    class Context:
        node_dir = tmp_path

        async def run_command(self, _command: list[str], **kwargs: Any) -> dict[str, Any]:
            output_dir = Path(str(kwargs["cwd"]))
            for name in (
                "output.geneBodyCoverage.txt",
                "output.geneBodyCoverage.r",
                "output.geneBodyCoverage.heatMap.pdf",
                "output.geneBodyCoverage.curves.pdf",
            ):
                (output_dir / name).write_bytes(b"artifact")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    result = await node_class().run(
        context=Context(),
        output_dir=tmp_path,
        input=["one.bam", "two.bam", "three.bam"],
        bam_indexes=["one.bam.bai", "two.bam.bai", "three.bam.bai"],
        refgene="genes.bed",
    )
    assert result["outputs"]["coverage_plots"] == [
        str(tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.heatMap.pdf"),
        str(tmp_path / "rseqc_gene_body_coverage" / "output.geneBodyCoverage.curves.pdf"),
    ]


def test_tin_uses_node_directory_for_cwd_relative_source_outputs(registry: NodeRegistry) -> None:
    node_class = registry.get("rseqc_tin")
    assert node_class is not None
    assert node_class.RUN_IN_NODE_OUTPUT_DIR is True
    assert node_class.RETURN_TYPES == ("DIRECTORY",)
    assert node_class.render_command(
        {
            "inputs": ["a.bam", "b.bam"],
            "bam_indexes": ["a.bam.bai", "b.bam.bai"],
            "refgene": "genes.bed",
            "minCov": 12,
            "samplesize": 80,
            "subtractbackground": True,
        }
    ) == ["tin.py", "-i", "a.bam,b.bam", "-r", "genes.bed", "-c", "12", "-n", "80", "-s"]


@pytest.mark.asyncio
async def test_tin_runtime_uses_node_cwd_and_verifies_source_outputs(
    tmp_path: Path,
    registry: NodeRegistry,
) -> None:
    node_class = registry.get("rseqc_tin")
    assert node_class is not None

    class Context:
        node_dir = tmp_path

        def __init__(self) -> None:
            self.calls: list[tuple[list[str], dict[str, object]]] = []

        async def run_command(self, command: list[str], **kwargs: object) -> dict[str, object]:
            self.calls.append((command, kwargs))
            cwd = Path(str(kwargs["cwd"]))
            (cwd / "a.summary.txt").write_text("summary\n")
            (cwd / "a.tin.xls").write_text("tin\n")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await node_class().run(
        context=context,
        input=["a.bam"],
        bam_indexes=["a.bam.bai"],
        refgene="genes.bed",
    )
    assert result == (str(tmp_path / "rseqc_tin"),)
    assert context.calls[0][1]["cwd"] == str(tmp_path / "rseqc_tin")


def test_tin_rejects_colliding_source_output_basenames(registry: NodeRegistry) -> None:
    node_class = registry.get("rseqc_tin")
    assert node_class is not None
    validation = node_class.VALIDATE_INPUTS(
        {
            "input": ["one/a.bam", "two/a.bam"],
            "bam_indexes": ["one/a.bam.bai", "two/a.bam.bai"],
            "refgene": "genes.bed",
        }
    )
    assert validation is not True
    assert "basenames must be unique" in str(validation)


def test_rseqc_ids_are_owned_by_focused_modules() -> None:
    index = build_index()
    rseqc = {node_id: module for node_id, module in index.items() if node_id.startswith("rseqc_")}
    assert set(rseqc) == {case[0] for case in CASES}
    assert all(module.startswith("bionodulo.nodes.builtin.rseqc_family.") for module in rseqc.values())
    assert "bionodulo.nodes.builtin.wrapped_rseqc" not in set(rseqc.values())
