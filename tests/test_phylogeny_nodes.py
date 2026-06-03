from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def _context(tmp_path: Path, name: str) -> SimpleNamespace:
    node_dir = tmp_path / name
    node_dir.mkdir()
    return SimpleNamespace(node_dir=node_dir)


def test_muscle_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["muscle"]
    assert node_info["display_name"] == "MUSCLE"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Multiple sequence alignment")
    assert node_info["output"] == ["ALIGNMENT"]
    assert node_info["output_name"] == ["alignment"]
    assert node_info["required_executables"] == ["muscle"]
    assert node_info["required_conda_packages"] == ["muscle"]
    assert "multiple alignment" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sequences"}
    assert set(inputs["optional"]) == {"maxiters", "diags", "stable"}


def test_muscle_renders_alignment_command_with_optional_flags() -> None:
    node_class = _node_class("muscle")

    cmd = node_class.render_command({
        "sequences": "proteins.faa",
        "maxiters": 8,
        "diags": True,
        "stable": True,
        "output": "/tmp/run/muscle",
    })

    assert cmd == [
        "muscle",
        "-align",
        "proteins.faa",
        "-output",
        "/tmp/run/muscle/alignment.aln.fasta",
        "-maxiters",
        "8",
        "-diags",
        "-stable",
    ]


def test_muscle_omits_disabled_optional_flags_and_plans_outputs() -> None:
    node_class = _node_class("muscle")

    cmd = node_class.render_command({
        "sequences": "dna.fa",
        "maxiters": 0,
        "diags": False,
        "stable": False,
        "output": "/tmp/run/muscle",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "muscle",
        "-align",
        "dna.fa",
        "-output",
        "/tmp/run/muscle/alignment.aln.fasta",
    ]
    assert [str(path) for path in outputs] == ["/tmp/run/muscle/alignment.aln.fasta"]


def test_trimal_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["trimal"]
    assert node_info["display_name"] == "trimAl"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Automated trimming")
    assert node_info["output"] == ["FASTA", "STATS_FILE"]
    assert node_info["output_name"] == ["trimmed", "stats"]
    assert node_info["required_executables"] == ["trimal"]
    assert node_info["required_conda_packages"] == ["trimal"]
    assert "alignment trimming" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"alignment"}
    assert set(inputs["optional"]) == {"automated", "fasta_output", "htmlout"}


def test_trimal_renders_automated_command_with_optional_reports() -> None:
    node_class = _node_class("trimal")

    cmd = node_class.render_command({
        "alignment": "alignment.fasta",
        "automated": "automated1",
        "fasta_output": True,
        "htmlout": True,
        "output": "/tmp/run/trimal",
    })

    assert cmd == [
        "trimal",
        "-in",
        "alignment.fasta",
        "-out",
        "/tmp/run/trimal/trimmed.fasta",
        "-automated1",
        "-fasta",
        "-htmlout",
        "/tmp/run/trimal/stats.html",
    ]


def test_trimal_supports_strict_mode_and_plans_outputs() -> None:
    node_class = _node_class("trimal")

    cmd = node_class.render_command({
        "alignment": "alignment.aln.fasta",
        "automated": "strict",
        "fasta_output": False,
        "htmlout": False,
        "output": "/tmp/run/trimal",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "trimal",
        "-in",
        "alignment.aln.fasta",
        "-out",
        "/tmp/run/trimal/trimmed.fasta",
        "-strict",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/trimal/trimmed.fasta",
        "/tmp/run/trimal/stats.stats.txt",
    ]


def test_raxml_ng_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["raxml_ng"]
    assert node_info["display_name"] == "RAxML-NG"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Maximum likelihood phylogenetic tree inference")
    assert node_info["output"] == ["NEWICK", "FILE"]
    assert node_info["output_name"] == ["tree", "bootstrap"]
    assert node_info["required_executables"] == ["raxml-ng"]
    assert node_info["required_conda_packages"] == ["raxml-ng"]
    assert "raxml-ng" in node_info["search_aliases"]
    assert "maximum likelihood" in node_info["search_aliases"]
    assert "bootstrap" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"alignment", "model", "threads"}
    assert set(inputs["optional"]) == {"seed", "bootstrap_replicates", "outgroup", "tree_search"}


