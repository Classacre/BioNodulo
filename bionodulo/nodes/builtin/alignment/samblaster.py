"""samblaster — alignment node(s). One tool per file (extracted from samblaster.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
SAMBLASTER_CITATION_DOI = '10.1093/bioinformatics/btu314'
SAMBLASTER_CITATION_TEXT = 'SAMBLASTER: fast duplicate marking and structural variant read extraction.'
def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get('output_dir', inputs.get('output', '.')))
def _threads(inputs: dict[str, Any]) -> str:
    return str(inputs.get('threads', 4))
def _input_format(inputs: dict[str, Any]) -> str:
    explicit = str(inputs.get('input_format', '') or '').lower()
    if explicit in {'sam', 'bam'}:
        return explicit
    suffixes = Path(str(inputs.get('input', ''))).suffixes
    return 'sam' if '.sam' in {suffix.lower() for suffix in suffixes} else 'bam'
def _enabled(inputs: dict[str, Any], name: str, default: bool=False) -> bool:
    return bool(inputs.get(name, default))


class SamblasterNode(CommandNode):
    """Mark duplicates and extract split, discordant, and unmapped reads."""
    NODE_ID = 'samblaster'
    DISPLAY_NAME = 'samblaster'
    REQUIRED_CONDA_PACKAGES = ['samblaster', 'sambamba']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Mark duplicates and optionally output split reads, discordant read pairs, and unmapped or clipped reads.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'samblaster', 'duplicate marking', 'split reads', 'discordant read pairs', 'structural variant extraction']
    RETURN_TYPES = ('BAM', 'BAM', 'BAM', 'FASTQ')
    RETURN_NAMES = ('alignments', 'discordant_alignments', 'split_alignments', 'unmapped_reads')
    REQUIRED_EXECUTABLES = ['samblaster', 'sambamba']
    DOCUMENTATION_URL = 'https://github.com/GregoryFaust/samblaster'
    CITATION_DOIS = [SAMBLASTER_CITATION_DOI]
    CITATION_URLS = [f'https://doi.org/{SAMBLASTER_CITATION_DOI}']
    CITATION_TEXT = SAMBLASTER_CITATION_TEXT
    VERSION = '0.1.26'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        threads = _threads(inputs)
        input_path = str(inputs.get('input', ''))
        if _input_format(inputs) == 'sam':
            stream = f'<(sambamba view -S -f bam -t {threads} -h {input_path!r})'
        else:
            stream = repr(input_path)
        cmd = ['sambamba', 'view', '-t', threads, '-h', f'<(sambamba sort -t {threads} -n {stream} -o /dev/stdout)', '|', 'samblaster']
        output_enabled = _enabled(inputs, 'output_bam', True)
        if output_enabled:
            cmd.extend(['-o', f'{out}/output.sam'])
        else:
            cmd.extend(['-o', '/dev/null'])
        if _enabled(inputs, 'discordantFile'):
            cmd.extend(['-d', f'{out}/discordant.sam'])
        if _enabled(inputs, 'splitterFile'):
            cmd.extend(['-s', f'{out}/splitter.sam'])
        if _enabled(inputs, 'unmappedFile'):
            cmd.extend(['-u', f'{out}/unmapped.fastq'])
        if _enabled(inputs, 'acceptDupMarks'):
            cmd.append('-a')
        if _enabled(inputs, 'excludeDups'):
            cmd.append('-e')
        if _enabled(inputs, 'removeDups'):
            cmd.append('-r')
        if _enabled(inputs, 'addMateTags'):
            cmd.append('--addMateTags')
        if _enabled(inputs, 'compatibility_mode'):
            cmd.append('-M')
        cmd.extend(['--maxSplitCount', str(inputs.get('maxSplitCount', 2)), '--maxUnmappedBases', str(inputs.get('maxUnmappedBases', 50)), '--minIndelSize', str(inputs.get('minIndelSize', 50)), '--minNonOverlap', str(inputs.get('minNonOverlap', 20)), '--minClipSize', str(inputs.get('minClipSize', 20))])
        if output_enabled:
            cmd.extend(cls._sort_sam_tokens(out, 'output', threads))
        if _enabled(inputs, 'discordantFile'):
            cmd.extend(cls._sort_sam_tokens(out, 'discordant', threads))
        if _enabled(inputs, 'splitterFile'):
            cmd.extend(cls._sort_sam_tokens(out, 'splitter', threads))
        return cmd

    @staticmethod
    def _sort_sam_tokens(out: str, stem: str, threads: str) -> list[str]:
        return ['&&', 'sambamba', 'sort', '-o', f'{out}/{stem}.bam', '-l', '6', '-t', threads, f'<(sambamba view -S -f bam {out}/{stem}.sam)']

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if _enabled(inputs, 'output_bam', True):
            outputs.append(out / 'output.bam')
        if _enabled(inputs, 'discordantFile'):
            outputs.append(out / 'discordant.bam')
        if _enabled(inputs, 'splitterFile'):
            outputs.append(out / 'splitter.bam')
        if _enabled(inputs, 'unmappedFile'):
            outputs.append(out / 'unmapped.fastq')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('BAM', {'description': 'Input SAM or BAM alignment file'})}, 'optional': {'output_bam': ('BOOLEAN', {'default': True, 'description': 'Output BAM file for all input alignments'}), 'discordantFile': ('BOOLEAN', {'default': False, 'description': 'Output discordant read pairs'}), 'splitterFile': ('BOOLEAN', {'default': False, 'description': 'Output split reads'}), 'unmappedFile': ('BOOLEAN', {'default': False, 'description': 'Output unmapped or clipped reads as FASTQ'}), 'acceptDupMarks': ('BOOLEAN', {'default': False, 'description': 'Accept duplicate marks already in the input'}), 'excludeDups': ('BOOLEAN', {'default': False, 'description': 'Exclude duplicate reads from optional side outputs'}), 'removeDups': ('BOOLEAN', {'default': False, 'description': 'Remove duplicate reads from all outputs'}), 'addMateTags': ('BOOLEAN', {'default': False, 'description': 'Add MC and MQ tags to paired-end SAM records'}), 'compatibility_mode': ('BOOLEAN', {'default': False, 'description': 'Treat 0x100 and 0x800 as chimeric alignments'}), 'maxSplitCount': ('INT', {'default': 2, 'min': 2, 'description': 'Maximum split alignments for splitter output'}), 'maxUnmappedBases': ('INT', {'default': 50, 'min': 1, 'description': 'Maximum unaligned bases between split alignments'}), 'minIndelSize': ('INT', {'default': 50, 'min': 1, 'description': 'Minimum structural variant size for split alignments'}), 'minNonOverlap': ('INT', {'default': 20, 'min': 1, 'description': 'Minimum non-overlapping bases between split alignments'}), 'minClipSize': ('INT', {'default': 20, 'min': 1, 'description': 'Minimum clipped bases for unmapped/clipped output'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'description': 'Sambamba sort/view threads'}), 'input_format': ('STRING', {'default': 'bam', 'options': ['bam', 'sam'], 'advanced': True, 'description': 'Input format hint'})}, 'hidden': {'output_dir': ('STRING', {})}}
