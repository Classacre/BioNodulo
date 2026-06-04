from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_sbol_design_import_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["sbol_design_import"]
    assert node_info["display_name"] == "SBOL Design Import"
    assert node_info["category"] == "synthetic_biology"
    assert node_info["description"].startswith("Import and summarize")
    assert node_info["output"] == ["SBOL", "JSON"]
    assert node_info["output_name"] == ["normalized_sbol", "summary"]
    assert node_info["required_executables"] == ["python"]
    assert node_info["required_conda_packages"] == ["pysbol3"]
    assert "sbol" in node_info["search_aliases"]
    assert "synthetic biology" in node_info["search_aliases"]
    assert "biocad" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"sbol_file"}
    assert set(inputs["optional"]) == {"namespace", "validate", "output_format", "output_name"}


def test_sbol_design_import_writes_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("sbol_design_import")
    output_dir = tmp_path / "sbol_design_import"

    cmd = node_class.render_command({
        "sbol_file": "design.xml",
        "namespace": "https://example.org/designs",
        "validate": True,
        "output_format": "rdfxml",
        "output_name": "toggle switch",
        "output": str(output_dir),
    })

    script_file = output_dir / "sbol_design_import.py"
    assert cmd == ["python", str(script_file)]
    script = script_file.read_text()
    assert "import sbol3" in script
    assert "doc = sbol3.Document()" in script
    assert "sbol3.set_namespace('https://example.org/designs')" in script
    assert "doc.read('design.xml')" in script
    assert "report = doc.validate()" in script
    assert f"doc.write('{output_dir}/toggle_switch.xml', file_format='rdfxml')" in script
    assert f"summary_path = Path('{output_dir}/toggle_switch.summary.json')" in script
    assert "\"components\"" in script
    assert "\"sequences\"" in script
    assert "\"interactions\"" in script


def test_sbol_design_import_accepts_default_output_name_and_skips_validation(tmp_path: Path) -> None:
    node_class = _node_class("sbol_design_import")
    output_dir = tmp_path / "sbol_design_import"

    cmd = node_class.render_command({
        "sbol_file": "/data/plasmid_design.nt",
        "namespace": "",
        "validate": False,
        "output_format": "ntriples",
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == ["python", str(output_dir / "sbol_design_import.py")]
    script = (output_dir / "sbol_design_import.py").read_text()
    assert "sbol3.set_namespace" not in script
    assert "report = doc.validate()" not in script
    assert "doc.read('/data/plasmid_design.nt')" in script
    assert f"doc.write('{output_dir}/plasmid_design.nt', file_format='ntriples')" in script
    assert f"summary_path = Path('{output_dir}/plasmid_design.summary.json')" in script


def test_sbol_design_import_plans_outputs() -> None:
    node_class = _node_class("sbol_design_import")

    outputs = node_class.PLAN_OUTPUTS({"sbol_file": "toggle.xml", "output_name": "toggle switch"}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/sbol_design_import/toggle_switch.xml",
        "/tmp/run/sbol_design_import/toggle_switch.summary.json",
    ]


def test_sbol_design_import_environment_metadata_is_declared() -> None:
    assert PACKAGE_MIN_VERSIONS["pysbol3"] == ">=1.1"
