from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.proteomics_family.comet import CometNode
from bionodulo.nodes.builtin.proteomics_family.dia_nn import DIANNAliasNode, DIANNNode
from bionodulo.nodes.builtin.proteomics_family.fragpipe import FragPipeWorkflowNode
from bionodulo.nodes.builtin.proteomics_family.maxquant import MaxQuantNode
from bionodulo.nodes.builtin.proteomics_family.msfragger import MSFraggerNode
from bionodulo.nodes.builtin.proteomics_family.openms_feature_finder import (
    OpenMSFeatureFinderNode,
    OpenMSFeatureNode,
)
from bionodulo.nodes.registry import NodeRegistry


def _write(path: Path, text: str = "fixture\n") -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def _maxquant_template(path: Path, version: str = "2.0.3.0") -> Path:
    return _write(
        path,
        f"""<?xml version="1.0"?>
<MaxQuantParams>
  <fastaFiles><FastaFileInfo><fastaFilePath>old.fasta</fastaFilePath><identifierParseRule>&gt;([^ ]*)</identifierParseRule></FastaFileInfo></fastaFiles>
  <maxQuantVersion>{version}</maxQuantVersion>
  <numThreads>1</numThreads>
  <filePaths><string>old.raw</string></filePaths>
  <experiments><string>old</string></experiments>
  <fractions><short>32767</short></fractions>
  <ptms><boolean>False</boolean></ptms>
  <paramGroupIndices><int>0</int></paramGroupIndices>
  <referenceChannel><string /></referenceChannel>
  <parameterGroups><parameterGroup><minPepLen>7</minPepLen></parameterGroup></parameterGroups>
</MaxQuantParams>
""",
    )


def _msfragger_template(path: Path, version: str = "4.2") -> Path:
    return _write(
        path,
        f"""# MSFragger-{version}
database_name = old.fasta
num_threads = 0
precursor_mass_lower = -20
precursor_mass_upper = 20
precursor_mass_units = 1
fragment_mass_tolerance = 20
fragment_mass_units = 1
calibrate_mass = 2
output_format = pepxml_pin
""",
    )


def _comet_template(path: Path, header: str = "# comet_version 2024.01 rev. 1") -> Path:
    return _write(
        path,
        f"""{header}
database_name = old.fasta
decoy_search = 0
num_threads = 0
peptide_mass_tolerance_lower = -20
peptide_mass_tolerance_upper = 20
peptide_mass_units = 2
fragment_bin_tol = 0.02
fragment_bin_offset = 0.0
search_enzyme_number = 1
allowed_missed_cleavage = 2
output_txtfile = 0
output_pepxmlfile = 1
[COMET_ENZYME_INFO]
0. No_enzyme 0 - -
1. Trypsin 1 KR P
""",
    )


def test_remaining_proteomics_ids_are_focused_and_source_pinned() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    expected = {
        "maxquant": MaxQuantNode,
        "msfragger": MSFraggerNode,
        "fragpipe": FragPipeWorkflowNode,
        "comet": CometNode,
        "openms_feature_finder": OpenMSFeatureFinderNode,
        "openms_feature": OpenMSFeatureNode,
        "dia_nn": DIANNNode,
        "diann": DIANNAliasNode,
    }
    authorities = {
        "maxquant": ("2.0.3.0", "c0fc669c7b8eb762ae6d2ad8753b941951e139c0"),
        "msfragger": ("4.2", "8a143152285d36e2958e6e3013017fa4ca62fdcc"),
        "fragpipe": ("24.0", "c2f256cb6a6a28a89a8b4d4da2e0e8eaee1ef3a5"),
        "comet": ("2024.01.1", "b23621001caeb758c1727bc1dafd7ec1f9b2bd15"),
        "openms_feature_finder": ("3.5.0", "c49149d47d6fcc76d1271d87d3a7fad15d2219de"),
        "openms_feature": ("3.5.0", "c49149d47d6fcc76d1271d87d3a7fad15d2219de"),
        "dia_nn": ("1.9.2", "af0e13d9eb3738c338dbbc4c61e6eb1d67d8bed8"),
        "diann": ("1.9.2", "af0e13d9eb3738c338dbbc4c61e6eb1d67d8bed8"),
    }
    for node_id, node_class in expected.items():
        assert registry.get(node_id) is node_class
        assert (node_class.VERSION, node_class.GIT_COMMIT) == authorities[node_id]
        assert node_class.DOCUMENTATION_URL.startswith("https://")


