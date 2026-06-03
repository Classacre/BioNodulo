from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_maxquant_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["maxquant"]
    assert node_info["display_name"] == "MaxQuant"
    assert node_info["category"] == "proteomics"
    assert node_info["description"].startswith("Quantitative proteomics")
    assert node_info["output"] == ["DIRECTORY", "CSV"]
    assert node_info["output_name"] == ["results_dir", "protein_groups"]
    assert node_info["required_executables"] == ["MaxQuantCmd.exe"]
    assert node_info["required_conda_packages"] == ["maxquant"]
    assert node_info["experimental"] is True
    assert "lfq" in node_info["search_aliases"]
    assert "protein quantification" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"raw_files", "fasta_db"}
    assert set(inputs["optional"]) == {
        "lfq",
        "min_peptide_length",
        "use_mono",
        "match_between_runs",
        "peptide_fdr",
        "protein_fdr",
    }


def test_maxquant_renders_mono_command_with_xml_generation_script() -> None:
    node_class = _node_class("maxquant")

    cmd = node_class.render_command({
        "raw_files": ["sample1.raw", "sample2.mzML"],
        "fasta_db": "proteome.fa",
        "lfq": True,
        "min_peptide_length": 8,
        "use_mono": True,
        "match_between_runs": False,
        "peptide_fdr": 0.02,
        "protein_fdr": 0.03,
        "output": "/tmp/run/maxquant",
    })

    assert cmd[0:2] == ["python", "-c"]
    assert cmd[3:] == ["&&", "mono", "MaxQuantCmd.exe", "/tmp/run/maxquant/mqpar.xml"]

    script = cmd[2]
    assert "xml.etree.ElementTree as ET" in script
    assert "ET.Element('MaxQuantParams')" in script
    assert "ET.SubElement(root, 'fastaFilePath').text = 'proteome.fa'" in script
    assert "for rf in ['sample1.raw', 'sample2.mzML']:" in script
    assert "ET.SubElement(root, 'configFolder').text = '/tmp/run/maxquant'" in script
    assert "ET.SubElement(root, 'lfqMode').text = 'true'" in script
    assert "ET.SubElement(root, 'minPeptideLen').text = '8'" in script
    assert "ET.SubElement(root, 'matchBetweenRuns').text = 'false'" in script
    assert "ET.SubElement(root, 'peptideFdr').text = '0.02'" in script
    assert "ET.SubElement(root, 'proteinFdr').text = '0.03'" in script
    assert "ET.ElementTree(root).write('/tmp/run/maxquant/mqpar.xml'" in script


def test_maxquant_accepts_single_raw_file_and_omits_mono() -> None:
    node_class = _node_class("maxquant")

    cmd = node_class.render_command({
        "raw_files": "sample.raw",
        "fasta_db": "proteome.fa",
        "lfq": False,
        "use_mono": False,
        "output": "/tmp/run/maxquant",
    })

    assert cmd[3:] == ["&&", "MaxQuantCmd.exe", "/tmp/run/maxquant/mqpar.xml"]
    assert "for rf in ['sample.raw']:" in cmd[2]
    assert "ET.SubElement(root, 'lfqMode').text = 'false'" in cmd[2]


def test_maxquant_plans_outputs() -> None:
    node_class = _node_class("maxquant")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/maxquant/results_dir",
        "/tmp/run/maxquant/protein_groups.csv",
    ]


def test_maxquant_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["MaxQuantCmd.exe"] == "maxquant"
    assert EXECUTABLE_TO_CONDA_PACKAGE["mono"] == "mono"
    assert PACKAGE_MIN_VERSIONS["maxquant"] == ">=2.6.0"


def test_msfragger_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["msfragger"]
    assert node_info["display_name"] == "MSFragger"
    assert node_info["category"] == "proteomics"
    assert node_info["description"].startswith("Ultra-fast peptide identification")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["pepxml"]
    assert node_info["required_executables"] == ["msfragger"]
    assert node_info["required_conda_packages"] == ["msfragger"]
    assert node_info["experimental"] is True
    assert "fragpipe" in node_info["search_aliases"]
    assert "peptide identification" in node_info["search_aliases"]
    assert "database search" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"raw_files", "fasta_db", "threads"}
    assert set(inputs["optional"]) == {
        "open_search",
        "prec_tol_low",
        "prec_tol_high",
        "prec_tol_units",
        "frag_tol",
        "frag_tol_units",
        "calibrate_mass",
    }


def test_msfragger_renders_command_and_closed_search_params(tmp_path: Path) -> None:
    node_class = _node_class("msfragger")
    output_dir = tmp_path / "msfragger"

    cmd = node_class.render_command({
        "raw_files": ["sample1.mzML", "sample2.raw"],
        "fasta_db": "target_decoy.fa",
        "threads": 8,
        "open_search": False,
        "prec_tol_low": 10,
        "prec_tol_high": 25,
        "prec_tol_units": 1,
        "frag_tol": 0.02,
        "frag_tol_units": 0,
        "calibrate_mass": "iterative",
        "output": str(output_dir),
    })

    params_file = output_dir / "fragger.params"
    assert cmd == ["msfragger", str(params_file), "sample1.mzML", "sample2.raw"]
    assert params_file.read_text() == (
        "database_name = target_decoy.fa\n"
        "num_threads = 8\n"
        "precursor_mass_lower = -10\n"
        "precursor_mass_upper = 25\n"
        "precursor_mass_units = 1\n"
        "fragment_mass_tolerance = 0.02\n"
        "fragment_mass_units = 0\n"
        "calibrate_mass = iterative\n"
        "variable_mod_01 = 15.99490 M\n"
        "variable_mod_02 = 42.01060 [^\n"
        "output_format = pepxml\n"
    )


def test_msfragger_open_search_omits_default_variable_mods(tmp_path: Path) -> None:
    node_class = _node_class("msfragger")
    output_dir = tmp_path / "msfragger"

    cmd = node_class.render_command({
        "raw_files": "sample.mzML",
        "fasta_db": "target_decoy.fa",
        "threads": 4,
        "open_search": True,
        "output": str(output_dir),
    })

    params_text = (output_dir / "fragger.params").read_text()
    assert cmd == ["msfragger", str(output_dir / "fragger.params"), "sample.mzML"]
    assert "variable_mod_01" not in params_text
    assert "variable_mod_02" not in params_text
    assert "precursor_mass_lower = -20\n" in params_text
    assert "precursor_mass_upper = 20\n" in params_text
    assert "calibrate_mass = none\n" in params_text


def test_msfragger_plans_pepxml_output() -> None:
    node_class = _node_class("msfragger")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == ["/tmp/run/msfragger/pepxml.pepXML"]


def test_msfragger_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["msfragger"] == "msfragger"
    assert PACKAGE_MIN_VERSIONS["msfragger"] == ">=4.0"
