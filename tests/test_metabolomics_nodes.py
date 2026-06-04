from __future__ import annotations

from pathlib import Path

from bionodulo.environments.constants import (
    EXECUTABLE_TO_CONDA_PACKAGE,
    PACKAGE_MIN_VERSIONS,
    R_PACKAGE_TO_CONDA_PACKAGE,
)
from bionodulo.environments.manifest import workflow_to_packages
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
    assert node_info["required_conda_packages"] == [
        "r-base",
        "bioconductor-xcms",
        "bioconductor-biocparallel",
        "r-jsonlite",
        "r-readr",
    ]
    assert node_info["required_r_packages"] == ["xcms", "jsonlite", "readr", "BiocParallel"]
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
    assert R_PACKAGE_TO_CONDA_PACKAGE["BiocParallel"] == "bioconductor-biocparallel"
    assert PACKAGE_MIN_VERSIONS["bioconductor-xcms"] == ">=3.20"
    assert PACKAGE_MIN_VERSIONS["bioconductor-biocparallel"] == ">=1.34"
    assert PACKAGE_MIN_VERSIONS["r-jsonlite"] == ">=1.8"


def test_xcms_retention_correction_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["xcms_retention_correction"]
    assert node_info["display_name"] == "XCMS Retention Time Correction"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Correct retention time")
    assert node_info["output"] == ["TSV", "FILE", "JSON"]
    assert node_info["output_name"] == ["aligned_feature_table", "aligned_xcms_object", "summary"]
    assert node_info["required_executables"] == ["Rscript"]
    assert node_info["required_conda_packages"] == [
        "r-base",
        "bioconductor-xcms",
        "bioconductor-biocparallel",
        "r-jsonlite",
        "r-readr",
    ]
    assert node_info["required_r_packages"] == ["xcms", "BiocParallel", "jsonlite", "readr"]
    assert "retention time" in node_info["search_aliases"]
    assert "obiwarp" in node_info["search_aliases"]
    assert "alignment" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"xcms_object"}
    assert set(inputs["optional"]) == {
        "method",
        "bin_size",
        "bw",
        "min_fraction",
        "sample_groups",
        "threads",
        "output_name",
    }


def test_xcms_retention_correction_writes_r_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("xcms_retention_correction")
    output_dir = tmp_path / "xcms_retention_correction"

    cmd = node_class.render_command({
        "xcms_object": "/data/study.xcms.rds",
        "method": "obiwarp",
        "bin_size": 0.5,
        "bw": 4,
        "min_fraction": 0.75,
        "sample_groups": "case,control",
        "threads": 4,
        "output_name": "aligned study",
        "output": str(output_dir),
    })

    script_file = output_dir / "xcms_retention_correction.R"
    assert cmd == ["Rscript", str(script_file)]
    script = script_file.read_text()
    assert 'library("xcms")' in script
    assert 'library("BiocParallel")' in script
    assert 'library("jsonlite")' in script
    assert 'library("readr")' in script
    assert 'xdata <- readRDS("/data/study.xcms.rds")' in script
    assert 'sample_groups <- c("case", "control")' in script
    assert 'adjust_param <- ObiwarpParam(binSize = 0.5)' in script
    assert "xdata <- adjustRtime(xdata, param = adjust_param, BPPARAM = MulticoreParam(workers = 4))" in script
    assert "group_param <- PeakDensityParam(sampleGroups = sample_groups, bw = 4, minFraction = 0.75)" in script
    assert "xdata <- groupChromPeaks(xdata, param = group_param)" in script
    assert "groupChromPeaks(xdata, param = group_param, BPPARAM" not in script
    assert "xdata <- fillChromPeaks(xdata, BPPARAM = MulticoreParam(workers = 4))" in script
    assert "feature_values <- featureValues(xdata, value = \"into\")" in script
    assert f'write_tsv(feature_table, "{output_dir}/aligned_study.aligned_feature_table.tsv")' in script
    assert f'saveRDS(xdata, "{output_dir}/aligned_study.aligned.xcms.rds")' in script
    assert f'write_json(summary, "{output_dir}/aligned_study.alignment.summary.json", pretty = TRUE, auto_unbox = TRUE)' in script


