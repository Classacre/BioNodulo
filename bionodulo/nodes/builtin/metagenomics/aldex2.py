"""aldex2 — metagenomics node(s). One tool per file (extracted from wrapped_amplicon_trimming.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ALDEx2Node(CommandNode):
    """Run ALDEx2 differential abundance analyses."""
    NODE_ID = 'aldex2'
    DISPLAY_NAME = 'ALDEx2'
    REQUIRED_CONDA_PACKAGES = ['bioconductor-aldex2', 'r-data.table', 'r-optparse', 'r-qgraph']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Differential abundance analysis with ALDEx2 compositional data methods.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ALDEx2', 'aldex2', 'ALDEx2 differential abundance', 'compositional data analysis', 'microbiome differential abundance', 'RNA-seq differential abundance', 'Dirichlet Monte Carlo']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'IMAGE', 'TSV', 'IMAGE', 'IMAGE', 'TSV', 'PDF')
    RETURN_NAMES = ('aldex', 'aldex_corr', 'aldex_effect', 'aldex_expected_distance', 'aldex_kw', 'aldex_plot', 'aldex_plot_feature', 'aldex_ttest', 'aldex_ttest_plot')
    REQUIRED_EXECUTABLES = ['Rscript']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/ALDEx2'
    CITATION_DOIS = ALDEX2_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in ALDEX2_CITATION_DOIS]
    CITATION_TEXT = ALDEX2_CITATION_TEXT
    VERSION = '1.26.0+galaxy0'
    SHELL = True
    ANALYSIS_TYPES = ['aldex', 'aldex_corr', 'aldex_effect', 'aldex_expected_distance', 'aldex_kw', 'aldex_plot', 'aldex_plot_feature', 'aldex_ttest']
    DENOM_OPTIONS = ['all', 'median', 'iqlr', 'zero', 'lvha']
    ALDEX_TEST_OPTIONS = ['t', 'kw', 'corr']
    PLOT_TYPES = ['MA', 'MW']
    PLOT_TESTS = ['welch', 'wilcox', 'kruskal']
    OUTPUT_FILES = {'aldex': 'output_aldex.tsv', 'aldex_corr': 'output_aldex_corr.tsv', 'aldex_effect': 'output_aldex_effect.tsv', 'aldex_expected_distance': 'output_aldex_expected_distance.png', 'aldex_kw': 'output_aldex_kw.tsv', 'aldex_plot': 'output_aldex_plot.png', 'aldex_plot_feature': 'output_aldex_plot_feature.png', 'aldex_ttest': 'output_aldex_ttest.tsv'}

    @classmethod
    def _analysis_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('analysis_type', 'aldex') or 'aldex')

    @classmethod
    def _csv(cls, value: Any) -> str:
        return ','.join(_as_list(value))

    @classmethod
    def _bool_arg(cls, inputs: dict[str, Any], name: str, default: bool) -> str:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return 'false' if value.lower() in {'false', '0', 'no'} else 'true'
        return 'true' if bool(value) else 'false'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        analysis_type = cls._analysis_type(inputs)
        cmd = ['Rscript', str(inputs.get('script_path', 'aldex2.R')), '--reads', str(inputs.get('reads', '')), '--group_names', cls._csv(inputs.get('group_names')), '--num_cols', cls._csv(inputs.get('num_cols')), '--num_mc_samples', str(inputs.get('num_mc_samples', 128)), '--denom', str(inputs.get('denom', 'all')), '--analysis_type', analysis_type]
        if analysis_type == 'aldex':
            cmd.extend(['--aldex_test', str(inputs.get('aldex_test', 't')), '--effect', cls._bool_arg(inputs, 'effect', True), '--include_sample_summary', cls._bool_arg(inputs, 'include_sample_summary', False), '--iterate', cls._bool_arg(inputs, 'iterate', False)])
        elif analysis_type == 'aldex_corr':
            cmd.extend(['--group_nums', cls._csv(inputs.get('group_nums')), '--num_cols_in_groups', cls._csv(inputs.get('num_cols_in_groups'))])
        elif analysis_type == 'aldex_effect':
            cmd.extend(['--include_sample_summary', cls._bool_arg(inputs, 'include_sample_summary', False)])
        elif analysis_type == 'aldex_plot':
            cmd.extend(['--aldex_test', str(inputs.get('aldex_test', 't')), '--effect', cls._bool_arg(inputs, 'effect', True), '--include_sample_summary', cls._bool_arg(inputs, 'include_sample_summary', False), '--iterate', cls._bool_arg(inputs, 'iterate', False), '--plot_type', str(inputs.get('plot_type', 'MA')), '--plot_test', str(inputs.get('plot_test', 'welch')), '--cutoff_pval', str(inputs.get('cutoff_pval', 0.1)), '--cutoff_effect', str(inputs.get('cutoff_effect', 1))])
            _add_if_value(cmd, '--xlab', inputs.get('xlab'))
            _add_if_value(cmd, '--ylab', inputs.get('ylab'))
        elif analysis_type == 'aldex_plot_feature':
            cmd.extend(['--feature_name', str(inputs.get('feature_name', ''))])
        elif analysis_type == 'aldex_ttest':
            cmd.extend(['--paired_test', cls._bool_arg(inputs, 'paired_test', False), '--hist_plot', cls._bool_arg(inputs, 'hist_plot', False)])
        cmd.extend(['--output', f"{out}/{cls.OUTPUT_FILES.get(analysis_type, cls.OUTPUT_FILES['aldex'])}"])
        command = _shell_join(cmd)
        if analysis_type == 'aldex_ttest' and cls._bool_arg(inputs, 'hist_plot', False) == 'true':
            command = f"{command} && mv Rplots.pdf {shlex.quote(f'{out}/output_aldex_ttest_plot.pdf')}"
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        analysis_type = cls._analysis_type(inputs)
        outputs = [out / cls.OUTPUT_FILES.get(analysis_type, cls.OUTPUT_FILES['aldex'])]
        if analysis_type == 'aldex_ttest' and cls._bool_arg(inputs, 'hist_plot', False) == 'true':
            outputs.append(out / 'output_aldex_ttest_plot.pdf')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('reads', '')).strip():
            return 'reads is required'
        group_names = _as_list(inputs.get('group_names'))
        num_cols = _as_list(inputs.get('num_cols'))
        if not group_names:
            return 'at least one comparison group is required'
        if len(group_names) != len(num_cols):
            return 'group_names and num_cols must have the same length'
        for value in num_cols:
            try:
                if int(value) < 1:
                    return 'num_cols values must be >= 1'
            except (TypeError, ValueError):
                return 'num_cols values must be integers'
        denom = str(inputs.get('denom', 'all') or 'all')
        if denom not in cls.DENOM_OPTIONS:
            return f"denom must be one of: {', '.join(cls.DENOM_OPTIONS)}"
        analysis_type = cls._analysis_type(inputs)
        if analysis_type not in cls.ANALYSIS_TYPES:
            return f"analysis_type must be one of: {', '.join(cls.ANALYSIS_TYPES)}"
        try:
            if int(inputs.get('num_mc_samples', 128)) < 1:
                return 'num_mc_samples must be >= 1'
        except (TypeError, ValueError):
            return 'num_mc_samples must be an integer'
        if analysis_type == 'aldex_corr':
            group_nums = _as_list(inputs.get('group_nums'))
            num_cols_in_groups = _as_list(inputs.get('num_cols_in_groups'))
            if not group_nums or not num_cols_in_groups:
                return 'aldex_corr requires group_nums and num_cols_in_groups'
            if len(group_nums) != len(num_cols_in_groups):
                return 'group_nums and num_cols_in_groups must have the same length'
        if analysis_type == 'aldex_plot_feature' and (not str(inputs.get('feature_name', '')).strip()):
            return 'feature_name is required for aldex_plot_feature'
        if str(inputs.get('aldex_test', 't') or 't') not in cls.ALDEX_TEST_OPTIONS:
            return f"aldex_test must be one of: {', '.join(cls.ALDEX_TEST_OPTIONS)}"
        if str(inputs.get('plot_type', 'MA') or 'MA') not in cls.PLOT_TYPES:
            return f"plot_type must be one of: {', '.join(cls.PLOT_TYPES)}"
        if str(inputs.get('plot_test', 'welch') or 'welch') not in cls.PLOT_TESTS:
            return f"plot_test must be one of: {', '.join(cls.PLOT_TESTS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('TSV', {'description': 'Reads table with genes/features in rows and sample count columns'}), 'group_names': ('STRING', {'multiple': True, 'default': ['Grp1'], 'description': 'Comparison group labels'}), 'num_cols': ('INT', {'multiple': True, 'default': [1], 'min': 1, 'description': 'Number of read-count columns per group'})}, 'optional': {'num_mc_samples': ('INT', {'default': 128, 'min': 1, 'description': 'Monte Carlo samples for Dirichlet distribution estimates'}), 'denom': ('STRING', {'default': 'all', 'options': cls.DENOM_OPTIONS, 'description': 'Denominator features for geometric means'}), 'analysis_type': ('STRING', {'default': 'aldex', 'options': cls.ANALYSIS_TYPES, 'description': 'ALDEx2 analysis function to run'}), 'aldex_test': ('STRING', {'default': 't', 'options': cls.ALDEX_TEST_OPTIONS, 'description': 'Statistical tests for aldex/aldex.plot'}), 'effect': ('BOOLEAN', {'default': True, 'description': 'Calculate abundances and effect sizes'}), 'include_sample_summary': ('BOOLEAN', {'default': False, 'description': 'Include median clr values for each sample'}), 'iterate': ('BOOLEAN', {'default': False, 'description': 'Perform tests iteratively'}), 'group_nums': ('INT', {'default': [], 'multiple': True, 'min': 1, 'description': 'Continuous variable group numbers for aldex.corr'}), 'num_cols_in_groups': ('INT', {'default': [], 'multiple': True, 'min': 1, 'description': 'Column counts per continuous variable group'}), 'plot_type': ('STRING', {'default': 'MA', 'options': cls.PLOT_TYPES, 'description': 'ALDEx plot type'}), 'plot_test': ('STRING', {'default': 'welch', 'options': cls.PLOT_TESTS, 'description': 'Significance test for aldex.plot'}), 'cutoff_pval': ('FLOAT', {'default': 0.1, 'min': 0, 'description': 'Benjamini-Hochberg FDR cutoff'}), 'cutoff_effect': ('INT', {'default': 1, 'min': 0, 'description': 'Effect-size cutoff for plotting'}), 'xlab': ('STRING', {'default': '', 'description': 'Optional x-axis label for aldex.plot'}), 'ylab': ('STRING', {'default': '', 'description': 'Optional y-axis label for aldex.plot'}), 'feature_name': ('STRING', {'default': '', 'description': 'Feature name for aldex.plotFeature'}), 'paired_test': ('BOOLEAN', {'default': False, 'description': 'Use paired tests for aldex.ttest'}), 'hist_plot': ('BOOLEAN', {'default': False, 'description': 'Generate a p-value histogram PDF for aldex.ttest'}), 'script_path': ('FILE', {'default': 'aldex2.R', 'advanced': True, 'description': 'Path to the Galaxy ALDEx2 R wrapper script'})}, 'hidden': {'output': ('STRING', {})}}
