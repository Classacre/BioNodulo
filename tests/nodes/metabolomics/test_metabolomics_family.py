from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.builtin.metabolomics_family import (
    CAMERAAnnotationNode,
    XCMSPeakDetectionNode,
    XCMSRetentionCorrectionNode,
)


def test_pinned_bioconductor_authorities_and_environments() -> None:
    assert XCMSPeakDetectionNode.VERSION == "4.8.0"
    assert XCMSPeakDetectionNode.GIT_COMMIT == "8c7e9cfe3e512a93a5850d2bdf1df28677c87ad4"
    assert XCMSRetentionCorrectionNode.GIT_COMMIT == XCMSPeakDetectionNode.GIT_COMMIT
    assert CAMERAAnnotationNode.VERSION == "1.66.0"
    assert CAMERAAnnotationNode.GIT_COMMIT == "fcd3b860012e0c1b93b57390363c56c6e1b8230f"
    assert dict(XCMSPeakDetectionNode.CONDA_PACKAGE_CONSTRAINTS) == {
        "r-base": "4.5.*",
        "bioconductor-xcms": "4.8.0",
        "bioconductor-msexperiment": "1.12.0",
        "bioconductor-biocparallel": "1.44.0",
        "r-jsonlite": "2.0.0",
        "r-readr": "2.2.0",
    }
    assert CAMERAAnnotationNode.CONDA_PACKAGE_CONSTRAINTS["bioconductor-camera"] == "1.66.0"


def test_xcms_source_defaults_and_validation() -> None:
    peak_options = XCMSPeakDetectionNode.INPUT_TYPES()["optional"]
    assert peak_options["ppm"][1]["default"] == 25.0
    assert peak_options["peakwidth_min"][1]["default"] == 20.0
    assert peak_options["peakwidth_max"][1]["default"] == 50.0
    assert peak_options["snthresh"][1]["default"] == 10.0
    assert peak_options["prefilter_k"][1]["default"] == 3
    assert peak_options["prefilter_i"][1]["default"] == 100.0
    assert "must not exceed" in str(
        XCMSPeakDetectionNode.VALIDATE_INPUTS(
            {"mzml_files": "sample.mzML", "peakwidth_min": 51.0, "peakwidth_max": 50.0}
        )
    )
    assert "at least one path" in str(XCMSPeakDetectionNode.VALIDATE_INPUTS({"mzml_files": ""}))
    assert "must be an integer" in str(
        XCMSPeakDetectionNode.VALIDATE_INPUTS({"mzml_files": "sample.mzML", "threads": 1.5})
    )


def test_retention_script_uses_xcms_48_gap_filling_contract(tmp_path: Path) -> None:
    output = tmp_path / "retention"
    command = XCMSRetentionCorrectionNode.render_command(
        {
            "xcms_object": "/inputs/sample.xcms.rds",
            "sample_groups": "case,control",
            "threads": 3,
            "output": str(output),
        }
    )

    assert command == ["Rscript", str(output / "xcms_retention_correction.R")]
    script = (output / "xcms_retention_correction.R").read_text(encoding="utf-8")
    assert 'is(xdata, "XcmsExperiment")' in script
    assert "adjustRtime(xdata, param = ObiwarpParam(binSize = 1.0), BPPARAM = workers)" in script
    assert "sample_groups <- c(\"case\", \"control\")" in script
    assert "fillChromPeaks(xdata, param = ChromPeakAreaParam(), BPPARAM = workers)" in script


def test_camera_accepts_current_xcms_objects_and_uses_documented_defaults(tmp_path: Path) -> None:
    options = CAMERAAnnotationNode.INPUT_TYPES()["optional"]
    assert options["perfwhm"][1]["default"] == 0.6
    assert options["sigma"][1]["default"] == 6.0
    assert options["maxcharge"][1]["default"] == 3
    assert options["maxiso"][1]["default"] == 4
    assert options["intval"][1]["default"] == "maxo"

    output = tmp_path / "camera"
    CAMERAAnnotationNode.render_command(
        {"xcms_object": "/inputs/aligned.xcms.rds", "output": str(output)}
    )
    script = (output / "camera_annotation.R").read_text(encoding="utf-8")
    assert 'is(xdata, "XcmsExperiment") || is(xdata, "XCMSnExp")' in script
    assert 'xset <- as(xdata, "xcmsSet")' in script
    assert script.index("groupFWHM(") < script.index("findIsotopes(")
    assert script.index("findIsotopes(") < script.index("groupCorr(")
    assert script.index("groupCorr(") < script.index("findAdducts(")


def test_legacy_module_no_longer_owns_template_metabolomics_ids() -> None:
    from bionodulo.nodes.builtin import metabolomics

    assert metabolomics.XCMSPeakDetectionNode is XCMSPeakDetectionNode
    assert metabolomics.XCMSRetentionCorrectionNode is XCMSRetentionCorrectionNode
    assert metabolomics.CAMERAAnnotationNode is CAMERAAnnotationNode
    assert metabolomics._LegacyXCMSPeakDetectionNode.NODE_ID == ""
    assert metabolomics._LegacyXCMSRetentionCorrectionNode.NODE_ID == ""
    assert metabolomics._LegacyCAMERAAnnotationNode.NODE_ID == ""
