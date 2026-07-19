from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.annotation import BEDToolsClosestNode as LegacyClosest
from bionodulo.nodes.builtin.bedtools_family.closest import BEDToolsClosestNode
from bionodulo.nodes.builtin.chip_seq import MACS2BdgPeakNode as LegacyBdgPeak
from bionodulo.nodes.builtin.chip_seq import MACS2CallpeakNode as LegacyCallpeak
from bionodulo.nodes.builtin.deeptools_family.bam_coverage import DeepToolsBamCoverageNode
from bionodulo.nodes.builtin.deeptools_family.compute_matrix import DeepToolsComputeMatrixNode
from bionodulo.nodes.builtin.deeptools_family.plot_heatmap import DeepToolsPlotHeatmapNode
from bionodulo.nodes.builtin.deeptools_family.plot_profile import DeepToolsPlotProfileNode
from bionodulo.nodes.builtin.epigenomics import DeepToolsBamCoverageNode as LegacyBamCoverage
from bionodulo.nodes.builtin.epigenomics import DeepToolsComputeMatrixNode as LegacyComputeMatrix
from bionodulo.nodes.builtin.epigenomics import DeepToolsPlotHeatmapNode as LegacyPlotHeatmap
from bionodulo.nodes.builtin.epigenomics import DeepToolsPlotProfileNode as LegacyPlotProfile
from bionodulo.nodes.builtin.macs2_family.bdgpeakcall import MACS2BdgPeakNode
from bionodulo.nodes.builtin.macs2_family.callpeak import MACS2CallpeakNode
from bionodulo.nodes.registry import NodeRegistry
from bionodulo.workflow.validation import validate_workflow


NODES = (
    MACS2CallpeakNode,
    MACS2BdgPeakNode,
    DeepToolsBamCoverageNode,
    DeepToolsComputeMatrixNode,
    DeepToolsPlotHeatmapNode,
    DeepToolsPlotProfileNode,
    BEDToolsClosestNode,
)

VALID_INPUTS: dict[str, dict[str, Any]] = {
    "macs2_callpeak": {
        "treatment": "chip.bam",
        "name": "sample peaks",
        "genome_size": "hs",
        "format": "AUTO",
        "qvalue": 0.05,
    },
    "macs2_bdgpeak": {"treatment_bdg": "score.bdg", "name": "score peaks"},
    "deeptools_bamcoverage": {
        "bam": "sample.bam",
        "bam_index": "sample.bam.bai",
        "threads": 1,
        "normalize_using": "None",
    },
    "deeptools_compute_matrix": {
        "bigwig": "signal.bw",
        "regions": "genes.bed",
        "mode": "reference-point",
        "threads": 1,
    },
    "deeptools_plot_heatmap": {"matrix": "matrix.gz"},
    "deeptools_plot_profile": {"matrix": "matrix.gz"},
    "bedtools_closest": {"variants": "peaks.bed", "annotations": "genes.bed"},
}

OUTPUT_NAMES = {
    "macs2_callpeak": ("sample_peaks_peaks.narrowPeak", "sample_peaks_treat_pileup.bdg"),
    "macs2_bdgpeak": ("score_peaks.narrowPeak",),
    "deeptools_bamcoverage": ("coverage_bw.bw",),
    "deeptools_compute_matrix": ("matrix.gz",),
    "deeptools_plot_heatmap": ("heatmap.png",),
    "deeptools_plot_profile": ("profile.png",),
    "bedtools_closest": ("closest.bed",),
}


@pytest.mark.parametrize(
    ("focused", "legacy"),
    (
        (MACS2CallpeakNode, LegacyCallpeak),
        (MACS2BdgPeakNode, LegacyBdgPeak),
        (DeepToolsBamCoverageNode, LegacyBamCoverage),
        (DeepToolsComputeMatrixNode, LegacyComputeMatrix),
        (DeepToolsPlotHeatmapNode, LegacyPlotHeatmap),
        (DeepToolsPlotProfileNode, LegacyPlotProfile),
        (BEDToolsClosestNode, LegacyClosest),
    ),
)
def test_legacy_imports_are_exact_focused_aliases(focused: type, legacy: type) -> None:
    assert legacy is focused


@pytest.mark.parametrize("node", NODES, ids=lambda node: node.NODE_ID)
def test_nodes_are_shell_free_source_pinned_and_plan_native_outputs(node: type, tmp_path: Path) -> None:
    expected_identity = {
        "macs2": ("2.2.9.1", "1afcae6a09ced8cf9bb1e87c44dd58f7d7e4891c"),
        "deeptools": ("3.5.6", "ea0f68bb4a1587d713dacb3791861308751ef7d0"),
        "bedtools": ("2.31.1", "705ccfdf2c9a77d71560c8adcece0663c2f5e18e"),
    }
    family = node.REQUIRED_CONDA_PACKAGES[0]

    assert (node.VERSION, node.GIT_COMMIT) == expected_identity[family]
    assert node.GIT_URL.endswith(".git")
    assert node.UPSTREAM_SOURCE
    assert node.SHELL is False
    assert node.PLAN_OUTPUTS(VALID_INPUTS[node.NODE_ID], tmp_path) == [
        tmp_path / node.NODE_ID / filename for filename in OUTPUT_NAMES[node.NODE_ID]
    ]


