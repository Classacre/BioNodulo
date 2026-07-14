"""bamutil — alignment node(s). One tool per file (extracted from bam_cram_utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
GALAXY_ALIAS = 'BioNodulo builtin'
CRAMINO_CITATION_DOI = '10.1093/bioinformatics/btad311'
CRAMINO_CITATION_TEXT = 'NanoPack2: population-scale evaluation of long-read sequencing data.'
BAMUTIL_CITATION_DOI = '10.1101/gr.176552.114'
BAMUTIL_CITATION_TEXT = 'GotCloud: a sequence analysis pipeline for high-quality variant calls.'
def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get('output', inputs.get('output_dir', '.')))
def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != '':
        cmd.extend([flag, str(value)])
def _common_output(node_id: str, filename: str, output_dir: str | Path) -> Path:
    out = Path(output_dir) / node_id
    out.mkdir(parents=True, exist_ok=True)
    return out / filename
def _cramino_metrics_name(inputs: dict[str, Any]) -> str:
    return {'json': 'metrics.json', 'tsv': 'metrics.tsv', 'text': 'metrics.txt'}.get(str(inputs.get('outfmt', 'text')), 'metrics.txt')
def _bamutil_diff_ext(inputs: dict[str, Any]) -> str:
    output_as = str(inputs.get('output_as', 'diff.txt'))
    return Path(output_as).suffix.lstrip('.') or 'txt'
def _path_stem(value: Any, fallback: str) -> str:
    stem = Path(str(value or '')).stem
    return stem or fallback


class BamUtilClipOverlapNode(CommandNode):
    """Clip overlapping paired-end reads with BamUtil clipOverlap."""
    NODE_ID = 'bamutil_clip_overlap'
    DISPLAY_NAME = 'BamUtil clipOverlap'
    REQUIRED_CONDA_PACKAGES = ['bamutil']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Clip overlapping paired-end reads in SAM or BAM alignments using BamUtil clipOverlap.'
    SEARCH_ALIASES = [GALAXY_ALIAS, 'bamutil', 'clipOverlap', 'clip overlapping read pairs', 'overlap clipping']
    RETURN_TYPES = ('BAM', 'STATS_FILE')
    RETURN_NAMES = ('clipped_alignment', 'overlap_stats')
    REQUIRED_EXECUTABLES = ['bam']
    DOCUMENTATION_URL = 'https://genome.sph.umich.edu/wiki/BamUtil:_clipOverlap'
    CITATION_DOIS = [BAMUTIL_CITATION_DOI]
    CITATION_URLS = [f'https://doi.org/{BAMUTIL_CITATION_DOI}']
    CITATION_TEXT = BAMUTIL_CITATION_TEXT
    VERSION = '1.0.15'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['bam', 'clipOverlap', '--in', str(inputs.get('input', ''))]
        _add_if_value(cmd, '--storeOrig', inputs.get('storeOrig'))
        if inputs.get('stats'):
            cmd.append('--stats')
        if inputs.get('readName'):
            cmd.append('--readName')
        if inputs.get('overlapsOnly'):
            cmd.append('--overlapsOnly')
        _add_if_value(cmd, '--excludeFlags', inputs.get('excludeFlags'))
        if inputs.get('unmapped'):
            cmd.append('--unmapped')
        cmd.extend(['--noPhoneHome', '--out', f'{out}/clipped.bam', '2>', f'{out}/output.log'])
        if inputs.get('stats'):
            cmd.extend(['&&', 'cp', f'{out}/output.log', f'{out}/overlap_stats.txt'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        outputs = [_common_output(cls.NODE_ID, 'clipped.bam', output_dir)]
        if inputs.get('stats'):
            outputs.append(_common_output(cls.NODE_ID, 'overlap_stats.txt', output_dir))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BAM', {'description': 'Coordinate-sorted SAM/BAM alignment file'})}, 'optional': {'storeOrig': ('STRING', {'default': '', 'description': 'SAM tag used to store original CIGAR values'}), 'stats': ('BOOLEAN', {'default': False, 'description': 'Output overlap clipping statistics'}), 'readName': ('BOOLEAN', {'default': False, 'description': 'Treat input as read-name sorted'}), 'overlapsOnly': ('BOOLEAN', {'default': False, 'description': 'Only output overlapping read pairs'}), 'excludeFlags': ('INT', {'default': '', 'description': 'Skip records with any of these SAM flag bits set'}), 'unmapped': ('BOOLEAN', {'default': False, 'description': 'Mark fully clipped reads as unmapped'})}, 'hidden': {'output': ('STRING', {})}}


class BamUtilDiffNode(CommandNode):
    """Compare coordinate-sorted SAM/BAM files with BamUtil diff."""
    NODE_ID = 'bamutil_diff'
    DISPLAY_NAME = 'BamUtil diff'
    REQUIRED_CONDA_PACKAGES = ['bamutil']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Compare two coordinate-sorted SAM or BAM files and report differing records with BamUtil diff.'
    SEARCH_ALIASES = [GALAXY_ALIAS, 'bamutil', 'diff', 'compare SAM BAM files', 'alignment diff']
    RETURN_TYPES = ('FILE', 'FILE', 'FILE')
    RETURN_NAMES = ('diff', 'only_in_first', 'only_in_second')
    REQUIRED_EXECUTABLES = ['bam']
    DOCUMENTATION_URL = 'https://genome.sph.umich.edu/wiki/BamUtil:_diff'
    CITATION_DOIS = [BAMUTIL_CITATION_DOI]
    CITATION_URLS = [f'https://doi.org/{BAMUTIL_CITATION_DOI}']
    CITATION_TEXT = BAMUTIL_CITATION_TEXT
    VERSION = '1.0.15'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        output_as = str(inputs.get('output_as', 'diff.txt'))
        cmd = ['bam', 'diff', '--in1', str(inputs.get('in1', '')), '--in2', str(inputs.get('in2', ''))]
        fields_choice = str(inputs.get('fields_choice', 'default'))
        if fields_choice == 'all':
            cmd.append('--all')
        elif fields_choice == 'select':
            for key, flag in (('flag', '--flag'), ('mapQual', '--mapQual'), ('mate', '--mate'), ('isize', '--isize'), ('seq', '--seq'), ('baseQual', '--baseQual'), ('noCigar', '--noCigar'), ('noPos', '--noPos')):
                if inputs.get(key):
                    cmd.append(flag)
            tagchoice = str(inputs.get('tagchoice', 'none'))
            if tagchoice == 'everyTag':
                cmd.append('--everyTag')
            elif tagchoice == 'specify':
                _add_if_value(cmd, '--tags', inputs.get('tags'))
        cmd.extend(['--posDiff', str(inputs.get('posDiff', 100000)), '--recPoolSize', '-1'])
        if inputs.get('onlyDiffs'):
            cmd.append('--onlyDiffs')
        cmd.extend(['--params', '--noPhoneHome', '--out', f'{out}/{output_as}'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_as = str(inputs.get('output_as', 'diff.txt'))
        output_stem = Path(output_as).stem or 'diff'
        ext = _bamutil_diff_ext(inputs)
        if ext == 'txt':
            return [_common_output(cls.NODE_ID, f'{output_stem}.txt', output_dir)]
        in1_stem = _path_stem(inputs.get('in1'), 'in1')
        in2_stem = _path_stem(inputs.get('in2'), 'in2')
        return [_common_output(cls.NODE_ID, f'{output_stem}.{ext}', output_dir), _common_output(cls.NODE_ID, f'{output_stem}_only1_{in1_stem}.{ext}', output_dir), _common_output(cls.NODE_ID, f'{output_stem}_only2_{in2_stem}.{ext}', output_dir)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in1': ('BAM', {'description': 'First coordinate-sorted SAM/BAM alignment file'}), 'in2': ('BAM', {'description': 'Second coordinate-sorted SAM/BAM alignment file'})}, 'optional': {'posDiff': ('INT', {'default': 100000, 'min': 0, 'description': 'Maximum position difference for potentially matching records'}), 'onlyDiffs': ('BOOLEAN', {'default': False, 'description': 'Only print compared fields that differ'}), 'fields_choice': ('STRING', {'default': 'default', 'options': ['default', 'all', 'select'], 'description': 'SAM/BAM fields to compare'}), 'flag': ('BOOLEAN', {'default': False, 'description': 'Compare SAM flags'}), 'mapQual': ('BOOLEAN', {'default': False, 'description': 'Compare mapping qualities'}), 'mate': ('BOOLEAN', {'default': False, 'description': 'Compare mate chromosome and position'}), 'isize': ('BOOLEAN', {'default': False, 'description': 'Compare insert sizes'}), 'seq': ('BOOLEAN', {'default': False, 'description': 'Compare sequence bases'}), 'baseQual': ('BOOLEAN', {'default': False, 'description': 'Compare base qualities'}), 'noCigar': ('BOOLEAN', {'default': False, 'description': 'Do not compare CIGAR strings'}), 'noPos': ('BOOLEAN', {'default': False, 'description': 'Do not compare positions'}), 'tagchoice': ('STRING', {'default': 'none', 'options': ['none', 'everyTag', 'specify'], 'description': 'SAM tag comparison mode'}), 'tags': ('STRING', {'default': '', 'description': 'Comma-separated tags to compare, such as AS:i,MD:Z'}), 'output_as': ('STRING', {'default': 'diff.txt', 'options': ['diff.txt', 'diff.bam', 'diff.sam'], 'description': 'Output format'})}, 'hidden': {'output': ('STRING', {})}}
