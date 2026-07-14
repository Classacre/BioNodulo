"""gfa — assembly node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class GfaToFaNode(CommandNode):
    """Convert GFA segment records to FASTA with Galaxy's helper script."""
    NODE_ID = 'gfa_to_fa'
    DISPLAY_NAME = 'GFA to FASTA'
    REQUIRED_CONDA_PACKAGES = ['python']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Convert Graphical Fragment Assembly files to FASTA format.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'gfa_to_fa', 'GFA to FASTA', 'Graphical Fragment Assembly', 'assembly graph conversion', 'GFA v1', 'FASTA conversion']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('out_fa',)
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = GFA_TO_FA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [GFA_TO_FA_CITATION_URL]
    CITATION_TEXT = GFA_TO_FA_CITATION_TEXT
    VERSION = '0.1.2'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out.fa'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['cat', str(inputs.get('in_gfa', '')), '|', 'python', str(inputs.get('script_path', 'gfa_to_fa.py')), '>', cls._output_path(inputs)]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.fa']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_gfa', '')).strip():
            return 'in_gfa is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_gfa': ('GFA', {'description': 'Input GFA file'})}, 'optional': {'script_path': ('FILE', {'default': 'gfa_to_fa.py', 'advanced': True, 'description': 'Path to the Galaxy gfa_to_fa helper script'})}, 'hidden': {'output': ('STRING', {})}}
