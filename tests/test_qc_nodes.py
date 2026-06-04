from pathlib import Path

from bionodulo.nodes.builtin.qc import QualiMapNode
from bionodulo.nodes.registry import NodeRegistry


def test_qualimap_alias_is_registered_by_builtin_loading() -> None:
    registry = NodeRegistry.create_isolated()

    registry.load_builtin_nodes()

    alias = registry.get("qualimap")
    assert alias is not None
    assert issubclass(alias, QualiMapNode)


def test_qualimap_alias_overrides_only_planner_metadata() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    alias = registry.get("qualimap")
    assert alias is not None

    assert alias.NODE_ID == "qualimap"
    assert alias.DISPLAY_NAME == "QualiMap"
    assert alias.DESCRIPTION == "Run QualiMap BAM quality control for alignment reports."
    assert {
        "qualimap",
        "bamqc",
        "bam qc",
        "alignment qc",
        "quality report",
    }.issubset(alias.SEARCH_ALIASES)

    assert alias.RETURN_TYPES == QualiMapNode.RETURN_TYPES
    assert alias.RETURN_NAMES == QualiMapNode.RETURN_NAMES
    assert alias.REQUIRED_EXECUTABLES == QualiMapNode.REQUIRED_EXECUTABLES
    assert alias.REQUIRED_CONDA_PACKAGES == QualiMapNode.REQUIRED_CONDA_PACKAGES
    assert alias.DOCUMENTATION_URL == QualiMapNode.DOCUMENTATION_URL
    assert alias.VERSION == QualiMapNode.VERSION
    assert alias.INPUT_TYPES() == QualiMapNode.INPUT_TYPES()


def test_qualimap_alias_renders_and_plans_with_alias_output_path() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    alias = registry.get("qualimap")
    assert alias is not None

    output = "/tmp/run/qualimap"
    cmd = alias.render_command(
        {
            "bam": "sample.bam",
            "threads": 4,
            "output": output,
        }
    )
    planned_outputs = alias.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "qualimap",
        "bamqc",
        "-bam",
        "sample.bam",
        "-outdir",
        f"{output}/report_dir.out",
        "-nt",
        "4",
    ]
    assert planned_outputs == [
        Path("/tmp/run/qualimap/report.html"),
        Path("/tmp/run/qualimap/report_dir.out"),
    ]
