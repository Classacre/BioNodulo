"""minimap2 — alignment node(s). One tool per file (extracted from alignment.py)."""
from __future__ import annotations
import shutil
from pathlib import Path
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode
def _split_reads(inputs: dict[str, Any]) -> tuple[Any, Any]:
    """Return R1/R2 from a FASTQ list or explicit r1/r2 aliases."""
    reads = inputs.get('reads', [])
    if isinstance(reads, str):
        reads = [reads]
    r1 = reads[0] if len(reads) > 0 else inputs.get('r1', '')
    r2 = reads[1] if len(reads) > 1 else inputs.get('r2', '')
    return (r1, r2)
def _inject_read_aliases(inputs: dict[str, Any]) -> None:
    """Populate r1/r2 aliases from reads when callers use FASTQ_LIST inputs."""
    r1, r2 = _split_reads(inputs)
    if r1:
        inputs['r1'] = r1
    if r2:
        inputs['r2'] = r2


class Minimap2IndexNode(CommandNode):
    """Build Minimap2 index."""
    NODE_ID = 'minimap2_index'
    DISPLAY_NAME = 'Minimap2 Index'
    REQUIRED_CONDA_PACKAGES = ['minimap2']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Build Minimap2 index for long-read alignment'
    SEARCH_ALIASES = ['minimap2', 'index', 'long reads']
    RETURN_TYPES = ('INDEX_DIR',)
    RETURN_NAMES = ('index',)
    REQUIRED_EXECUTABLES = ['minimap2']
    DOCUMENTATION_URL = 'https://lh3.github.io/minimap2/'
    VERSION = '2.30'
    COMMAND = ['minimap2', '-d', '{output}/index.mmi', '{inputs.reference}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference': ('FASTA', {'description': 'Reference FASTA'})}, 'optional': {'preset': ('STRING', {'default': 'map-ont'})}, 'hidden': {'output': ('STRING', {})}}


class Minimap2AlignNode(CommandNode):
    """Align reads with Minimap2."""
    NODE_ID = 'minimap2_align'
    DISPLAY_NAME = 'Minimap2 Align'
    REQUIRED_CONDA_PACKAGES = ['minimap2']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Align reads to a reference with Minimap2 (long or short reads)'
    SEARCH_ALIASES = ['minimap2', 'align', 'long read', 'pacbio', 'ont']
    RETURN_TYPES = ('SAM',)
    RETURN_NAMES = ('alignment',)
    REQUIRED_EXECUTABLES = ['minimap2']
    DOCUMENTATION_URL = 'https://lh3.github.io/minimap2/'
    VERSION = '2.30'
    SHELL = True
    COMMAND = ['minimap2', '-ax', '{inputs.preset}', '-t', '{inputs.threads}', '{inputs.reference}', '{inputs.reads}', '>', '{output}/alignment.sam']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'FASTQ reads (single-end or long reads)'}), 'reference': ('FASTA', {'description': 'Reference FASTA or Minimap2 index'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'preset': ('STRING', {'default': 'sr'})}, 'hidden': {'output': ('STRING', {})}}
