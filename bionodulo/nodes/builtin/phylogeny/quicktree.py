"""quicktree — phylogeny node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class QuicktreeNode(CommandNode):
    """Build phylogenetic trees or distance matrices with Quicktree."""
    NODE_ID = 'quicktree'
    DISPLAY_NAME = 'Quicktree'
    REQUIRED_CONDA_PACKAGES = ['quicktree', 'hmmer']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Construct phylogenetic trees or distance matrices from alignments with Quicktree.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Quicktree', 'quicktree', 'neighbor joining', 'distance matrix', 'UPGMA', 'Kimura', 'bootstrap']
    RETURN_TYPES = ('PHYLOGENY_TREE',)
    RETURN_NAMES = ('output_file',)
    REQUIRED_EXECUTABLES = ['quicktree', 'esl-reformat']
    DOCUMENTATION_URL = 'https://github.com/khowe/quicktree'
    CITATION_DOIS = [QUICKTREE_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{QUICKTREE_CITATION_DOI}']
    CITATION_TEXT = QUICKTREE_CITATION_TEXT
    VERSION = '2.5'
    SHELL = True

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return '.dist' if str(inputs.get('output_type', 'tree_out')) == 'dist_out' else '.nwk'

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/output_file{cls._output_suffix(inputs)}'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get('format', 'align'))
        input_file = str(inputs.get('input_file', ''))
        if input_format == 'dist':
            stage = f'ln -s {shlex.quote(input_file)} input.quicktree'
            in_mode = 'm'
        else:
            stage = f'esl-reformat -o input.quicktree stockholm {shlex.quote(input_file)}'
            in_mode = 'a'
        out_mode = 'm' if str(inputs.get('output_type', 'tree_out')) == 'dist_out' else 't'
        cmd = ['quicktree', '-in', in_mode, '-out', out_mode]
        if inputs.get('upgma'):
            cmd.append('-upgma')
        if inputs.get('kimura'):
            cmd.append('-kimura')
        if inputs.get('boot') not in (None, ''):
            cmd.extend(['-boot', str(inputs.get('boot'))])
        cmd.append('input.quicktree')
        return f'{stage} && {_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f'output_file{cls._output_suffix(inputs)}']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input_file'):
            return 'input alignment or distance matrix is required'
        if inputs.get('boot') not in (None, ''):
            try:
                boot = int(inputs.get('boot'))
            except (TypeError, ValueError):
                return 'boot must be an integer'
            if boot < 0:
                return 'boot must be >= 0'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'format': ('STRING', {'default': 'align', 'options': ['align', 'dist'], 'description': 'Input alignment or distance matrix'}), 'input_file': ('ALIGNMENT', {'description': 'Alignment or PHYLIP-format distance matrix'}), 'output_type': ('STRING', {'default': 'tree_out', 'options': ['tree_out', 'dist_out'], 'description': 'Newick tree or distance matrix output'})}, 'optional': {'upgma': ('BOOLEAN', {'default': False, 'description': 'Use UPGMA instead of neighbor joining'}), 'kimura': ('BOOLEAN', {'default': False, 'description': 'Apply Kimura translation to pairwise distances'}), 'boot': ('INT', {'default': '', 'min': 0, 'description': 'Bootstrap iterations'})}, 'hidden': {'output': ('STRING', {})}}
