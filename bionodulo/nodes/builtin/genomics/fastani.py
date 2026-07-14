"""fastani — genomics node(s). One tool per file (extracted from wrapped_hyphy_metagenomics.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class FastANINode(CommandNode):
    """Compute whole-genome average nucleotide identity with FastANI."""
    NODE_ID = 'fastani'
    DISPLAY_NAME = 'FastANI'
    REQUIRED_CONDA_PACKAGES = ['fastani']
    CATEGORY = 'genomics'
    DESCRIPTION = 'Compute alignment-free whole-genome Average Nucleotide Identity for one or more query/reference genomes.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'fastani', 'ANI', 'average nucleotide identity', 'genome comparison']
    RETURN_TYPES = ('TSV', 'FILE', 'FILE')
    RETURN_NAMES = ('ani_table', 'ani_matrix', 'visual_mappings')
    REQUIRED_EXECUTABLES = ['fastANI']
    DOCUMENTATION_URL = 'https://github.com/ParBLiSS/FastANI'
    CITATION_DOIS = ['10.1038/s41467-018-07641-9']
    CITATION_URLS = [f'{DOI_URL}10.1038/s41467-018-07641-9']
    CITATION_TEXT = 'High throughput ANI analysis of 90K prokaryotic genomes reveals clear species boundaries.'
    VERSION = '1.3'

    async def run(self, **kwargs: Any) -> Any:
        output_dir = kwargs.get('output_dir')
        context = kwargs.get('context')
        if output_dir is None and context is not None:
            output_dir = getattr(context, 'node_dir', '.')
        node_out = Path(output_dir) / self.__class__.NODE_ID if output_dir else Path('.')
        node_out.mkdir(parents=True, exist_ok=True)
        query_files = _as_list(kwargs.get('query'))
        ref_files = _as_list(kwargs.get('reference'))
        if query_files:
            (node_out / 'query.lst').write_text('\n'.join(query_files) + '\n', encoding='utf-8')
        if ref_files:
            (node_out / 'ref.lst').write_text('\n'.join(ref_files) + '\n', encoding='utf-8')
        return await super().run(**kwargs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        query_files = _as_list(inputs.get('query'))
        ref_files = _as_list(inputs.get('reference'))
        cmd = ['fastANI']
        if len(query_files) == 1:
            cmd.extend(['-q', query_files[0]])
        else:
            cmd.extend(['--ql', f'{out}/query.lst'])
        if len(ref_files) == 1:
            cmd.extend(['-r', ref_files[0]])
        else:
            cmd.extend(['--rl', f'{out}/ref.lst'])
        cmd.extend(['-o', f'{out}/fastani.tsv', '-t', str(inputs.get('threads', 1))])
        _add_if_value(cmd, '--fragLen', inputs.get('frag_len'))
        _add_if_value(cmd, '--minFraction', inputs.get('min_fraction'))
        _add_if_value(cmd, '-k', inputs.get('kmer'))
        if inputs.get('matrix'):
            cmd.append('--matrix')
        if inputs.get('visualize'):
            cmd.append('--visualize')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'fastani.tsv']
        if inputs.get('matrix'):
            outputs.append(out / 'fastani.tsv.matrix')
        if inputs.get('visualize'):
            outputs.append(out / 'fastani.tsv.visual')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTA_LIST', {'description': 'One or more query genome assemblies'}), 'reference': ('FASTA_LIST', {'description': 'One or more reference genome assemblies'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 128, 'display': 'slider'}), 'frag_len': ('INT', {'default': 3000, 'min': 100, 'description': 'Fragment length used by FastANI'}), 'min_fraction': ('FLOAT', {'default': 0.2, 'min': 0, 'max': 1}), 'kmer': ('INT', {'default': 16, 'min': 4, 'max': 32}), 'matrix': ('BOOLEAN', {'default': False, 'description': 'Also emit PHYLIP-style ANI matrix'}), 'visualize': ('BOOLEAN', {'default': False, 'description': 'Emit reciprocal mapping file for visualization'})}, 'hidden': {'output': ('STRING', {})}}
