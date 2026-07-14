"""biscot — assembly node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BiSCoTNode(CommandNode):
    """Improve Bionano optical-map scaffolding with BiSCoT."""
    NODE_ID = 'biscot'
    DISPLAY_NAME = 'BiSCoT'
    REQUIRED_CONDA_PACKAGES = ['biscot', 'blat', 'ucsc-pslsort', 'ucsc-pslreps']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Correct Bionano optical-map scaffolds by merging contigs, re-estimating gaps, and writing FASTA and AGP scaffolds.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'BiSCoT', 'BiSCoT optical map', 'Bionano scaffolding correction', 'optical maps', 'CMAP', 'XMAP', 'AGP scaffolds']
    RETURN_TYPES = ('TXT', 'FASTA', 'AGP')
    RETURN_NAMES = ('log', 'fasta', 'agp')
    REQUIRED_EXECUTABLES = ['biscot']
    DOCUMENTATION_URL = 'https://github.com/institut-de-genomique/biscot'
    CITATION_DOIS = ['10.7717/peerj.10150']
    CITATION_URLS = [f'{DOI_URL}10.7717/peerj.10150']
    CITATION_TEXT = 'BiSCoT: improving large eukaryotic genome assemblies with optical maps.'
    VERSION = '2.3.3'
    SHELL = True

    @classmethod
    def _secondary_cmap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('secondary_map_cmap_2', inputs.get('cmap_2', '')) or '')

    @classmethod
    def _secondary_xmap(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('secondary_map_xmap_2', inputs.get('xmap_2', '')) or '')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['biscot', '--cmap-ref', str(inputs.get('cmap_ref', '')), '--cmap-1', str(inputs.get('cmap_1', '')), '--xmap-1', str(inputs.get('xmap_1', '')), '--key', str(inputs.get('key', '')), '--contigs', str(inputs.get('contigs', ''))]
        secondary_cmap = cls._secondary_cmap(inputs)
        secondary_xmap = cls._secondary_xmap(inputs)
        if secondary_cmap:
            cmd.extend(['--cmap-2', secondary_cmap, '--xmap-2', secondary_xmap])
        if inputs.get('xmap_2enz'):
            cmd.extend(['--xmap-2enz', str(inputs.get('xmap_2enz'))])
        if inputs.get('only_confirmed_pos'):
            cmd.append('--only-confirmed-pos')
        if inputs.get('log_file'):
            cmd.extend(['&&', 'cp', 'biscot/biscot.log', f'{out}/biscot.log'])
        cmd.extend(['&&', 'cp', 'biscot/scaffolds.fasta', f'{out}/scaffolds.fasta', '&&', 'cp', 'biscot/scaffolds.agp', f'{out}/scaffolds.agp'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = []
        if inputs.get('log_file'):
            outputs.append(out / 'biscot.log')
        outputs.extend([out / 'scaffolds.fasta', out / 'scaffolds.agp'])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'cmap_ref': ('FILE', {'description': 'Reference anchor CMAP file from Bionano scaffolding'}), 'cmap_1': ('FILE', {'description': 'Primary query CMAP file describing contig labels'}), 'xmap_1': ('FILE', {'description': 'Primary XMAP alignment file for contig labels on the anchor'}), 'key': ('TSV', {'description': 'Bionano key file mapping maps to contig names'}), 'contigs': ('FASTA', {'description': 'Contig FASTA previously scaffolded with Bionano'})}, 'optional': {'secondary_map_cmap_2': ('FILE', {'default': '', 'description': 'Optional secondary-enzyme query CMAP file'}), 'secondary_map_xmap_2': ('FILE', {'default': '', 'description': 'Optional secondary-enzyme XMAP file'}), 'xmap_2enz': ('FILE', {'default': '', 'description': 'Optional two-enzyme XMAP file confirming label mappings'}), 'only_confirmed_pos': ('BOOLEAN', {'default': False, 'description': 'Retain only alignment positions confirmed by the two-enzyme XMAP'}), 'log_file': ('BOOLEAN', {'default': False, 'description': 'Export the BiSCoT log file'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        for field in ['cmap_ref', 'cmap_1', 'xmap_1', 'key', 'contigs']:
            if not str(inputs.get(field, '')).strip():
                return f'{field} is required'
        secondary_cmap = cls._secondary_cmap(inputs)
        secondary_xmap = cls._secondary_xmap(inputs)
        if secondary_cmap and (not secondary_xmap):
            return 'secondary_map_xmap_2 is required when secondary_map_cmap_2 is provided'
        if secondary_xmap and (not secondary_cmap):
            return 'secondary_map_cmap_2 is required when secondary_map_xmap_2 is provided'
        return super().VALIDATE_INPUTS(inputs)
