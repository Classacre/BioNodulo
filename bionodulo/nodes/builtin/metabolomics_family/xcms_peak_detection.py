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
    """Detect LC-MS chromatographic peaks with centWave."""

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
    RETURN_NAMES = ("chrom_peaks", "xcms_object", "summary")
    OUTPUT_SUFFIXES = (".chrom_peaks.tsv", ".xcms.rds", ".summary.json")
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
    UPSTREAM_SOURCE = (
        "DESCRIPTION; R/DataClasses.R; R/XcmsExperiment.R; "
        "R/MsExperiment-functions.R; vignettes/xcms.Rmd"
    )
    CITATION_DOIS = ["10.1186/1471-2105-9-504", "10.1021/acs.analchem.7b00671"]
    CITATION_URLS = [f"https://doi.org/{doi}" for doi in CITATION_DOIS]
    EXIT_SEMANTICS = (
        "XCMS stops on unreadable spectra or invalid centWave parameters; BioNodulo also fails "
        "closed when centWave detects no chromatographic peaks and requires all three artifacts."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mzml_files": (
                    "FILE",
                    {
                        "multiple": True,
                        "description": (
                            "One or more ordered centroided LC-MS files supported by "
                            "MsExperiment; preserve this order for downstream raw_files inputs"
                        ),
                    },
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
        chrom_peaks_table = out_dir / f"{stem}.chrom_peaks.tsv"
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
            if (nrow(sampleData(raw_data)) != length(files)) {{
                stop("MsExperiment sample count does not match the ordered input files.")
            }}
            sampleData(raw_data)$bionodulo_input_index <- seq_along(files)
            # centWave requires spectra sorted by retention time WITHIN each
            # file; an mzML that stores them in another order aborts the run with
            # "Spectra are not ordered by retention time". Order by dataOrigin
            # first so files stay contiguous — a global rtime sort would
            # interleave samples and silently corrupt per-sample peak tables.
            spectra_set <- spectra(raw_data)
            spectra_order <- order(dataOrigin(spectra_set), rtime(spectra_set))
            if (is.unsorted(spectra_order)) {{
                spectra(raw_data) <- spectra_set[spectra_order]
            }}
            param <- CentWaveParam(
                ppm = {inputs.get('ppm', 25.0)},
                peakwidth = c({inputs.get('peakwidth_min', 20.0)}, {inputs.get('peakwidth_max', 50.0)}),
                snthresh = {inputs.get('snthresh', 10.0)},
                prefilter = c({inputs.get('prefilter_k', 3)}, {inputs.get('prefilter_i', 100.0)}),
                noise = {inputs.get('noise', 0.0)}
            )
            workers <- MulticoreParam(workers = {inputs.get('threads', 1)})
            xdata <- findChromPeaks(raw_data, param = param, BPPARAM = workers)
            peak_table <- as.data.frame(chromPeaks(xdata))
            if (nrow(peak_table) == 0) stop("XCMS centWave detected no chromatographic peaks.")
            peak_table <- data.frame(chrom_peak_id = rownames(peak_table), peak_table, check.names = FALSE)
            write_tsv(peak_table, {r_string(chrom_peaks_table.as_posix())})
            saveRDS(xdata, {r_string(xcms_object.as_posix())})
            summary <- list(
                input_files = files,
                file_count = length(files),
                peak_count = nrow(peak_table),
                ppm = {inputs.get('ppm', 25.0)},
                peakwidth = c({inputs.get('peakwidth_min', 20.0)}, {inputs.get('peakwidth_max', 50.0)}),
                snthresh = {inputs.get('snthresh', 10.0)},
                chrom_peaks = {r_string(chrom_peaks_table.as_posix())},
                xcms_object = {r_string(xcms_object.as_posix())}
            )
            write_json(summary, {r_string(summary_json.as_posix())}, pretty = TRUE, auto_unbox = TRUE)
            """
        )
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]
