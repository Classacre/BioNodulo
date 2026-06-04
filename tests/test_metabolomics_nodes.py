from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
    R_PACKAGE_TO_CONDA_PACKAGE,
)
from bionodulo.nodes.registry import NodeRegistry


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None, f"{node_id} is not registered"
    return node_class


def test_xcms_peak_detection_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["xcms_peak_detection"]
    assert node_info["display_name"] == "XCMS Peak Detection"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Detect LC-MS chromatographic peaks")
    assert node_info["output"] == ["TSV", "FILE", "JSON"]
    assert node_info["output_name"] == ["feature_table", "xcms_object", "summary"]
    assert node_info["required_executables"] == ["Rscript"]
    assert node_info["required_conda_packages"] == ["r-base", "bioconductor-xcms", "r-jsonlite", "r-readr"]
    assert node_info["required_r_packages"] == ["xcms", "jsonlite", "readr"]
    assert "metabolomics" in node_info["search_aliases"]
    assert "centwave" in node_info["search_aliases"]
    assert "lc-ms" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"mzml_files"}
    assert set(inputs["optional"]) == {
        "ppm",
        "peakwidth_min",
        "peakwidth_max",
        "snthresh",
        "prefilter_k",
        "prefilter_i",
        "noise",
        "threads",
        "output_name",
    }


def test_xcms_peak_detection_writes_r_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("xcms_peak_detection")
    output_dir = tmp_path / "xcms_peak_detection"

    cmd = node_class.render_command({
        "mzml_files": ["sample1.mzML", "sample2.mzML"],
        "ppm": 25,
        "peakwidth_min": 8,
        "peakwidth_max": 35,
        "snthresh": 12,
        "prefilter_k": 4,
        "prefilter_i": 120,
        "noise": 500,
        "threads": 6,
        "output_name": "study one",
        "output": str(output_dir),
    })

    script_file = output_dir / "xcms_peak_detection.R"
    assert cmd == ["Rscript", str(script_file)]
    script = script_file.read_text()
    assert 'library("xcms")' in script
    assert 'library("jsonlite")' in script
    assert 'library("readr")' in script
    assert 'files <- c("sample1.mzML", "sample2.mzML")' in script
    assert "param <- CentWaveParam(" in script
    assert "ppm = 25" in script
    assert "peakwidth = c(8, 35)" in script
    assert "snthresh = 12" in script
    assert "prefilter = c(4, 120)" in script
    assert "noise = 500" in script
    assert "BPPARAM = MulticoreParam(workers = 6)" in script
    assert "xdata <- findChromPeaks(raw_data, param = param" in script
    assert "feature_values <- featureValues(xdata, value = \"into\")" in script
    assert f'write_tsv(feature_table, "{output_dir}/study_one.feature_table.tsv")' in script
    assert f'saveRDS(xdata, "{output_dir}/study_one.xcms.rds")' in script
    assert f'write_json(summary, "{output_dir}/study_one.summary.json", pretty = TRUE, auto_unbox = TRUE)' in script