def test_xcms_retention_correction_defaults_to_single_group_and_input_stem(tmp_path: Path) -> None:
    node_class = _node_class("xcms_retention_correction")
    output_dir = tmp_path / "xcms_retention_correction"

    cmd = node_class.render_command({
        "xcms_object": "/data/study.xcms.rds",
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == ["Rscript", str(output_dir / "xcms_retention_correction.R")]
    script = (output_dir / "xcms_retention_correction.R").read_text()
    assert 'sample_groups <- rep(1L, length(fileNames(xdata)))' in script
    assert "adjust_param <- ObiwarpParam(binSize = 1.0)" in script
    assert "group_param <- PeakDensityParam(sampleGroups = sample_groups, bw = 5.0, minFraction = 0.5)" in script
    assert "MulticoreParam(workers = 1)" in script
    assert f'write_tsv(feature_table, "{output_dir}/study.aligned_feature_table.tsv")' in script
    assert f'saveRDS(xdata, "{output_dir}/study.aligned.xcms.rds")' in script


def test_xcms_retention_correction_plans_outputs() -> None:
    node_class = _node_class("xcms_retention_correction")

    outputs = node_class.PLAN_OUTPUTS(
        {"xcms_object": "input.xcms.rds", "output_name": "study one"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/xcms_retention_correction/study_one.aligned_feature_table.tsv",
        "/tmp/run/xcms_retention_correction/study_one.aligned.xcms.rds",
        "/tmp/run/xcms_retention_correction/study_one.alignment.summary.json",
    ]


def test_xcms_retention_correction_environment_metadata_is_declared() -> None:
    assert R_PACKAGE_TO_CONDA_PACKAGE["BiocParallel"] == "bioconductor-biocparallel"
    assert PACKAGE_MIN_VERSIONS["bioconductor-biocparallel"] == ">=1.34"


def test_camera_annotation_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["camera_annotation"]
    assert node_info["display_name"] == "CAMERA Annotation"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Annotate LC-MS peaks")
    assert node_info["output"] == ["TSV", "FILE", "JSON"]
    assert node_info["output_name"] == ["annotated_peaklist", "camera_object", "summary"]
    assert node_info["required_executables"] == ["Rscript"]
    assert node_info["required_conda_packages"] == [
        "r-base",
        "bioconductor-camera",
        "bioconductor-xcms",
        "r-jsonlite",
        "r-readr",
    ]
    assert node_info["required_r_packages"] == ["CAMERA", "xcms", "jsonlite", "readr"]
    assert "camera" in node_info["search_aliases"]
    assert "adducts" in node_info["search_aliases"]
    assert "isotopes" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"xcms_object"}
    assert set(inputs["optional"]) == {
        "polarity",
        "perfwhm",
        "sigma",
        "maxcharge",
        "maxiso",
        "isotope_ppm",
        "isotope_mzabs",
        "cor_eic_th",
        "pval",
        "run_group_corr",
        "run_adducts",
        "adduct_ppm",
        "adduct_mzabs",
        "intval",
        "output_name",
    }


def test_camera_annotation_writes_r_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("camera_annotation")
    output_dir = tmp_path / "camera_annotation"

    cmd = node_class.render_command({
        "xcms_object": "/data/study.aligned.xcms.rds",
        "polarity": "negative",
        "perfwhm": 0.7,
        "sigma": 5,
        "maxcharge": 2,
        "maxiso": 5,
        "isotope_ppm": 7,
        "isotope_mzabs": 0.02,
        "cor_eic_th": 0.8,
        "pval": 0.01,
        "run_group_corr": True,
        "run_adducts": True,
        "adduct_ppm": 6,
        "adduct_mzabs": 0.015,
        "intval": "into",
        "output_name": "annotated study",
        "output": str(output_dir),
    })

    script_file = output_dir / "camera_annotation.R"
    assert cmd == ["Rscript", str(script_file)]
    script = script_file.read_text()
    assert 'library("CAMERA")' in script
    assert 'library("xcms")' in script
    assert 'library("jsonlite")' in script
    assert 'library("readr")' in script
    assert 'xdata <- readRDS("/data/study.aligned.xcms.rds")' in script
    assert 'if (is(xdata, "xcmsSet")) {' in script
    assert 'if (any(msLevel(xdata) > 1)) stop("CAMERA conversion from XCMSnExp to xcmsSet supports MS1-only objects.' in script
    assert 'xset <- as(xdata, "xcmsSet")' in script
    assert 'xsa <- xsAnnotate(xset, polarity = "negative")' in script
    assert 'xsa <- groupFWHM(xsa, sigma = 5, perfwhm = 0.7, intval = "into")' in script
    assert 'xsa <- findIsotopes(xsa, maxcharge = 2, maxiso = 5, ppm = 7, mzabs = 0.02, intval = "into")' in script
    assert 'xsa <- groupCorr(xsa, cor_eic_th = 0.8, pval = 0.01, calcIso = TRUE, intval = "into")' in script
    assert 'xsa <- findAdducts(xsa, ppm = 6, mzabs = 0.015, polarity = "negative", intval = "into")' in script
    assert 'peaklist <- as.data.frame(getPeaklist(xsa, intval = "into"))' in script
    assert f'write_tsv(peaklist, "{output_dir}/annotated_study.camera_peaklist.tsv")' in script
    assert f'saveRDS(xsa, "{output_dir}/annotated_study.camera.rds")' in script
    assert f'write_json(summary, "{output_dir}/annotated_study.camera.summary.json", pretty = TRUE, auto_unbox = TRUE)' in script


def test_camera_annotation_can_skip_correlation_and_adduct_steps(tmp_path: Path) -> None:
    node_class = _node_class("camera_annotation")
    output_dir = tmp_path / "camera_annotation"

    cmd = node_class.render_command({
        "xcms_object": "/data/study.aligned.xcms.rds",
        "run_group_corr": False,
        "run_adducts": False,
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == ["Rscript", str(output_dir / "camera_annotation.R")]
    script = (output_dir / "camera_annotation.R").read_text()
    assert 'xsa <- xsAnnotate(xset, polarity = "positive")' in script
    assert 'xsa <- groupFWHM(xsa, sigma = 6, perfwhm = 0.6, intval = "into")' in script
    assert 'xsa <- findIsotopes(xsa, maxcharge = 3, maxiso = 4, ppm = 5, mzabs = 0.01, intval = "into")' in script
    assert "groupCorr(" not in script
    assert "findAdducts(" not in script
    assert f'write_tsv(peaklist, "{output_dir}/study.aligned.camera_peaklist.tsv")' in script
    assert f'saveRDS(xsa, "{output_dir}/study.aligned.camera.rds")' in script


def test_camera_annotation_plans_outputs() -> None:
    node_class = _node_class("camera_annotation")

    outputs = node_class.PLAN_OUTPUTS(
        {"xcms_object": "input.xcms.rds", "output_name": "study one"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/camera_annotation/study_one.camera_peaklist.tsv",
        "/tmp/run/camera_annotation/study_one.camera.rds",
        "/tmp/run/camera_annotation/study_one.camera.summary.json",
    ]


def test_camera_annotation_environment_metadata_is_declared() -> None:
    assert R_PACKAGE_TO_CONDA_PACKAGE["CAMERA"] == "bioconductor-camera"
    assert PACKAGE_MIN_VERSIONS["bioconductor-camera"] == ">=1.66"


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


def test_mzmine_batch_processing_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["mzmine_batch_processing"]
    assert node_info["display_name"] == "MZmine Batch Processing"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Run an MZmine batch workflow")
    assert node_info["output"] == ["DIRECTORY", "JSON"]
    assert node_info["output_name"] == ["results_dir", "metadata"]
    assert node_info["required_executables"] == ["mzmine"]
    assert node_info["required_conda_packages"] == ["mzmine"]
    assert "mzmine" in node_info["search_aliases"]
    assert "batch" in node_info["search_aliases"]
    assert "lc-ms" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"batch_file"}
    assert set(inputs["optional"]) == {
        "input_files",
        "user_file",
        "preferences_file",
        "threads",
        "memory_mode",
        "temp_dir",
        "ignore_parameter_warnings",
        "output_name",
    }


def test_mzmine_batch_processing_renders_cli_with_inputs_and_metadata(tmp_path: Path) -> None:
    node_class = _node_class("mzmine_batch_processing")
    output_dir = tmp_path / "mzmine_batch_processing"
    input_list_file = output_dir / "study_one.input_files.txt"
    results_dir = output_dir / "study_one"
    metadata_json = output_dir / "study_one.metadata.json"

    cmd = node_class.render_command({
        "batch_file": "/workflows/lcms.mzbatch",
        "input_files": ["sample1.mzML", "sample2.mzML"],
        "user_file": "/users/offline.mzuser",
        "preferences_file": "/configs/lcms.mzconfig",
        "threads": 8,
        "memory_mode": "all",
        "temp_dir": "/scratch/mzmine",
        "ignore_parameter_warnings": True,
        "output_name": "study one",
        "output": str(output_dir),
    })

    assert cmd == [
        "mzmine",
        "-user",
        "/users/offline.mzuser",
        "-batch",
        "/workflows/lcms.mzbatch",
        "-input",
        str(input_list_file),
        "-output",
        str(results_dir / "study_one"),
        "-temp",
        "/scratch/mzmine",
        "-pref",
        "/configs/lcms.mzconfig",
        "-memory",
        "all",
        "-threads",
        "8",
        "-ignore-parameter-warnings",
        "&&",
        "python",
        "-c",
        node_class.METADATA_SCRIPT,
        str(results_dir),
        str(metadata_json),
        "/workflows/lcms.mzbatch",
        "sample1.mzML\nsample2.mzML",
        "/users/offline.mzuser",
        "/configs/lcms.mzconfig",
        "8",
        "all",
        "/scratch/mzmine",
        "true",
    ]
    assert input_list_file.read_text() == "sample1.mzML\nsample2.mzML\n"


def test_mzmine_batch_processing_omits_optional_cli_flags_and_uses_batch_stem(tmp_path: Path) -> None:
    node_class = _node_class("mzmine_batch_processing")
    output_dir = tmp_path / "mzmine_batch_processing"

    cmd = node_class.render_command({
        "batch_file": "/workflows/lcms.mzbatch",
        "input_files": "",
        "user_file": "",
        "preferences_file": "",
        "threads": 1,
        "memory_mode": "",
        "temp_dir": "",
        "ignore_parameter_warnings": False,
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == [
        "mzmine",
        "-batch",
        "/workflows/lcms.mzbatch",
        "-output",
        str(output_dir / "lcms" / "lcms"),
        "-threads",
        "1",
        "&&",
        "python",
        "-c",
        node_class.METADATA_SCRIPT,
        str(output_dir / "lcms"),
        str(output_dir / "lcms.metadata.json"),
        "/workflows/lcms.mzbatch",
        "",
        "",
        "",
        "1",
        "",
        "",
        "false",
    ]
    assert "-input" not in cmd
    assert "-user" not in cmd
    assert "-pref" not in cmd
    assert "-temp" not in cmd
    assert "-memory" not in cmd
    assert "-ignore-parameter-warnings" not in cmd


def test_mzmine_batch_processing_plans_outputs() -> None:
    node_class = _node_class("mzmine_batch_processing")

    outputs = node_class.PLAN_OUTPUTS(
        {"batch_file": "/workflows/lcms.mzbatch", "output_name": "study one"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/mzmine_batch_processing/study_one",
        "/tmp/run/mzmine_batch_processing/study_one.metadata.json",
    ]


def test_mzmine_batch_processing_environment_metadata_is_declared() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["mzmine"] == "mzmine"
    assert PACKAGE_MIN_VERSIONS["mzmine"] == ">=4.7"


def test_metaboanalyst_stats_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["metaboanalyst_stats"]
    assert node_info["display_name"] == "MetaboAnalyst Stats"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Run MetaboAnalystR normalization")
    assert node_info["output"] == ["TSV", "TSV", "TSV", "TSV", "IMAGE", "FILE", "JSON"]
    assert node_info["output_name"] == [
        "normalized_table",
        "pca_scores",
        "pca_loadings",
        "ttest_results",
        "pca_plot",
        "metaboanalyst_object",
        "summary",
    ]
    assert node_info["required_executables"] == ["Rscript"]
    assert node_info["required_conda_packages"] == ["r-base", "r-jsonlite", "r-readr"]
    assert node_info["required_r_packages"] == ["MetaboAnalystR", "jsonlite", "readr"]
    assert node_info["experimental"] is True
    assert "metaboanalyst" in node_info["search_aliases"]
    assert "statistics" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"data_table"}
    assert set(inputs["optional"]) == {
        "format",
        "label_type",
        "row_norm",
        "trans_norm",
        "scale_norm",
        "run_pca",
        "run_ttest",
        "tt_method",
        "p_threshold",
        "pval_type",
        "paired",
        "equal_var",
        "output_name",
    }


def test_metaboanalyst_stats_writes_r_script_and_renders_command(tmp_path: Path) -> None:
    node_class = _node_class("metaboanalyst_stats")
    output_dir = tmp_path / "metaboanalyst_stats"

    cmd = node_class.render_command({
        "data_table": "/data/metabolites.csv",
        "format": "colu",
        "label_type": "disc",
        "row_norm": "SumNorm",
        "trans_norm": "LogNorm",
        "scale_norm": "ParetoNorm",
        "run_pca": True,
        "run_ttest": True,
        "tt_method": "welch",
        "p_threshold": 0.01,
        "pval_type": "fdr",
        "paired": False,
        "equal_var": False,
        "output_name": "case control stats",
        "output": str(output_dir),
    })

    script_file = output_dir / "metaboanalyst_stats.R"
    assert cmd == ["Rscript", str(script_file)]
    script = script_file.read_text()
    assert 'library("MetaboAnalystR")' in script
    assert 'library("jsonlite")' in script
    assert 'library("readr")' in script
    assert f'setwd("{output_dir.as_posix()}")' in script
    assert 'mSet <- InitDataObjects("conc", "stat", paired = FALSE)' in script
    assert 'mSet <- Read.TextData(mSet, "/data/metabolites.csv", format = "colu", lbl.type = "disc")' in script
    assert "mSet <- SanityCheckData(mSet)" in script
    assert "mSet <- ReplaceMin(mSet)" in script
    assert "mSet <- PreparePrenormData(mSet)" in script
    assert 'mSet <- Normalization(mSet, rowNorm = "SumNorm", transNorm = "LogNorm", scaleNorm = "ParetoNorm")' in script
    assert "mSet <- PCA.Anal(mSet)" in script
    assert 'PlotPCA2DScore(mSet, "case_control_stats.pca", "png", dpi = 150, width = 0, pcx = 1, pcy = 2, reg = 0.95, show = 0)' in script
    assert 'mSet <- Ttests.Anal(mSet, nonpar = FALSE, threshp = 0.01, paired = FALSE, equal.var = FALSE, pvalType = "fdr", all_results = TRUE, tt.method = "welch")' in script
    assert f'write_tsv(norm_table, "{output_dir}/case_control_stats.normalized.tsv")' in script
    assert f'write_tsv(pca_scores, "{output_dir}/case_control_stats.pca_scores.tsv")' in script
    assert f'write_tsv(pca_loadings, "{output_dir}/case_control_stats.pca_loadings.tsv")' in script
    assert f'write_tsv(ttest_results, "{output_dir}/case_control_stats.ttest.tsv")' in script
    assert f'saveRDS(mSet, "{output_dir}/case_control_stats.metaboanalyst.rds")' in script
    assert f'write_json(summary, "{output_dir}/case_control_stats.summary.json", pretty = TRUE, auto_unbox = TRUE)' in script


def test_metaboanalyst_stats_can_skip_pca_and_ttest(tmp_path: Path) -> None:
    node_class = _node_class("metaboanalyst_stats")
    output_dir = tmp_path / "metaboanalyst_stats"

    cmd = node_class.render_command({
        "data_table": "/data/metabolites.csv",
        "run_pca": False,
        "run_ttest": False,
        "output_name": "",
        "output": str(output_dir),
    })

    assert cmd == ["Rscript", str(output_dir / "metaboanalyst_stats.R")]
    script = (output_dir / "metaboanalyst_stats.R").read_text()
    assert 'mSet <- Read.TextData(mSet, "/data/metabolites.csv", format = "rowu", lbl.type = "disc")' in script
    assert 'mSet <- Normalization(mSet, rowNorm = "MedianNorm", transNorm = "LogNorm", scaleNorm = "AutoNorm")' in script
    assert "PCA.Anal" not in script
    assert "Ttests.Anal" not in script
    assert f'write_tsv(norm_table, "{output_dir}/metabolites.normalized.tsv")' in script
    assert f'saveRDS(mSet, "{output_dir}/metabolites.metaboanalyst.rds")' in script


def test_metaboanalyst_stats_plans_outputs() -> None:
    node_class = _node_class("metaboanalyst_stats")

    outputs = node_class.PLAN_OUTPUTS(
        {"data_table": "/data/metabolites.csv", "output_name": "case control stats"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/metaboanalyst_stats/case_control_stats.normalized.tsv",
        "/tmp/run/metaboanalyst_stats/case_control_stats.pca_scores.tsv",
        "/tmp/run/metaboanalyst_stats/case_control_stats.pca_loadings.tsv",
        "/tmp/run/metaboanalyst_stats/case_control_stats.ttest.tsv",
        "/tmp/run/metaboanalyst_stats/case_control_stats.pca.png",
        "/tmp/run/metaboanalyst_stats/case_control_stats.metaboanalyst.rds",
        "/tmp/run/metaboanalyst_stats/case_control_stats.summary.json",
    ]


def test_metaboanalyst_stats_environment_metadata_is_declared_without_fake_conda_package() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["Rscript"] == "r-base"
    assert "MetaboAnalystR" not in R_PACKAGE_TO_CONDA_PACKAGE
    packages = workflow_to_packages({"nodes": [{"id": "stats", "type": "metaboanalyst_stats"}]}, registry)

    assert "MetaboAnalystR" not in packages
    assert packages == ["r-base", "r-jsonlite", "r-readr"]


def test_msdial_processing_is_registered_for_frontend_discovery() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    info = registry.object_info()

    node_info = info["msdial_processing"]
    assert node_info["display_name"] == "MS-DIAL Processing"
    assert node_info["category"] == "metabolomics"
    assert node_info["description"].startswith("Run MS-DIAL console batch processing")
    assert node_info["output"] == ["DIRECTORY", "TSV", "JSON"]
    assert node_info["output_name"] == ["results_dir", "result_index", "metadata"]
    assert node_info["required_executables"] == ["mono"]
    assert node_info["required_conda_packages"] == ["mono"]
    assert node_info["experimental"] is True
    assert "ms-dial" in node_info["search_aliases"]
    assert "lcmsdda" in node_info["search_aliases"]
    assert "gcms" in node_info["search_aliases"]

    inputs = node_info["input"]
    assert set(inputs["required"]) == {"input_dir", "parameter_file"}
    assert set(inputs["optional"]) == {
        "analysis_type",
        "msdial_executable",
        "use_mono",
        "keep_project_file",
        "output_name",
    }


def test_msdial_processing_renders_mono_command_with_project_retention() -> None:
    node_class = _node_class("msdial_processing")

    cmd = node_class.render_command({
        "input_dir": "/data/lcms",
        "parameter_file": "/params/lcmsdda.txt",
        "analysis_type": "lcmsdda",
        "msdial_executable": "/opt/msdial/MsdialConsoleApp.exe",
        "use_mono": True,
        "keep_project_file": True,
        "output_name": "study one",
        "output": "/tmp/run/msdial_processing",
    })

    assert cmd == [
        "mono",
        "/opt/msdial/MsdialConsoleApp.exe",
        "lcmsdda",
        "-i",
        "/data/lcms",
        "-o",
        "/tmp/run/msdial_processing/study_one",
        "-m",
        "/params/lcmsdda.txt",
        "-p",
        "&&",
        "python",
        "-c",
        node_class.INDEX_SCRIPT,
        "/tmp/run/msdial_processing/study_one",
        "/tmp/run/msdial_processing/study_one.result_index.tsv",
        "/tmp/run/msdial_processing/study_one.metadata.json",
        "/data/lcms",
        "/params/lcmsdda.txt",
        "lcmsdda",
        "/opt/msdial/MsdialConsoleApp.exe",
        "true",
        "true",
    ]


def test_msdial_processing_renders_custom_executable_without_mono() -> None:
    node_class = _node_class("msdial_processing")

    cmd = node_class.render_command({
        "input_dir": "/data/gcms",
        "parameter_file": "/params/gcms.txt",
        "analysis_type": "gcms",
        "msdial_executable": "MsdialConsoleApp.exe",
        "use_mono": False,
        "keep_project_file": False,
        "output_name": "",
        "output": "/tmp/run/msdial_processing",
    })

    assert cmd == [
        "MsdialConsoleApp.exe",
        "gcms",
        "-i",
        "/data/gcms",
        "-o",
        "/tmp/run/msdial_processing/gcms",
        "-m",
        "/params/gcms.txt",
        "&&",
        "python",
        "-c",
        node_class.INDEX_SCRIPT,
        "/tmp/run/msdial_processing/gcms",
        "/tmp/run/msdial_processing/gcms.result_index.tsv",
        "/tmp/run/msdial_processing/gcms.metadata.json",
        "/data/gcms",
        "/params/gcms.txt",
        "gcms",
        "MsdialConsoleApp.exe",
        "false",
        "false",
    ]
    assert "mono" not in cmd
    assert "-p" not in cmd


def test_msdial_processing_rejects_unsupported_analysis_type() -> None:
    node_class = _node_class("msdial_processing")

    try:
        node_class.render_command({
            "input_dir": "/data/lcms",
            "parameter_file": "/params/params.txt",
            "analysis_type": "invalid",
            "output": "/tmp/run/msdial_processing",
        })
    except ValueError as exc:
        assert "analysis_type" in str(exc)
    else:
        raise AssertionError("Expected ValueError for unsupported MS-DIAL analysis type")


def test_msdial_processing_plans_outputs() -> None:
    node_class = _node_class("msdial_processing")

    outputs = node_class.PLAN_OUTPUTS(
        {"analysis_type": "lcmsdia", "output_name": "dia study"},
        "/tmp/run",
    )

    assert [str(path) for path in outputs] == [
        "/tmp/run/msdial_processing/dia_study",
        "/tmp/run/msdial_processing/dia_study.result_index.tsv",
        "/tmp/run/msdial_processing/dia_study.metadata.json",
    ]


def test_msdial_processing_environment_metadata_avoids_fake_msdial_conda_package() -> None:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()

    assert EXECUTABLE_TO_CONDA_PACKAGE["mono"] == "mono"
    packages = workflow_to_packages({"nodes": [{"id": "msdial", "type": "msdial_processing"}]}, registry)

    assert packages == ["mono"]
    assert "msdial" not in packages
    assert "MsdialConsoleApp.exe" not in packages
