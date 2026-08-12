from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.nodes.builtin.bam_cram_utils_family.clip_overlap import BamUtilClipOverlapNode
from bionodulo.nodes.builtin.bam_cram_utils_family.cramino import CraminoNode
from bionodulo.nodes.builtin.bam_cram_utils_family.diff import BamUtilDiffNode
from bionodulo.nodes.registry import NodeRegistry
from scripts.gen_node_index import build_index


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_bam_cram_utility_nodes_expose_bionodulo_builtin_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    expected = {
        "cramino": {
            "display_name": "Cramino",
            "category": "qc",
            "output": ["STATS_FILE", "FILE", "TSV"],
            "output_name": ["metrics", "arrow_output", "histogram"],
            "required_executables": ["cramino"],
            "required_conda_packages": ["cramino"],
            "documentation_url": "https://github.com/wdecoster/cramino",
            "citation_doi": "10.1093/bioinformatics/btad311",
            "search_alias": "BAM CRAM QC",
        },
        "bamutil_clip_overlap": {
            "display_name": "BamUtil clipOverlap",
            "category": "alignment",
            "output": ["BAM", "STATS_FILE"],
            "output_name": ["clipped_alignment", "overlap_stats"],
            "required_executables": ["bam"],
            "required_conda_packages": ["bamutil"],
            "documentation_url": "https://genome.sph.umich.edu/wiki/BamUtil:_clipOverlap",
            "citation_doi": "10.1101/gr.176552.114",
            "search_alias": "clip overlapping read pairs",
        },
        "bamutil_diff": {
            "display_name": "BamUtil diff",
            "category": "alignment",
            "output": ["FILE", "FILE", "FILE"],
            "output_name": ["diff", "only_in_first", "only_in_second"],
            "required_executables": ["bam"],
            "required_conda_packages": ["bamutil"],
            "documentation_url": "https://genome.sph.umich.edu/wiki/BamUtil:_diff",
            "citation_doi": "10.1101/gr.176552.114",
            "search_alias": "compare SAM BAM files",
        },
    }

    for node_id, metadata in expected.items():
        node_info = info[node_id]
        assert node_info["display_name"] == metadata["display_name"]
        assert node_info["category"] == metadata["category"]
        assert node_info["output"] == metadata["output"]
        assert node_info["output_name"] == metadata["output_name"]
        assert node_info["required_executables"] == metadata["required_executables"]
        assert node_info["required_conda_packages"] == metadata["required_conda_packages"]
        assert node_info["documentation_url"] == metadata["documentation_url"]
        assert metadata["citation_doi"] in node_info["citation_dois"]
        assert f"https://doi.org/{metadata['citation_doi']}" in node_info["citation_urls"]
        assert metadata["search_alias"] in node_info["search_aliases"]
        assert "BioNodulo builtin" in node_info["search_aliases"]


def test_bam_cram_utility_ids_have_focused_source_pinned_owners() -> None:
    index = build_index()
    expected = {
        "cramino": (CraminoNode, "src/main.rs"),
        "bamutil_clip_overlap": (BamUtilClipOverlapNode, "src/ClipOverlap.cpp"),
        "bamutil_diff": (BamUtilDiffNode, "src/Diff.cpp"),
    }

    for node_id, (node_class, source) in expected.items():
        assert index[node_id] == node_class.__module__
        assert node_class.GIT_COMMIT in node_class.SOURCE_URL
        assert node_class.UPSTREAM_SOURCE == source
        assert node_class.SHELL is False

    assert CraminoNode.CONDA_PACKAGE_CONSTRAINTS == {"cramino": "1.3.0"}
    assert BamUtilClipOverlapNode.CONDA_PACKAGE_CONSTRAINTS == {"bamutil": "1.0.15"}
    assert BamUtilDiffNode.CONDA_PACKAGE_CONSTRAINTS == {"bamutil": "1.0.15"}


def test_cramino_renders_optional_qc_outputs(tmp_path: Path) -> None:
    node_class = _node_class("cramino")

    assert node_class.render_command(
        {
            "input_file": "reads.cram",
            "reference": "ref.fa",
            "threads": 6,
            "ubam": False,
            "spliced": True,
            "phased": True,
            "karyotype": True,
            "min_read_len": 500,
            "outfmt": "json",
            "arrow": True,
            "histtype": "hist_count",
            "scaled": True,
            "output": "/work/cramino",
        }
    ) == [
        "cramino",
        "reads.cram",
        "--threads",
        "6",
        "--reference",
        "ref.fa",
        "--spliced",
        "--phased",
        "--karyotype",
        "--min-read-len",
        "500",
        "--format",
        "json",
        "--arrow",
        "/work/cramino/reads.arrow",
        "--hist-count=/work/cramino/histogram_counts.tsv",
        "--scaled",
    ]

    assert node_class.PLAN_OUTPUTS(
        {
            "outfmt": "json",
            "arrow": True,
            "histtype": "hist_count",
        },
        tmp_path,
    ) == [
        tmp_path / "cramino" / "metrics.json",
        tmp_path / "cramino" / "reads.arrow",
        tmp_path / "cramino" / "histogram_counts.tsv",
    ]
    assert node_class.STDOUT_OUTPUT_INDEX == 0
    assert node_class.INPUT_TYPES()["optional"]["ubam"][1]["default"] is False


