"""Tests for the domain gold-standard viz nodes (Krona, Scanpy) and their
wiring into the metagenomics / single-cell templates."""

from __future__ import annotations

import json
from pathlib import Path

from bionodulo.nodes.builtin.metagenomics_family.krona import KronaTaxonomyNode
from bionodulo.nodes.builtin.single_cell_spatial_family.scanpy_umap import ScanpyUmapNode
from bionodulo.nodes.registry import NodeRegistry

ROOT = Path(__file__).resolve().parents[1]


def _registry() -> NodeRegistry:
    r = NodeRegistry.create_isolated()
    r.load_builtin_nodes()
    return r


def _template(name: str) -> dict:
    return json.loads((ROOT / "templates" / name).read_text(encoding="utf-8"))


def _has_edge(wf: dict, src: str, out: str, dst: str, inp: str) -> bool:
    return any(
        e.get("from") == {"node": src, "output": out} and e.get("to") == {"node": dst, "input": inp}
        for e in wf["edges"]
    )


def test_krona_and_scanpy_nodes_registered_for_discovery() -> None:
    info = _registry().object_info()
    assert info["krona"]["category"] == "metagenomics"
    assert info["scanpy_umap"]["category"] == "single_cell"
    assert "ktImportTaxonomy" in KronaTaxonomyNode.REQUIRED_EXECUTABLES
    assert "scanpy" in ScanpyUmapNode.REQUIRED_CONDA_PACKAGES


def test_inline_preview_flag_marks_terminal_visual_nodes() -> None:
    info = _registry().object_info()
    # Terminal-visual producers render on the node (no separate preview sink).
    for nid in ("bar_chart", "volcano_plot", "heatmap", "r_plot", "r_pheatmap",
                "quast", "krona", "multiqc", "coverage_plot"):
        assert info[nid]["inline_preview"] is True, nid
    # Sinks, multi-figure, and non-visual tools are not inline-previewable.
    for nid in ("image_preview", "html_preview", "table_preview", "text_preview",
                "scanpy_umap", "bwa_mem", "samtools_sort"):
        assert info[nid]["inline_preview"] is False, nid


def test_krona_command_targets_kraken_columns() -> None:
    cmd = KronaTaxonomyNode.render_command({
        "classification": "reads.kraken",
        "taxonomy": "taxonomy",
        "query_column": 2,
        "taxid_column": 3,
        "output": "krona-output",
    })
    assert cmd[0] == "ktImportTaxonomy"
    assert "-q" in cmd and "2" in cmd and "-t" in cmd and "3" in cmd
    assert cmd[cmd.index("-tax") + 1] == "taxonomy"
    assert cmd[-1] == "reads.kraken"
    assert "krona-output/krona.html" in cmd


def test_scanpy_script_runs_standard_pipeline() -> None:
    script = ScanpyUmapNode._build_script(
        h5="m.h5", min_genes=200, min_cells=3, n_pcs=30, n_neighbors=15,
        resolution=1.0, umap_png="umap.png", violin_png="qc.png",
    )
    for needle in (
        "import scanpy as sc",
        "read_10x_h5",
        "sc.pp.pca",
        "sc.tl.umap",
        "sc.tl.leiden",
        'flavor="igraph"',
        "umap.png",
        "qc.png",
    ):
        assert needle in script


def test_metagenomics_template_wires_krona_from_kraken() -> None:
    wf = _template("metagenomics_pipeline.json")
    types = {n["id"]: n["type"] for n in wf["nodes"]}
    assert types["krona_001"] == "krona"
    # Krona is inline-previewable, so it renders on the node — no separate sink.
    assert "render_krona_html_1" not in types
    assert _has_edge(wf, "kraken2_001", "classification", "krona_001", "classification")
    # taxonomy.tab is built in-workflow from the NCBI taxdump: KronaTools
    # publishes no prebuilt database, only updateTaxonomy.sh.
    assert _has_edge(wf, "krona_build_taxonomy_001", "taxonomy", "krona_001", "taxonomy")


def test_single_cell_template_wires_scanpy_umap() -> None:
    wf = _template("single_cell_pipeline.json")
    types = {n["id"]: n["type"] for n in wf["nodes"]}
    assert types["scanpy_umap_001"] == "scanpy_umap"
    assert types["render_umap_ima_1"] == "image_preview"
    # Cell Ranger is BYOL and unusable unattended; STARsolo feeds the same
    # matrix, as a Matrix-Market directory rather than an HDF5.
    assert _has_edge(wf, "starsolo_001", "filtered_matrix", "scanpy_umap_001", "matrix_h5")
    assert _has_edge(wf, "scanpy_umap_001", "umap_png", "render_umap_ima_1", "file")
    assert _has_edge(wf, "scanpy_umap_001", "qc_violin_png", "render_qc_violin_ima_2", "file")
