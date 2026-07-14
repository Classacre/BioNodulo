"""red — genomics node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class RedNode(CommandNode):
    """Detect and mask genomic repeats with RED."""
    NODE_ID = 'red'
    DISPLAY_NAME = 'Red'
    REQUIRED_CONDA_PACKAGES = ['red']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Detect and mask repeats de novo in genome FASTA sequences with RED.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Red', 'RED', 'REpeat Detector', 'repeat masking', 'de novo repeats', 'genome masking']
    RETURN_TYPES = ('FASTA', 'BED')
    RETURN_NAMES = ('masked', 'bed')
    REQUIRED_EXECUTABLES = ['Red']
    DOCUMENTATION_URL = 'https://github.com/BioinformaticsToolsmith/Red'
    CITATION_DOIS = [RED_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{RED_CITATION_DOI}']
    CITATION_TEXT = RED_CITATION_TEXT
    VERSION = '2018.09.10'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = ['Red', '-gnm', f'{out}/input/', '-msk', f'{out}/output/', '-rpt', f'{out}/output/', '-frm', '2', '-cor', slots]
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"mkdir -p {shlex.quote(f'{out}/input')} {shlex.quote(f'{out}/output')} && ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(f'{out}/input/genome.fa')} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / 'output'
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'genome.msk', out / 'genome.bed']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('input'):
            return 'genome FASTA is required'
        try:
            threads = int(inputs.get('threads', 1))
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads < 1:
            return 'threads must be >= 1'
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('FASTA', {'description': 'Genome FASTA sequence to mask'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
