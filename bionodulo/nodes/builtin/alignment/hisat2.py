"""hisat2 — alignment node(s). One tool per file (extracted from alignment.py)."""
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


class HISAT2BuildNode(CommandNode):
    """Build HISAT2 index."""
    NODE_ID = 'hisat2_build'
    DISPLAY_NAME = 'HISAT2 Build'
    CATEGORY = 'alignment'
    DESCRIPTION = 'Build HISAT2 spliced alignment index'
    SEARCH_ALIASES = ['hisat2', 'index', 'spliced', 'rna']
    RETURN_TYPES = ('INDEX_DIR',)
    RETURN_NAMES = ('index',)
    REQUIRED_EXECUTABLES = ['hisat2-build']
    REQUIRED_CONDA_PACKAGES = ['hisat2']
    DOCUMENTATION_URL = 'https://daehwankimlab.github.io/hisat2/'
    VERSION = '2.2.2'
    COMMAND = ['hisat2-build', '-p', '{inputs.threads}', '{inputs.reference}', '{output}/index']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference': ('FASTA', {'description': 'Reference FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this HISAT2 index (perf §15 #3 / §40) —
        shared platform-wide; keys on the FASTA identity + hisat2 version."""
        from bionodulo.execution import reference_cache as _rc
        return _rc.compute_ref_id('hisat2', [_rc.file_identity(inputs.get('reference', '')), f'hisat2-{cls.VERSION}'])


class HISAT2AlignNode(CommandNode):
    """Align RNA-seq reads with HISAT2."""
    NODE_ID = 'hisat2_align'
    DISPLAY_NAME = 'HISAT2 Align'
    REQUIRED_CONDA_PACKAGES = ['hisat2']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Align RNA-seq reads with splice-aware HISAT2'
    SEARCH_ALIASES = ['hisat2', 'align', 'rna-seq', 'spliced']
    RETURN_TYPES = ('SAM',)
    RETURN_NAMES = ('alignment',)
    REQUIRED_EXECUTABLES = ['hisat2']
    DOCUMENTATION_URL = 'https://daehwankimlab.github.io/hisat2/'
    VERSION = '2.2.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['hisat2', '-p', str(inputs.get('threads', 8)), '-x', str(inputs.get('index', ''))]
        r1, r2 = _split_reads(inputs)
        if r1 and r2:
            cmd.extend(['-1', str(r1), '-2', str(r2)])
        elif r1:
            cmd.extend(['-U', str(r1)])
        if inputs.get('rg_id'):
            cmd.extend(['--rg-id', str(inputs['rg_id'])])
        if inputs.get('rg_sample'):
            cmd.extend(['--rg', f"SM:{inputs['rg_sample']}"])
        if inputs.get('dta'):
            cmd.append('--dta')
        if inputs.get('no_softclip'):
            cmd.append('--no-softclip')
        cmd.extend(['-S', f"{inputs.get('output', '.')}/alignment.sam"])
        return cmd

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for HISAT2."""
        _inject_read_aliases(kwargs)
        return await super().run(**kwargs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'index': ('INDEX_DIR', {'description': 'HISAT2 index prefix'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'r1': ('FASTQ', {'description': 'Forward reads (R1)'}), 'r2': ('FASTQ', {'description': 'Reverse reads (R2)'}), 'rg_id': ('STRING', {'default': '1', 'label': 'Read Group ID'}), 'rg_sample': ('STRING', {'default': 'sample', 'label': 'Sample Name'}), 'dta': ('BOOLEAN', {'default': True, 'description': 'Report alignments for StringTie', 'advanced': True}), 'no_softclip': ('BOOLEAN', {'default': False, 'label': 'No Softclip', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
