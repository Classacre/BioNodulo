"""XCMS 4.8.0 centWave peak detection with reproducible R artifacts."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    r_string,
    r_string_vector,
    safe_output_stem,
    split_paths,
    validate_number,
)


class XCMSPeakDetectionNode(MetabolomicsCommandNode):
    """Detect and group LC-MS chromatographic peaks with centWave."""

    NODE_ID = "xcms_peak_detection"
    DISPLAY_NAME = "XCMS Peak Detection"
    DESCRIPTION = "Detect LC-MS chromatographic peaks with XCMS 4.8.0 centWave."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "XCMS",
        "centWave",
        "centwave",
        "LC-MS",
        "lc-ms",
        "metabolomics",
        "chromatographic peaks",
    ]
    RETURN_TYPES = ("TSV", "FILE", "JSON")
    RETURN_NAMES = ("feature_table", "xcms_object", "summary")
    OUTPUT_SUFFIXES = (".feature_table.tsv", ".xcms.rds", ".summary.json")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = [
        "r-base",
        "bioconductor-xcms",
        "bioconductor-msexperiment",
        "bioconductor-biocparallel",
        "r-jsonlite",
        "r-readr",
    ]
    REQUIRED_R_PACKAGES = ["xcms", "MsExperiment", "BiocParallel", "jsonlite", "readr"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "r-base": "4.5.*",
        "bioconductor-xcms": "4.8.0",
        "bioconductor-msexperiment": "1.12.0",
        "bioconductor-biocparallel": "1.44.0",
        "r-jsonlite": "2.0.0",
        "r-readr": "2.2.0",
    }
    VERSION = "4.8.0"
    GIT_URL = "https://git.bioconductor.org/packages/xcms"
    GIT_COMMIT = "8c7e9cfe3e512a93a5850d2bdf1df28677c87ad4"
    DOCUMENTATION_URL = "https://bioconductor.org/packages/release/bioc/html/xcms.html"
    SOURCE_URL = "https://git.bioconductor.org/packages/xcms"
    UPSTREAM_SOURCE = "DESCRIPTION; R/DataClasses.R; R/XcmsExperiment.R; vignettes/xcms.Rmd"
    CITATION_DOIS = ["10.1186/1471-2105-9-504", "10.1021/acs.analchem.7b00671"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    EXIT_SEMANTICS = (
        "XCMS stops on unreadable spectra, invalid centWave parameters, or failed peak grouping; "
        "BioNodulo propagates that Rscript exit and requires all three artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mzml_files": (
                    "FILE",
                    {"description": "One or more centroided mzML/mzXML files"},
                ),
            },
            "optional": {
                "ppm": ("FLOAT", {"default": 25.0, "min": 0.0}),
                "peakwidth_min": ("FLOAT", {"default": 20.0, "min": 0.0}),
                "peakwidth_max": ("FLOAT", {"default": 50.0, "min": 0.0}),
                "snthresh": ("FLOAT", {"default": 10.0, "min": 0.0}),
                "prefilter_k": ("INT", {"default": 3, "min": 0}),
                "prefilter_i": ("FLOAT", {"default": 100.0, "min": 0.0}),
                "noise": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "output_name": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not split_paths(inputs.get("mzml_files")):
            return "Input 'mzml_files' must contain at least one path"
        for key, default in (
            ("ppm", 25.0),
            ("peakwidth_min", 20.0),
            ("peakwidth_max", 50.0),
            ("snthresh", 10.0),
            ("prefilter_i", 100.0),
            ("noise", 0.0),
        ):
            validation = validate_number(inputs.get(key, default), key, minimum=0)
            if validation is not True:
                return validation
        validation = validate_number(inputs.get("prefilter_k", 3), "prefilter_k", minimum=0, integer=True)
        if validation is not True:
            return validation
        validation = validate_number(inputs.get("threads", 1), "threads", minimum=1, maximum=64, integer=True)
        if validation is not True:
            return validation
        if inputs.get("peakwidth_min", 20.0) > inputs.get("peakwidth_max", 50.0):
            return "Input 'peakwidth_min' must not exceed 'peakwidth_max'"
        return True

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        files = split_paths(inputs.get("mzml_files"))
        source_stem = safe_output_stem(files[0] if files else "xcms", "xcms")
        return safe_output_stem(inputs.get("output_name"), source_stem)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        out_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "xcms_peak_detection.R"
        stem = cls.output_stem(inputs, "xcms")
        feature_table = out_dir / f"{stem}.feature_table.tsv"
        xcms_object = out_dir / f"{stem}.xcms.rds"
        summary_json = out_dir / f"{stem}.summary.json"
        files = split_paths(inputs["mzml_files"])

        script = textwrap.dedent(
            f"""\
            suppressPackageStartupMessages({{
                library("xcms")
                library("MsExperiment")
                library("BiocParallel")
                library("jsonlite")
                library("readr")
            }})

            files <- {r_string_vector(files)}
            missing <- files[!file.exists(files)]
            if (length(missing) > 0) stop(paste("Input file(s) not found:", paste(missing, collapse = ", ")))
            raw_data <- readMsExperiment(spectraFiles = files)
            sp <- spectra(raw_data)
            ord <- order(dataOrigin(sp), rtime(sp))
            spectra(raw_data) <- sp[ord]
            param <- CentWaveParam(
                ppm = {inputs.get('ppm', 25.0)},
                peakwidth = c({inputs.get('peakwidth_min', 20.0)}, {inputs.get('peakwidth_max', 50.0)}),
                snthresh = {inputs.get('snthresh', 10.0)},
                prefilter = c({inputs.get('prefilter_k', 3)}, {inputs.get('prefilter_i', 100.0)}),
                noise = {inputs.get('noise', 0.0)}
            )
            workers <- MulticoreParam(workers = {inputs.get('threads', 1)})
            xdata <- findChromPeaks(raw_data, param = param, BPPARAM = workers)
            sample_groups <- rep(1L, nrow(sampleData(xdata)))
            xdata <- groupChromPeaks(xdata, param = PeakDensityParam(sampleGroups = sample_groups))
            feature_values <- featureValues(xdata, value = "into")
            feature_table <- data.frame(feature_id = rownames(feature_values), feature_values, check.names = FALSE)
            write_tsv(feature_table, {r_string(feature_table.as_posix())})
            saveRDS(xdata, {r_string(xcms_object.as_posix())})
            summary <- list(
                input_files = files,
                file_count = length(files),
                peak_count = nrow(chromPeaks(xdata)),
                feature_count = nrow(feature_values),
                ppm = {inputs.get('ppm', 25.0)},
                peakwidth = c({inputs.get('peakwidth_min', 20.0)}, {inputs.get('peakwidth_max', 50.0)}),
                snthresh = {inputs.get('snthresh', 10.0)},
                feature_table = {r_string(feature_table.as_posix())},
                xcms_object = {r_string(xcms_object.as_posix())}
            )
            write_json(summary, {r_string(summary_json.as_posix())}, pretty = TRUE, auto_unbox = TRUE)
            """
        )
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]