def test_maxquant_rewrites_version_matched_mqpar_and_native_outputs(tmp_path: Path) -> None:
    raw1 = _write(tmp_path / "run1.mzML")
    raw2 = _write(tmp_path / "run2.raw")
    fasta = _write(tmp_path / "proteome.fasta", ">P1\nMPEPTIDE\n")
    template = _maxquant_template(tmp_path / "mqpar-template.xml")
    inputs = {
        "raw_files": [raw1, raw2],
        "fasta_db": fasta,
        "mqpar_template": template,
        "threads": 6,
        "output": str(tmp_path / "run" / "maxquant"),
    }
    outputs = MaxQuantNode.PLAN_OUTPUTS(inputs, tmp_path / "run")
    MaxQuantNode.PREPARE_EXECUTION(inputs, outputs)

    root = ET.parse(outputs[2]).getroot()
    file_paths = root.find("filePaths")
    experiments = root.find("experiments")
    assert file_paths is not None
    assert experiments is not None
    assert [item.text for item in file_paths] == [
        str((outputs[0].parent / "inputs" / raw1.name).absolute()),
        str((outputs[0].parent / "inputs" / raw2.name).absolute()),
    ]
    assert [item.text for item in experiments] == ["run1", "run2"]
    assert root.findtext("fastaFiles/FastaFileInfo/fastaFilePath") == str(
        (outputs[0].parent / "inputs" / fasta.name).absolute()
    )
    assert root.findtext("numThreads") == "6"
    assert MaxQuantNode.render_command(inputs) == ["maxquant", str(outputs[2])]
    assert outputs[1] == tmp_path / "run" / "maxquant" / "combined" / "txt" / "proteinGroups.txt"


def test_maxquant_rejects_wrong_mqpar_version(tmp_path: Path) -> None:
    inputs = {
        "raw_files": [_write(tmp_path / "run.mzML")],
        "fasta_db": _write(tmp_path / "db.fasta"),
        "mqpar_template": _maxquant_template(tmp_path / "mqpar.xml", "2.6.3.0"),
    }
    outputs = MaxQuantNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    with pytest.raises(ValueError, match="mqpar version must be 2.0.3.0"):
        MaxQuantNode.PREPARE_EXECUTION(inputs, outputs)


def test_msfragger_prepares_complete_template_and_native_outputs(tmp_path: Path) -> None:
    spectrum = _write(tmp_path / "sample.mzML")
    fasta = _write(tmp_path / "db.fasta")
    inputs = {
        "spectra_file": spectrum,
        "fasta_db": fasta,
        "params_template": _msfragger_template(tmp_path / "closed.params"),
        "license_key": "test-key",
        "threads": 8,
        "precursor_mass_lower": -150,
        "precursor_mass_upper": 500,
        "precursor_mass_units": "Da",
        "fragment_mass_tolerance": 0.02,
        "fragment_mass_units": "Da",
        "calibrate_mass": 4,
        "output": str(tmp_path / "out" / "msfragger"),
    }
    outputs = MSFraggerNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    MSFraggerNode.PREPARE_EXECUTION(inputs, outputs)

    params = outputs[2].read_text(encoding="utf-8")
    assert "database_name = " + str(fasta.resolve()) in params
    assert "precursor_mass_units = 0" in params
    assert "fragment_mass_units = 0" in params
    assert "calibrate_mass = 4" in params
    assert "output_format = pepxml_pin" in params
    assert MSFraggerNode.render_command(inputs) == [
        "msfragger",
        "--key",
        "test-key",
        str(outputs[2]),
        str(outputs[0].parent / spectrum.name),
    ]
    assert [path.name for path in outputs] == ["sample.pepXML", "sample.pin", "fragger.params"]


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"license_key": ""}, "license_key"),
        ({"precursor_mass_lower": 10, "precursor_mass_upper": -10}, "must not exceed"),
        ({"calibrate_mass": 3}, "0, 1, 2, 4"),
    ],
)
def test_msfragger_rejects_invalid_contract_values(updates: dict[str, object], message: str) -> None:
    inputs = {
        "spectra_file": "sample.mzML",
        "fasta_db": "db.fasta",
        "params_template": "fragger.params",
        "license_key": "key",
        **updates,
    }
    assert message in str(MSFraggerNode.VALIDATE_INPUTS(inputs))


