from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_samtools_duplicate_marking_path_nodes_are_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    collate_info = info["samtools_collate"]
    assert collate_info["display_name"] == "Samtools Collate"
    assert collate_info["category"] == "samtools"
    assert collate_info["description"].startswith("Name-collate a BAM")
    assert collate_info["output"] == ["BAM"]
    assert collate_info["output_name"] == ["name_collated_bam"]
    assert collate_info["required_executables"] == ["samtools"]
    assert collate_info["required_conda_packages"] == ["samtools"]
    assert "markdup prerequisite" in collate_info["search_aliases"]

    fixmate_info = info["samtools_fixmate"]
    assert fixmate_info["display_name"] == "Samtools Fixmate"
    assert fixmate_info["category"] == "samtools"
    assert fixmate_info["description"].startswith("Add mate coordinates")
    assert fixmate_info["output"] == ["BAM"]
    assert fixmate_info["output_name"] == ["fixmate_bam"]
    assert fixmate_info["required_executables"] == ["samtools"]
    assert fixmate_info["required_conda_packages"] == ["samtools"]
    assert "markdup prerequisite" in fixmate_info["search_aliases"]

    assert set(collate_info["input"]["required"]) == {"bam", "threads"}
    assert set(collate_info["input"]["optional"]) == {"output_name", "temp_prefix"}
    assert set(fixmate_info["input"]["required"]) == {"bam", "threads"}
    assert set(fixmate_info["input"]["optional"]) == {"add_markdup_tags", "remove_secondary_and_unmapped", "output_name"}


def test_samtools_collate_and_fixmate_render_duplicate_marking_prerequisite_commands() -> None:
    collate_class = _node_class("samtools_collate")
    fixmate_class = _node_class("samtools_fixmate")

    assert collate_class.render_command(
        {
            "bam": "/data/sample.aligned.bam",
            "threads": 4,
            "output": "/work/samtools_collate",
            "output_name": "sample",
        }
    ) == [
        "samtools",
        "collate",
        "-@",
        "4",
        "-o",
        "/work/samtools_collate/sample.name_collated.bam",
        "/data/sample.aligned.bam",
    ]

    assert fixmate_class.render_command(
        {
            "bam": "/work/samtools_collate/sample.name_collated.bam",
            "threads": 4,
            "output": "/work/samtools_fixmate",
            "remove_secondary_and_unmapped": True,
            "output_name": "sample",
        }
    ) == [
        "samtools",
        "fixmate",
        "-@",
        "4",
        "-m",
        "-r",
        "/work/samtools_collate/sample.name_collated.bam",
        "/work/samtools_fixmate/sample.fixmate.bam",
    ]


def test_samtools_collate_and_fixmate_plan_safe_named_outputs(tmp_path: Path) -> None:
    collate_class = _node_class("samtools_collate")
    fixmate_class = _node_class("samtools_fixmate")

    collate_outputs = collate_class.PLAN_OUTPUTS({"output_name": "tumor normal"}, tmp_path)
    fixmate_outputs = fixmate_class.PLAN_OUTPUTS({"output_name": "tumor normal"}, tmp_path)

    assert [path.name for path in collate_outputs] == ["tumor_normal.name_collated.bam"]
    assert [path.name for path in fixmate_outputs] == ["tumor_normal.fixmate.bam"]
    assert collate_outputs[0].parent == tmp_path / "samtools_collate"
    assert fixmate_outputs[0].parent == tmp_path / "samtools_fixmate"


def test_samtools_markdup_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["samtools_markdup"]
    assert node_info["display_name"] == "Samtools Markdup"
    assert node_info["category"] == "samtools"
    assert node_info["description"].startswith("Mark or remove duplicate alignments")
    assert node_info["output"] == ["BAM", "STATS_FILE"]
    assert node_info["output_name"] == ["marked_bam", "duplicate_stats"]
    assert node_info["requires_external_tools"] is True
    assert node_info["required_executables"] == ["samtools"]
    assert node_info["required_conda_packages"] == ["samtools"]
    assert "mark duplicates" in node_info["search_aliases"]
    assert "picard equivalent" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"bam", "threads"}
    assert set(inputs["optional"]) == {
        "remove_duplicates",
        "mark_supplementary",
        "mark_optical_duplicates",
        "optical_distance",
        "read_name_regex",
        "clear_existing_duplicate_flags",
        "output_name",
    }


def test_samtools_markdup_renders_default_marking_command() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.render_command(
        {
            "bam": "/data/sample.sorted.fixmate.bam",
            "threads": 8,
            "output": "/work/samtools_markdup",
            "output_name": "sample",
        }
    ) == [
        "samtools",
        "markdup",
        "-@",
        "8",
        "-f",
        "/work/samtools_markdup/sample.duplicate_stats.txt",
        "/data/sample.sorted.fixmate.bam",
        "/work/samtools_markdup/sample.markdup.bam",
    ]


def test_samtools_markdup_renders_remove_and_optical_duplicate_options() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.render_command(
        {
            "bam": "/data/sample.bam",
            "threads": 2,
            "output": "/work/samtools_markdup",
            "remove_duplicates": True,
            "mark_supplementary": True,
            "mark_optical_duplicates": True,
            "optical_distance": 120,
            "read_name_regex": "(\\d+):(\\d+):(\\d+)",
            "clear_existing_duplicate_flags": True,
            "output_name": "tumor normal",
        }
    ) == [
        "samtools",
        "markdup",
        "-@",
        "2",
        "-r",
        "-S",
        "-d",
        "120",
        "--read-coords",
        "(\\d+):(\\d+):(\\d+)",
        "-c",
        "-f",
        "/work/samtools_markdup/tumor_normal.duplicate_stats.txt",
        "/data/sample.bam",
        "/work/samtools_markdup/tumor_normal.markdup.bam",
    ]


def test_samtools_markdup_plans_safe_named_outputs(tmp_path: Path) -> None:
    node_class = _node_class("samtools_markdup")

    outputs = node_class.PLAN_OUTPUTS({"output_name": "tumor normal"}, tmp_path)

    assert [path.name for path in outputs] == [
        "tumor_normal.markdup.bam",
        "tumor_normal.duplicate_stats.txt",
    ]
    assert outputs[0].parent == tmp_path / "samtools_markdup"
    assert outputs[0].parent.exists()


def test_samtools_markdup_infers_clean_output_stem_from_processed_bam_name(tmp_path: Path) -> None:
    node_class = _node_class("samtools_markdup")

    outputs = node_class.PLAN_OUTPUTS({"bam": "/data/sample.name_collated.fixmate.sorted.bam"}, tmp_path)

    assert [path.name for path in outputs] == [
        "sample.markdup.bam",
        "sample.duplicate_stats.txt",
    ]


def test_samtools_markdup_rejects_invalid_numeric_options() -> None:
    node_class = _node_class("samtools_markdup")

    assert node_class.VALIDATE_INPUTS({"bam": "sample.bam", "threads": 0}) == "threads must be between 1 and 64"
    assert (
        node_class.VALIDATE_INPUTS({"bam": "sample.bam", "threads": 2, "optical_distance": -1})
        == "optical_distance must be non-negative"
    )
