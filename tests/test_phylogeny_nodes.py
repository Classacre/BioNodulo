from __future__ import annotations

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


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
