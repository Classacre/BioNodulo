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


def _r_string(value: Any) -> str:
    text = str(value or "")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _r_bool(value: Any) -> str:
    return "TRUE" if bool(value) else "FALSE"


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
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-xcms", "bioconductor-biocparallel", "r-jsonlite", "r-readr"]
    REQUIRED_R_PACKAGES = ["xcms", "jsonlite", "readr", "BiocParallel"]
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


class XCMSRetentionCorrectionNode(CommandNode):
    """Correct retention time, align, and fill XCMS chromatographic peaks."""

    NODE_ID = "xcms_retention_correction"
    DISPLAY_NAME = "XCMS Retention Time Correction"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Correct retention time, align grouped peaks, and fill missing LC-MS features with XCMS."
    SEARCH_ALIASES = ["xcms", "metabolomics", "retention time", "obiwarp", "alignment", "fill peaks"]
    RETURN_TYPES = ("TSV", "FILE", "JSON")
    RETURN_NAMES = ("aligned_feature_table", "aligned_xcms_object", "summary")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = [
        "r-base",
        "bioconductor-xcms",
        "bioconductor-biocparallel",
        "r-jsonlite",
        "r-readr",
    ]
    REQUIRED_R_PACKAGES = ["xcms", "BiocParallel", "jsonlite", "readr"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/xcms/"
    VERSION = "3.20"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "xcms_retention_correction.R"
        xcms_object = str(inputs.get("xcms_object", ""))
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(xcms_object, "xcms"))
        feature_table = out_dir / f"{stem}.aligned_feature_table.tsv"
        aligned_object = out_dir / f"{stem}.aligned.xcms.rds"
        summary_json = out_dir / f"{stem}.alignment.summary.json"
        sample_groups = _split_path_list(inputs.get("sample_groups"))
        sample_groups_r = _r_string_vector(sample_groups)

        if str(inputs.get("method", "obiwarp") or "obiwarp") != "obiwarp":
            msg = "XCMS retention correction currently supports only method='obiwarp'."
            raise ValueError(msg)

        sample_group_block = (
            f"sample_groups <- {sample_groups_r}\n"
            '            if (length(sample_groups) != length(fileNames(xdata))) stop("sample_groups length must match the number of samples.")'
            if sample_groups
            else "sample_groups <- rep(1L, length(fileNames(xdata)))"
        )

        script = textwrap.dedent(f"""\
            if (!requireNamespace("xcms", quietly = TRUE)) stop("Package 'xcms' is required but not installed.")
            if (!requireNamespace("BiocParallel", quietly = TRUE)) stop("Package 'BiocParallel' is required but not installed.")
            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")
            library("xcms")
            library("BiocParallel")
            library("jsonlite")
            library("readr")

            xdata <- readRDS("{xcms_object}")
            {sample_group_block}

            adjust_param <- ObiwarpParam(binSize = {inputs.get("bin_size", 1.0)})
            xdata <- adjustRtime(xdata, param = adjust_param, BPPARAM = MulticoreParam(workers = {inputs.get("threads", 1)}))
            group_param <- PeakDensityParam(sampleGroups = sample_groups, bw = {inputs.get("bw", 5.0)}, minFraction = {inputs.get("min_fraction", 0.5)})
            xdata <- groupChromPeaks(xdata, param = group_param)
            xdata <- fillChromPeaks(xdata, BPPARAM = MulticoreParam(workers = {inputs.get("threads", 1)}))
            feature_values <- featureValues(xdata, value = "into")
            chrom_peaks <- as.data.frame(chromPeaks(xdata))

            feature_table <- data.frame(feature_id = rownames(feature_values), feature_values, check.names = FALSE)
            write_tsv(feature_table, "{feature_table.as_posix()}")
            saveRDS(xdata, "{aligned_object.as_posix()}")

            summary <- list(
                input_xcms_object = "{xcms_object}",
                sample_count = length(fileNames(xdata)),
                peak_count = nrow(chrom_peaks),
                feature_count = nrow(feature_values),
                method = "obiwarp",
                bin_size = {inputs.get("bin_size", 1.0)},
                bw = {inputs.get("bw", 5.0)},
                min_fraction = {inputs.get("min_fraction", 0.5)},
                sample_groups = sample_groups,
                aligned_feature_table = "{feature_table.as_posix()}",
                aligned_xcms_object = "{aligned_object.as_posix()}"
            )
            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)
        """)
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("xcms_object"), "xcms"))
        return [
            node_out / f"{stem}.aligned_feature_table.tsv",
            node_out / f"{stem}.aligned.xcms.rds",
            node_out / f"{stem}.alignment.summary.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "xcms_object": ("FILE", {"description": "XCMS object RDS from XCMS Peak Detection"}),
            },
            "optional": {
                "method": ("STRING", {"default": "obiwarp", "options": ["obiwarp"]}),
                "bin_size": ("FLOAT", {"default": 1.0, "min": 0.0, "description": "Obiwarp bin size"}),
                "bw": ("FLOAT", {"default": 5.0, "min": 0.0, "description": "Peak density bandwidth"}),
                "min_fraction": ("FLOAT", {"default": 0.5, "min": 0.0, "max": 1.0}),
                "sample_groups": (
                    "STRING",
                    {"default": "", "description": "Optional comma/newline sample group labels matching input samples"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CAMERAAnnotationNode(CommandNode):
    """Annotate XCMS peak lists with CAMERA isotope and adduct calls."""

    NODE_ID = "camera_annotation"
    DISPLAY_NAME = "CAMERA Annotation"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Annotate LC-MS peaks with CAMERA pseudospectra, isotope, and adduct assignments."
    SEARCH_ALIASES = ["camera", "metabolomics", "lc-ms", "peak annotation", "adducts", "isotopes"]
    RETURN_TYPES = ("TSV", "FILE", "JSON")
    RETURN_NAMES = ("annotated_peaklist", "camera_object", "summary")
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = [
        "r-base",
        "bioconductor-camera",
        "bioconductor-xcms",
        "r-jsonlite",
        "r-readr",
    ]
    REQUIRED_R_PACKAGES = ["CAMERA", "xcms", "jsonlite", "readr"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/CAMERA/"
    VERSION = "1.66"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "camera_annotation.R"
        xcms_object = str(inputs.get("xcms_object", ""))
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(xcms_object, "camera"))
        annotated_peaklist = out_dir / f"{stem}.camera_peaklist.tsv"
        camera_object = out_dir / f"{stem}.camera.rds"
        summary_json = out_dir / f"{stem}.camera.summary.json"
        polarity = str(inputs.get("polarity", "positive") or "positive")
        intval = str(inputs.get("intval", "into") or "into")
        run_group_corr = inputs.get("run_group_corr", True)
        run_adducts = inputs.get("run_adducts", True)

        group_corr_step = (
            "xsa <- groupCorr("
            f"xsa, cor_eic_th = {inputs.get('cor_eic_th', 0.75)}, pval = {inputs.get('pval', 0.05)}, "
            f'calcIso = TRUE, intval = "{intval}")'
            if run_group_corr
            else ""
        )
        adduct_step = (
            "xsa <- findAdducts("
            f"xsa, ppm = {inputs.get('adduct_ppm', 5)}, mzabs = {inputs.get('adduct_mzabs', 0.015)}, "
            f'polarity = "{polarity}", intval = "{intval}")'
            if run_adducts
            else ""
        )

        script = textwrap.dedent(f"""\
            if (!requireNamespace("CAMERA", quietly = TRUE)) stop("Package 'CAMERA' is required but not installed.")
            if (!requireNamespace("xcms", quietly = TRUE)) stop("Package 'xcms' is required but not installed.")
            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")
            library("CAMERA")
            library("xcms")
            library("jsonlite")
            library("readr")

            xdata <- readRDS("{xcms_object}")
            if (is(xdata, "xcmsSet")) {{
                xset <- xdata
            }} else if (is(xdata, "XCMSnExp")) {{
                if (any(msLevel(xdata) > 1)) stop("CAMERA conversion from XCMSnExp to xcmsSet supports MS1-only objects. Use an MS1-only XCMS object or a legacy xcmsSet.")
                xset <- as(xdata, "xcmsSet")
            }} else {{
                stop("CAMERA Annotation requires an xcmsSet or XCMSnExp object saved as RDS.")
            }}

            xsa <- xsAnnotate(xset, polarity = "{polarity}")
            xsa <- groupFWHM(xsa, sigma = {inputs.get("sigma", 6)}, perfwhm = {inputs.get("perfwhm", 0.6)}, intval = "{intval}")
            xsa <- findIsotopes(xsa, maxcharge = {inputs.get("maxcharge", 3)}, maxiso = {inputs.get("maxiso", 4)}, ppm = {inputs.get("isotope_ppm", 5)}, mzabs = {inputs.get("isotope_mzabs", 0.01)}, intval = "{intval}")
            {group_corr_step}
            {adduct_step}
            peaklist <- as.data.frame(getPeaklist(xsa, intval = "{intval}"))
            write_tsv(peaklist, "{annotated_peaklist.as_posix()}")
            saveRDS(xsa, "{camera_object.as_posix()}")

            summary <- list(
                input_xcms_object = "{xcms_object}",
                annotated_peaklist = "{annotated_peaklist.as_posix()}",
                camera_object = "{camera_object.as_posix()}",
                peak_count = nrow(peaklist),
                polarity = "{polarity}",
                intval = "{intval}",
                run_group_corr = {str(bool(run_group_corr)).upper()},
                run_adducts = {str(bool(run_adducts)).upper()}
            )
            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)
        """)
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("xcms_object"), "camera"))
        return [
            node_out / f"{stem}.camera_peaklist.tsv",
            node_out / f"{stem}.camera.rds",
            node_out / f"{stem}.camera.summary.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "xcms_object": ("FILE", {"description": "XCMS RDS object from retention correction/alignment"}),
            },
            "optional": {
                "polarity": ("STRING", {"default": "positive", "options": ["positive", "negative"]}),
                "perfwhm": ("FLOAT", {"default": 0.6, "min": 0.0}),
                "sigma": ("FLOAT", {"default": 6.0, "min": 0.0}),
                "maxcharge": ("INT", {"default": 3, "min": 1}),
                "maxiso": ("INT", {"default": 4, "min": 1}),
                "isotope_ppm": ("FLOAT", {"default": 5.0, "min": 0.0}),
                "isotope_mzabs": ("FLOAT", {"default": 0.01, "min": 0.0}),
                "cor_eic_th": ("FLOAT", {"default": 0.75, "min": 0.0, "max": 1.0}),
                "pval": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "run_group_corr": ("BOOLEAN", {"default": True}),
                "run_adducts": ("BOOLEAN", {"default": True}),
                "adduct_ppm": ("FLOAT", {"default": 5.0, "min": 0.0}),
                "adduct_mzabs": ("FLOAT", {"default": 0.015, "min": 0.0}),
                "intval": ("STRING", {"default": "into", "options": ["into", "maxo", "intb"]}),
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


class MZmineBatchProcessingNode(CommandNode):
    """Run an MZmine batch workflow from the command-line interface."""

    NODE_ID = "mzmine_batch_processing"
    DISPLAY_NAME = "MZmine Batch Processing"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Run an MZmine batch workflow for LC-MS preprocessing and export steps."
    SEARCH_ALIASES = ["mzmine", "metabolomics", "lc-ms", "batch", "peak detection", "feature finding"]
    RETURN_TYPES = ("DIRECTORY", "JSON")
    RETURN_NAMES = ("results_dir", "metadata")
    REQUIRED_EXECUTABLES = ["mzmine"]
    REQUIRED_CONDA_PACKAGES = ["mzmine"]
    DOCUMENTATION_URL = "https://mzmine.github.io/mzmine_documentation/commandline_tool.html"
    VERSION = "4.7"
    SHELL = True

    METADATA_SCRIPT = (
        "import json, sys; "
        "from pathlib import Path; "
        "results=Path(sys.argv[1]); metadata=Path(sys.argv[2]); batch=sys.argv[3]; "
        "inputs=sys.argv[4].split('\\n') if sys.argv[4] else []; user=sys.argv[5]; prefs=sys.argv[6]; "
        "threads=int(sys.argv[7]) if sys.argv[7] else None; memory=sys.argv[8]; temp=sys.argv[9]; "
        "ignore=sys.argv[10].lower() == 'true'; "
        "metadata.parent.mkdir(parents=True, exist_ok=True); results.mkdir(parents=True, exist_ok=True); "
        "metadata.write_text(json.dumps({'batch_file': batch, 'input_files': inputs, 'user_file': user, "
        "'preferences_file': prefs, 'threads': threads, 'memory_mode': memory, 'temp_dir': temp, "
        "'ignore_parameter_warnings': ignore, 'results_dir': str(results)}, indent=2, sort_keys=True) + '\\n', "
        "encoding='utf-8')"
    )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        batch_file = str(inputs.get("batch_file", ""))
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(batch_file, "mzmine"))
        results_dir = out_dir / stem
        metadata_json = out_dir / f"{stem}.metadata.json"
        input_files = _split_path_list(inputs.get("input_files"))
        input_list_file = out_dir / f"{stem}.input_files.txt"
        user_file = str(inputs.get("user_file", "") or "")
        preferences_file = str(inputs.get("preferences_file", "") or "")
        threads = inputs.get("threads", 1)
        memory_mode = str(inputs.get("memory_mode", "") or "")
        temp_dir = str(inputs.get("temp_dir", "") or "")
        ignore_warnings = bool(inputs.get("ignore_parameter_warnings", False))

        cmd = ["mzmine"]
        if user_file:
            cmd.extend(["-user", user_file])
        cmd.extend(["-batch", batch_file])
        if input_files:
            input_list_file.write_text("\n".join(input_files) + "\n", encoding="utf-8")
            cmd.extend(["-input", str(input_list_file)])
        cmd.extend(["-output", str(results_dir / stem)])
        if temp_dir:
            cmd.extend(["-temp", temp_dir])
        if preferences_file:
            cmd.extend(["-pref", preferences_file])
        if memory_mode:
            cmd.extend(["-memory", memory_mode])
        cmd.extend(["-threads", str(threads)])
        if ignore_warnings:
            cmd.append("-ignore-parameter-warnings")
        cmd.extend([
            "&&",
            "python",
            "-c",
            cls.METADATA_SCRIPT,
            str(results_dir),
            str(metadata_json),
            batch_file,
            "\n".join(input_files),
            user_file,
            preferences_file,
            str(threads),
            memory_mode,
            temp_dir,
            str(ignore_warnings).lower(),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("batch_file"), "mzmine"))
        return [
            node_out / stem,
            node_out / f"{stem}.metadata.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "batch_file": ("FILE", {"description": "MZmine .mzbatch workflow file"}),
            },
            "optional": {
                "input_files": (
                    "FILE",
                    {"description": "Optional input files passed to MZmine as a generated file list"},
                ),
                "user_file": ("FILE", {"default": "", "description": "Optional MZmine user/login file for offline use"}),
                "preferences_file": ("FILE", {"default": "", "description": "Optional MZmine preferences file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "memory_mode": (
                    "STRING",
                    {"default": "", "options": ["", "none", "all", "features", "raw"], "description": "MZmine memory mode"},
                ),
                "temp_dir": ("DIRECTORY", {"default": "", "description": "Optional MZmine temporary directory"}),
                "ignore_parameter_warnings": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MetaboAnalystStatsNode(CommandNode):
    """Run basic MetaboAnalystR statistical analysis on a prepared concentration table."""

    NODE_ID = "metaboanalyst_stats"
    DISPLAY_NAME = "MetaboAnalyst Stats"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Run MetaboAnalystR normalization, PCA, and two-class t-test statistics on a prepared table."
    SEARCH_ALIASES = [
        "metaboanalyst",
        "metaboanalystr",
        "metabolomics",
        "statistics",
        "pca",
        "normalization",
        "t-test",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "IMAGE", "FILE", "JSON")
    RETURN_NAMES = (
        "normalized_table",
        "pca_scores",
        "pca_loadings",
        "ttest_results",
        "pca_plot",
        "metaboanalyst_object",
        "summary",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "r-jsonlite", "r-readr"]
    REQUIRED_R_PACKAGES = ["MetaboAnalystR", "jsonlite", "readr"]
    DOCUMENTATION_URL = "https://github.com/xia-lab/MetaboAnalystR"
    VERSION = "4.3.0"
    EXPERIMENTAL = True
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / "metaboanalyst_stats.R"
        data_table = str(inputs.get("data_table", ""))
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(data_table, "metaboanalyst"))
        normalized_table = out_dir / f"{stem}.normalized.tsv"
        pca_scores = out_dir / f"{stem}.pca_scores.tsv"
        pca_loadings = out_dir / f"{stem}.pca_loadings.tsv"
        ttest_results = out_dir / f"{stem}.ttest.tsv"
        pca_plot = out_dir / f"{stem}.pca.png"
        rds_file = out_dir / f"{stem}.metaboanalyst.rds"
        summary_json = out_dir / f"{stem}.summary.json"

        table_format = str(inputs.get("format", "rowu") or "rowu")
        label_type = str(inputs.get("label_type", "disc") or "disc")
        row_norm = str(inputs.get("row_norm", "MedianNorm") or "MedianNorm")
        trans_norm = str(inputs.get("trans_norm", "LogNorm") or "LogNorm")
        scale_norm = str(inputs.get("scale_norm", "AutoNorm") or "AutoNorm")
        run_pca = bool(inputs.get("run_pca", True))
        run_ttest = bool(inputs.get("run_ttest", True))
        tt_method = str(inputs.get("tt_method", "welch") or "welch")
        p_threshold = inputs.get("p_threshold", 0.05)
        pval_type = str(inputs.get("pval_type", "fdr") or "fdr")
        paired = bool(inputs.get("paired", False))
        equal_var = bool(inputs.get("equal_var", False))

        pca_block = (
            textwrap.dedent(f"""\
                mSet <- PCA.Anal(mSet)
                PlotPCA2DScore(mSet, "{stem}.pca", "png", dpi = 150, width = 0, pcx = 1, pcy = 2, reg = 0.95, show = 0)
                pca_scores <- as.data.frame(mSet$analSet$pca$x)
                pca_scores <- data.frame(sample = rownames(pca_scores), pca_scores, check.names = FALSE)
                pca_loadings <- as.data.frame(mSet$analSet$pca$rotation)
                pca_loadings <- data.frame(feature = rownames(pca_loadings), pca_loadings, check.names = FALSE)
            """)
            if run_pca
            else textwrap.dedent("""\
                pca_scores <- data.frame()
                pca_loadings <- data.frame()
            """)
        )
        ttest_block = (
            textwrap.dedent(f"""\
                mSet <- Ttests.Anal(mSet, nonpar = FALSE, threshp = {p_threshold}, paired = {_r_bool(paired)}, equal.var = {_r_bool(equal_var)}, pvalType = "{pval_type}", all_results = TRUE, tt.method = "{tt_method}")
                ttest_results <- as.data.frame(mSet$analSet$tt)
                if (nrow(ttest_results) > 0) {{
                    ttest_results <- data.frame(feature = rownames(ttest_results), ttest_results, check.names = FALSE)
                }}
            """)
            if run_ttest
            else "ttest_results <- data.frame()"
        )

        script = textwrap.dedent(f"""\
            if (!requireNamespace("MetaboAnalystR", quietly = TRUE)) stop("Package 'MetaboAnalystR' is required but not installed. Install it from https://github.com/xia-lab/MetaboAnalystR.")
            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")
            library("MetaboAnalystR")
            library("jsonlite")
            library("readr")

            setwd("{out_dir.as_posix()}")
            data_table <- {_r_string(data_table)}
            if (!file.exists(data_table)) stop(paste("Input data table not found:", data_table))

            mSet <- InitDataObjects("conc", "stat", paired = {_r_bool(paired)})
            mSet <- Read.TextData(mSet, {_r_string(data_table)}, format = "{table_format}", lbl.type = "{label_type}")
            mSet <- SanityCheckData(mSet)
            mSet <- ReplaceMin(mSet)
            mSet <- PreparePrenormData(mSet)
            mSet <- Normalization(mSet, rowNorm = "{row_norm}", transNorm = "{trans_norm}", scaleNorm = "{scale_norm}")

            norm_table <- as.data.frame(mSet$dataSet$norm)
            norm_table <- data.frame(feature = rownames(norm_table), norm_table, check.names = FALSE)
            {pca_block}
            {ttest_block}

            if (file.exists("{stem}.pca_dpi150.png")) {{
                file.copy("{stem}.pca_dpi150.png", "{pca_plot.as_posix()}", overwrite = TRUE)
            }} else if (file.exists("{stem}.pca.png")) {{
                file.copy("{stem}.pca.png", "{pca_plot.as_posix()}", overwrite = TRUE)
            }}

            write_tsv(norm_table, "{normalized_table.as_posix()}")
            write_tsv(pca_scores, "{pca_scores.as_posix()}")
            write_tsv(pca_loadings, "{pca_loadings.as_posix()}")
            write_tsv(ttest_results, "{ttest_results.as_posix()}")
            saveRDS(mSet, "{rds_file.as_posix()}")

            summary <- list(
                data_table = data_table,
                format = "{table_format}",
                label_type = "{label_type}",
                row_norm = "{row_norm}",
                trans_norm = "{trans_norm}",
                scale_norm = "{scale_norm}",
                run_pca = {_r_bool(run_pca)},
                run_ttest = {_r_bool(run_ttest)},
                tt_method = "{tt_method}",
                p_threshold = {p_threshold},
                pval_type = "{pval_type}",
                paired = {_r_bool(paired)},
                equal_var = {_r_bool(equal_var)},
                normalized_table = "{normalized_table.as_posix()}",
                pca_scores = "{pca_scores.as_posix()}",
                pca_loadings = "{pca_loadings.as_posix()}",
                ttest_results = "{ttest_results.as_posix()}",
                pca_plot = "{pca_plot.as_posix()}",
                metaboanalyst_object = "{rds_file.as_posix()}"
            )
            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)
        """)
        script_file.write_text(script, encoding="utf-8")
        return ["Rscript", str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), _safe_output_stem(inputs.get("data_table"), "metaboanalyst"))
        return [
            node_out / f"{stem}.normalized.tsv",
            node_out / f"{stem}.pca_scores.tsv",
            node_out / f"{stem}.pca_loadings.tsv",
            node_out / f"{stem}.ttest.tsv",
            node_out / f"{stem}.pca.png",
            node_out / f"{stem}.metaboanalyst.rds",
            node_out / f"{stem}.summary.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data_table": ("FILE", {"description": "MetaboAnalyst-ready concentration table with class labels"}),
            },
            "optional": {
                "format": ("STRING", {"default": "rowu", "options": ["rowu", "colu", "rowp", "colp"]}),
                "label_type": ("STRING", {"default": "disc", "options": ["disc", "cont"]}),
                "row_norm": (
                    "STRING",
                    {"default": "MedianNorm", "options": ["MedianNorm", "SumNorm", "QuantileNorm", "CompNorm", "SpecNorm"]},
                ),
                "trans_norm": ("STRING", {"default": "LogNorm", "options": ["LogNorm", "CrNorm", "NULL"]}),
                "scale_norm": (
                    "STRING",
                    {"default": "AutoNorm", "options": ["AutoNorm", "ParetoNorm", "MeanCenter", "RangeNorm", "NULL"]},
                ),
                "run_pca": ("BOOLEAN", {"default": True}),
                "run_ttest": ("BOOLEAN", {"default": True}),
                "tt_method": ("STRING", {"default": "welch", "options": ["welch", "student", "classical", "wilcox", "limma"]}),
                "p_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
                "pval_type": ("STRING", {"default": "fdr", "options": ["fdr", "raw"]}),
                "paired": ("BOOLEAN", {"default": False}),
                "equal_var": ("BOOLEAN", {"default": False}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MSDIALProcessingNode(CommandNode):
    """Run MS-DIAL console batch processing with a user-supplied parameter file."""

    NODE_ID = "msdial_processing"
    DISPLAY_NAME = "MS-DIAL Processing"
    CATEGORY = "metabolomics"
    DESCRIPTION = "Run MS-DIAL console batch processing for LC-MS or GC-MS data with a parameter file."
    SEARCH_ALIASES = ["ms-dial", "msdial", "metabolomics", "lcmsdda", "lcmsdia", "gcms", "peak picking"]
    RETURN_TYPES = ("DIRECTORY", "TSV", "JSON")
    RETURN_NAMES = ("results_dir", "result_index", "metadata")
    REQUIRED_EXECUTABLES = ["mono"]
    REQUIRED_CONDA_PACKAGES = ["mono"]
    DOCUMENTATION_URL = "https://systemsomicslab.github.io/compms/msdial/consoleapp.html"
    VERSION = "4.0"
    EXPERIMENTAL = True
    SHELL = True

    INDEX_SCRIPT = (
        "import json, sys; "
        "from pathlib import Path; "
        "results=Path(sys.argv[1]); index=Path(sys.argv[2]); metadata=Path(sys.argv[3]); "
        "input_dir=sys.argv[4]; parameter_file=sys.argv[5]; analysis_type=sys.argv[6]; executable=sys.argv[7]; "
        "use_mono=sys.argv[8].lower() == 'true'; keep_project=sys.argv[9].lower() == 'true'; "
        "files=sorted(p for p in results.rglob('*') if p.is_file()); "
        "index.parent.mkdir(parents=True, exist_ok=True); metadata.parent.mkdir(parents=True, exist_ok=True); "
        "index.write_text('path\\tname\\tsuffix\\tsize_bytes\\n' + ''.join("
        "f'{p}\\t{p.name}\\t{p.suffix}\\t{p.stat().st_size}\\n' for p in files), encoding='utf-8'); "
        "metadata.write_text(json.dumps({'input_dir': input_dir, 'parameter_file': parameter_file, "
        "'analysis_type': analysis_type, 'msdial_executable': executable, 'use_mono': use_mono, "
        "'keep_project_file': keep_project, 'results_dir': str(results), 'result_count': len(files), "
        "'result_files': [str(p) for p in files]}, indent=2, sort_keys=True) + '\\n', encoding='utf-8')"
    )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        analysis_type = str(inputs.get("analysis_type", "lcmsdda") or "lcmsdda")
        allowed_types = {"gcms", "lcmsdda", "lcmsdia"}
        if analysis_type not in allowed_types:
            msg = f"MS-DIAL analysis_type must be one of {sorted(allowed_types)}."
            raise ValueError(msg)

        input_dir = str(inputs.get("input_dir", ""))
        parameter_file = str(inputs.get("parameter_file", ""))
        msdial_executable = str(inputs.get("msdial_executable", "MsdialConsoleApp.exe") or "MsdialConsoleApp.exe")
        use_mono = bool(inputs.get("use_mono", True))
        keep_project_file = bool(inputs.get("keep_project_file", False))
        stem = _safe_output_stem(inputs.get("output_name"), analysis_type)
        results_dir = out_dir / stem
        result_index = out_dir / f"{stem}.result_index.tsv"
        metadata_json = out_dir / f"{stem}.metadata.json"

        cmd: list[str] = []
        if use_mono:
            cmd.append("mono")
        cmd.extend([
            msdial_executable,
            analysis_type,
            "-i",
            input_dir,
            "-o",
            str(results_dir),
            "-m",
            parameter_file,
        ])
        if keep_project_file:
            cmd.append("-p")
        cmd.extend([
            "&&",
            "python",
            "-c",
            cls.INDEX_SCRIPT,
            str(results_dir),
            str(result_index),
            str(metadata_json),
            input_dir,
            parameter_file,
            analysis_type,
            msdial_executable,
            str(use_mono).lower(),
            str(keep_project_file).lower(),
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get("output_name"), str(inputs.get("analysis_type", "lcmsdda") or "lcmsdda"))
        return [
            node_out / stem,
            node_out / f"{stem}.result_index.tsv",
            node_out / f"{stem}.metadata.json",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_dir": ("DIRECTORY", {"description": "Folder containing MS-DIAL input files"}),
                "parameter_file": ("FILE", {"description": "MS-DIAL parameter text file"}),
            },
            "optional": {
                "analysis_type": ("STRING", {"default": "lcmsdda", "options": ["lcmsdda", "lcmsdia", "gcms"]}),
                "msdial_executable": (
                    "STRING",
                    {"default": "MsdialConsoleApp.exe", "description": "Path to the manually installed MS-DIAL console app"},
                ),
                "use_mono": ("BOOLEAN", {"default": True}),
                "keep_project_file": ("BOOLEAN", {"default": False, "description": "Add -p to keep MS-DIAL MTD project files"}),
                "output_name": ("STRING", {"default": "", "description": "Optional output filename stem"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }
