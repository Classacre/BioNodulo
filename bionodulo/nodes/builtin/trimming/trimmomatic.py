"""trimmomatic — trimming node(s). One tool per file (extracted from trimming.py)."""
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


class TrimmomaticNode(CommandNode):
    """Adapter trimming with Trimmomatic."""
    NODE_ID = 'trimmomatic'
    DISPLAY_NAME = 'Trimmomatic'
    REQUIRED_CONDA_PACKAGES = ['trimmomatic']
    CATEGORY = 'trimming'
    DESCRIPTION = 'Flexible read trimming tool for Illumina NGS data'
    SEARCH_ALIASES = ['trimmomatic', 'trim', 'adapter removal']
    RETURN_TYPES = ('FASTQ_LIST', 'FASTQ_LIST', 'FASTQ_LIST', 'FASTQ_LIST')
    RETURN_NAMES = ('R1_paired', 'R1_unpaired', 'R2_paired', 'R2_unpaired')
    REQUIRED_EXECUTABLES = ['trimmomatic']
    DOCUMENTATION_URL = 'http://www.usadellab.org/cms/?page=trimmomatic'
    VERSION = '0.40'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', inputs.get('output_dir', '.')))
        reads = inputs.get('reads', [])
        if isinstance(reads, str):
            reads = [reads]
        cmd = ['trimmomatic', 'PE', '-threads', str(inputs.get('threads', 4)), str(reads[0]) if len(reads) > 0 else '', str(reads[1]) if len(reads) > 1 else '', f'{output}/R1_paired.fastq.gz', f'{output}/R1_unpaired.fastq.gz', f'{output}/R2_paired.fastq.gz', f'{output}/R2_unpaired.fastq.gz', f"ILLUMINACLIP:{inputs.get('adapters', 'TruSeq3-PE.fa')}:2:30:10", f"LEADING:{inputs.get('leading', 3)}", f"TRAILING:{inputs.get('trailing', 3)}", f"SLIDINGWINDOW:4:{inputs.get('quality', 15)}", f"MINLEN:{inputs.get('minlen', 36)}"]
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'}), 'adapters': ('STRING', {'default': 'TruSeq3-PE.fa'})}, 'optional': {'leading': ('INT', {'default': 3, 'min': 1, 'max': 40}), 'trailing': ('INT', {'default': 3, 'min': 1, 'max': 40}), 'quality': ('INT', {'default': 15, 'min': 1, 'max': 40}), 'minlen': ('INT', {'default': 36, 'min': 1})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run Trimmomatic and return all four outputs."""
        output_dir = kwargs.get('output_dir')
        ctx = kwargs.get('context')
        if output_dir is None and ctx is not None:
            output_dir = getattr(ctx, 'node_dir', '.')
        if output_dir is None:
            output_dir = '.'
        await super().run(**kwargs)
        out = Path(output_dir) / self.NODE_ID
        return {'outputs': {'R1_paired': [str(out / 'R1_paired.fastq.gz')], 'R1_unpaired': [str(out / 'R1_unpaired.fastq.gz')], 'R2_paired': [str(out / 'R2_paired.fastq.gz')], 'R2_unpaired': [str(out / 'R2_unpaired.fastq.gz')]}}
