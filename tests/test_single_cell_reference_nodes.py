from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.registry import NodeRegistry


def _node_class() -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get("cellranger_mkref")
    assert node_class is not None
    return node_class


def test_cellranger_mkref_resolves_to_focused_external_contract() -> None:
    node_class = _node_class()
    assert node_class.__module__ == "bionodulo.nodes.builtin.single_cell_spatial_family.cellranger_mkref"
    assert node_class.VERSION == "9.0.1"
    assert node_class.GIT_COMMIT == "6ebad209b8354353b4a9ee3eed1cb248d102af88"
    assert node_class.REQUIRED_CONDA_PACKAGES == []
    assert node_class.ENVIRONMENT["provisioning"] == "external_worker_binary"


def test_cellranger_mkref_renders_documented_arguments() -> None:
    command = _node_class().render_command(
        {
            "fasta": "/refs/genome.fa",
            "gtf": "/refs/genes.gtf",
            "genome_name": "GRCh38_custom",
            "threads": 6,
            "memory": 24,
            "ref_version": "2026-01",
        }
    )
    assert command == [
        "cellranger",
        "mkref",
        "--genome",
        "GRCh38_custom",
        "--fasta",
        "/refs/genome.fa",
        "--genes",
        "/refs/genes.gtf",
        "--nthreads",
        "6",
        "--memgb",
        "24",
        "--disable-ui",
        "--ref-version",
        "2026-01",
    ]


def test_cellranger_mkref_defaults_match_upstream_wrapper() -> None:
    command = _node_class().render_command({"fasta": "genome.fa", "gtf": "genes.gtf", "genome_name": "custom_ref"})
    assert ["--nthreads", "1"] == command[8:10]
    assert ["--memgb", "16"] == command[10:12]
    assert command[-1] == "--disable-ui"


def test_cellranger_mkref_rejects_non_ascii_or_path_like_names() -> None:
    validation = _node_class().VALIDATE_INPUTS(
        {"fasta": "genome.fa", "gtf": "genes.gtf", "genome_name": "reference/one"}
    )
    assert validation == "Input 'genome_name' may only contain ASCII letters, numbers, underscores, and hyphens"


def test_cellranger_mkref_output_and_cache_include_reference_identity(tmp_path: Path) -> None:
    node_class = _node_class()
    inputs = {
        "fasta": "genome.fa",
        "gtf": "genes.gtf",
        "genome_name": "custom_ref",
        "ref_version": "v1",
    }
    assert node_class.PLAN_OUTPUTS(inputs, tmp_path) == [tmp_path / "cellranger_mkref" / "custom_ref"]
    first = node_class.reference_cache_id(inputs)
    second = node_class.reference_cache_id({**inputs, "genome_name": "custom_ref_2"})
    third = node_class.reference_cache_id({**inputs, "ref_version": "v2"})
    assert len({first, second, third}) == 3
