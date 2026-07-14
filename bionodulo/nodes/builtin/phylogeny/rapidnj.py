"""rapidnj — phylogeny node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class RapidNJNode(CommandNode):
    """Build neighbour-joining trees or distance matrices with RapidNJ."""
    NODE_ID = 'rapidnj'
    DISPLAY_NAME = 'RapidNJ'
    REQUIRED_CONDA_PACKAGES = ['rapidnj']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Construct neighbour-joining phylogenetic trees or distance matrices rapidly with RapidNJ.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'RapidNJ', 'rapidnj', 'neighbor joining', 'neighbour joining', 'distance matrix', 'Kimura', 'Jukes-Cantor', 'bootstrap']
    RETURN_TYPES = ('PHYLOGENY_TREE',)
    RETURN_NAMES = ('distances',)
    REQUIRED_EXECUTABLES = ['rapidnj']
    DOCUMENTATION_URL = 'https://birc.au.dk/software/rapidnj'
    CITATION_DOIS = [RAPIDNJ_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{RAPIDNJ_CITATION_DOI}']
    CITATION_TEXT = RAPIDNJ_CITATION_TEXT
    VERSION = '2.3.2'
    SHELL = True
    INPUT_FORMAT_OPTIONS = ['fasta', 'stockholm', 'phylip']
    INPUT_FORMAT_FLAGS = {'fasta': ('fa', 'fa'), 'stockholm': ('sth', 'sth'), 'phylip': ('pd', 'pd')}
    OUTPUT_FORMAT_OPTIONS = ['t', 'm']
    EVOLUTION_MODEL_OPTIONS = ['kim', 'jc']
    ALIGNMENT_TYPE_OPTIONS = ['p', 'd']

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_format', 'fasta') or 'fasta')

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output_format', 't') or 't')

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return '.tsv' if cls._output_format(inputs) == 'm' else '.nhx'

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        input_format = cls._input_format(inputs)
        _rapidnj_format, suffix = cls.INPUT_FORMAT_FLAGS.get(input_format, cls.INPUT_FORMAT_FLAGS['fasta'])
        return f'{_out(inputs)}/input.{suffix}'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/distances{cls._output_suffix(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_format = cls._input_format(inputs)
        rapidnj_format, _suffix = cls.INPUT_FORMAT_FLAGS.get(input_format, cls.INPUT_FORMAT_FLAGS['fasta'])
        staged_input = cls._staged_input(inputs)
        cmd = ['rapidnj', staged_input, '--input-format', rapidnj_format, '--output-format', cls._output_format(inputs), '--evolution-model', str(inputs.get('evolution_model', 'kim') or 'kim'), '--cores', str(inputs.get('threads', 1) or 1)]
        if inputs.get('bootstrap') not in (None, ''):
            cmd.extend(['--bootstrap', str(inputs.get('bootstrap'))])
        cmd.extend(['--alignment-type', str(inputs.get('alignment_type', 'p') or 'p')])
        if inputs.get('no_negative_length'):
            cmd.append('--no-negative-length')
        cmd.extend(['>', cls._output_path(inputs)])
        return ' && '.join([f'mkdir -p {shlex.quote(out)}', _shell_join(['ln', '-s', str(inputs.get('alignments', '')), staged_input]), _shell_join(cmd)])

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'distances{cls._output_suffix(inputs)}']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('alignments', '')).strip():
            return 'alignments is required'
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMAT_OPTIONS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMAT_OPTIONS)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMAT_OPTIONS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMAT_OPTIONS)}"
        evolution_model = str(inputs.get('evolution_model', 'kim') or 'kim')
        if evolution_model not in cls.EVOLUTION_MODEL_OPTIONS:
            return f"evolution_model must be one of: {', '.join(cls.EVOLUTION_MODEL_OPTIONS)}"
        alignment_type = str(inputs.get('alignment_type', 'p') or 'p')
        if alignment_type not in cls.ALIGNMENT_TYPE_OPTIONS:
            return f"alignment_type must be one of: {', '.join(cls.ALIGNMENT_TYPE_OPTIONS)}"
        if inputs.get('bootstrap') not in (None, ''):
            try:
                bootstrap = int(inputs.get('bootstrap'))
            except (TypeError, ValueError):
                return 'bootstrap must be an integer'
            if bootstrap < 0:
                return 'bootstrap must be >= 0'
        try:
            threads = int(inputs.get('threads', 1) or 1)
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'alignments': ('ALIGNMENT', {'description': 'FASTA, Stockholm, or PHYLIP alignment/distance input'})}, 'optional': {'input_format': ('STRING', {'default': 'fasta', 'options': cls.INPUT_FORMAT_OPTIONS, 'description': 'Input format: FASTA, Stockholm, or PHYLIP distance/alignment'}), 'output_format': ('STRING', {'default': 't', 'options': cls.OUTPUT_FORMAT_OPTIONS, 'description': 'Output a Newick/NHX tree or distance matrix'}), 'evolution_model': ('STRING', {'default': 'kim', 'options': cls.EVOLUTION_MODEL_OPTIONS, 'description': 'Sequence evolution model'}), 'bootstrap': ('INT', {'default': '', 'min': 0, 'description': 'Bootstrap samples'}), 'alignment_type': ('STRING', {'default': 'p', 'options': cls.ALIGNMENT_TYPE_OPTIONS, 'description': 'Protein or DNA alignment'}), 'no_negative_length': ('BOOLEAN', {'default': False, 'description': 'Adjust negative branch lengths'}), 'threads': ('INT', {'default': 1, 'min': 1, 'description': 'Number of CPU cores'})}, 'hidden': {'output': ('STRING', {})}}
