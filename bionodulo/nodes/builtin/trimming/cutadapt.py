"""cutadapt — trimming node(s). One tool per file (extracted from trimming.py)."""
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


class CutadaptNode(CommandNode):
    """Adapter trimming with Cutadapt."""
    NODE_ID = 'cutadapt'
    DISPLAY_NAME = 'Cutadapt'
    CATEGORY = 'trimming'
    DESCRIPTION = 'Remove adapter sequences from high-throughput sequencing reads'
    SEARCH_ALIASES = ['cutadapt', 'trim adapters', 'adapter']
    RETURN_TYPES = ('FASTQ_LIST',)
    RETURN_NAMES = ('trimmed_reads',)
    REQUIRED_EXECUTABLES = ['cutadapt']
    REQUIRED_CONDA_PACKAGES = ['cutadapt']
    DOCUMENTATION_URL = 'https://cutadapt.readthedocs.io/'
    VERSION = '5.2'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', inputs.get('output_dir', '.')))
        reads = inputs.get('reads', [])
        if isinstance(reads, str):
            reads = [reads]
        cmd = ['cutadapt', '-a', str(inputs.get('adapter_r1', 'AGATCGGAAGAGC')), '-A', str(inputs.get('adapter_r2', 'AGATCGGAAGAGC')), '-o', f'{output}/trimmed_reads.fastq.gz', '-p', f'{output}/trimmed_reads_2.fastq.gz', '-j', str(inputs.get('threads', 4))]
        if inputs.get('minimum_length') is not None:
            cmd.extend(['-m', str(inputs['minimum_length'])])
        if inputs.get('quality_cutoff') is not None:
            cmd.extend(['-q', str(inputs['quality_cutoff'])])
        if len(reads) > 0:
            cmd.append(str(reads[0]))
        if len(reads) > 1:
            cmd.append(str(reads[1]))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'}), 'adapter_r1': ('STRING', {'default': 'AGATCGGAAGAGC'})}, 'optional': {'adapter_r2': ('STRING', {'default': 'AGATCGGAAGAGC'}), 'minimum_length': ('INT', {'default': 20, 'min': 1}), 'quality_cutoff': ('INT', {'default': 20, 'min': 1, 'max': 40})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run Cutadapt and return paired trimmed reads."""
        output_dir = kwargs.get('output_dir')
        ctx = kwargs.get('context')
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, 'node_dir', '.')
        if output_dir is None:
            output_dir = '.'
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {'outputs': {'trimmed_reads': [str(out / 'trimmed_reads.fastq.gz'), str(out / 'trimmed_reads_2.fastq.gz')]}}