def test_callpeak_uses_native_outputs_and_pvalue_replaces_qvalue(tmp_path: Path) -> None:
    inputs = {
        **VALID_INPUTS["macs2_callpeak"],
        "control": "input.bam",
        "pvalue": 1e-5,
        "output": str(tmp_path),
    }

    command = MACS2CallpeakNode.render_command(inputs)

    assert command == [
        "macs2",
        "callpeak",
        "-t",
        "chip.bam",
        "-c",
        "input.bam",
        "-f",
        "AUTO",
        "-g",
        "hs",
        "-n",
        "sample_peaks",
        "--outdir",
        str(tmp_path),
        "--bdg",
        "-p",
        "1e-05",
    ]
    assert "-q" not in command
    assert "--broad" not in command


def test_bdgpeakcall_is_one_operation_with_upstream_defaults(tmp_path: Path) -> None:
    command = MACS2BdgPeakNode.render_command({
        **VALID_INPUTS["macs2_bdgpeak"],
        "output": str(tmp_path),
    })

    assert command == [
        "macs2",
        "bdgpeakcall",
        "-i",
        "score.bdg",
        "-c",
        "5.0",
        "-l",
        "200",
        "-g",
        "30",
        "--outdir",
        str(tmp_path),
        "-o",
        "score_peaks.narrowPeak",
    ]
    assert "bdgcmp" not in command
    assert "&&" not in command


@pytest.mark.parametrize(
    ("legacy_inputs", "message"),
    [
        ({"method": "bdgcmp"}, "legacy method=bdgcmp"),
        ({"control_bdg": "control.bdg"}, "legacy control_bdg"),
    ],
)
def test_bdgpeakcall_rejects_legacy_composite_inputs(
    legacy_inputs: dict[str, Any],
    message: str,
) -> None:
    validation = MACS2BdgPeakNode.VALIDATE_INPUTS({
        **VALID_INPUTS["macs2_bdgpeak"],
        **legacy_inputs,
    })

    assert message in str(validation)


def test_bamcoverage_uses_upstream_defaults_and_explicit_bai_pair(tmp_path: Path) -> None:
    command = DeepToolsBamCoverageNode.render_command({
        **VALID_INPUTS["deeptools_bamcoverage"],
        "output": str(tmp_path),
    })

    assert command == [
        "bamCoverage",
        "-b",
        "sample.bam",
        "-o",
        str(tmp_path / "coverage_bw.bw"),
        "-p",
        "1",
        "--binSize",
        "50",
    ]
    assert DeepToolsBamCoverageNode.VALIDATE_INPUTS({
        **VALID_INPUTS["deeptools_bamcoverage"],
        "bam_index": "other.bai",
    }) is not True
    assert DeepToolsBamCoverageNode.VALIDATE_INPUTS({
        **VALID_INPUTS["deeptools_bamcoverage"],
        "normalize_using": "RPGC",
    }) == "RPGC normalization requires a positive effective_genome_size"


@pytest.mark.parametrize(
    ("mode", "updates", "tail"),
    (
        ("reference-point", {}, ["--referencePoint", "TSS", "-b", "500", "-a", "1500"]),
        (
            "scale-regions",
            {"before_region": 0, "after_region": 0},
            ["-b", "0", "-a", "0", "--regionBodyLength", "1000"],
        ),
    ),
)
def test_compute_matrix_defaults_match_each_mode(
    mode: str,
    updates: dict[str, Any],
    tail: list[str],
    tmp_path: Path,
) -> None:
    command = DeepToolsComputeMatrixNode.render_command({
        **VALID_INPUTS["deeptools_compute_matrix"],
        "mode": mode,
        **updates,
        "output": str(tmp_path),
    })

    assert command[:13] == [
        "computeMatrix",
        mode,
        "-S",
        "signal.bw",
        "-R",
        "genes.bed",
        "-o",
        str(tmp_path / "matrix.gz"),
        "-p",
        "1",
        "--binSize",
        "10",
        *tail[:1],
    ]
    assert command[-len(tail):] == tail


