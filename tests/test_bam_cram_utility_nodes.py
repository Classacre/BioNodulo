from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_bam_cram_utility_nodes_expose_galaxy_metadata() -> None:
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
        assert "Galaxy" in node_info["search_aliases"]


def test_cramino_renders_optional_qc_outputs(tmp_path: Path) -> None:
    node_class = _node_class("cramino")

    assert node_class.render_command(
        {
            "input_file": "reads.cram",
            "reference": "ref.fa",
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
        ">",
        "/work/cramino/metrics.json",
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


def test_bamutil_clip_overlap_renders_transform_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("bamutil_clip_overlap")

    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "storeOrig": "OC",
            "stats": True,
            "readName": True,
            "overlapsOnly": True,
            "excludeFlags": 3852,
            "unmapped": True,
            "output": "/work/bamutil_clip_overlap",
        }
    ) == [
        "bam",
        "clipOverlap",
        "--in",
        "aligned.bam",
        "--storeOrig",
        "OC",
        "--stats",
        "--readName",
        "--overlapsOnly",
        "--excludeFlags",
        "3852",
        "--unmapped",
        "--noPhoneHome",
        "--out",
        "/work/bamutil_clip_overlap/clipped.bam",
        "2>",
        "/work/bamutil_clip_overlap/output.log",
        "&&",
        "cp",
        "/work/bamutil_clip_overlap/output.log",
        "/work/bamutil_clip_overlap/overlap_stats.txt",
    ]

    assert node_class.PLAN_OUTPUTS({"stats": True}, tmp_path) == [
        tmp_path / "bamutil_clip_overlap" / "clipped.bam",
        tmp_path / "bamutil_clip_overlap" / "overlap_stats.txt",
    ]


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
            "onlyDiffs": True,
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
        "--posDiff",
        "5000",
        "--recPoolSize",
        "-1",
        "--onlyDiffs",
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
