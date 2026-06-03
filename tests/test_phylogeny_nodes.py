from __future__ import annotations

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
