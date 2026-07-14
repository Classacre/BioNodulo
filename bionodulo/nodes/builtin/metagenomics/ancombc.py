"""ancombc — metagenomics node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ANCOMBCNode(CommandNode):
    """Run ANCOM-BC differential abundance analysis for microbiome data."""
    NODE_ID = 'ancombc'
    DISPLAY_NAME = 'ANCOM-BC'
    REQUIRED_CONDA_PACKAGES = ['bioconductor-ancombc', 'r-data.table', 'r-optparse']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Differential abundance analysis for microbiome compositions with bias correction.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ANCOM-BC', 'ANCOMBC', 'ancombc', 'ANCOM-BC differential abundance', 'microbiome composition', 'bias correction', 'phyloseq', 'structural zeros', 'global test']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('output_collection',)
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/ANCOMBC'
    CITATION_DOIS = ANCOMBC_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in ANCOMBC_CITATION_DOIS]
    CITATION_TEXT = ANCOMBC_CITATION_TEXT
    VERSION = '1.4.0+galaxy0'
    SHELL = True
    P_ADJ_METHODS = ['holm', 'hochberg', 'hommel', 'bonferroni', 'BH', 'BY', 'fdr', 'none']
    OUTPUT_FILES = ['feature_table.tabular', 'zero_ind.tabular', 'samp_frac.tabular', 'resid.tabular', 'delta_em.tabular', 'delta_wls.tabular', 'res_beta.tabular', 'res_se.tabular', 'res_W.tabular', 'res_p_val.tabular', 'res_q_val.tabular', 'res_diff_abn.tabular', 'res_global.tabular']

    @classmethod
    def _bool_arg(cls, inputs: dict[str, Any], name: str, default: bool) -> str:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return 'false' if value.lower() in {'false', '0', 'no'} else 'true'
        return 'true' if bool(value) else 'false'

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_collection'

    @classmethod
    def expected_output_files(cls) -> list[str]:
        return list(cls.OUTPUT_FILES)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_dir = cls._output_dir(inputs)
        cmd = ['Rscript', str(inputs.get('script_path', 'ancombc.R')), '--phyloseq', str(inputs.get('phyloseq', '')), '--formula', str(inputs.get('formula', '')), '--p_adj_method', str(inputs.get('p_adj_method', 'holm')), '--zero_cut', str(inputs.get('zero_cut', 0.1)), '--lib_cut', str(inputs.get('lib_cut', 0)), '--group', str(inputs.get('group', '')), '--struc_zero', cls._bool_arg(inputs, 'struc_zero', False), '--neg_lb', cls._bool_arg(inputs, 'neg_lb', False), '--tol', str(inputs.get('tol', 1e-05)), '--max_iter', str(inputs.get('max_iter', 100)), '--conserve', cls._bool_arg(inputs, 'conserve', False), '--alpha', str(inputs.get('alpha', 0.05)), '--global', cls._bool_arg(inputs, 'global_test', False), '--output_dir', output_dir]
        return f'mkdir -p {shlex.quote(output_dir)} && {_shell_join(cmd)}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output_collection'
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def _validate_range(cls, inputs: dict[str, Any], name: str, default: int | float, minimum: int | float, maximum: int | float | None=None) -> bool | str:
        value = inputs.get(name, default)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return f'{name} must be numeric'
        if numeric < minimum:
            return f'{name} must be >= {minimum:g}'
        if maximum is not None and numeric > maximum:
            return f'{name} must be between {minimum:g} and {maximum:g}'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('phyloseq', '')).strip():
            return 'phyloseq is required'
        if not str(inputs.get('formula', '')).strip():
            return 'formula is required'
        p_adj_method = str(inputs.get('p_adj_method', 'holm') or 'holm')
        if p_adj_method not in cls.P_ADJ_METHODS:
            return f"p_adj_method must be one of: {', '.join(cls.P_ADJ_METHODS)}"
        for name, default, minimum, maximum in [('zero_cut', 0.1, 0, 1), ('lib_cut', 0, 0, None), ('tol', 1e-05, 0, None), ('alpha', 0.05, 0, None)]:
            result = cls._validate_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        try:
            if int(inputs.get('max_iter', 100)) < 1:
                return 'max_iter must be >= 1'
        except (TypeError, ValueError):
            return 'max_iter must be an integer'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'phyloseq': ('FILE', {'description': 'RDS file containing a phyloseq object'}), 'formula': ('STRING', {'default': '', 'description': 'Model formula describing metadata variables that explain microbial abundances'})}, 'optional': {'p_adj_method': ('STRING', {'default': 'holm', 'options': cls.P_ADJ_METHODS, 'description': 'Method used to adjust p-values'}), 'zero_cut': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'Minimum taxa prevalence retained'}), 'lib_cut': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum sample library size retained'}), 'group': ('STRING', {'default': '', 'description': 'Discrete metadata variable for structural-zero detection and global testing'}), 'struc_zero': ('BOOLEAN', {'default': False, 'description': 'Detect structural zeros using the group variable'}), 'neg_lb': ('BOOLEAN', {'default': False, 'description': 'Use asymptotic lower bounds when classifying structural zeros'}), 'tol': ('FLOAT', {'default': 1e-05, 'min': 0, 'description': 'E-M algorithm convergence tolerance'}), 'max_iter': ('INT', {'default': 100, 'min': 1, 'description': 'Maximum E-M algorithm iterations'}), 'conserve': ('BOOLEAN', {'default': False, 'description': 'Use a conservative variance estimator for test statistics'}), 'alpha': ('FLOAT', {'default': 0.05, 'min': 0, 'description': 'Significance level'}), 'global_test': ('BOOLEAN', {'default': False, 'description': 'Perform the ANCOM-BC global test for the group variable'}), 'script_path': ('FILE', {'default': 'ancombc.R', 'advanced': True, 'description': 'Path to the Galaxy ANCOM-BC R wrapper script'})}, 'hidden': {'output': ('STRING', {})}}
