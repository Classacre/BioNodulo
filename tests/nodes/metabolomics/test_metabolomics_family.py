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
    peak_required = XCMSPeakDetectionNode.INPUT_TYPES()["required"]
    peak_options = XCMSPeakDetectionNode.INPUT_TYPES()["optional"]
    assert peak_required["mzml_files"][0] == "FILE"
    assert peak_required["mzml_files"][1]["multiple"] is True
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


def test_peak_detection_stops_before_alignment_and_exports_chrom_peaks(tmp_path: Path) -> None:
    output = tmp_path / "peaks"
    command = XCMSPeakDetectionNode.render_command(
        {
            "mzml_files": ["/inputs/z-sample.mzML", "/inputs/a-sample.mzML"],
            "output": str(output),
        }
    )

    assert command == ["Rscript", str(output / "xcms_peak_detection.R")]
    script = (output / "xcms_peak_detection.R").read_text(encoding="utf-8")
    assert 'files <- c("/inputs/z-sample.mzML", "/inputs/a-sample.mzML")' in script
    assert "sampleData(raw_data)$bionodulo_input_index <- seq_along(files)" in script
    # centWave aborts with "Spectra are not ordered by retention time" unless
    # spectra are RT-sorted within each file. Order by dataOrigin FIRST so files
    # stay contiguous; a bare rtime sort would interleave samples.
    assert "order(dataOrigin(spectra_set), rtime(spectra_set))" in script
    assert "spectra(raw_data) <- spectra_set[spectra_order]" in script
    assert "xdata <- findChromPeaks(" in script
    assert "peak_table <- as.data.frame(chromPeaks(xdata))" in script
    assert "groupChromPeaks(" not in script
    assert "featureValues(" not in script
    assert XCMSPeakDetectionNode.RETURN_NAMES == ("chrom_peaks", "xcms_object", "summary")


def test_retention_script_rebinds_raw_files_and_follows_xcms_order(tmp_path: Path) -> None:
    output = tmp_path / "retention"
    command = XCMSRetentionCorrectionNode.render_command(
        {
            "xcms_object": "/inputs/sample.xcms.rds",
            "raw_files": ["/staged/z-sample.mzML", "/staged/a-sample.mzML"],
            "sample_groups": ["case", "NA"],
            "threads": 3,
            "output": str(output),
        }
    )

    assert command == ["Rscript", str(output / "xcms_retention_correction.R")]
    script = (output / "xcms_retention_correction.R").read_text(encoding="utf-8")
    assert 'raw_files <- c("/staged/z-sample.mzML", "/staged/a-sample.mzML")' in script
    assert 'if (!is(xdata, "XcmsExperiment"))' in script
    assert "sample_identity <- suppressWarnings(" in script
    assert 'spectra_links <- xdata@sampleDataLinks[["spectra"]]' in script
    assert "sample_storage <- raw_files[sample_identity]" in script
    assert "xdata@spectra$dataStorage <- sample_storage[spectrum_sample]" in script
    assert "unique(xdata@spectra$dataStorage)" not in script
    assert "adjustRtime(xdata, param = ObiwarpParam(binSize = 1.0), BPPARAM = workers)" in script
    assert 'input_sample_groups <- c("case", NA_character_)' in script
    assert "sample_groups <- input_sample_groups[sample_identity]" in script
    assert "feature_definitions <- as.data.frame(featureDefinitions(xdata))" in script
    assert "feature_values <- as.data.frame(featureValues(xdata, value = \"into\"))" in script
    assert 'c("mzmed", "mzmin", "mzmax", "rtmed", "rtmin", "rtmax")' in script
    assert "fillChromPeaks(xdata, param = ChromPeakAreaParam(), BPPARAM = workers)" in script
    assert script.index("adjustRtime(") < script.index("groupChromPeaks(")
    assert script.index("groupChromPeaks(") < script.index("fillChromPeaks(")

    assert "raw_files" in str(
        XCMSRetentionCorrectionNode.VALIDATE_INPUTS(
            {"xcms_object": "sample.xcms.rds", "raw_files": []}
        )
    )
    assert "exactly one value" in str(
        XCMSRetentionCorrectionNode.VALIDATE_INPUTS(
            {
                "xcms_object": "sample.xcms.rds",
                "raw_files": ["a.mzML", "b.mzML"],
                "sample_groups": ["case"],
            }
        )
    )


def test_camera_accepts_current_xcms_objects_and_uses_documented_defaults(tmp_path: Path) -> None:
    options = CAMERAAnnotationNode.INPUT_TYPES()["optional"]
    assert options["perfwhm"][1]["default"] == 0.6
    assert options["sigma"][1]["default"] == 6.0
    assert options["maxcharge"][1]["default"] == 3
    assert options["maxiso"][1]["default"] == 4
    assert options["maxiso"][1]["max"] == 8
    assert options["group_intval"][1]["default"] == "maxo"
    assert options["isotope_intval"][1]["default"] == "maxo"
    assert options["correlation_intval"][1]["default"] == "into"
    assert options["adduct_intval"][1]["default"] == "maxo"
    assert options["peaklist_intval"][1]["default"] == "into"
    assert options["correlation_include_isotopes"][1]["default"] is False

    output = tmp_path / "camera"
    CAMERAAnnotationNode.render_command(
        {
            "xcms_object": "/inputs/aligned.xcms.rds",
            "raw_files": ["/staged/z-sample.mzML", "/staged/a-sample.mzML"],
            "output": str(output),
        }
    )
    script = (output / "camera_annotation.R").read_text(encoding="utf-8")
    assert 'is(xdata, "XcmsExperiment") || is(xdata, "XCMSnExp")' in script
    assert 'xset <- as(xdata, "xcmsSet")' in script
    assert 'raw_files <- c("/staged/z-sample.mzML", "/staged/a-sample.mzML")' in script
    assert '"bionodulo_input_index" %in% colnames(phenoData(xset))' in script
    assert "filepaths(xset) <- raw_files[sample_identity]" in script
    assert 'intval = "maxo"' in script
    assert 'calcIso = FALSE, intval = "into")' in script
    assert 'getPeaklist(xsa, intval = "into")' in script
    assert script.index("groupFWHM(") < script.index("findIsotopes(")
    assert script.index("findIsotopes(") < script.index("groupCorr(")
    assert script.index("groupCorr(") < script.index("findAdducts(")

    assert "raw_files" in str(
        CAMERAAnnotationNode.VALIDATE_INPUTS({"xcms_object": "aligned.xcms.rds"})
    )
    assert "at most 8" in str(
        CAMERAAnnotationNode.VALIDATE_INPUTS(
            {
                "xcms_object": "aligned.xcms.rds",
                "raw_files": ["sample.mzML"],
                "maxiso": 9,
            }
        )
    )

