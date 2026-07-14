"""metaboanalyst — metabolomics node(s). One tool per file (extracted from metabolomics.py)."""
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


class MetaboAnalystStatsNode(CommandNode):
    """Run basic MetaboAnalystR statistical analysis on a prepared concentration table."""
    NODE_ID = 'metaboanalyst_stats'
    DISPLAY_NAME = 'MetaboAnalyst Stats'
    CATEGORY = 'metabolomics'
    DESCRIPTION = 'Run MetaboAnalystR normalization, PCA, and two-class t-test statistics on a prepared table.'
    SEARCH_ALIASES = ['metaboanalyst', 'metaboanalystr', 'metabolomics', 'statistics', 'pca', 'normalization', 't-test']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'TSV', 'IMAGE', 'FILE', 'JSON')
    RETURN_NAMES = ('normalized_table', 'pca_scores', 'pca_loadings', 'ttest_results', 'pca_plot', 'metaboanalyst_object', 'summary')
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_CONDA_PACKAGES = ['r-base', 'r-jsonlite', 'r-readr']
    REQUIRED_R_PACKAGES = ['MetaboAnalystR', 'jsonlite', 'readr']
    DOCUMENTATION_URL = 'https://github.com/xia-lab/MetaboAnalystR'
    VERSION = '4.3.0'
    EXPERIMENTAL = True
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        script_file = out_dir / 'metaboanalyst_stats.R'
        data_table = str(inputs.get('data_table', ''))
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(data_table, 'metaboanalyst'))
        normalized_table = out_dir / f'{stem}.normalized.tsv'
        pca_scores = out_dir / f'{stem}.pca_scores.tsv'
        pca_loadings = out_dir / f'{stem}.pca_loadings.tsv'
        ttest_results = out_dir / f'{stem}.ttest.tsv'
        pca_plot = out_dir / f'{stem}.pca.png'
        rds_file = out_dir / f'{stem}.metaboanalyst.rds'
        summary_json = out_dir / f'{stem}.summary.json'
        table_format = str(inputs.get('format', 'rowu') or 'rowu')
        label_type = str(inputs.get('label_type', 'disc') or 'disc')
        row_norm = str(inputs.get('row_norm', 'MedianNorm') or 'MedianNorm')
        trans_norm = str(inputs.get('trans_norm', 'LogNorm') or 'LogNorm')
        scale_norm = str(inputs.get('scale_norm', 'AutoNorm') or 'AutoNorm')
        run_pca = bool(inputs.get('run_pca', True))
        run_ttest = bool(inputs.get('run_ttest', True))
        tt_method = str(inputs.get('tt_method', 'welch') or 'welch')
        p_threshold = inputs.get('p_threshold', 0.05)
        pval_type = str(inputs.get('pval_type', 'fdr') or 'fdr')
        paired = bool(inputs.get('paired', False))
        equal_var = bool(inputs.get('equal_var', False))
        pca_block = textwrap.dedent(f'                mSet <- PCA.Anal(mSet)\n                PlotPCA2DScore(mSet, "{stem}.pca", "png", dpi = 150, width = 0, pcx = 1, pcy = 2, reg = 0.95, show = 0)\n                pca_scores <- as.data.frame(mSet$analSet$pca$x)\n                pca_scores <- data.frame(sample = rownames(pca_scores), pca_scores, check.names = FALSE)\n                pca_loadings <- as.data.frame(mSet$analSet$pca$rotation)\n                pca_loadings <- data.frame(feature = rownames(pca_loadings), pca_loadings, check.names = FALSE)\n            ') if run_pca else textwrap.dedent('                pca_scores <- data.frame()\n                pca_loadings <- data.frame()\n            ')
        ttest_block = textwrap.dedent(f'                mSet <- Ttests.Anal(mSet, nonpar = FALSE, threshp = {p_threshold}, paired = {_r_bool(paired)}, equal.var = {_r_bool(equal_var)}, pvalType = "{pval_type}", all_results = TRUE, tt.method = "{tt_method}")\n                ttest_results <- as.data.frame(mSet$analSet$tt)\n                if (nrow(ttest_results) > 0) {{\n                    ttest_results <- data.frame(feature = rownames(ttest_results), ttest_results, check.names = FALSE)\n                }}\n            ') if run_ttest else 'ttest_results <- data.frame()'
        script = textwrap.dedent(f'''            if (!requireNamespace("MetaboAnalystR", quietly = TRUE)) stop("Package 'MetaboAnalystR' is required but not installed. Install it from https://github.com/xia-lab/MetaboAnalystR.")\n            if (!requireNamespace("jsonlite", quietly = TRUE)) stop("Package 'jsonlite' is required but not installed.")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed.")\n            library("MetaboAnalystR")\n            library("jsonlite")\n            library("readr")\n\n            setwd("{out_dir.as_posix()}")\n            data_table <- {_r_string(data_table)}\n            if (!file.exists(data_table)) stop(paste("Input data table not found:", data_table))\n\n            mSet <- InitDataObjects("conc", "stat", paired = {_r_bool(paired)})\n            mSet <- Read.TextData(mSet, {_r_string(data_table)}, format = "{table_format}", lbl.type = "{label_type}")\n            mSet <- SanityCheckData(mSet)\n            mSet <- ReplaceMin(mSet)\n            mSet <- PreparePrenormData(mSet)\n            mSet <- Normalization(mSet, rowNorm = "{row_norm}", transNorm = "{trans_norm}", scaleNorm = "{scale_norm}")\n\n            norm_table <- as.data.frame(mSet$dataSet$norm)\n            norm_table <- data.frame(feature = rownames(norm_table), norm_table, check.names = FALSE)\n            {pca_block}\n            {ttest_block}\n\n            if (file.exists("{stem}.pca_dpi150.png")) {{\n                file.copy("{stem}.pca_dpi150.png", "{pca_plot.as_posix()}", overwrite = TRUE)\n            }} else if (file.exists("{stem}.pca.png")) {{\n                file.copy("{stem}.pca.png", "{pca_plot.as_posix()}", overwrite = TRUE)\n            }}\n\n            write_tsv(norm_table, "{normalized_table.as_posix()}")\n            write_tsv(pca_scores, "{pca_scores.as_posix()}")\n            write_tsv(pca_loadings, "{pca_loadings.as_posix()}")\n            write_tsv(ttest_results, "{ttest_results.as_posix()}")\n            saveRDS(mSet, "{rds_file.as_posix()}")\n\n            summary <- list(\n                data_table = data_table,\n                format = "{table_format}",\n                label_type = "{label_type}",\n                row_norm = "{row_norm}",\n                trans_norm = "{trans_norm}",\n                scale_norm = "{scale_norm}",\n                run_pca = {_r_bool(run_pca)},\n                run_ttest = {_r_bool(run_ttest)},\n                tt_method = "{tt_method}",\n                p_threshold = {p_threshold},\n                pval_type = "{pval_type}",\n                paired = {_r_bool(paired)},\n                equal_var = {_r_bool(equal_var)},\n                normalized_table = "{normalized_table.as_posix()}",\n                pca_scores = "{pca_scores.as_posix()}",\n                pca_loadings = "{pca_loadings.as_posix()}",\n                ttest_results = "{ttest_results.as_posix()}",\n                pca_plot = "{pca_plot.as_posix()}",\n                metaboanalyst_object = "{rds_file.as_posix()}"\n            )\n            write_json(summary, "{summary_json.as_posix()}", pretty = TRUE, auto_unbox = TRUE)\n        ''')
        script_file.write_text(script, encoding='utf-8')
        return ['Rscript', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('output_name'), _safe_output_stem(inputs.get('data_table'), 'metaboanalyst'))
        return [node_out / f'{stem}.normalized.tsv', node_out / f'{stem}.pca_scores.tsv', node_out / f'{stem}.pca_loadings.tsv', node_out / f'{stem}.ttest.tsv', node_out / f'{stem}.pca.png', node_out / f'{stem}.metaboanalyst.rds', node_out / f'{stem}.summary.json']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data_table': ('FILE', {'description': 'MetaboAnalyst-ready concentration table with class labels'})}, 'optional': {'format': ('STRING', {'default': 'rowu', 'options': ['rowu', 'colu', 'rowp', 'colp']}), 'label_type': ('STRING', {'default': 'disc', 'options': ['disc', 'cont']}), 'row_norm': ('STRING', {'default': 'MedianNorm', 'options': ['MedianNorm', 'SumNorm', 'QuantileNorm', 'CompNorm', 'SpecNorm']}), 'trans_norm': ('STRING', {'default': 'LogNorm', 'options': ['LogNorm', 'CrNorm', 'NULL']}), 'scale_norm': ('STRING', {'default': 'AutoNorm', 'options': ['AutoNorm', 'ParetoNorm', 'MeanCenter', 'RangeNorm', 'NULL']}), 'run_pca': ('BOOLEAN', {'default': True}), 'run_ttest': ('BOOLEAN', {'default': True}), 'tt_method': ('STRING', {'default': 'welch', 'options': ['welch', 'student', 'classical', 'wilcox', 'limma']}), 'p_threshold': ('FLOAT', {'default': 0.05, 'min': 0.0, 'max': 1.0}), 'pval_type': ('STRING', {'default': 'fdr', 'options': ['fdr', 'raw']}), 'paired': ('BOOLEAN', {'default': False}), 'equal_var': ('BOOLEAN', {'default': False}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output filename stem'})}, 'hidden': {'output': ('STRING', {})}}
