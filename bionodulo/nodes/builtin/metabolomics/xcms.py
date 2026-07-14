"""xcms — metabolomics node(s). One tool per file (extracted from metabolomics.py)."""
from __future__ import annotations
import re
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback
def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in re.split('[\\n,]+', text) if part.strip()]
def _r_string_vector(values: list[str]) -> str:
    quoted = [value.replace('\\', '\\\\').replace('"', '\\"') for value in values]
    return 'c(' + ', '.join((f'"{value}"' for value in quoted)) + ')'
def _r_string(value: Any) -> str:
    text = str(value or '')
    return '"' + text.replace('\\', '\\\\').replace('"', '\\"') + '"'
def _r_bool(value: Any) -> str:
    return 'TRUE' if bool(value) else 'FALSE'


class XCMSPeakDetectionNode(CommandNode):
    """Detect chromatographic peaks in LC-MS data with XCMS."""
    NODE_ID = 'xcms_peak_detection'
    DISPLAY_NAME = 'XCMS Peak Detection'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Detect LC-MS chromatographic peaks with XCMS centWave and export feature intensities.'
    SEARCH_ALIASES = ['xcms', 'metabolomics', 'lc-ms', 'centwave', 'peak detection', 'mass spectrometry']
    RETURN_TYPES = ('TSV', 'FILE', 'JSON')
    RETURN_NAMES = ('feature_table', 'xcms_object', 'summary')
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-xcms', 'bioconductor-msexperiment', 'bioconductor-biocparallel', 'r-jsonlite', 'r-readr']
    REQUIRED_R_PACKAGES = ['xcms', 'MsExperiment', 'jsonlite', 'readr', 'BiocParallel']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/xcms/'
    VERSION = '3.20'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / 'xcms_peak_detection.R'
        files = _split_path_list(inputs.get('mzml_files'))
        fallback_stem = _safe_output_stem(files[0] if files else 'xcms', 'xcms')
        stem = _safe_output_stem(inputs.get('output_name'), fallback_stem)
        feature_table = out_dir / f'{stem}.feature_table.tsv'
        xcms_object = out_dir / f'{stem}.xcms.rds'
        summary_json = out_dir / f'{stem}.summary.json'
        script = textwrap.dedent(f'''            if (!requireNamespace("xcms", quietly = TRUE)) stop("Package 'xcms' is required but not installed.")\n            if (!requireNamespace("MsExperiment", quietly = TRUE)) stop("Package 'MsExperiment' is required but not installed.")\n            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")\n            if (!requireNamespace("BiocParallel", quietly = TRUE)) stop("Package 'BiocParallel' is required but not installed.")\n            library("xcms")\n            library("MsExperiment")\n            library("jsonlite")\n            library("readr")\n            library("BiocParallel")\n\n            files <- {_r_string_vector(files)}\n            if (length(files) == 0) stop("At least one mzML/mzXML file is required.")\n            missing <- files[!file.exists(files)]\n            if (length(missing) > 0) stop(paste("Input file(s) not found:", paste(missing, collapse = ", ")))\n\n            # xcms 4.x removed the MSnbase-based readMSData(); the current reader\n            # is MsExperiment::readMsExperiment (spectra-backed). findChromPeaks\n            # operates on the returned MsExperiment directly.\n            raw_data <- readMsExperiment(spectraFiles = files)\n            # xcms/CentWave requires spectra ordered by retention time within each\n            # file (else: "Spectra are not ordered by retention time"). Order the\n            # backing Spectra by (file-of-origin, rtime). Spectra exposes the\n            # source file via dataOrigin() (fromFile() is an MSnbase/OnDiskMSnExp\n            # method that does NOT exist on a Spectra object).\n            sp <- spectra(raw_data)\n            ord <- order(dataOrigin(sp), rtime(sp))\n            spectra(raw_data) <- sp[ord]\n            param <- CentWaveParam(\n                ppm = {inputs.get('ppm', 25)},\n                peakwidth = c({inputs.get('peakwidth_min', 20)}, {inputs.get('peakwidth_max', 50)}),\n                snthresh = {inputs.get('snthresh', 10)},\n                prefilter = c({inputs.get('prefilter_k', 3)}, {inputs.get('prefilter_i', 100)}),\n                noise = {inputs.get('noise', 0)}\n            )\n            xdata <- findChromPeaks(raw_data, param = param, BPPARAM = MulticoreParam(workers = {inputs.get('threads', 1)}))\n            # featureValues() requires correspondence (peak grouping) first; group\n            # across samples with the density method before extracting the matrix.\n            xdata <- groupChromPeaks(xdata, param = PeakDensityParam(sampleGroups = rep(1, length(files))))\n            feature_values <- featureValues(xdata, value = "into")\n            chrom_peaks <- as.data.frame(chromPeaks(xdata))\n            peak_count <- nrow(chrom_peaks)\n\n            feature_table <- data.frame(feature_id = rownames(feature_values), feature_values, check.names = FALSE)\n            write_tsv(feature_table, "{feature_table.as_posix()}")\n            saveRDS(xdata, "{xcms_object.as_posix()}")\n\n            summary <- list(\n                input_files = files,\n                file_count = length(files),\n                peak_count = peak_count,\n                feature_count = nrow(feature_values),\n                ppm = {inputs.get('ppm', 25)},\n                peakwidth = c({inputs.get('peakwidth_min', 20)}, {inputs.get('peakwidth_max', 50)}),\n                snthresh = {inputs.get('snthresh', 10)},\n                feature_table = "{feature_table.as_posix()}",\n                xcms_object = "{xcms_object.as_posix()}"\n            )\n            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)\n        ''')
        script_file.write_text(script, encoding='utf-8')
        return ['Rscript', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        files = _split_path_list(inputs.get('mzml_files'))
        fallback_stem = _safe_output_stem(files[0] if files else 'xcms', 'xcms')
        stem = _safe_output_stem(inputs.get('output_name'), fallback_stem)
        return [node_out / f'{stem}.feature_table.tsv', node_out / f'{stem}.xcms.rds', node_out / f'{stem}.summary.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'mzml_files': ('FILE', {'description': 'mzML/mzXML LC-MS files; accepts a file list or comma/newline-separated paths'})}, 'optional': {'ppm': ('FLOAT', {'default': 25.0, 'min': 1.0, 'description': 'Mass accuracy in ppm'}), 'peakwidth_min': ('FLOAT', {'default': 20.0, 'min': 0.0}), 'peakwidth_max': ('FLOAT', {'default': 50.0, 'min': 0.0}), 'snthresh': ('FLOAT', {'default': 10.0, 'min': 0.0}), 'prefilter_k': ('INT', {'default': 3, 'min': 0}), 'prefilter_i': ('FLOAT', {'default': 100.0, 'min': 0.0}), 'noise': ('FLOAT', {'default': 0.0, 'min': 0.0}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}


class XCMSRetentionCorrectionNode(CommandNode):
    """Correct retention time, align, and fill XCMS chromatographic peaks."""
    NODE_ID = 'xcms_retention_correction'
    DISPLAY_NAME = 'XCMS Retention Time Correction'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Correct retention time, align grouped peaks, and fill missing LC-MS features with XCMS.'
    SEARCH_ALIASES = ['xcms', 'metabolomics', 'retention time', 'obiwarp', 'alignment', 'fill peaks']
    RETURN_TYPES = ('TSV', 'FILE', 'JSON')
    RETURN_NAMES = ('aligned_feature_table', 'aligned_xcms_object', 'summary')
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-xcms', 'bioconductor-biocparallel', 'r-jsonlite', 'r-readr']
    REQUIRED_R_PACKAGES = ['xcms', 'BiocParallel', 'jsonlite', 'readr']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/xcms/'
    VERSION = '3.20'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / 'xcms_retention_correction.R'
        xcms_object = str(inputs.get('xcms_object', ''))
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(xcms_object, 'xcms'))
        feature_table = out_dir / f'{stem}.aligned_feature_table.tsv'
        aligned_object = out_dir / f'{stem}.aligned.xcms.rds'
        summary_json = out_dir / f'{stem}.alignment.summary.json'
        sample_groups = _split_path_list(inputs.get('sample_groups'))
        sample_groups_r = _r_string_vector(sample_groups)
        if str(inputs.get('method', 'obiwarp') or 'obiwarp') != 'obiwarp':
            msg = "XCMS retention correction currently supports only method='obiwarp'."
            raise ValueError(msg)
        sample_group_block = f'sample_groups <- {sample_groups_r}\n            if (length(sample_groups) != length(fileNames(xdata))) stop("sample_groups length must match the number of samples.")' if sample_groups else 'sample_groups <- rep(1L, length(fileNames(xdata)))'
        script = textwrap.dedent(f'''            if (!requireNamespace("xcms", quietly = TRUE)) stop("Package 'xcms' is required but not installed.")\n            if (!requireNamespace("BiocParallel", quietly = TRUE)) stop("Package 'BiocParallel' is required but not installed.")\n            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")\n            library("xcms")\n            library("BiocParallel")\n            library("jsonlite")\n            library("readr")\n\n            xdata <- readRDS("{xcms_object}")\n            {sample_group_block}\n\n            adjust_param <- ObiwarpParam(binSize = {inputs.get('bin_size', 1.0)})\n            xdata <- adjustRtime(xdata, param = adjust_param, BPPARAM = MulticoreParam(workers = {inputs.get('threads', 1)}))\n            group_param <- PeakDensityParam(sampleGroups = sample_groups, bw = {inputs.get('bw', 5.0)}, minFraction = {inputs.get('min_fraction', 0.5)})\n            xdata <- groupChromPeaks(xdata, param = group_param)\n            xdata <- fillChromPeaks(xdata, BPPARAM = MulticoreParam(workers = {inputs.get('threads', 1)}))\n            feature_values <- featureValues(xdata, value = "into")\n            chrom_peaks <- as.data.frame(chromPeaks(xdata))\n\n            feature_table <- data.frame(feature_id = rownames(feature_values), feature_values, check.names = FALSE)\n            write_tsv(feature_table, "{feature_table.as_posix()}")\n            saveRDS(xdata, "{aligned_object.as_posix()}")\n\n            summary <- list(\n                input_xcms_object = "{xcms_object}",\n                sample_count = length(fileNames(xdata)),\n                peak_count = nrow(chrom_peaks),\n                feature_count = nrow(feature_values),\n                method = "obiwarp",\n                bin_size = {inputs.get('bin_size', 1.0)},\n                bw = {inputs.get('bw', 5.0)},\n                min_fraction = {inputs.get('min_fraction', 0.5)},\n                sample_groups = sample_groups,\n                aligned_feature_table = "{feature_table.as_posix()}",\n                aligned_xcms_object = "{aligned_object.as_posix()}"\n            )\n            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)\n        ''')
        script_file.write_text(script, encoding='utf-8')
        return ['Rscript', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('xcms_object'), 'xcms'))
        return [node_out / f'{stem}.aligned_feature_table.tsv', node_out / f'{stem}.aligned.xcms.rds', node_out / f'{stem}.alignment.summary.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'xcms_object': ('FILE', {'description': 'XCMS object RDS from XCMS Peak Detection'})}, 'optional': {'method': ('STRING', {'default': 'obiwarp', 'options': ['obiwarp']}), 'bin_size': ('FLOAT', {'default': 1.0, 'min': 0.0, 'description': 'Obiwarp bin size'}), 'bw': ('FLOAT', {'default': 5.0, 'min': 0.0, 'description': 'Peak density bandwidth'}), 'min_fraction': ('FLOAT', {'default': 0.5, 'min': 0.0, 'max': 1.0}), 'sample_groups': ('STRING', {'default': '', 'description': 'Optional comma/newline sample group labels matching input samples'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