def test_plot_nodes_are_single_operations_and_split_multi_value_arguments(tmp_path: Path) -> None:
    heatmap = DeepToolsPlotHeatmapNode.render_command({
        "matrix": "matrix.gz",
        "colormap": "RdYlBu viridis",
        "output": str(tmp_path),
    })
    profile = DeepToolsPlotProfileNode.render_command({
        "matrix": "matrix.gz",
        "colors": "red blue",
        "samples_label": 'control "treated replicate"',
        "regions_label": "promoters enhancers",
        "output": str(tmp_path),
    })

    assert heatmap == [
        "plotHeatmap",
        "-m",
        "matrix.gz",
        "--outFileName",
        str(tmp_path / "heatmap.png"),
        "--heatmapHeight",
        "28.0",
        "--heatmapWidth",
        "4.0",
        "--colorMap",
        "RdYlBu",
        "viridis",
        "--sortRegions",
        "descend",
    ]
    assert "plotProfile" not in heatmap
    assert profile[profile.index("--colors") + 1 : profile.index("--samplesLabel")] == ["red", "blue"]
    assert profile[profile.index("--samplesLabel") + 1 : profile.index("--regionsLabel")] == [
        "control",
        "treated replicate",
    ]
    assert profile[profile.index("--regionsLabel") + 1 : profile.index("--legendLocation")] == [
        "promoters",
        "enhancers",
    ]
    assert "&&" not in profile


def test_removed_plot_heatmap_profile_port_fails_workflow_validation() -> None:
    registry = NodeRegistry.create_isolated()
    registry.register(DeepToolsPlotHeatmapNode)
    result = validate_workflow(
        {
            "nodes": [
                {"id": "source", "type": "deeptools_plot_heatmap", "params": {"matrix": "matrix.gz"}},
                {"id": "target", "type": "deeptools_plot_heatmap", "params": {}},
            ],
            "edges": [
                {
                    "from": {"node": "source", "output": "profile_plot"},
                    "to": {"node": "target", "input": "matrix"},
                }
            ],
        },
        registry,
    )

    assert result.valid is False
    assert "unknown output port 'profile_plot'" in result.errors[0]


def test_closest_captures_stdout_without_unsupported_sorted_flag() -> None:
    command = BEDToolsClosestNode.render_command({
        "variants": "peaks.bed",
        "annotations": "genes.bed",
        "distance": True,
        "strand": "same",
    })

    assert command == [
        "bedtools",
        "closest",
        "-a",
        "peaks.bed",
        "-b",
        "genes.bed",
        "-d",
        "-s",
        "-t",
        "all",
    ]
    assert BEDToolsClosestNode.STDOUT_OUTPUT_INDEX == 0
    assert "-sorted" not in command
    assert ">" not in command
    assert "sorted" not in BEDToolsClosestNode.INPUT_TYPES()["optional"]


class FakeContext:
    def __init__(self, outputs: list[Path], *, returncode: int = 0, create: bool = True) -> None:
        self.outputs = outputs
        self.returncode = returncode
        self.create = create
        self.command: list[str] | None = None
        self.stdout_path: Path | None = None

    async def run_command(self, command: str | list[str], **kwargs: Any) -> dict[str, Any]:
        assert isinstance(command, list)
        self.command = command
        stdout_path = kwargs.get("stdout_path")
        self.stdout_path = Path(stdout_path) if stdout_path is not None else None
        if self.create and self.returncode == 0:
            for output in self.outputs:
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(b"synthetic artifact\n")
        return {"returncode": self.returncode, "stdout": "", "stderr": "synthetic failure"}


@pytest.mark.asyncio
@pytest.mark.parametrize("node", NODES, ids=lambda node: node.NODE_ID)
async def test_fake_execution_returns_every_native_artifact(node: type, tmp_path: Path) -> None:
    inputs = dict(VALID_INPUTS[node.NODE_ID])
    outputs = node.PLAN_OUTPUTS(inputs, tmp_path)
    context = FakeContext(outputs)

    result = await node().run(**inputs, context=context, output_dir=tmp_path)

    assert result == tuple(str(output) for output in outputs)
    assert context.command is not None
    assert all(output.read_bytes() == b"synthetic artifact\n" for output in outputs)
    if node is BEDToolsClosestNode:
        assert context.stdout_path == outputs[0]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node",
    (MACS2CallpeakNode, DeepToolsBamCoverageNode, BEDToolsClosestNode),
    ids=lambda node: node.NODE_ID,
)
async def test_nonzero_exit_is_propagated(node: type, tmp_path: Path) -> None:
    inputs = dict(VALID_INPUTS[node.NODE_ID])
    context = FakeContext(node.PLAN_OUTPUTS(inputs, tmp_path), returncode=19, create=False)

    with pytest.raises(RuntimeError, match=r"Command failed \(exit 19\): synthetic failure"):
        await node().run(**inputs, context=context, output_dir=tmp_path)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "node",
    (MACS2BdgPeakNode, DeepToolsPlotHeatmapNode, BEDToolsClosestNode),
    ids=lambda node: node.NODE_ID,
)
async def test_success_without_required_artifact_fails_closed(node: type, tmp_path: Path) -> None:
    inputs = dict(VALID_INPUTS[node.NODE_ID])
    context = FakeContext(node.PLAN_OUTPUTS(inputs, tmp_path), create=False)

    with pytest.raises(RuntimeError, match="did not create expected output"):
        await node().run(**inputs, context=context, output_dir=tmp_path)


def test_live_discovery_preserves_all_node_ids_and_uses_focused_owners() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert len(registry.all()) == 943
    for node in NODES:
        assert registry.get(node.NODE_ID) is node
