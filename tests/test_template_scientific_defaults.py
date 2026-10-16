from __future__ import annotations

import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace

import pytest

from bionodulo.nodes.builtin.annotation_family.intersect_genes import IntersectGenesNode
from bionodulo.nodes.builtin.utility_preview_family.image_preview import ImagePreviewNode
from bionodulo.nodes.builtin.variant_family.freebayes import FreeBayesNode
from bionodulo.nodes.builtin.variant_family.gatk_haplotype_caller import GatkHaplotypeCallerNode
from bionodulo.nodes.builtin.visualization_family.phylo_tree_viewer import PhylogeneticTreeViewerNode
from bionodulo.nodes.builtin.visualization_family.adapter import _bootstrap_value


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).parent / "fixtures"


def _workflow(stem: str) -> dict:
    return json.loads((ROOT / "templates" / f"{stem}.json").read_text(encoding="utf-8"))


def _node(workflow: dict, identifier: str) -> dict:
    return next(node for node in workflow["nodes"] if node["id"] == identifier)


def test_airway_example_groups_use_verified_ids_and_do_not_claim_pathways() -> None:
    evidence = json.loads((FIXTURES / "airway_example_gene_sets_source.json").read_text())
    workflow = _workflow("deseq2_differential_expression")
    asset = ROOT / _node(workflow, "pathway_gene_sets_001")["params"]["file"]
    assert asset == ROOT / evidence["fixture"]
    assert asset.name != "deseq2_gene_sets.json"
    assert hashlib.sha256(asset.read_bytes()).hexdigest() == evidence["fixture_sha256"]
    groups = json.loads(asset.read_text())
    assert set(groups) == {"Illustrative group A", "Illustrative group B", "Illustrative group C"}
    source_genes = {row["ensgene"] for row in evidence["selected_source_rows"]}
    assert len(source_genes) == 15
    assert all(re.fullmatch(r"ENSG\d{11}", gene) for gene in source_genes)
    assert set(gene for members in groups.values() for gene in members) == source_genes
    assert all(len(members) == 5 for members in groups.values())
    assert f"/{evidence['source_commit']}/" in evidence["source_url"]
    assert evidence["source_rows"] == 38694
    significant = evidence["selected_significant_rows"]
    assert {row["gene"] for row in significant} == source_genes
    assert all(0 <= float(row["padj"]) <= 0.05 for row in significant)
    assert evidence["significant_output"]["verified"] is True
    assert evidence["significant_output"]["sha256"] == "dd42b142d692c976384e887e05dfc9f9a93b3414af6a5905ed546c22ea7d775c"
    note = _node(workflow, "note_deseq2")["params"]["text"]
    assert "arbitrarily" in note and "not biological pathways" in note
    # The original general-purpose fixture remains a separate synthetic-ID asset.
    original = json.loads((ROOT / "templates/data/deseq2_gene_sets.json").read_text())
    assert all(gene.startswith("gene_") for members in original.values() for gene in members)


@pytest.mark.asyncio
async def test_airway_identifiers_produce_real_overlap_rows(tmp_path: Path) -> None:
    workflow = _workflow("deseq2_differential_expression")
    asset = ROOT / _node(workflow, "pathway_gene_sets_001")["params"]["file"]
    groups = json.loads(asset.read_text())
    evidence = json.loads((FIXTURES / "airway_example_gene_sets_source.json").read_text())
    selected = evidence["selected_significant_rows"]
    query = tmp_path / "selected_genes.csv"
    with query.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
        writer.writerow({"gene": "UNMAPPED", "padj": "0.01"})
    table, summary = await IntersectGenesNode().run(
        input_genes=query, database=asset, output_dir=tmp_path,
        **_node(workflow, "pathway_enrichment_001")["params"],
    )
    rows = list(csv.DictReader(Path(table).open(encoding="utf-8"), delimiter="\t"))
    assert {row["gene"] for row in rows} == {row["gene"] for row in selected}
    assert {row["gene_set"] for row in rows} == set(groups)
    result = json.loads(Path(summary).read_text())
    assert result["query_gene_count"] == 16
    assert result["overlap_gene_count"] == 15


@pytest.mark.parametrize(
    ("stem", "identifier", "node_class", "option"),
    [
        ("variant_calling_pipeline", "gatk_001", GatkHaplotypeCallerNode, "--sample-ploidy"),
        ("wgs_variant_pipeline", "fb_001", FreeBayesNode, "-p"),
    ],
)
def test_bacterial_defaults_reach_the_native_haploid_command(
    tmp_path: Path, stem: str, identifier: str, node_class: type, option: str,
) -> None:
    workflow = _workflow(stem)
    reference = tmp_path / "reference.fa"
    bam = tmp_path / "sample.bam"
    inputs = {
        "reference": reference, "reference_index": Path(f"{reference}.fai"),
        "sequence_dictionary": reference.with_suffix(".dict"),
        "bam": bam, "bam_index": Path(f"{bam}.bai"), "threads": 4,
        "output": tmp_path / "output", **_node(workflow, identifier)["params"],
    }
    for key in ("reference", "reference_index", "sequence_dictionary", "bam", "bam_index"):
        inputs[key].write_text("fixture\n")
    command = node_class.render_command(inputs)
    assert command[command.index(option) + 1] == "1"
    note = next(node["params"]["text"] for node in workflow["nodes"] if node["type"] == "note")
    assert "197,394" in note and "haploid" in note
    assert "complete germline" not in note.lower()


