"""Metabolomics workflow nodes."""
from __future__ import annotations

import re
import textwrap
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode


def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub(r"\.(gz|bz2|xz|zip)$", "", stem)
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", stem).strip("._-")
    return stem or fallback


def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[\n,]+", text) if part.strip()]


def _r_string_vector(values: list[str]) -> str:
    quoted = [value.replace("\\", "\\\\").replace('"', '\\"') for value in values]
    return "c(" + ", ".join(f'"{value}"' for value in quoted) + ")"


class XCMSPeakDetectionNode(CommandNode):
    """Detect chromatographic peaks in LC-MS data with XCMS."""

    NODE_ID = "xcms_peak_detection"
    DISPLAY_NAME = "XCMS Peak Detection"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Detect LC-MS chromatographic peaks with XCMS centWave and export feature intensities."
    SEARCH_ALIASES = ["xcms", "metabolomics", "lc-ms", "centwave", "peak detection", "mass spectrometry"]
    RETURN_TYPES = ("TSV", "FILE", "JSON")
    RETURN_NAMES = ("feature_table", "xcms_object", "summary")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-xcms", "r-jsonlite", "r-readr"]
    REQUIRED_R_PACKAGES = ["xcms", "jsonlite", "readr"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/xcms/"
    VERSION = "3.20"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "xcms_peak_detection.R"
        files = _split_path_list(inputs.get("mzml_files"))
        fallback_stem = _safe_output_stem(files[0] if files else "xcms", "xcms")
        stem = _safe_output_stem(inputs.get("output_name"), fallback_stem)
        feature_table = out_dir / f"{stem}.feature_table.tsv"
        xcms_object = out_dir / f"{stem}.xcms.rds"
        summary_json = out_dir / f"{stem}.summary.json"

        script = textwrap.dedent(f"""\
            if (!requireNamespace("xcms", quietly = TRUE)) stop("Package 'xcms' is required but not installed.")
            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")
            if (!requireNamespace("BiocParallel", quietly = TRUE)) stop("Package 'BiocParallel' is required but not installed.")
            library("xcms")
            library("jsonlite")
            library("readr")
            library("BiocParallel")

            files <- {_r_string_vector(files)}
            if (length(files) == 0) stop("At least one mzML/mzXML file is required.")
            missing <- files[!file.exists(files)]
            if (length(missing) > 0) stop(paste("Input file(s) not found:", paste(missing, collapse = ", ")))

            raw_data <- readMSData(files, mode = "onDisk")
            param <- CentWaveParam(
                ppm = {inputs.get("ppm", 25)},
                peakwidth = c({inputs.get("peakwidth_min", 20)}, {inputs.get("peakwidth_max", 50)}),
                snthresh = {inputs.get("snthresh", 10)},
                prefilter = c({inputs.get("prefilter_k", 3)}, {inputs.get("prefilter_i", 100)}),
                noise = {inputs.get("noise", 0)}
            )
            xdata <- findChromPeaks(raw_data, param = param, BPPARAM = MulticoreParam(workers = {inputs.get("threads", 1)}))
            feature_values <- featureValues(xdata, value = "into")
            chrom_peaks <- as.data.frame(chromPeaks(xdata))
            peak_count <- nrow(chrom_peaks)

            feature_table <- data.frame(feature_id = rownames(feature_values), feature_values, check.names = FALSE)
            write_tsv(feature_table, "{feature_table.as_posix()}")
            saveRDS(xdata, "{xcms_object.as_posix()}")

            summary <- list(
                input_files = files,
                file_count = length(files),
                peak_count = peak_count,
                feature_count = nrow(feature_values),
                ppm = {inputs.get("ppm", 25)},
                peakwidth = c({inputs.get("peakwidth_min", 20)}, {inputs.get("peakwidth_max", 50)}),
                snthresh = {inputs.get("snthresh", 10)},
                feature_table = "{feature_table.as_posix()}",
                xcms_object = "{xcms_object.as_posix()}"
            )
            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)
        """)
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        files = _split_path_list(inputs.get("mzml_files"))
        fallback_stem = _safe_output_stem(files[0] if files else "xcms", "xcms")
        stem = _safe_output_stem(inputs.get("output_name"), fallback_stem)
        return [
            node_out / f"{stem}.feature_table.tsv",
            node_out / f"{stem}.xcms.rds",
            node_out / f"{stem}.summary.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "mzml_files": ("FILE", {"description": "mzML/mzXML LC-MS files; accepts a file list or comma/newline-separated paths"}),
            },
            "optional": {
                "ppm": ("FLOAT", {"default": 25.0, "min": 1.0, "description": "Mass accuracy in ppm"}),
                "peakwidth_min": ("FLOAT", {"default": 20.0, "min": 0.0}),
                "peakwidth_max": ("FLOAT", {"default": 50.0, "min": 0.0}),
                "snthresh": ("FLOAT", {"default": 10.0, "min": 0.0}),
                "prefilter_k": ("INT", {"default": 3, "min": 0}),
                "prefilter_i": ("FLOAT", {"default": 100.0, "min": 0.0}),
                "noise": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class SiriusFormulaIDNode(CommandNode):
    """Identify molecular formulas and structures from MS/MS data with SIRIUS."""

    NODE_ID = "sirius_formula_id"
    DISPLAY_NAME = "SIRIUS Formula ID"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Identify molecular formulas and optional structures from MS/MS spectra using SIRIUS."
    SEARCH_ALIASES = ["sirius", "csi:fingerid", "formula identification", "metabolomics", "ms/ms", "canopus"]
    RETURN_TYPES = ("DIRECTORY", "TSV", "JSON")
    RETURN_NAMES = ("results_dir", "summary", "metadata")
    REQUIRED_EXECUTABLES = ["sirius"]
    REQUIRED_CONDA_PACKAGES = ["sirius"]
    DOCUMENTATION_URL = "https://bio.informatik.uni-jena.de/software/sirius/"
    VERSION = "5.8"
    SHELL = True

    SUMMARY_SCRIPT = (
        "import json, sys; "
        "from pathlib import Path; "
        "results=Path(sys.argv[1]); summary=Path(sys.argv[2]); metadata=Path(sys.argv[3]); "
        "spectra=sys.argv[4]; database=sys.argv[5]; profile=sys.argv[6]; ionization=sys.argv[7]; "
        "candidates=sorted(results.rglob('*.tsv')) + sorted(results.rglob('*.csv')); "
        "summary.parent.mkdir(parents=True, exist_ok=True); metadata.parent.mkdir(parents=True, exist_ok=True); "
        "summary.write_text('source_file\\tpath\\n' + ''.join(f'{p.name}\\t{p}\\n' for p in candidates), encoding='utf-8'); "
        "metadata.write_text(json.dumps({'spectra_file': spectra, 'database': database, 'profile': profile, "
        "'ionization': ionization, 'results_dir': str(results), 'candidate_tables': [str(p) for p in candidates]}, "
        "indent=2, sort_keys=True) + '\\n', encoding='utf-8')"
    )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        spectra_file = str(inputs.get("spectra_file", ""))
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(spectra_file, "sirius"))
        results_dir = out_dir / stem
        summary_tsv = out_dir / f"{stem}.summary.tsv"
        metadata_json = out_dir / f"{stem}.metadata.json"
        database = str(inputs.get("database", "") or "")
        profile = str(inputs.get("profile", "") or "")
        ionization = str(inputs.get("ionization", "") or "")

        cmd = [
            "sirius",
            "-i",
            spectra_file,
            "-o",
            str(results_dir),
        ]
        if database:
            cmd.extend(["--database", database])
        if profile:
            cmd.extend(["--profile", profile])
        if ionization:
            cmd.extend(["--ionization", ionization])
        if inputs.get("ppm_max"):
            cmd.extend(["--ppm-max", str(inputs["ppm_max"])])
        cmd.extend(["--cores", str(inputs.get("cores", 1))])
        cmd.append("formula")
        if inputs.get("run_zodiac", True):
            cmd.append("zodiac")
        if inputs.get("run_structure", False):
            cmd.append("structure")
        if inputs.get("run_canopus", False):
            cmd.append("canopus")
        cmd.extend([
            "&&",
            "python",
            "-c",
            cls.SUMMARY_SCRIPT,
            str(results_dir),
            str(summary_tsv),
            str(metadata_json),
            spectra_file,
            database,
            profile,
            ionization,
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("spectra_file"), "sirius"))
        return [
            node_out / stem,
            node_out / f"{stem}.summary.tsv",
            node_out / f"{stem}.metadata.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "spectra_file": ("FILE", {"description": "MS/MS input file for SIRIUS (.ms, .mgf, .mzML)"}),
            },
            "optional": {
                "database": ("STRING", {"default": "ALL", "description": "SIRIUS structure database, e.g. ALL"}),
                "profile": ("STRING", {"default": "", "description": "Instrument/profile preset"}),
                "ionization": ("STRING", {"default": "", "description": "Ion/adduct, e.g. [M+H]+"}),
                "ppm_max": ("FLOAT", {"default": 0.0, "min": 0.0, "description": "Optional maximum precursor ppm error"}),
                "cores": ("INT", {"default": 1, "min": 1, "max": 64}),
                "run_zodiac": ("BOOLEAN", {"default": True}),
                "run_structure": ("BOOLEAN", {"default": False}),
                "run_canopus": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
