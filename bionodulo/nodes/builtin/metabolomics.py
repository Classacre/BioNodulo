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
