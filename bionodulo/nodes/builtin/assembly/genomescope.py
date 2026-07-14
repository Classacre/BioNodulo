"""genomescope — assembly node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class GenomeScopeNode(CommandNode):
    """Profile genomes from k-mer spectra with GenomeScope 2.0."""
    NODE_ID = 'genomescope'
    DISPLAY_NAME = 'GenomeScope'
    REQUIRED_CONDA_PACKAGES = ['genomescope2']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Profile genomes from k-mer frequency histograms with the GenomeScope 2.0 model.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'GenomeScope', 'GenomeScope 2.0', 'genomescope2', 'reference-free genome profiling', 'k-mer spectrum', 'kmer histogram', 'polyploid genome profiling']
    RETURN_TYPES = ('IMAGE', 'IMAGE', 'IMAGE', 'IMAGE', 'TEXT', 'TEXT', 'TEXT', 'TSV')
    RETURN_NAMES = ('linear_plot', 'log_plot', 'transformed_linear_plot', 'transformed_log_plot', 'model', 'summary', 'progress', 'model_params')
    REQUIRED_EXECUTABLES = ['genomescope2']
    DOCUMENTATION_URL = 'https://github.com/tbenavi1/genomescope2.0'
    CITATION_DOIS = GENOMESCOPE_CITATION_DOIS
    CITATION_URLS = [f'{DOI_URL}{doi}' for doi in GENOMESCOPE_CITATION_DOIS]
    CITATION_TEXT = GENOMESCOPE_CITATION_TEXT
    VERSION = '2.1.0+galaxy0'
    OUTPUT_CHOICES = ['model_output', 'summary_output', 'progress_output']
    OUTPUT_FILES = {'model_output': 'model.txt', 'summary_output': 'summary.txt', 'progress_output': 'progress.txt'}

    @classmethod
    def _output_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('output_files'))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['genomescope2', '--input', str(inputs.get('input', '')), '--output', _out(inputs), '--kmer_length', str(inputs.get('kmer_length', 21))]
        if inputs.get('no_unique_sequence'):
            cmd.append('--no_unique_sequence')
        if inputs.get('testing'):
            cmd.append('--testing')
        if inputs.get('trace_flag'):
            cmd.append('--trace_flag')
        for name, flag in (('ploidy', '--ploidy'), ('lambda', '--lambda'), ('max_kmercov', '--max_kmercov'), ('topology', '--topology'), ('initial_repetitiveness', '--initial_repetitiveness'), ('initial_heterozygosities', '--initial_heterozygosities'), ('transform_exp', '--transform_exp'), ('true_params', '--true_params'), ('num_rounds', '--num_rounds')):
            _add_if_value(cmd, flag, inputs.get(name))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'linear_plot.png', out / 'log_plot.png', out / 'transformed_linear_plot.png', out / 'transformed_log_plot.png']
        outputs.extend((out / cls.OUTPUT_FILES[output] for output in cls._output_files(inputs) if output in cls.OUTPUT_FILES))
        if inputs.get('testing'):
            outputs.append(out / 'SIMULATED_testing.tsv')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input histogram is required'
        for name, default, minimum, maximum in (('kmer_length', 21, 1, None), ('ploidy', None, 1, 6), ('lambda', None, 1, None), ('max_kmercov', None, 1, None), ('topology', None, 1, None), ('transform_exp', None, 1, None), ('num_rounds', None, 1, None)):
            raw = inputs.get(name, default)
            if raw in (None, ''):
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f'{name} must be an integer'
            if minimum is not None and value < minimum:
                return f'{name} must be >= {minimum}'
            if maximum is not None and value > maximum:
                return f'{name} must be between {minimum} and {maximum}'
        repetitiveness = inputs.get('initial_repetitiveness')
        if repetitiveness not in (None, ''):
            try:
                repetitiveness_value = float(repetitiveness)
            except (TypeError, ValueError):
                return 'initial_repetitiveness must be a number'
            if repetitiveness_value < 0 or repetitiveness_value > 1:
                return 'initial_repetitiveness must be between 0 and 1'
        unsupported_outputs = [output for output in cls._output_files(inputs) if output not in cls.OUTPUT_CHOICES]
        if unsupported_outputs:
            return f"output_files contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Two-column k-mer histogram, such as a Jellyfish histo output'}), 'kmer_length': ('INT', {'default': 21, 'min': 1, 'description': 'K-mer length used to calculate the spectra'})}, 'optional': {'ploidy': ('INT', {'default': '', 'min': 1, 'max': 6, 'description': 'Ploidy for the GenomeScope model'}), 'lambda': ('INT', {'default': '', 'min': 1, 'description': 'Initial k-mer coverage estimate'}), 'max_kmercov': ('INT', {'default': '', 'min': 1, 'description': 'Maximum k-mer coverage threshold'}), 'output_files': ('STRING', {'default': [], 'multiple': True, 'options': cls.OUTPUT_CHOICES, 'description': 'Optional model, summary, and optimization progress reports'}), 'no_unique_sequence': ('BOOLEAN', {'default': False, 'description': 'Turn off the yellow unique-sequence line in plots'}), 'topology': ('INT', {'default': '', 'min': 1, 'description': 'Ploidy topology flag for homologous chromosome relationships'}), 'initial_repetitiveness': ('FLOAT', {'default': '', 'min': 0, 'max': 1, 'description': 'Initial repetitiveness value'}), 'initial_heterozygosities': ('STRING', {'default': '', 'description': 'Comma-separated initial nucleotide heterozygosity rates'}), 'transform_exp': ('INT', {'default': '', 'min': 1, 'description': 'Exponent for transformed k-mer histogram fitting'}), 'testing': ('BOOLEAN', {'default': False, 'description': 'Create SIMULATED_testing.tsv with model parameters'}), 'true_params': ('STRING', {'default': '', 'description': 'Comma-separated true simulated parameters for testing mode'}), 'trace_flag': ('BOOLEAN', {'default': False, 'description': 'Print nlsLM iteration progress'}), 'num_rounds': ('INT', {'default': '', 'min': 1, 'description': 'Number of optimization rounds'})}, 'hidden': {'output': ('STRING', {})}}
