"""fastp — trimming node(s). One tool per file (extracted from trimming.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _read_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if str(item)]
    text = str(value).strip()
    return [text] if text else []
def _fastq_stem(value: Any, default: str) -> str:
    name = Path(str(value or default)).name
    for suffix in ('.fastq.gz', '.fq.gz', '.fastq', '.fq', '.gz'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    return name or default


class FastpNode(CommandNode):
    """Adapter trimming and quality filtering with fastp."""
    NODE_ID = 'fastp'
    DISPLAY_NAME = 'fastp Trim'
    REQUIRED_CONDA_PACKAGES = ['fastp']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Ultra-fast all-in-one FASTQ preprocessor: trim adapters, filter by quality'
    SEARCH_ALIASES = ['fastp', 'trim', 'adapter', 'quality filter']
    RETURN_TYPES = ('FASTQ_LIST', 'HTML_REPORT')
    RETURN_NAMES = ('trimmed_reads', 'report')
    REQUIRED_EXECUTABLES = ['fastp']
    DOCUMENTATION_URL = 'https://github.com/OpenGene/fastp'
    VERSION = '0.24.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', inputs.get('output_dir', '.')))
        reads = inputs.get('reads', [])
        if isinstance(reads, str):
            reads = [reads]
        cmd = ['fastp', '-i', str(reads[0]) if len(reads) > 0 else '', '-I', str(reads[1]) if len(reads) > 1 else '', '-o', f'{output}/trimmed_reads.fastq.gz', '-O', f'{output}/trimmed_reads_2.fastq.gz', '-h', f'{output}/report.html', '-j', f'{output}/report.json', '-w', str(inputs.get('threads', 4))]
        if inputs.get('qualified_quality_phred') is not None:
            cmd.extend(['-q', str(inputs['qualified_quality_phred'])])
        if inputs.get('cut_front'):
            cmd.append('--cut_front')
        if inputs.get('cut_tail'):
            cmd.append('--cut_tail')
        if inputs.get('length_required') is not None:
            cmd.extend(['--length_required', str(inputs['length_required'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'qualified_quality_phred': ('INT', {'default': 15, 'min': 1, 'max': 40, 'description': 'Quality threshold for trimming (fastp default: 15)'}), 'cut_front': ('BOOLEAN', {'default': False, 'description': "Trim low-quality bases from 5' end (fastp default: OFF)"}), 'cut_tail': ('BOOLEAN', {'default': False, 'description': "Trim low-quality bases from 3' end (fastp default: OFF)"}), 'length_required': ('INT', {'default': 15, 'min': 1, 'description': 'Discard reads shorter than this (fastp default: 15)'})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run fastp and return paired trimmed reads as a list."""
        output_dir = kwargs.get('output_dir')
        ctx = kwargs.get('context')
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, 'node_dir', '.')
        if output_dir is None:
            output_dir = '.'
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {'outputs': {'trimmed_reads': [str(out / 'trimmed_reads.fastq.gz'), str(out / 'trimmed_reads_2.fastq.gz')], 'report': str(out / 'report.html')}}