def test_raxml_ng_renders_tree_search_with_bootstrap_command() -> None:
    node_class = _node_class("raxml_ng")

    cmd = node_class.render_command({
        "alignment": "trimmed.fasta",
        "model": "GTR+G",
        "threads": 8,
        "seed": 42,
        "bootstrap_replicates": 100,
        "outgroup": "sampleA,sampleB",
        "tree_search": True,
        "output": "/tmp/run/raxml_ng",
    })

    assert cmd == [
        "raxml-ng",
        "--msa",
        "trimmed.fasta",
        "--model",
        "GTR+G",
        "--prefix",
        "/tmp/run/raxml_ng/raxml_ng",
        "--threads",
        "8",
        "--seed",
        "42",
        "--all",
        "--bs-trees",
        "100",
        "--outgroup",
        "sampleA,sampleB",
    ]


def test_raxml_ng_supports_evaluate_mode_and_plans_outputs() -> None:
    node_class = _node_class("raxml_ng")

    cmd = node_class.render_command({
        "alignment": "alignment.phy",
        "model": "LG+G",
        "threads": 2,
        "seed": 0,
        "bootstrap_replicates": 0,
        "outgroup": "",
        "tree_search": False,
        "output": "/tmp/run/raxml_ng",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert cmd == [
        "raxml-ng",
        "--msa",
        "alignment.phy",
        "--model",
        "LG+G",
        "--prefix",
        "/tmp/run/raxml_ng/raxml_ng",
        "--threads",
        "2",
        "--evaluate",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/raxml_ng/raxml_ng.raxml.bestTree",
        "/tmp/run/raxml_ng/raxml_ng.raxml.bootstraps",
    ]


def test_raxml_ng_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["raxml-ng"] == "raxml-ng"
    assert PACKAGE_MIN_VERSIONS["raxml-ng"] == ">=1.2.2"


def test_modeltest_ng_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["modeltest_ng"]
    assert node_info["display_name"] == "ModelTest-NG"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Select best-fit substitution model")
    assert node_info["output"] == ["STRING", "JSON"]
    assert node_info["output_name"] == ["best_model", "model_stats"]
    assert node_info["required_executables"] == ["modeltest-ng"]
    assert node_info["required_conda_packages"] == ["modeltest-ng"]
    assert "modeltest-ng" in node_info["search_aliases"]
    assert "substitution model" in node_info["search_aliases"]
    assert "phylogeny" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"alignment", "datatype", "threads"}
    assert set(inputs["optional"]) == {"template", "models", "schemes", "ascertainment_bias"}


def test_modeltest_ng_renders_model_selection_command() -> None:
    node_class = _node_class("modeltest_ng")

    cmd = node_class.render_command({
        "alignment": "alignment.fasta",
        "datatype": "nt",
        "threads": 8,
        "template": "raxml",
        "models": "GTR,HKY,JC",
        "schemes": 5,
        "ascertainment_bias": True,
        "output": "/tmp/run/modeltest_ng",
    })

    assert cmd == [
        "modeltest-ng",
        "-i",
        "alignment.fasta",
        "-d",
        "nt",
        "-p",
        "8",
        "-o",
        "/tmp/run/modeltest_ng/modeltest",
        "-T",
        "raxml",
        "-m",
        "GTR,HKY,JC",
        "-s",
        "5",
        "--asc-bias",
        "&&",
        "printf",
        "'best_model\\tSee /tmp/run/modeltest_ng/modeltest.out\\n'",
        ">",
        "/tmp/run/modeltest_ng/best_model.txt",
        "&&",
        "printf",
        "'{\\n  \"modeltest_output\": \"/tmp/run/modeltest_ng/modeltest.out\",\\n  \"ranking\": \"/tmp/run/modeltest_ng/modeltest.ranking\"\\n}\\n'",
        ">",
        "/tmp/run/modeltest_ng/model_stats.json",
    ]


def test_modeltest_ng_omits_empty_optional_flags_and_plans_outputs() -> None:
    node_class = _node_class("modeltest_ng")

    cmd = node_class.render_command({
        "alignment": "proteins.phy",
        "datatype": "aa",
        "threads": 2,
        "template": "",
        "models": "",
        "schemes": 0,
        "ascertainment_bias": False,
        "output": "/tmp/run/modeltest_ng",
    })
    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert "-T" not in cmd
    assert "-m" not in cmd
    assert "-s" not in cmd
    assert "--asc-bias" not in cmd
    assert cmd[:9] == [
        "modeltest-ng",
        "-i",
        "proteins.phy",
        "-d",
        "aa",
        "-p",
        "2",
        "-o",
        "/tmp/run/modeltest_ng/modeltest",
    ]
    assert [str(path) for path in outputs] == [
        "/tmp/run/modeltest_ng/best_model.txt",
        "/tmp/run/modeltest_ng/model_stats.json",
    ]


def test_modeltest_ng_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["modeltest-ng"] == "modeltest-ng"
    assert PACKAGE_MIN_VERSIONS["modeltest-ng"] == ">=0.1.7"


def test_phylot_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["phylot"]
    assert node_info["display_name"] == "PhyloT"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Generate taxonomy-derived phylogenetic trees")
    assert node_info["output"] == ["NEWICK", "JSON"]
    assert node_info["output_name"] == ["tree", "request_metadata"]
    assert node_info["requires_external_tools"] is False
    assert node_info["required_executables"] == []
    assert node_info["required_conda_packages"] == []
    assert "taxonomy tree" in node_info["search_aliases"]
    assert "newick" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"taxa"}
    assert set(inputs["optional"]) == {
        "taxonomy_source",
        "output_format",
        "node_identifiers",
        "collapse_internal_nodes",
        "force_binary_tree",
        "interrupt_at",
        "filter_terms",
        "ignore_errors",
        "gtdb_source",
        "include_gtdb_branch_support",
        "include_gtdb_genome_ids",
        "gtdb_version",
        "output_name",
    }