def test_fragpipe_stages_manifest_database_and_license_flags(tmp_path: Path) -> None:
    raw1 = _write(tmp_path / "run1.mzML")
    raw2 = _write(tmp_path / "run2.raw")
    manifest = _write(
        tmp_path / "samples.manifest",
        "run1.mzML\tE1\t1\tDDA+\nrun2.raw\tE2\t2\tdia-lib\n",
    )
    workflow = _write(tmp_path / "basic.workflow", "# Workflow\ndatabase.db-path=old.fasta\n")
    fasta = _write(tmp_path / "db.fasta")
    inputs = {
        "raw_files": [raw1, raw2],
        "manifest_file": manifest,
        "workflow_file": workflow,
        "fasta_db": fasta,
        "msfragger_key": "fragger-key",
        "ionquant_key": "ion-key",
        "threads": 12,
        "memory_gb": 24,
        "output": str(tmp_path / "out" / "fragpipe"),
    }
    outputs = FragPipeWorkflowNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    FragPipeWorkflowNode.PREPARE_EXECUTION(inputs, outputs)

    prepared_manifest = Path(inputs["_fragpipe_manifest"])
    lines = prepared_manifest.read_text(encoding="utf-8").splitlines()
    assert lines[0].startswith(str(outputs[0].parent / "scans" / "run1.mzML"))
    assert lines[0].endswith("\tDDA+")
    assert lines[1].endswith("\tDIA-Lib")
    prepared_workflow = Path(inputs["_fragpipe_workflow"]).read_text(encoding="utf-8")
    assert f"database.db-path={outputs[0].parent / 'database.fasta'}" in prepared_workflow
    assert FragPipeWorkflowNode.render_command(inputs) == [
        "fragpipe",
        "--msfragger_key",
        "fragger-key",
        "--ionquant_key",
        "ion-key",
        "--headless",
        "--threads",
        "12",
        "--ram",
        "24",
        "--workflow",
        str(inputs["_fragpipe_workflow"]),
        "--manifest",
        str(inputs["_fragpipe_manifest"]),
        "--workdir",
        str(outputs[0]),
    ]


def test_fragpipe_omits_optional_resource_flags_and_rejects_unknown_data_type(tmp_path: Path) -> None:
    inputs = {
        "raw_files": [_write(tmp_path / "run.mzML")],
        "manifest_file": _write(tmp_path / "manifest.tsv", "run.mzML\tE1\t1\tDIA_LIBRARY\n"),
        "workflow_file": _write(tmp_path / "workflow.txt"),
        "fasta_db": _write(tmp_path / "db.fasta"),
        "msfragger_key": "key",
        "ionquant_key": "key",
        "output": str(tmp_path / "out" / "fragpipe"),
    }
    command = FragPipeWorkflowNode.render_command(inputs)
    assert "--threads" not in command
    assert "--ram" not in command
    assert "--diatracer_key" not in command

    outputs = FragPipeWorkflowNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    with pytest.raises(ValueError, match=r"DDA\+"):
        FragPipeWorkflowNode.PREPARE_EXECUTION(inputs, outputs)


def test_fragpipe_rejects_manifest_not_matching_staged_inputs(tmp_path: Path) -> None:
    inputs = {
        "raw_files": [_write(tmp_path / "run.mzML")],
        "manifest_file": _write(tmp_path / "manifest.tsv", "other.mzML\tE1\t1\tDDA\n"),
        "workflow_file": _write(tmp_path / "workflow.txt"),
        "fasta_db": _write(tmp_path / "db.fasta"),
        "msfragger_key": "key",
        "ionquant_key": "key",
    }
    outputs = FragPipeWorkflowNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    with pytest.raises(ValueError, match="exactly match"):
        FragPipeWorkflowNode.PREPARE_EXECUTION(inputs, outputs)


def test_comet_rewrites_template_and_concatenates_cli_options(tmp_path: Path) -> None:
    spectrum = _write(tmp_path / "sample.mzML")
    fasta = _write(tmp_path / "db.fasta")
    inputs = {
        "spectra_file": spectrum,
        "fasta_db": fasta,
        "params_template": _comet_template(tmp_path / "comet-template.params"),
        "threads": 10,
        "allowed_missed_cleavage": 3,
        "output": str(tmp_path / "out" / "comet"),
    }
    outputs = CometNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    CometNode.PREPARE_EXECUTION(inputs, outputs)

    params = outputs[2].read_text(encoding="utf-8")
    assert params.startswith(CometNode.PARAMETER_HEADER)
    assert "num_threads = 10" in params
    assert "allowed_missed_cleavage = 3" in params
    assert "output_txtfile = 1" in params
    assert CometNode.render_command(inputs) == [
        "comet",
        f"-P{outputs[2]}",
        f"-D{fasta}",
        f"-N{outputs[0].parent / 'comet'}",
        str(spectrum),
    ]


