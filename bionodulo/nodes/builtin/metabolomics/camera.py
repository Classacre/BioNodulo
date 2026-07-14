"""camera — metabolomics node(s). One tool per file (extracted from metabolomics.py)."""
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


class CAMERAAnnotationNode(CommandNode):
    """Annotate XCMS peak lists with CAMERA isotope and adduct calls."""
    NODE_ID = 'camera_annotation'
    DISPLAY_NAME = 'CAMERA Annotation'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Annotate LC-MS peaks with CAMERA pseudospectra, isotope, and adduct assignments.'
    SEARCH_ALIASES = ['camera', 'metabolomics', 'lc-ms', 'peak annotation', 'adducts', 'isotopes']
    RETURN_TYPES = ('TSV', 'FILE', 'JSON')
    RETURN_NAMES = ('annotated_peaklist', 'camera_object', 'summary')
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-camera', 'bioconductor-xcms', 'r-jsonlite', 'r-readr']
    REQUIRED_R_PACKAGES = ['CAMERA', 'xcms', 'jsonlite', 'readr']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/CAMERA/'
    VERSION = '1.66'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / 'camera_annotation.R'
        xcms_object = str(inputs.get('xcms_object', ''))
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(xcms_object, 'camera'))
        annotated_peaklist = out_dir / f'{stem}.camera_peaklist.tsv'
        camera_object = out_dir / f'{stem}.camera.rds'
        summary_json = out_dir / f'{stem}.camera.summary.json'
        polarity = str(inputs.get('polarity', 'positive') or 'positive')
        intval = str(inputs.get('intval', 'into') or 'into')
        run_group_corr = inputs.get('run_group_corr', True)
        run_adducts = inputs.get('run_adducts', True)
        group_corr_step = f'''xsa <- groupCorr(xsa, cor_eic_th = {inputs.get('cor_eic_th', 0.75)}, pval = {inputs.get('pval', 0.05)}, calcIso = TRUE, intval = "{intval}")''' if run_group_corr else ''
        adduct_step = f'''xsa <- findAdducts(xsa, ppm = {inputs.get('adduct_ppm', 5)}, mzabs = {inputs.get('adduct_mzabs', 0.015)}, polarity = "{polarity}", intval = "{intval}")''' if run_adducts else ''
        script = textwrap.dedent(f'''            if (!requireNamespace("CAMERA", quietly = TRUE)) stop("Package 'CAMERA' is required but not installed.")\n            if (!requireNamespace("xcms", quietly = TRUE)) stop("Package 'xcms' is required but not installed.")\n            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")\n            library("CAMERA")\n            library("xcms")\n            library("jsonlite")\n            library("readr")\n\n            xdata <- readRDS("{xcms_object}")\n            if (is(xdata, "xcmsSet")) {{\n                xset <- xdata\n            }} else if (is(xdata, "XCMSnExp")) {{\n                if (any(msLevel(xdata) > 1)) stop("CAMERA conversion from XCMSnExp to xcmsSet supports MS1-only objects. Use an MS1-only XCMS object or a legacy xcmsSet.")\n                xset <- as(xdata, "xcmsSet")\n            }} else {{\n                stop("CAMERA Annotation requires an xcmsSet or XCMSnExp object saved as RDS.")\n            }}\n\n            xsa <- xsAnnotate(xset, polarity = "{polarity}")\n            xsa <- groupFWHM(xsa, sigma = {inputs.get('sigma', 6)}, perfwhm = {inputs.get('perfwhm', 0.6)}, intval = "{intval}")\n            xsa <- findIsotopes(xsa, maxcharge = {inputs.get('maxcharge', 3)}, maxiso = {inputs.get('maxiso', 4)}, ppm = {inputs.get('isotope_ppm', 5)}, mzabs = {inputs.get('isotope_mzabs', 0.01)}, intval = "{intval}")\n            {group_corr_step}\n            {adduct_step}\n            peaklist <- as.data.frame(getPeaklist(xsa, intval = "{intval}"))\n            write_tsv(peaklist, "{annotated_peaklist.as_posix()}")\n            saveRDS(xsa, "{camera_object.as_posix()}")\n\n            summary <- list(\n                input_xcms_object = "{xcms_object}",\n                annotated_peaklist = "{annotated_peaklist.as_posix()}",\n                camera_object = "{camera_object.as_posix()}",\n                peak_count = nrow(peaklist),\n                polarity = "{polarity}",\n                intval = "{intval}",\n                run_group_corr = {str(bool(run_group_corr)).upper()},\n                run_adducts = {str(bool(run_adducts)).upper()}\n            )\n            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)\n        ''')
        script_file.write_text(script, encoding='utf-8')
        return ['Rscript', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('xcms_object'), 'camera'))
        return [node_out / f'{stem}.camera_peaklist.tsv', node_out / f'{stem}.camera.rds', node_out / f'{stem}.camera.summary.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'xcms_object': ('FILE', {'description': 'XCMS RDS object from retention correction/alignment'})}, 'optional': {'polarity': ('STRING', {'default': 'positive', 'options': ['positive', 'negative']}), 'perfwhm': ('FLOAT', {'default': 0.6, 'min': 0.0}), 'sigma': ('FLOAT', {'default': 6.0, 'min': 0.0}), 'maxcharge': ('INT', {'default': 3, 'min': 1}), 'maxiso': ('INT', {'default': 4, 'min': 1}), 'isotope_ppm': ('FLOAT', {'default': 5.0, 'min': 0.0}), 'isotope_mzabs': ('FLOAT', {'default': 0.01, 'min': 0.0}), 'cor_eic_th': ('FLOAT', {'default': 0.75, 'min': 0.0, 'max': 1.0}), 'pval': ('FLOAT', {'default': 0.05, 'min': 0.0, 'max': 1.0}), 'run_group_corr': ('BOOLEAN', {'default': True}), 'run_adducts': ('BOOLEAN', {'default': True}), 'adduct_ppm': ('FLOAT', {'default': 5.0, 'min': 0.0}), 'adduct_mzabs': ('FLOAT', {'default': 0.015, 'min': 0.0}), 'intval': ('STRING', {'default': 'into', 'options': ['into', 'maxo', 'intb']}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
