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


def test_percolator_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["percolator"]
    assert node_info["display_name"] == "Percolator"
    assert node_info["category"] == "proteomics"
    assert node_info["description"].startswith("Semi-supervised ML")
    assert node_info["output"] == ["TSV", "TSV"]
    assert node_info["output_name"] == ["percolator_psms", "percolator_proteins"]
    assert node_info["required_executables"] == ["percolator"]
    assert node_info["required_conda_packages"] == ["percolator"]
    assert "psm validation" in node_info["search_aliases"]
    assert "fdr" in node_info["search_aliases"]
    assert "peptide spectrum match" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"pin_file", "fasta_db"}
    assert set(inputs["optional"]) == {"decoy_prefix", "fdr_psm", "fdr_protein", "enzyme"}


def test_percolator_renders_command_with_fdr_and_protein_options() -> None:
    node_class = _node_class("percolator")

    cmd = node_class.render_command({
        "pin_file": "search.pin",
        "fasta_db": "target_decoy.fa",
        "decoy_prefix": "DECOY_",
        "fdr_psm": 0.01,
        "fdr_protein": 0.02,
        "enzyme": "trypsin",
        "output": "/tmp/run/percolator",
    })

    assert cmd == [
        "percolator",
        "search.pin",
        "-X",
        "/tmp/run/percolator/percolator_psms.tsv",
        "--protein-decoy-pattern",
        "DECOY_",
        "--decoy-xml-output",
        "--no-split-large-instances",
        "--post-processing-tdc",
        "--fdr",
        "0.01",
        "--picked-protein",
        "target_decoy.fa",
        "--protein-fdr",
        "0.02",
        "--enzyme",
        "trypsin",
        "-l",
        "/tmp/run/percolator/percolator_proteins.tsv",
    ]


def test_percolator_omits_disabled_optional_flags() -> None:
    node_class = _node_class("percolator")

    cmd = node_class.render_command({
        "pin_file": "search.pin",
        "fasta_db": "target_decoy.fa",
        "decoy_prefix": "decoy",
        "fdr_psm": 0,
        "fdr_protein": 0,
        "enzyme": "",
        "output": "/tmp/run/percolator",
    })

    assert cmd == [
        "percolator",
        "search.pin",
        "-X",
        "/tmp/run/percolator/percolator_psms.tsv",
        "--protein-decoy-pattern",
        "decoy",
        "--decoy-xml-output",
        "--no-split-large-instances",
        "-l",
        "/tmp/run/percolator/percolator_proteins.tsv",
    ]


def test_percolator_plans_outputs() -> None:
    node_class = _node_class("percolator")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/percolator/percolator_psms.tsv",
        "/tmp/run/percolator/percolator_proteins.tsv",
    ]


def test_percolator_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["percolator"] == "percolator"
    assert PACKAGE_MIN_VERSIONS["percolator"] == ">=3.7"


def test_openms_feature_finder_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["openms_feature_finder"]
    assert node_info["display_name"] == "OpenMS FeatureFinder"
    assert node_info["category"] == "proteomics"
    assert node_info["description"].startswith("Detect peptide features")
    assert node_info["output"] == ["FILE"]
    assert node_info["output_name"] == ["feature_xml"]
    assert node_info["required_executables"] == ["FeatureFinderCentroided"]
    assert node_info["required_conda_packages"] == ["openms"]
    assert "openms" in node_info["search_aliases"]
    assert "feature finder" in node_info["search_aliases"]
    assert "lc-ms" in node_info["search_aliases"]
    assert "peptide feature" in node_info["search_aliases"]
    assert "topp" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"mzml_file"}
    assert set(inputs["optional"]) == {"ini_file", "min_peak_width", "signal_to_noise", "threads"}


def test_openms_feature_finder_renders_default_algorithm_command() -> None:
    node_class = _node_class("openms_feature_finder")

    cmd = node_class.render_command({
        "mzml_file": "sample.centroided.mzML",
        "min_peak_width": 0.3,
        "signal_to_noise": 5.0,
        "threads": 8,
        "output": "/tmp/run/openms_feature_finder",
    })

    assert cmd == [
        "FeatureFinderCentroided",
        "-in",
        "sample.centroided.mzML",
        "-out",
        "/tmp/run/openms_feature_finder/feature_xml.featureXML",
        "-algorithm:min_peak_width",
        "0.3",
        "-algorithm:signal_to_noise",
        "5.0",
        "-threads",
        "8",
    ]


