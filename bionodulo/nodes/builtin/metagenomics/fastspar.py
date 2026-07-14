"""fastspar — metagenomics node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FastSparNode(CommandNode):
    """Estimate sparse correlations for compositional OTU tables with FastSpar."""
    NODE_ID = 'fastspar'
    DISPLAY_NAME = 'FastSpar'
    REQUIRED_CONDA_PACKAGES = ['fastspar']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Estimate FastSpar/SparCC correlation and covariance matrices from compositional OTU count tables.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'FastSpar', 'FastSpar correlation', 'SparCC compositional correlation', 'OTU correlation', 'microbiome co-occurrence']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('correlation', 'covariance')
    REQUIRED_EXECUTABLES = ['fastspar']
    DOCUMENTATION_URL = 'https://github.com/scwatts/fastspar'
    CITATION_DOIS = ['10.1093/bioinformatics/bty734', '10.1371/journal.pcbi.1002687']
    CITATION_URLS = [f'{DOI_URL}10.1093/bioinformatics/bty734', f'{DOI_URL}10.1371/journal.pcbi.1002687']
    CITATION_TEXT = 'FastSpar: rapid and scalable correlation estimation for compositional data; Sparse correlations for compositional data.'
    VERSION = '1.0.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['fastspar', '--otu_table', str(inputs.get('otu_table', '')), '--iterations', str(inputs.get('iterations', 50)), '--exclude_iterations', str(inputs.get('exclude_iterations', 10)), '--threshold', str(inputs.get('threshold', 0.1)), '--seed', str(inputs.get('seed', 1)), '--correlation', f'{out}/median_correlation.tsv', '--covariance', f'{out}/median_covariance.tsv', '--threads', f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}", '--yes']
        return _shell_join(['mkdir', '-p', out]) + ' && ' + _shell_join(cmd).replace("'${GALAXY_SLOTS:-", '${GALAXY_SLOTS:-').replace("}'", '}')

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'median_correlation.tsv', out / 'median_covariance.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'otu_table': ('TSV', {'description': 'Absolute OTU count table in TSV format'})}, 'optional': {'iterations': ('INT', {'default': 50, 'min': 1, 'max': 1000, 'description': 'Correlation estimation rounds'}), 'exclude_iterations': ('INT', {'default': 10, 'min': 0, 'max': 100, 'description': 'Iterations excluding highly correlated pairs'}), 'threshold': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'Correlation exclusion threshold'}), 'seed': ('INT', {'default': 1, 'description': 'Random number seed'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('otu_table', '')).strip():
            return 'otu_table is required'
        for name, minimum, maximum in [('iterations', 1, 1000), ('exclude_iterations', 0, 100), ('threads', 1, None)]:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum or (maximum is not None and value > maximum):
                return f'{name} must be between {minimum} and {maximum}' if maximum is not None else f'{name} must be >= {minimum}'
        threshold_raw = inputs.get('threshold')
        if threshold_raw is not None and str(threshold_raw) != '':
            try:
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                return 'threshold must be a number'
            if not 0 <= threshold <= 1:
                return 'threshold must be between 0 and 1'
        return super().VALIDATE_INPUTS(inputs)


class FastSparReduceNode(CommandNode):
    """Filter FastSpar matrices into sparse edge tables."""
    NODE_ID = 'fastspar_reduce'
    DISPLAY_NAME = 'FastSpar: Reduce correlation table'
    REQUIRED_CONDA_PACKAGES = ['fastspar']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Filter FastSpar correlation and p-value matrices into sparse tabular edge lists.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'FastSpar reduce', 'FastSpar: Reduce correlation table', 'FastSpar sparse filter', 'filtered correlations', 'p-value threshold', 'microbiome network edges']
    RETURN_TYPES = ('TSV', 'TSV')
    RETURN_NAMES = ('correlations', 'pvalues')
    REQUIRED_EXECUTABLES = ['fastspar_reduce']
    DOCUMENTATION_URL = 'https://github.com/scwatts/fastspar'
    CITATION_DOIS = ['10.1093/bioinformatics/bty734', '10.1371/journal.pcbi.1002687']
    CITATION_URLS = [f'{DOI_URL}10.1093/bioinformatics/bty734', f'{DOI_URL}10.1371/journal.pcbi.1002687']
    CITATION_TEXT = 'FastSpar: rapid and scalable correlation estimation for compositional data; Sparse correlations for compositional data.'
    VERSION = '1.0.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = ['fastspar_reduce', '--correlation_table', str(inputs.get('correlation_table', '')), '--pvalue_table', str(inputs.get('pvalue_table', '')), '--correlation', str(inputs.get('correlation', 0.1)), '--pvalue', str(inputs.get('pvalue', 0.05)), '--output_prefix', 'sparse']
        moves = ['mv', 'sparse_filtered_correlation.tsv', f'{out}/filtered_correlations.tsv', '&&', 'mv', 'sparse_filtered_pvalue.tsv', f'{out}/filtered_pvalues.tsv']
        return f"{_shell_join(['mkdir', '-p', out])} && {_shell_join(cmd)} && {_shell_join(moves)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'filtered_correlations.tsv', out / 'filtered_pvalues.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'correlation_table': ('TSV', {'description': 'Symmetric FastSpar correlation matrix'}), 'pvalue_table': ('TSV', {'description': 'Matching FastSpar empirical p-value matrix'})}, 'optional': {'correlation': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'Minimum absolute correlation to retain'}), 'pvalue': ('FLOAT', {'default': 0.05, 'min': 0, 'max': 1, 'description': 'Maximum p-value to retain'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('correlation_table', '')).strip():
            return 'correlation_table is required'
        if not str(inputs.get('pvalue_table', '')).strip():
            return 'pvalue_table is required'
        for name in ['correlation', 'pvalue']:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f'{name} must be a number'
            if not 0 <= value <= 1:
                return f'{name} must be between 0 and 1'
        return super().VALIDATE_INPUTS(inputs)


class FastSparPvaluesNode(CommandNode):
    """Estimate empirical p-values for FastSpar correlations."""
    NODE_ID = 'fastspar_pvalues'
    DISPLAY_NAME = 'FastSpar: estimate p-values'
    REQUIRED_CONDA_PACKAGES = ['fastspar', 'parallel']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Estimate empirical p-values for FastSpar correlations with bootstrap resampling.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'FastSpar p-values', 'FastSpar: estimate p-values', 'FastSpar bootstrap p-values', 'SparCC empirical p-values', 'microbiome correlation significance']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('correlation', 'covariance', 'pvalues')
    REQUIRED_EXECUTABLES = ['fastspar', 'fastspar_bootstrap', 'fastspar_pvalues', 'parallel']
    DOCUMENTATION_URL = 'https://github.com/scwatts/fastspar'
    CITATION_DOIS = ['10.1093/bioinformatics/bty734', '10.1371/journal.pcbi.1002687']
    CITATION_URLS = [f'{DOI_URL}10.1093/bioinformatics/bty734', f'{DOI_URL}10.1371/journal.pcbi.1002687']
    CITATION_TEXT = 'FastSpar: rapid and scalable correlation estimation for compositional data; Sparse correlations for compositional data.'
    VERSION = '1.0.0'
    SHELL = True

    @classmethod
    def _slots(cls, inputs: dict[str, Any]) -> str:
        return f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"

    @classmethod
    def _shell(cls, cmd: list[str]) -> str:
        command = re.sub("'\\$\\{GALAXY_SLOTS:-([^}]+)\\}'", '${GALAXY_SLOTS:-\\1}', _shell_join(cmd))
        return command.replace("'{}'", '{}').replace("'bootstrap_correlation/cor_{/}'", 'bootstrap_correlation/cor_{/}').replace("'bootstrap_correlation/cov_{/}'", 'bootstrap_correlation/cov_{/}').replace("'bootstrap_counts/*'", 'bootstrap_counts/*')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        slots = cls._slots(inputs)
        otu_table = str(inputs.get('otu_table', ''))
        iterations = str(inputs.get('iterations', 50))
        exclude_iterations = str(inputs.get('exclude_iterations', 10))
        threshold = str(inputs.get('threshold', 0.1))
        seed = str(inputs.get('seed', 1))
        number = str(inputs.get('number', 1000))
        mode = str(inputs.get('correlation_mode', 'original') or 'original')
        steps = [cls._shell(['mkdir', '-p', out, 'bootstrap_counts', 'bootstrap_correlation'])]
        if mode == 'new':
            correlation_file = f'{out}/median_correlation.tsv'
            steps.append(cls._shell(['fastspar', '--otu_table', otu_table, '--iterations', iterations, '--exclude_iterations', exclude_iterations, '--threshold', threshold, '--seed', seed, '--correlation', correlation_file, '--covariance', f'{out}/median_covariance.tsv', '--threads', slots, '--yes']))
        else:
            correlation_file = str(inputs.get('correlation_file', ''))
        steps.append(cls._shell(['fastspar_bootstrap', '--otu_table', otu_table, '--number', number, '--prefix', 'bootstrap_counts/data', '--seed', seed, '--threads', slots]))
        steps.append(cls._shell(['parallel', '--max-procs', slots, 'fastspar', '--otu_table', '{}', '--correlation', 'bootstrap_correlation/cor_{/}', '--covariance', 'bootstrap_correlation/cov_{/}', '--iterations', iterations, '--exclude_iterations', exclude_iterations, '--threshold', threshold, '--seed', seed, ':::', 'bootstrap_counts/*']))
        pvalues_cmd = ['fastspar_pvalues', '--otu_table', otu_table, '--correlation', correlation_file, '--prefix', 'bootstrap_correlation/cor_data_', '--permutations', number]
        if inputs.get('pseudo'):
            pvalues_cmd.append('--pseudo')
        pvalues_cmd.extend(['--threads', slots, '--outfile', f'{out}/pvalues.tsv'])
        steps.append(cls._shell(pvalues_cmd))
        return ' && '.join(steps)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        if str(inputs.get('correlation_mode', 'original') or 'original') == 'new':
            outputs.extend([out / 'median_correlation.tsv', out / 'median_covariance.tsv'])
        outputs.append(out / 'pvalues.tsv')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'otu_table': ('TSV', {'description': 'Absolute OTU count table in TSV format'})}, 'optional': {'correlation_mode': ('STRING', {'default': 'original', 'options': ['new', 'original'], 'description': 'Recalculate or use an existing correlation matrix'}), 'correlation_file': ('TSV', {'default': '', 'description': 'Existing FastSpar correlation matrix for original mode'}), 'number': ('INT', {'default': 1000, 'min': 10, 'max': 10000, 'description': 'Number of bootstrap samples'}), 'iterations': ('INT', {'default': 50, 'min': 1, 'max': 1000, 'description': 'Correlation estimation rounds'}), 'exclude_iterations': ('INT', {'default': 10, 'min': 0, 'max': 100, 'description': 'Iterations excluding highly correlated pairs'}), 'threshold': ('FLOAT', {'default': 0.1, 'min': 0, 'max': 1, 'description': 'Correlation exclusion threshold'}), 'seed': ('INT', {'default': 1, 'description': 'Random number seed'}), 'pseudo': ('BOOLEAN', {'default': False, 'description': 'Calculate pseudo p-values instead of exact p-values'}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('otu_table', '')).strip():
            return 'otu_table is required'
        mode = str(inputs.get('correlation_mode', 'original') or 'original')
        if mode not in {'new', 'original'}:
            return 'correlation_mode must be one of: new, original'
        if mode == 'original' and (not str(inputs.get('correlation_file', '')).strip()):
            return 'correlation_file is required when correlation_mode is original'
        for name, minimum, maximum in [('number', 10, 10000), ('iterations', 1, 1000), ('exclude_iterations', 0, 100), ('threads', 1, None)]:
            raw = inputs.get(name)
            if raw is None or str(raw) == '':
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if value < minimum or (maximum is not None and value > maximum):
                return f'{name} must be between {minimum} and {maximum}' if maximum is not None else f'{name} must be >= {minimum}'
        threshold_raw = inputs.get('threshold')
        if threshold_raw is not None and str(threshold_raw) != '':
            try:
                threshold = float(threshold_raw)
            except (TypeError, ValueError):
                return 'threshold must be a number'
            if not 0 <= threshold <= 1:
                return 'threshold must be between 0 and 1'
        return super().VALIDATE_INPUTS(inputs)
