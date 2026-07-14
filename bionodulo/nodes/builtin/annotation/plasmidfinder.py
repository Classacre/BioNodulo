"""plasmidfinder — annotation node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class PlasmidFinderNode(CommandNode):
    """Identify bacterial plasmid replicons with PlasmidFinder."""
    NODE_ID = 'plasmidfinder'
    DISPLAY_NAME = 'PlasmidFinder'
    REQUIRED_CONDA_PACKAGES = ['plasmidfinder']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Identify plasmid replicons in bacterial assemblies or reads with PlasmidFinder.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'PlasmidFinder', 'plasmidfinder', 'plasmid identification', 'plasmid replicon', 'pMLST', 'bacterial WGS', 'replicon typing']
    RETURN_TYPES = ('JSON', 'FASTA', 'FASTA', 'TSV', 'TXT', 'TXT')
    RETURN_NAMES = ('json_file', 'hit_file', 'plasmid_file', 'result_file', 'raw_file', 'log_file')
    REQUIRED_EXECUTABLES = ['plasmidfinder.py']
    DOCUMENTATION_URL = PLASMIDFINDER_DOCUMENTATION_URL
    CITATION_DOIS = [PLASMIDFINDER_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{PLASMIDFINDER_CITATION_DOI}']
    CITATION_TEXT = PLASMIDFINDER_CITATION_TEXT
    VERSION = '2.1.6'
    SHELL = True
    INPUT_FORMATS = ['fasta', 'fastq']
    OUTPUT_SELECTIONS = ['data_json', 'hit_fasta', 'plasmid_fasta', 'result_tsv', 'result_txt', 'logfile']
    DEFAULT_OUTPUT_SELECTIONS = ['hit_fasta', 'plasmid_fasta', 'result_tsv', 'result_txt']
    OUTPUT_FILES = {'data_json': 'data.json', 'hit_fasta': 'Hit_in_genome_seq.fsa', 'plasmid_fasta': 'Plasmid_seqs.fsa', 'result_tsv': 'results_tab.tsv', 'result_txt': 'results.txt', 'logfile': 'log.txt'}

    @classmethod
    def _format_fraction(cls, value: Any, default: float) -> str:
        parsed = float(value if value not in (None, '') else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_dir'

    @classmethod
    def _temp_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/temp_dir'

    @classmethod
    def _log_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/log.txt'

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        selected = _as_list(inputs.get('output_selection'))
        return selected or list(cls.DEFAULT_OUTPUT_SELECTIONS)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get('input_format', 'fasta') or 'fasta')
        method = 'kma' if input_format == 'fastq' else 'blastn'
        cmd = ['plasmidfinder.py', '-i', str(inputs.get('input_file', '')), '-p', str(inputs.get('database', '')), '-l', cls._format_fraction(inputs.get('min_cov'), 0.6), '-t', cls._format_fraction(inputs.get('threshold'), 0.95), '-mp', method, '-x', '-o', cls._output_dir(inputs), '-tmp', cls._temp_dir(inputs)]
        return f'mkdir -p {shlex.quote(cls._output_dir(inputs))} {shlex.quote(cls._temp_dir(inputs))} && {_shell_join(cmd)} | tee {shlex.quote(cls._log_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[selection] for selection in cls._selected_outputs(inputs)]

    @classmethod
    def _fraction_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < 0 or value > 1:
            return f'{name} must be between 0 and 1'
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input_file', '')).strip():
            return 'input_file is required'
        if not str(inputs.get('database', '')).strip():
            return 'database is required'
        input_format = str(inputs.get('input_format', 'fasta') or 'fasta')
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        for name, default in [('min_cov', 0.6), ('threshold', 0.95)]:
            result = cls._fraction_range(inputs, name, default)
            if result is not True:
                return result
        invalid_outputs = [selection for selection in cls._selected_outputs(inputs) if selection not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"output_selection values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('FILE', {'description': 'FASTA assembly or FASTQ reads to scan for plasmid replicons'}), 'database': ('DIRECTORY', {'description': "PlasmidFinder database directory from Galaxy's plasmidfinder_database table"})}, 'optional': {'input_format': ('STRING', {'default': 'fasta', 'options': cls.INPUT_FORMATS, 'description': 'Input data type; FASTA uses blastn and FASTQ uses KMA like the Galaxy wrapper'}), 'min_cov': ('FLOAT', {'default': 0.6, 'min': 0, 'max': 1, 'description': 'Minimum fraction of target sequence covered'}), 'threshold': ('FLOAT', {'default': 0.95, 'min': 0, 'max': 1, 'description': 'Minimum nucleotide identity fraction'}), 'output_selection': ('STRING_LIST', {'default': cls.DEFAULT_OUTPUT_SELECTIONS, 'options': cls.OUTPUT_SELECTIONS, 'multiple': True, 'description': 'Galaxy output files to collect from the PlasmidFinder run'})}, 'hidden': {'output': ('STRING', {})}}