def test_bamutil_clip_overlap_renders_transform_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bamutil_clip_overlap")

    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "storeOrig": "OC",
            "stats": True,
            "readName": True,
            "noRNValidate": True,
            "overlapsOnly": True,
            "excludeFlags": 3852,
            "unmapped": True,
            "poolSize": 500000,
            "poolSkipOverlap": True,
            "noeof": True,
            "params": True,
            "output": "/work/bamutil_clip_overlap",
        }
    ) == [
        "bam",
        "clipOverlap",
        "--in",
        "aligned.bam",
        "--storeOrig",
        "OC",
        "--readName",
        "--noRNValidate",
        "--stats",
        "--overlapsOnly",
        "--excludeFlags",
        "3852",
        "--unmapped",
        "--poolSize",
        "500000",
        "--poolSkipOverlap",
        "--noeof",
        "--params",
        "--noPhoneHome",
        "--out",
        "/work/bamutil_clip_overlap/clipped.bam",
    ]

    assert node_class.PLAN_OUTPUTS({"stats": True}, tmp_path) == [
        tmp_path / "bamutil_clip_overlap" / "clipped.bam",
        tmp_path / "bamutil_clip_overlap" / "overlap_stats.txt",
    ]
    assert node_class.PLAN_OUTPUTS({"stats": False}, tmp_path) == [
        tmp_path / "bamutil_clip_overlap" / "clipped.bam",
        tmp_path / "bamutil_clip_overlap" / "overlap_stats.txt",
    ]
    assert node_class.STDERR_OUTPUT_INDEX == 1


def test_bamutil_diff_renders_selective_sam_diff_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bamutil_diff")

    assert node_class.render_command(
        {
            "in1": "before.sam",
            "in2": "after.sam",
            "fields_choice": "select",
            "flag": True,
            "seq": True,
            "tagchoice": "specify",
            "tags": "AS:i,MD:Z",
            "posDiff": 5000,
            "recPoolSize": 250,
            "onlyDiffs": True,
            "noeof": True,
            "params": True,
            "output_as": "diff.sam",
            "output": "/work/bamutil_diff",
        }
    ) == [
        "bam",
        "diff",
        "--in1",
        "before.sam",
        "--in2",
        "after.sam",
        "--flag",
        "--seq",
        "--tags",
        "AS:i,MD:Z",
        "--onlyDiffs",
        "--recPoolSize",
        "250",
        "--posDiff",
        "5000",
        "--noeof",
        "--params",
        "--noPhoneHome",
        "--out",
        "/work/bamutil_diff/diff.sam",
    ]

    assert node_class.PLAN_OUTPUTS({"in1": "before.sam", "in2": "after.sam", "output_as": "diff.sam"}, tmp_path) == [
        tmp_path / "bamutil_diff" / "diff.sam",
        tmp_path / "bamutil_diff" / "diff_only1_before.sam",
        tmp_path / "bamutil_diff" / "diff_only2_after.sam",
    ]


def test_bamutil_diff_uses_the_parser_registered_every_tags_flag() -> None:
    command = BamUtilDiffNode.render_command(
        {
            "in1": "before.bam",
            "in2": "after.bam",
            "fields_choice": "select",
            "tagchoice": "everyTag",
        }
    )
    assert "--everyTags" in command
    assert "--everyTag" not in command


@pytest.mark.parametrize(
    ("node_class", "inputs"),
    [
        (CraminoNode, {"input_file": "reads.bam", "threads": 0}),
        (CraminoNode, {"input_file": "reads.bam", "ubam": True, "phased": True}),
        (BamUtilClipOverlapNode, {"input": "reads.bam", "noRNValidate": True}),
        (BamUtilClipOverlapNode, {"input": "reads.bam", "poolSize": -1}),
        (BamUtilDiffNode, {"in1": "a.bam", "in2": "b.bam", "recPoolSize": 0}),
        (
            BamUtilDiffNode,
            {
                "in1": "a.bam",
                "in2": "b.bam",
                "fields_choice": "select",
                "tagchoice": "specify",
                "tags": "",
            },
        ),
    ],
)
def test_bam_cram_utility_validation_rejects_invalid_contracts(
    node_class: type,
    inputs: dict[str, Any],
) -> None:
    assert node_class.VALIDATE_INPUTS(inputs) is not True


@pytest.mark.asyncio
async def test_cramino_fake_execution_captures_native_stdout(tmp_path: Path) -> None:
    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None
        kwargs: dict[str, Any] | None = None

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            Path(kwargs["stdout_path"]).write_text("Number of reads\t2\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await CraminoNode().run(input_file="reads.bam", threads=2, context=context)
    expected = tmp_path / "run" / "cramino" / "metrics.txt"
    assert result == (str(expected),)
    assert context.command == ["cramino", "reads.bam", "--threads", "2", "--format", "text"]
    assert context.kwargs == {"env": None, "cwd": tmp_path / "run", "stdout_path": expected}


@pytest.mark.asyncio
async def test_clip_overlap_fake_execution_captures_native_stderr(tmp_path: Path) -> None:
    class Context:
        node_dir = tmp_path / "run"
        command: list[str] | None = None
        kwargs: dict[str, Any] | None = None

        async def run_command(self, command: list[str], **kwargs: Any) -> dict[str, Any]:
            self.command = command
            self.kwargs = kwargs
            Path(command[command.index("--out") + 1]).write_bytes(b"bam")
            Path(kwargs["stderr_path"]).write_text("Completed ClipOverlap Successfully.\n", encoding="ascii")
            return {"returncode": 0, "stdout": "", "stderr": ""}

    context = Context()
    result = await BamUtilClipOverlapNode().run(input="reads.bam", stats=False, context=context)
    clipped = tmp_path / "run" / "bamutil_clip_overlap" / "clipped.bam"
    stats = tmp_path / "run" / "bamutil_clip_overlap" / "overlap_stats.txt"
    assert result == (str(clipped), str(stats))
    assert context.kwargs == {"env": None, "cwd": tmp_path / "run", "stderr_path": stats}
