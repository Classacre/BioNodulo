"""chromeister — comparative_genomics node(s). One tool per file (extracted from wrapped_variant_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ChromeisterNode(CommandNode):
    """Run ultra-fast pairwise genome comparison and dotplot generation with Chromeister."""
    NODE_ID = 'chromeister'
    DISPLAY_NAME = 'Chromeister'
    REQUIRED_CONDA_PACKAGES = ['chromeister']
    CATEGORY = 'comparative_genomics'
    DESCRIPTION = 'Compare two FASTA assemblies with Chromeister to produce a comparison matrix, dotplot, event calls, and similarity score.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Chromeister', 'pairwise genome comparison', 'dotplot', 'synteny blocks', 'large-scale rearrangements', 'whole genome comparison', 'CHROMEISTER']
    RETURN_TYPES = ('TXT', 'IMAGE', 'CSV', 'TXT', 'IMAGE', 'TXT')
    RETURN_NAMES = ('matrix', 'dotplot_png', 'metainfo_csv', 'events_txt', 'events_png', 'score')
    REQUIRED_EXECUTABLES = ['CHROMEISTER', 'compute_score.R', 'compute_score-nogrid.R', 'detect_events.py']
    DOCUMENTATION_URL = 'https://github.com/estebanpw/chromeister'
    CITATION_DOIS = ['10.1038/s41598-019-46773-w']
    CITATION_URLS = [f'{DOI_URL}10.1038/s41598-019-46773-w']
    CITATION_TEXT = 'Ultrafast genome comparison for large-scale genomic experiments.'
    VERSION = '1.5.a'
    SHELL = True

    @classmethod
    def _staged_names(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        out = _out(inputs)
        query_name = _safe_name(str(inputs.get('query', 'query.fasta'))) or 'query.fasta'
        db_name = _safe_name(str(inputs.get('db', 'db.fasta'))) or 'db.fasta'
        return (f'{out}/{query_name}', f'{out}/{db_name}')

    @classmethod
    def _matrix_prefix(cls, inputs: dict[str, Any]) -> str:
        query_name, db_name = cls._staged_names(inputs)
        return f'{query_name}-{Path(db_name).name}.mat'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        query_name, db_name = cls._staged_names(inputs)
        matrix = cls._matrix_prefix(inputs)
        score_script = 'compute_score.R' if inputs.get('grid', True) else 'compute_score-nogrid.R'
        cmd = ['ln', '-s', str(inputs.get('query', '')), query_name, '&&', 'ln', '-s', str(inputs.get('db', '')), db_name, '&&', 'CHROMEISTER', '-query', query_name, '-db', db_name, '-dimension', str(inputs.get('dimension', 1000)), '-kmer', str(inputs.get('kmer', 32)), '-diffuse', str(inputs.get('diffuse', 4)), '-out', matrix, '&&', score_script, matrix, str(inputs.get('dimension', 1000)), '>', f'{out}/comparison_score.txt', '&&', 'detect_events.py', f'{matrix}.raw.txt']
        if inputs.get('pngevents', True):
            cmd.extend(['png', '&&', 'mv', f'{matrix}.events.png', f'{out}/events.png'])
        cmd.extend(['&&', 'mv', matrix, f'{out}/comparison_matrix.txt', '&&', 'mv', f'{matrix}.filt.png', f'{out}/dotplot.png', '&&', 'mv', f'{matrix}.events.txt', f'{out}/events.txt', '&&', 'mv', f'{matrix}.csv', f'{out}/comparison_metainfo.csv'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'comparison_matrix.txt', out / 'dotplot.png', out / 'comparison_metainfo.csv', out / 'events.txt']
        if inputs.get('pngevents', False):
            outputs.append(out / 'events.png')
        outputs.append(out / 'comparison_score.txt')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'query': ('FASTA', {'description': 'Query sequence FASTA'}), 'db': ('FASTA', {'description': 'Reference sequence FASTA'})}, 'optional': {'dimension': ('INT', {'default': 1000, 'min': 500, 'max': 2000, 'description': 'Output dotplot size in pixels per side'}), 'kmer': ('INT', {'default': 32, 'options': [32, 16], 'description': 'K-mer seed size'}), 'diffuse': ('INT', {'default': 4, 'min': 1, 'max': 4, 'description': 'Heuristic subsampling level'}), 'grid': ('BOOLEAN', {'default': True, 'description': 'Use grid-aware score computation for multi-FASTA inputs'}), 'pngevents': ('BOOLEAN', {'default': True, 'description': 'Generate a PNG plot of detected rearrangement events'})}, 'hidden': {'output': ('STRING', {})}}
