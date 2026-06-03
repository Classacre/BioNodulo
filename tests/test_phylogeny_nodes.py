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
