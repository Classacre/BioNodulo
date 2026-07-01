from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_mosdepth_exposes_bionodulo_builtin_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mosdepth"]
    assert node_info["display_name"] == "mosdepth"
    assert node_info["category"] == "qc"
    assert node_info["output"] == ["TSV", "TSV", "TSV", "BEDGRAPH", "BED", "BED", "BED"]
    assert node_info["output_name"] == [
        "global_distribution",
        "summary",
        "region_distribution",
        "per_base_depth",
        "regions_bed",
        "quantized_bed",
        "thresholds_bed",
    ]
    assert node_info["required_executables"] == ["mosdepth", "gunzip"]
    assert node_info["required_conda_packages"] == ["mosdepth", "gzip"]
    assert node_info["documentation_url"] == "https://github.com/brentp/mosdepth"
    assert "10.1093/bioinformatics/btx699" in node_info["citation_dois"]
    assert "https://doi.org/10.1093/bioinformatics/btx699" in node_info["citation_urls"]
    assert "quick coverage calculation" in node_info["citation_text"]
    assert "BioNodulo builtin" in node_info["search_aliases"]
    assert "BAM CRAM depth" in node_info["search_aliases"]


def test_mosdepth_renders_default_summary_only_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mosdepth")

    assert node_class.render_command(
        {
            "input_alignment": "sample.bam",
            "threads": 4,
            "per_base_coverage": False,
            "window_mode": "no",
            "output": "/work/mosdepth",
        }
    ) == [
        "mosdepth",
        "-t",
        "4",
        "--no-per-base",
        "/work/mosdepth/output",
        "sample.bam",
    ]

    assert node_class.PLAN_OUTPUTS({"per_base_coverage": False, "window_mode": "no"}, tmp_path) == [
        tmp_path / "mosdepth" / "output.mosdepth.global.dist.txt",
        tmp_path / "mosdepth" / "output.mosdepth.summary.txt",
    ]


def test_mosdepth_renders_regions_thresholds_quantize_command_and_outputs(tmp_path: Path) -> None:
    node_class = _node_class("mosdepth")
    inputs = {
        "input_alignment": "sample.cram",
        "threads": 8,
        "per_base_coverage": True,
        "window_mode": "bed",
        "region_file": "targets.bed",
        "chrom": "chr1",
        "exclude_flag": 1796,
        "include_flag": 2,
        "mapq": 20,
        "fast_mode": True,
        "fragment_mode": False,
        "thresholds": "10,20",
        "use_median": True,
        "read_groups": "tumor,normal",
        "quantize_depths": "0:1:20:",
        "quantize_labels": "NO_COVERAGE,LOW_COVERAGE,CALLABLE",
        "min_frag_len": 100,
        "max_frag_len": 500,
        "output": "/work/mosdepth",
    }

    assert node_class.render_command(inputs) == [
        "export",
        "MOSDEPTH_Q0=NO_COVERAGE",
        "&&",
        "export",
        "MOSDEPTH_Q1=LOW_COVERAGE",
        "&&",
        "export",
        "MOSDEPTH_Q2=CALLABLE",
        "&&",
        "mosdepth",
        "-t",
        "8",
        "--by",
        "targets.bed",
        "--chrom",
        "chr1",
        "--flag",
        "1796",
        "--include-flag",
        "2",
        "--mapq",
        "20",
        "--fast-mode",
        "--thresholds",
        "10,20",
        "--use-median",
        "--read-groups",
        "tumor,normal",
        "--quantize",
        "0:1:20:",
        "--min-frag-len",
        "100",
        "--max-frag-len",
        "500",
        "/work/mosdepth/output",
        "sample.cram",
        "&&",
        "gunzip",
        "/work/mosdepth/output.per-base.bed.gz",
        "&&",
        "gunzip",
        "/work/mosdepth/output.regions.bed.gz",
        "&&",
        "gunzip",
        "/work/mosdepth/output.thresholds.bed.gz",
        "&&",
        "gunzip",
        "/work/mosdepth/output.quantized.bed.gz",
    ]

    assert node_class.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "mosdepth" / "output.mosdepth.global.dist.txt",
        tmp_path / "mosdepth" / "output.mosdepth.summary.txt",
        tmp_path / "mosdepth" / "output.mosdepth.region.dist.txt",
        tmp_path / "mosdepth" / "output.per-base.bed",
        tmp_path / "mosdepth" / "output.regions.bed",
        tmp_path / "mosdepth" / "output.quantized.bed",
        tmp_path / "mosdepth" / "output.thresholds.bed",
    ]