@pytest.mark.asyncio
async def test_cloud_tree_renders_labeled_svg_accepted_by_image_preview(tmp_path: Path) -> None:
    workflow = _workflow("phylogenetics_pipeline")
    params = _node(workflow, "tree_viewer_001")["params"]
    assert params["format"] == "svg" and params["show_bootstrap"] is True
    source = FIXTURES / "phylogenetics_cloud_tree.treefile"
    evidence = json.loads((FIXTURES / "phylogenetics_svg_source_verification.json").read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest() == evidence["source_sha256"]
    previews = []
    context = SimpleNamespace(node_dir=tmp_path, register_preview=lambda path, **kwargs: previews.append(path))
    result = await PhylogeneticTreeViewerNode().run(tree_file=str(source), context=context, **params)
    image = Path(result["outputs"]["tree_image"])
    assert image.name == "phylo_tree.svg"
    root = ET.fromstring(image.read_text())
    ns = {"svg": "http://www.w3.org/2000/svg"}
    assert root.find("svg:title", ns).text == params["title"]
    texts = root.findall("svg:text", ns)
    tips = [text for text in texts if text.get("class") == "tree-tip"]
    assert {text.get("data-tip") for text in tips} == set(evidence["taxon_ids"])
    supports = [float(text.get("data-bootstrap")) for text in texts if text.get("class") == "tree-bootstrap"]
    assert supports and all(value >= params["bootstrap_threshold"] for value in supports)
    assert {text.text for text in texts if text.get("class") == "tree-bootstrap"} == {"98.8/100", "100/100"}
    expected_size = PhylogeneticTreeViewerNode.INPUT_TYPES()["optional"]["tip_label_size"][1]["default"]
    assert all(text.get("font-size") == str(expected_size) for text in tips)
    assert ImagePreviewNode.VALIDATE_INPUTS({"file": image}) is True
    await ImagePreviewNode().run(file=image, context=context)
    assert previews == [image, image]


@pytest.mark.parametrize(
    ("label", "expected"),
    [("95", 95), ("70.5", 70.5), ("0", 0), (" 98.8/100 ", 100), ("100/69", 69),
     ("bad/100", None), ("95/", None), ("/100", None), ("1/2/3", None),
     ("nan/100", None), ("98/inf", None), ("101/100", None), ("-1/100", None),
     ("-1", None), ("101", None), ("nan", None)],
)
def test_tree_support_accepts_numeric_or_iqtree_paired_percentages(label: str, expected: float | None) -> None:
    assert _bootstrap_value(label) == expected


@pytest.mark.asyncio
async def test_iqtree_svg_threshold_uses_ufboot_and_preserves_support_labels(tmp_path: Path) -> None:
    source = tmp_path / "supports.treefile"
    source.write_text("(((A:1,B:1)98.8/100:1,(C:1,D:1)100/69:1)95:1,(E:1,F:1)69:1,G:1);")
    context = SimpleNamespace(node_dir=tmp_path)
    node = PhylogeneticTreeViewerNode()
    result = await node.run(tree_file=source, context=context, format="svg", show_bootstrap=True, bootstrap_threshold=70, tip_label_size=14)
    root = ET.fromstring(Path(result["outputs"]["tree_image"]).read_text())
    supports = root.findall("{http://www.w3.org/2000/svg}text[@class='tree-bootstrap']")
    assert {text.text for text in supports} == {"98.8/100", "95"}
    assert {text.get("data-bootstrap") for text in supports} == {"100", "95"}
    assert all(text.get("font-size") == "14" for text in root.findall("{http://www.w3.org/2000/svg}text[@class='tree-tip']"))
    result = await node.run(tree_file=source, context=context, format="html", show_bootstrap=True, bootstrap_threshold=70)
    document = Path(result["outputs"]["tree_image"]).read_text()
    assert '"bootstrap: 98.8/100"' in document and '"bootstrap: 95"' in document
    assert '"bootstrap: 100/69"' not in document and '"bootstrap: 69"' not in document
    result = await node.run(tree_file=source, context=context, format="svg", show_bootstrap=False)
    root = ET.fromstring(Path(result["outputs"]["tree_image"]).read_text())
    assert root.findall("{http://www.w3.org/2000/svg}text[@class='tree-bootstrap']") == []
