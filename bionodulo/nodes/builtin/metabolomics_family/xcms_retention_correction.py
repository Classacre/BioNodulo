"""XCMS 4.8.0 obiwarp alignment, correspondence, and gap filling."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import (
    MetabolomicsCommandNode,
    path_value,
    r_group_vector,
    r_string,
    r_string_vector,
    safe_output_stem,
    split_paths,
    split_values,
    validate_choice,
    validate_number,
)


class XCMSRetentionCorrectionNode(MetabolomicsCommandNode):
    """Align retention times, regroup peaks, and fill missing features."""

    NODE_ID = "xcms_retention_correction"
    DISPLAY_NAME = "XCMS Retention Time Correction"
    DESCRIPTION = "Align, regroup, and gap-fill XCMS 4.8.0 LC-MS features with obiwarp."
    SEARCH_ALIASES = ["BioNodulo builtin", "XCMS", "obiwarp", "retention time", "alignment"]
    RETURN_TYPES = ("TSV", "FILE", "JSON")
    RETURN_NAMES = ("aligned_feature_table", "aligned_xcms_object", "summary")
    OUTPUT_SUFFIXES = (".aligned_feature_table.tsv", ".aligned.xcms.rds", ".alignment.summary.json")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = [
        "r-base",
        "bioconductor-xcms",
        "bioconductor-biocparallel",
        "r-jsonlite",
        "r-readr",
    ]
    REQUIRED_R_PACKAGES = ["xcms", "BiocParallel", "jsonlite", "readr"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "r-base": "4.5.*",
        "bioconductor-xcms": "4.8.0",
        "bioconductor-biocparallel": "1.44.0",
        "r-jsonlite": "2.0.0",
        "r-readr": "2.2.0",
    }
    VERSION = "4.8.0"
    GIT_URL = "https://git.bioconductor.org/packages/xcms"
    GIT_COMMIT = "8c7e9cfe3e512a93a5850d2bdf1df28677c87ad4"
    DOCUMENTATION_URL = "https://bioconductor.org/packages/release/bioc/html/xcms.html"
    SOURCE_URL = "https://git.bioconductor.org/packages/xcms"
    UPSTREAM_SOURCE = "R/DataClasses.R; R/XcmsExperiment.R; vignettes/xcms.Rmd"
    CITATION_DOIS = ["10.1021/acs.analchem.7b00671"]
    CITATION_URLS = ["https://doi.org/10.1021/acs.analchem.7b00671"]
    EXIT_SEMANTICS = (
        "XCMS stops when the RDS is not an XcmsExperiment, the ordered raw files cannot be "
        "rebound, obiwarp cannot align the samples, or correspondence/gap filling fails; "
        "BioNodulo also requires a non-empty feature table and all three artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "xcms_object": ("FILE", {"description": "XcmsExperiment RDS from peak detection"}),
                "raw_files": (
                    "FILE",
                    {
                        "multiple": True,
                        "description": (
                            "The original staged LC-MS files in exactly the same order supplied "
                            "to XCMS Peak Detection; required because the RDS stores on-disk spectra"
                        ),
                    },
                ),
            },
            "optional": {
                "method": ("STRING", {"default": "obiwarp", "options": ["obiwarp"]}),
                "bin_size": ("FLOAT", {"default": 1.0, "min": 0.0}),
                "bw": ("FLOAT", {"default": 30.0, "min": 0.0}),
                "min_fraction": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
                "sample_groups": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": (
                            "One group label per raw file; use the reserved value NA to exclude a "
                            "sample from correspondence grouping"
                        ),
                    },
                ),
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
        if not path_value(inputs.get("xcms_object")):
            return "Input 'xcms_object' must be a non-empty path-like value"
        raw_files = split_paths(inputs.get("raw_files"))
        if not raw_files:
            return "Input 'raw_files' must contain the original ordered LC-MS paths"
        sample_groups = split_values(inputs.get("sample_groups"))
        if sample_groups and len(sample_groups) != len(raw_files):
            return "Input 'sample_groups' must contain exactly one value per raw file"
        validation = validate_choice(inputs.get("method", "obiwarp"), "method", ("obiwarp",))
        if validation is not True:
            return validation
        for key, default, maximum in (
            ("bin_size", 1.0, None),
            ("bw", 30.0, None),
            ("min_fraction", 0.5, 1.0),
        ):
            validation = validate_number(inputs.get(key, default), key, minimum=0, maximum=maximum)
            if validation is not True:
                return validation
        return validate_number(inputs.get("threads", 1), "threads", minimum=1, maximum=64, integer=True)

    @classmethod
    def output_stem(cls, inputs: dict[str, Any], fallback: str) -> str:
        source_stem = safe_output_stem(inputs.get("xcms_object"), "xcms")
        return safe_output_stem(inputs.get("output_name"), source_stem)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        out_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "xcms_retention_correction.R"
        stem = cls.output_stem(inputs, "xcms")
        feature_table = out_dir / f"{stem}.aligned_feature_table.tsv"
        aligned_object = out_dir / f"{stem}.aligned.xcms.rds"
        summary_json = out_dir / f"{stem}.alignment.summary.json"
        xcms_object = path_value(inputs["xcms_object"])
        raw_files = split_paths(inputs["raw_files"])
        sample_groups = split_values(inputs.get("sample_groups"))
        if sample_groups:
            sample_group_block = textwrap.dedent(
                f"""\
                input_sample_groups <- {r_group_vector(sample_groups)}
                sample_groups <- input_sample_groups[sample_identity]
                if (length(sample_groups) != nrow(sampleData(xdata))) stop("sample_groups length must match sample count.")
                """
            ).strip()
        else:
            sample_group_block = "sample_groups <- rep(1L, nrow(sampleData(xdata)))"

        script = textwrap.dedent(
            f"""\
            suppressPackageStartupMessages({{
                library("xcms")
                library("BiocParallel")
                library("jsonlite")
                library("readr")
            }})

            raw_files <- {r_string_vector(raw_files)}
            missing <- raw_files[!file.exists(raw_files)]
            if (length(missing) > 0) stop(paste("Raw LC-MS file(s) not found:", paste(missing, collapse = ", ")))
            xdata <- readRDS({r_string(xcms_object)})
            if (!is(xdata, "XcmsExperiment")) {{
                stop("XCMS Retention Time Correction requires an XcmsExperiment RDS object.")
            }}
            if (nrow(sampleData(xdata)) != length(raw_files)) {{
                stop("raw_files length must match the XcmsExperiment sample count.")
            }}
            if (!("bionodulo_input_index" %in% colnames(sampleData(xdata)))) {{
                stop("XcmsExperiment lacks the explicit BioNodulo sample identity required for raw-file rebinding.")
            }}
            sample_identity <- suppressWarnings(as.integer(as.character(sampleData(xdata)$bionodulo_input_index)))
            expected_identity <- seq_along(raw_files)
            if (length(sample_identity) != length(expected_identity) ||
                anyNA(sample_identity) || anyDuplicated(sample_identity) ||
                !setequal(sample_identity, expected_identity)) {{
                stop("XcmsExperiment has an invalid BioNodulo sample identity mapping.")
            }}
            spectra_links <- xdata@sampleDataLinks[["spectra"]]
            if (is.null(spectra_links) || nrow(spectra_links) != length(xdata@spectra)) {{
                stop("XcmsExperiment spectra-to-sample links are missing or incomplete.")
            }}
            spectrum_sample <- as.integer(spectra_links[, 1L])
            if (anyNA(spectrum_sample) || any(spectrum_sample < 1L) ||
                any(spectrum_sample > length(sample_identity))) {{
                stop("XcmsExperiment spectra-to-sample links contain invalid sample indices.")
            }}
            sample_storage <- raw_files[sample_identity]
            xdata@spectra$dataStorage <- sample_storage[spectrum_sample]
            workers <- MulticoreParam(workers = {inputs.get('threads', 1)})
            xdata <- adjustRtime(xdata, param = ObiwarpParam(binSize = {inputs.get('bin_size', 1.0)}), BPPARAM = workers)
            {sample_group_block}
            group_param <- PeakDensityParam(
                sampleGroups = sample_groups,
                bw = {inputs.get('bw', 30.0)},
                minFraction = {inputs.get('min_fraction', 0.5)}
            )
            xdata <- groupChromPeaks(xdata, param = group_param)
            xdata <- fillChromPeaks(xdata, param = ChromPeakAreaParam(), BPPARAM = workers)
            feature_definitions <- as.data.frame(featureDefinitions(xdata))
            feature_values <- as.data.frame(featureValues(xdata, value = "into"))
            if (nrow(feature_definitions) == 0) stop("XCMS correspondence produced no features.")
            required_definition_columns <- c("mzmed", "mzmin", "mzmax", "rtmed", "rtmin", "rtmax")
            if (!all(required_definition_columns %in% colnames(feature_definitions))) {{
                stop("XCMS feature definitions are missing required m/z or retention-time columns.")
            }}
            value_order <- match(rownames(feature_definitions), rownames(feature_values))
            if (anyNA(value_order)) stop("XCMS feature definitions and intensity rows do not align.")
            feature_values <- feature_values[value_order, , drop = FALSE]
            scalar_columns <- !vapply(feature_definitions, is.list, logical(1))
            feature_definitions <- feature_definitions[, scalar_columns, drop = FALSE]
            feature_table <- data.frame(
                feature_id = rownames(feature_definitions),
                feature_definitions,
                feature_values,
                check.names = FALSE
            )
            write_tsv(feature_table, {r_string(feature_table.as_posix())})
            saveRDS(xdata, {r_string(aligned_object.as_posix())})
            summary <- list(
                input_xcms_object = {r_string(xcms_object)},
                raw_files = raw_files,
                sample_count = nrow(sampleData(xdata)),
                peak_count = nrow(chromPeaks(xdata)),
                feature_count = nrow(feature_values),
                method = "obiwarp",
                bin_size = {inputs.get('bin_size', 1.0)},
                bw = {inputs.get('bw', 30.0)},
                min_fraction = {inputs.get('min_fraction', 0.5)},
                sample_groups = sample_groups,
                aligned_feature_table = {r_string(feature_table.as_posix())},
                aligned_xcms_object = {r_string(aligned_object.as_posix())}
            )
            write_json(summary, {r_string(summary_json.as_posix())}, pretty = TRUE, auto_unbox = TRUE)
            """
        )
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]