def test_xcms_peak_detection_accepts_single_file_and_default_output_name(tmp_path: Path) -> None:
    node_class = _node_class("xcms_peak_detection")
    output_dir = tmp_path / "xcms_peak_detection"

    cmd = node_class.render_command({
        "mzml_files": "/data/sampleA.mzML",
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == ["Rscript", str(output_dir / "xcms_peak_detection.R")]
    script = (output_dir / "xcms_peak_detection.R").read_text()
    assert 'files <- c("/data/sampleA.mzML")' in script
    assert "ppm = 25" in script
    assert "peakwidth = c(20, 50)" in script
    assert "BPPARAM = MulticoreParam(workers = 1)" in script
    assert f'write_tsv(feature_table, "{output_dir}/sampleA.feature_table.tsv")' in script
    assert f'saveRDS(xdata, "{output_dir}/sampleA.xcms.rds")' in script


def test_xcms_peak_detection_plans_outputs() -> None:
    node_class = _node_class("xcms_peak_detection")

    outputs = node_class.PLAN_OUTPUTS(
        {"mzml_files": ["sample1.mzML"], "output_name": "study one"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/xcms_peak_detection/study_one.feature_table.tsv",
        "/tmp/run/xcms_peak_detection/study_one.xcms.rds",
        "/tmp/run/xcms_peak_detection/study_one.summary.json",
    ]


def test_xcms_peak_detection_environment_metadata_is_declared() -> None:
    assert R_PACKAGE_TO_CONDA_PACKAGE["xcms"] == "bioconductor-xcms"
    assert R_PACKAGE_TO_CONDA_PACKAGE["jsonlite"] == "r-jsonlite"
    assert PACKAGE_MIN_VERSIONS["bioconductor-xcms"] == ">=3.20"
    assert PACKAGE_MIN_VERSIONS["r-jsonlite"] == ">=1.8"


def test_sirius_formula_id_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["sirius_formula_id"]
    assert node_info["display_name"] == "SIRIUS Formula ID"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Identify molecular formulas")
    assert node_info["output"] == ["DIRECTORY", "TSV", "JSON"]
    assert node_info["output_name"] == ["results_dir", "summary", "metadata"]
    assert node_info["required_executables"] == ["sirius"]
    assert node_info["required_conda_packages"] == ["sirius"]
    assert "sirius" in node_info["search_aliases"]
    assert "formula identification" in node_info["search_aliases"]
    assert "canopus" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"spectra_file"}
    assert set(inputs["optional"]) == {
        "database",
        "profile",
        "ionization",
        "ppm_max",
        "cores",
        "run_zodiac",
        "run_structure",
        "run_canopus",
        "output_name",
    }


def test_sirius_formula_id_renders_command_with_optional_tools() -> None:
    node_class = _node_class("sirius_formula_id")

    cmd = node_class.render_command({
        "spectra_file": "input.ms",
        "database": "ALL",
        "profile": "orbitrap",
        "ionization": "[M+H]+",
        "ppm_max": 10,
        "cores": 8,
        "run_zodiac": True,
        "run_structure": True,
        "run_canopus": True,
        "output_name": "sample one",
        "output": "/tmp/run/sirius_formula_id",
    })

    assert cmd == [
        "sirius",
        "-i",
        "input.ms",
        "-o",
        "/tmp/run/sirius_formula_id/sample_one",
        "--database",
        "ALL",
        "--profile",
        "orbitrap",
        "--ionization",
        "[M+H]+",
        "--ppm-max",
        "10",
        "--cores",
        "8",
        "formula",
        "zodiac",
        "structure",
        "canopus",
        "&&",
        "python",
        "-c",
        node_class.SUMMARY_SCRIPT,
        "/tmp/run/sirius_formula_id/sample_one",
        "/tmp/run/sirius_formula_id/sample_one.summary.tsv",
        "/tmp/run/sirius_formula_id/sample_one.metadata.json",
        "input.ms",
        "ALL",
        "orbitrap",
        "[M+H]+",
    ]


def test_sirius_formula_id_defaults_to_formula_only_and_sanitized_input_stem() -> None:
    node_class = _node_class("sirius_formula_id")

    cmd = node_class.render_command({
        "spectra_file": "/data/compound-spectrum.mgf",
        "database": "",
        "profile": "",
        "ionization": "",
        "ppm_max": 0,
        "cores": 1,
        "run_zodiac": False,
        "run_structure": False,
        "run_canopus": False,
        "output_name": "",
        "output": "/tmp/run/sirius_formula_id",
    })

    assert cmd == [
        "sirius",
        "-i",
        "/data/compound-spectrum.mgf",
        "-o",
        "/tmp/run/sirius_formula_id/compound-spectrum",
        "--cores",
        "1",
        "formula",
        "&&",
        "python",
        "-c",
        node_class.SUMMARY_SCRIPT,
        "/tmp/run/sirius_formula_id/compound-spectrum",
        "/tmp/run/sirius_formula_id/compound-spectrum.summary.tsv",
        "/tmp/run/sirius_formula_id/compound-spectrum.metadata.json",
        "/data/compound-spectrum.mgf",
        "",
        "",
        "",
    ]
    assert "zodiac" not in cmd
    assert "structure" not in cmd
    assert "canopus" not in cmd


def test_sirius_formula_id_plans_outputs() -> None:
    node_class = _node_class("sirius_formula_id")

    outputs = node_class.PLAN_OUTPUTS(
        {"spectra_file": "input.ms", "output_name": "sample one"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/sirius_formula_id/sample_one",
        "/tmp/run/sirius_formula_id/sample_one.summary.tsv",
        "/tmp/run/sirius_formula_id/sample_one.metadata.json",
    ]


def test_sirius_formula_id_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["sirius"] == "sirius"
    assert PACKAGE_MIN_VERSIONS["sirius"] == ">=5.8"