@pytest.mark.asyncio
async def test_phylot_posts_ncbi_form_and_writes_tree_and_manifest(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_request_text(endpoint: str, data: dict[str, str], **_: Any) -> str:
        calls.append((endpoint, data))
        return "((Homo_sapiens,Mus_musculus)Mammalia,Escherichia_coli);\n"

    monkeypatch.setattr(module, "_phylot_request_text", fake_request_text)

    tree_path, metadata_path = await node_class().run(
        taxa="Homo sapiens, Mus musculus\nEscherichia coli",
        taxonomy_source="ncbi",
        output_format="newick",
        node_identifiers="name",
        collapse_internal_nodes=True,
        force_binary_tree=True,
        interrupt_at="genus",
        filter_terms="unclassified,environmental sample",
        ignore_errors=True,
        output_name="mammals_ecoli",
        context=_context(tmp_path, "phylot"),
    )

    assert Path(tree_path).name == "mammals_ecoli.nwk"
    assert Path(tree_path).read_text(encoding="utf-8") == "((Homo_sapiens,Mus_musculus)Mammalia,Escherichia_coli);\n"
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    assert metadata == {
        "endpoint": "treeGenerator.cgi",
        "format": "newick",
        "taxonomy_source": "ncbi",
        "taxa_count": 3,
        "tree": str(Path(tree_path)),
        "params": {
            "binary": "1",
            "collapse": "1",
            "fileName": "mammals_ecoli",
            "filter": "unclassified,environmental sample",
            "format": "newick",
            "ids": "name",
            "interrupt": "genus",
            "itol": "0",
            "itolProject": "0",
            "noerror": "1",
            "phylot": "1",
            "treeElements": "Homo sapiens\nMus musculus\nEscherichia coli",
        },
    }
    assert calls == [("treeGenerator.cgi", metadata["params"])]


@pytest.mark.asyncio
async def test_phylot_posts_gtdb_form_and_uses_format_extension(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_request_text(endpoint: str, data: dict[str, str], **_: Any) -> str:
        calls.append((endpoint, data))
        return "#NEXUS\nBegin trees;\nTree tree1 = (s__Escherichia_coli,s__Vibrio_cholerae);\nEnd;\n"

    monkeypatch.setattr(module, "_phylot_request_text", fake_request_text)

    tree_path, metadata_path = await node_class().run(
        taxa=["s__Escherichia coli", "s__Vibrio cholerae"],
        taxonomy_source="gtdb",
        output_format="nexus",
        gtdb_source="ar",
        include_gtdb_branch_support=False,
        include_gtdb_genome_ids=True,
        gtdb_version="232",
        output_name="gtdb_pair",
        context=_context(tmp_path, "phylot_gtdb"),
    )

    assert Path(tree_path).name == "gtdb_pair.nex"
    assert Path(tree_path).read_text(encoding="utf-8").startswith("#NEXUS\n")
    metadata = json.loads(Path(metadata_path).read_text(encoding="utf-8"))
    assert metadata["endpoint"] == "treeGeneratorGTD.cgi"
    assert metadata["format"] == "nexus"
    assert metadata["taxonomy_source"] == "gtdb"
    assert metadata["taxa_count"] == 2
    assert calls == [
        (
            "treeGeneratorGTD.cgi",
            {
                "boot": "0",
                "fileName": "gtdb_pair",
                "filter": "",
                "format": "nexus",
                "gtdb_version": "232",
                "gid": "1",
                "interrupt": "0",
                "itol": "0",
                "itolProject": "0",
                "noerror": "0",
                "phylotgtd": "1",
                "src": "ar",
                "treeElements": "s__Escherichia coli\ns__Vibrio cholerae",
            },
        )
    ]


def test_phylot_plans_outputs_from_output_name_and_format() -> None:
    node_class = _node_class("phylot")

    default_outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")
    nexus_outputs = node_class.PLAN_OUTPUTS(
        {"output_name": "gtdb pair", "output_format": "nexus"},
        "/tmp/run",
    )

    assert [str(path) for path in default_outputs] == [
        "/tmp/run/phylot/phylot_tree.nwk",
        "/tmp/run/phylot/request_metadata.json",
    ]
    assert [str(path) for path in nexus_outputs] == [
        "/tmp/run/phylot/gtdb_pair.nex",
        "/tmp/run/phylot/request_metadata.json",
    ]


@pytest.mark.asyncio
async def test_phylot_rejects_html_error_response_without_writing_outputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    node_class = _node_class("phylot")
    module = importlib.import_module(node_class.__module__)

    async def fake_request_text(endpoint: str, data: dict[str, str], **_: Any) -> str:
        return """
<!DOCTYPE html>
<html lang="en">
<head><title>phyloT: Invalid IDs</title></head>
<body><h2>Error: Invalid IDs</h2><p>DefinitelyNotATaxon</p></body>
</html>
"""

    monkeypatch.setattr(module, "_phylot_request_text", fake_request_text)
    context = _context(tmp_path, "phylot_error")

    with pytest.raises(RuntimeError, match="Invalid IDs"):
        await node_class().run(
            taxa="DefinitelyNotATaxon,StillNotATaxon",
            context=context,
        )

    assert not (context.node_dir / "phylot").exists()


@pytest.mark.asyncio
async def test_phylot_rejects_empty_taxa(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="at least two taxa or one subtree"):
        await _node_class("phylot")().run(
            taxa="Homo sapiens",
            context=_context(tmp_path, "phylot_empty"),
        )


def test_phylogenetic_tree_builder_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["phylogenetic_tree_builder"]
    assert node_info["display_name"] == "Phylo Tree Builder"
    assert node_info["category"] == "phylogeny"
    assert node_info["description"].startswith("Build phylogenetic trees using multiple methods")
    assert node_info["output"] == ["NEWICK", "JSON"]
    assert node_info["output_name"] == ["consensus_tree", "individual_trees"]
    assert node_info["requires_external_tools"] is False
    assert node_info["required_conda_packages"] == ["biopython"]
    assert "consensus tree" in node_info["search_aliases"]
    assert "newick" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"tree_files"}
    assert set(inputs["optional"]) == {"methods", "consensus_method"}


@pytest.mark.asyncio
async def test_phylogenetic_tree_builder_writes_consensus_and_manifest(tmp_path: Path) -> None:
    iqtree = tmp_path / "iqtree.treefile"
    raxml = tmp_path / "raxml.bestTree"
    fasttree = tmp_path / "fasttree.nwk"
    iqtree.write_text("((A:0.1,B:0.2):0.3,C:0.4);\n", encoding="utf-8")
    raxml.write_text("((A:0.1,B:0.2):0.3,C:0.4);\n", encoding="utf-8")
    fasttree.write_text("(A:0.1,(B:0.2,C:0.4):0.3);\n", encoding="utf-8")

    consensus_path, manifest_path = await _node_class("phylogenetic_tree_builder")().run(
        tree_files="\n".join([str(iqtree), str(raxml), str(fasttree)]),
        methods="iqtree,raxml_ng,fasttree",
        consensus_method="majority",
        context=_context(tmp_path, "phylo_builder"),
    )

    assert Path(consensus_path).name == "consensus_tree.nwk"
    assert Path(consensus_path).read_text(encoding="utf-8") == "((A:0.10000,B:0.20000):0.30000,C:0.40000):0.00000;\n"

    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    assert manifest["consensus_method"] == "majority"
    assert manifest["selected_tree_index"] == 0
    assert manifest["tree_count"] == 3
    assert [entry["method"] for entry in manifest["trees"]] == ["iqtree", "raxml_ng", "fasttree"]
    assert manifest["trees"][0]["support_count"] == 2


@pytest.mark.asyncio
async def test_phylogenetic_tree_builder_rejects_missing_tree_files(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="At least one tree file is required"):
        await _node_class("phylogenetic_tree_builder")().run(
            tree_files="",
            methods="",
            consensus_method="first",
            context=_context(tmp_path, "phylo_builder"),
        )