def test_comet_rejects_wrong_parameter_header(tmp_path: Path) -> None:
    inputs = {
        "spectra_file": _write(tmp_path / "sample.mzML"),
        "fasta_db": _write(tmp_path / "db.fasta"),
        "params_template": _comet_template(tmp_path / "params", "# comet_version 2026.01 rev. 1"),
    }
    outputs = CometNode.PLAN_OUTPUTS(inputs, tmp_path / "out")
    with pytest.raises(ValueError, match="2024.01 rev. 1"):
        CometNode.PREPARE_EXECUTION(inputs, outputs)


def test_comet_rejects_unexposed_separate_decoy_outputs() -> None:
    validation = CometNode.VALIDATE_INPUTS(
        {
            "spectra_file": "sample.mzML",
            "fasta_db": "db.fasta",
            "params_template": "comet.params",
            "decoy_search": 2,
        }
    )

    assert validation == "Input 'decoy_search' must be at most 1"


def test_openms_uses_native_feature_finder_parameters() -> None:
    command = OpenMSFeatureFinderNode.render_command(
        {
            "mzml_file": "sample.mzML",
            "seeds_file": "seeds.featureXML",
            "mass_trace_mz_tolerance": 0.004,
            "isotope_mz_tolerance": 0.005,
            "min_spectra": 12,
            "force_profile_input": True,
            "faims_merge_features": False,
            "threads": 6,
            "output": "/work/openms_feature_finder",
        }
    )
    assert command == [
        "FeatureFinderCentroided",
        "-in",
        "sample.mzML",
        "-out",
        "/work/openms_feature_finder/feature_xml.featureXML",
        "-seeds",
        "seeds.featureXML",
        "-algorithm:mass_trace:mz_tolerance",
        "0.004",
        "-algorithm:isotopic_pattern:mz_tolerance",
        "0.005",
        "-algorithm:mass_trace:min_spectra",
        "12",
        "-force",
        "-faims_merge_features",
        "false",
        "-threads",
        "6",
    ]
    assert "-algorithm:min_peak_width" not in command
    assert "-algorithm:signal_to_noise" not in command


def test_openms_alias_preserves_id_specific_output_directory(tmp_path: Path) -> None:
    assert issubclass(OpenMSFeatureNode, OpenMSFeatureFinderNode)
    assert OpenMSFeatureNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "openms_feature" / "feature_xml.featureXML"
    ]


def test_diann_uses_native_report_and_stats_without_synthetic_postprocessing() -> None:
    inputs = {
        "raw_files": ["run1.mzML", "run2.mzML"],
        "library": "library.tsv",
        "fasta": "proteome.fasta",
        "threads": 12,
        "qvalue": 0.005,
        "mass_accuracy": 15,
        "use_predictor": True,
        "output": "/work/dia_nn",
    }
    command = DIANNNode.render_command(inputs)
    assert command == [
        "diann",
        "--lib",
        "library.tsv",
        "--fasta",
        "proteome.fasta",
        "--out",
        "/work/dia_nn/report.tsv",
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
    ]
    assert "python" not in command
    assert DIANNNode.REQUIRED_CONDA_PACKAGES == []
    assert DIANNNode.OUTPUT_FILENAMES == ("report.tsv", "report.stats.tsv")


def test_diann_alias_preserves_id_specific_output_directory(tmp_path: Path) -> None:
    assert issubclass(DIANNAliasNode, DIANNNode)
    assert DIANNAliasNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "diann" / "report.tsv",
        tmp_path / "diann" / "report.stats.tsv",
    ]


@pytest.mark.parametrize(
    ("node", "inputs", "message"),
    [
        (OpenMSFeatureFinderNode, {"mzml_file": "x", "min_spectra": 0}, "at least 1"),
        (
            DIANNNode,
            {"raw_files": ["x"], "library": "lib", "fasta": "db", "qvalue": 1.1},
            "at most 1",
        ),
    ],
)
def test_openms_and_diann_reject_invalid_source_values(
    node: type,
    inputs: dict[str, object],
    message: str,
) -> None:
    assert message in str(node.VALIDATE_INPUTS(inputs))
