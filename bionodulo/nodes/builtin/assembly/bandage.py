"""bandage — assembly node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BandageInfoNode(CommandNode):
    """Summarize de novo assembly graph statistics with Bandage info."""
    NODE_ID = 'bandage_info'
    DISPLAY_NAME = 'Bandage Info'
    REQUIRED_CONDA_PACKAGES = ['bandage_ng']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Determine node, edge, length, connectivity, and N50 statistics for de novo assembly graphs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Bandage', 'bandage info', 'assembly graph', 'GFA statistics', 'FASTG statistics', 'de novo assembly graph']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('outfile',)
    REQUIRED_EXECUTABLES = ['Bandage']
    DOCUMENTATION_URL = 'https://github.com/rrwick/Bandage/wiki/Command-line-options#info'
    CITATION_DOIS = [BANDAGE_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BANDAGE_CITATION_DOI}']
    CITATION_TEXT = BANDAGE_CITATION_TEXT
    VERSION = '2022.09'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = _bandage_prefix(inputs, out)
        cmd.extend(['Bandage', 'info', f'{out}/input.gfa'])
        if inputs.get('tsv'):
            cmd.append('--tsv')
        cmd.extend(['|', 'sed', 's/:\\s\\+/:\\t/g', '>', f'{out}/out.tab'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out.tab']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('GFA', {'description': 'Assembly graph in GFA1, GFA2, FASTG, LastGraph, Trinity.fasta, ASQG, or text format'})}, 'optional': {'tsv': ('BOOLEAN', {'default': False, 'description': 'Output information as a single tab-delimited line'})}, 'hidden': {'output': ('STRING', {})}}