def test_openms_feature_finder_uses_ini_file_instead_of_algorithm_flags() -> None:
    node_class = _node_class("openms_feature_finder")

    cmd = node_class.render_command({
        "mzml_file": "sample.centroided.mzML",
        "ini_file": "feature_finder.ini",
        "min_peak_width": 0.3,
        "signal_to_noise": 5.0,
        "threads": 4,
        "output": "/tmp/run/openms_feature_finder",
    })

    assert cmd == [
        "FeatureFinderCentroided",
        "-in",
        "sample.centroided.mzML",
        "-out",
        "/tmp/run/openms_feature_finder/feature_xml.featureXML",
        "-ini",
        "feature_finder.ini",
        "-threads",
        "4",
    ]


def test_openms_feature_finder_plans_featurexml_output() -> None:
    node_class = _node_class("openms_feature_finder")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/openms_feature_finder/feature_xml.featureXML",
    ]


def test_openms_feature_finder_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["FeatureFinderCentroided"] == "openms"
    assert PACKAGE_MIN_VERSIONS["openms"] == ">=3.2"


def test_dia_nn_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["dia_nn"]
    assert node_info["display_name"] == "DIA-NN"
    assert node_info["category"] == "proteomics"
    assert node_info["description"].startswith("Analyze DIA")
    assert node_info["output"] == ["TSV", "JSON"]
    assert node_info["output_name"] == ["report", "stats"]
    assert node_info["required_executables"] == ["diann"]
    assert node_info["required_conda_packages"] == ["diann"]
    assert "dia" in node_info["search_aliases"]
    assert "data independent acquisition" in node_info["search_aliases"]
    assert "quantification" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"raw_files", "library", "fasta"}
    assert set(inputs["optional"]) == {"threads", "qvalue", "mass_accuracy", "use_predictor"}


def test_dia_nn_renders_batch_analysis_command_with_optional_flags() -> None:
    node_class = _node_class("dia_nn")

    cmd = node_class.render_command({
        "raw_files": ["run1.mzML", "run2.mzML"],
        "library": "library.tsv",
        "fasta": "proteome.fa",
        "threads": 12,
        "qvalue": 0.005,
        "mass_accuracy": 15,
        "use_predictor": True,
        "output": "/tmp/run/dia_nn",
    })

    assert cmd == [
        "diann",
        "--lib",
        "library.tsv",
        "--fasta",
        "proteome.fa",
        "--out",
        "/tmp/run/dia_nn/report.tsv",
        "--threads",
        "12",
        "--qvalue",
        "0.005",
        "--mass-acc",
        "15",
        "--predictor",
        "--f",
        "run1.mzML",
        "--f",
        "run2.mzML",
        "&&",
        "python",
        "-c",
        "import csv, json, sys; rows=list(csv.DictReader(open(sys.argv[1]), delimiter='\\t')); "
        "json.dump({'rows': len(rows), 'columns': list(rows[0]) if rows else []}, open(sys.argv[2], 'w'))",
        "/tmp/run/dia_nn/report.tsv",
        "/tmp/run/dia_nn/stats.json",
    ]


def test_dia_nn_accepts_single_raw_file_and_omits_disabled_predictor() -> None:
    node_class = _node_class("dia_nn")

    cmd = node_class.render_command({
        "raw_files": "run1.mzML",
        "library": "library.tsv",
        "fasta": "proteome.fa",
        "threads": 4,
        "qvalue": 0.01,
        "mass_accuracy": 0,
        "use_predictor": False,
        "output": "/tmp/run/dia_nn",
    })

    assert "--predictor" not in cmd
    assert "--mass-acc" not in cmd
    assert cmd[0:15] == [
        "diann",
        "--lib",
        "library.tsv",
        "--fasta",
        "proteome.fa",
        "--out",
        "/tmp/run/dia_nn/report.tsv",
        "--threads",
        "4",
        "--qvalue",
        "0.01",
        "--f",
        "run1.mzML",
        "&&",
        "python",
    ]


def test_dia_nn_plans_outputs() -> None:
    node_class = _node_class("dia_nn")

    outputs = node_class.PLAN_OUTPUTS({}, "/tmp/run")

    assert [str(path) for path in outputs] == [
        "/tmp/run/dia_nn/report.tsv",
        "/tmp/run/dia_nn/stats.json",
    ]


def test_dia_nn_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["diann"] == "diann"
    assert PACKAGE_MIN_VERSIONS["diann"] == ">=1.8"
