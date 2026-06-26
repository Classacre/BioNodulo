from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_samblaster_exposes_galaxy_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["samblaster"]
    assert node_info["display_name"] == "samblaster"
    assert node_info["category"] == "alignment"
    assert node_info["output"] == ["BAM", "BAM", "BAM", "FASTQ"]
    assert node_info["output_name"] == ["alignments", "discordant_alignments", "split_alignments", "unmapped_reads"]
    assert node_info["required_executables"] == ["samblaster", "sambamba"]
    assert node_info["required_conda_packages"] == ["samblaster", "sambamba"]
    assert node_info["documentation_url"] == "https://github.com/GregoryFaust/samblaster"
    assert "10.1093/bioinformatics/btu314" in node_info["citation_dois"]
    assert "https://doi.org/10.1093/bioinformatics/btu314" in node_info["citation_urls"]
    assert "SAMBLASTER" in node_info["citation_text"]
    assert "Galaxy" in node_info["search_aliases"]
    assert "split reads" in node_info["search_aliases"]


def test_samblaster_renders_bam_command_with_optional_outputs(tmp_path: Path) -> None:
    node_class = _node_class("samblaster")

    assert node_class.render_command(
        {
            "input": "aligned.bam",
            "output_bam": True,
            "discordantFile": True,
            "splitterFile": True,
            "unmappedFile": True,
            "acceptDupMarks": True,
            "excludeDups": True,
            "removeDups": True,
            "addMateTags": True,
            "compatibility_mode": True,
            "maxSplitCount": 3,
            "maxUnmappedBases": 75,
            "minIndelSize": 100,
            "minNonOverlap": 25,
            "minClipSize": 30,
            "threads": 8,
            "input_format": "bam",
            "output_dir": "/work/samblaster",
        }
    ) == [
        "sambamba",
        "view",
        "-t",
        "8",
        "-h",
        "<(sambamba sort -t 8 -n 'aligned.bam' -o /dev/stdout)",
        "|",
        "samblaster",
        "-o",
        "/work/samblaster/output.sam",
        "-d",
        "/work/samblaster/discordant.sam",
        "-s",
        "/work/samblaster/splitter.sam",
        "-u",
        "/work/samblaster/unmapped.fastq",
        "-a",
        "-e",
        "-r",
        "--addMateTags",
        "-M",
        "--maxSplitCount",
        "3",
        "--maxUnmappedBases",
        "75",
        "--minIndelSize",
        "100",
        "--minNonOverlap",
        "25",
        "--minClipSize",
        "30",
        "&&",
        "sambamba",
        "sort",
        "-o",
        "/work/samblaster/output.bam",
        "-l",
        "6",
        "-t",
        "8",
        "<(sambamba view -S -f bam /work/samblaster/output.sam)",
        "&&",
        "sambamba",
        "sort",
        "-o",
        "/work/samblaster/discordant.bam",
        "-l",
        "6",
        "-t",
        "8",
        "<(sambamba view -S -f bam /work/samblaster/discordant.sam)",
        "&&",
        "sambamba",
        "sort",
        "-o",
        "/work/samblaster/splitter.bam",
        "-l",
        "6",
        "-t",
        "8",
        "<(sambamba view -S -f bam /work/samblaster/splitter.sam)",
    ]

    assert node_class.PLAN_OUTPUTS(
        {"output_bam": True, "discordantFile": True, "splitterFile": True, "unmappedFile": True},
        tmp_path,
    ) == [
        tmp_path / "samblaster" / "output.bam",
        tmp_path / "samblaster" / "discordant.bam",
        tmp_path / "samblaster" / "splitter.bam",
        tmp_path / "samblaster" / "unmapped.fastq",
    ]


def test_samblaster_renders_sam_input_and_suppressed_primary_output(tmp_path: Path) -> None:
    node_class = _node_class("samblaster")

    command = node_class.render_command(
        {
            "input": "aligned.sam",
            "output": "/work/samblaster",
            "output_bam": False,
            "splitterFile": True,
            "unmappedFile": False,
            "input_format": "sam",
            "threads": 4,
            "output_dir": "/work/samblaster",
        }
    )

    assert command[:8] == [
        "sambamba",
        "view",
        "-t",
        "4",
        "-h",
        "<(sambamba sort -t 4 -n <(sambamba view -S -f bam -t 4 -h 'aligned.sam') -o /dev/stdout)",
        "|",
        "samblaster",
    ]
    assert "-o" in command
    assert "/dev/null" in command
    assert "/work/samblaster/output.bam" not in command

    assert node_class.PLAN_OUTPUTS({"output": str(tmp_path / "runner_path"), "output_bam": False, "splitterFile": True}, tmp_path) == [
        tmp_path / "samblaster" / "splitter.bam",
    ]
