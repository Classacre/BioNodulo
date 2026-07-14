"""bwa — alignment node(s). One tool per file (extracted from alignment.py)."""
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


class BWAIndexNode(CommandNode):
    """Build BWA index for a reference genome."""
    NODE_ID = 'bwa_index'
    DISPLAY_NAME = 'BWA Index'
    REQUIRED_CONDA_PACKAGES = ['bwa']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Build BWA MEM index for a reference FASTA'
    SEARCH_ALIASES = ['bwa', 'index', 'reference index']
    RETURN_TYPES = ('INDEX_DIR',)
    RETURN_NAMES = ('indexed_reference',)
    REQUIRED_EXECUTABLES = ['bwa']
    DOCUMENTATION_URL = 'https://bio-bwa.sourceforge.net/'
    VERSION = '0.7.19'
    COMMAND = ['bwa', 'index', '{inputs.reference}']

    async def run(self, **kwargs: Any) -> Any:
        reference = kwargs.get('reference', '')
        result = await super().run(**kwargs)
        if reference and result and isinstance(result, tuple):
            ref_path = Path(reference)
            planned = Path(str(result[0]))
            target_dir = planned.parent
            target_dir.mkdir(parents=True, exist_ok=True)
            if ref_path.exists():
                shutil.copy2(str(ref_path), str(target_dir / ref_path.name))
            for suffix in ['.amb', '.ann', '.bwt', '.pac', '.sa']:
                idx_file = ref_path.parent / (ref_path.name + suffix)
                if idx_file.exists():
                    shutil.copy2(str(idx_file), str(target_dir / (ref_path.name + suffix)))
        return result

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference': ('FASTA', {'description': 'Reference FASTA to index'})}, 'optional': {'algorithm': ('STRING', {'default': 'bwtsw'})}, 'hidden': {}}

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this BWA index (perf §15 #3 / §40) — shared
        platform-wide; keys on the FASTA identity + bwa version + algorithm."""
        from bionodulo.execution import reference_cache as _rc
        return _rc.compute_ref_id('bwa', [_rc.file_identity(inputs.get('reference', '')), f'bwa-{cls.VERSION}', str(inputs.get('algorithm', 'bwtsw'))])


class BWAMemNode(CommandNode):
    """Align reads with BWA-MEM."""
    NODE_ID = 'bwa_mem'
    DISPLAY_NAME = 'BWA-MEM Align'
    REQUIRED_CONDA_PACKAGES = ['bwa']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Align paired-end reads to a reference using BWA-MEM'
    SEARCH_ALIASES = ['bwa', 'mem', 'align', 'mapper', 'map']
    RETURN_TYPES = ('SAM',)
    RETURN_NAMES = ('alignment',)
    REQUIRED_EXECUTABLES = ['bwa']
    DOCUMENTATION_URL = 'https://bio-bwa.sourceforge.net/'
    VERSION = '0.7.17'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        r1, r2 = _split_reads(inputs)
        rg = f"@RG\\tID:{inputs.get('rg_id', '1')}\\tSM:{inputs.get('rg_sample', 'sample')}\\tPL:{inputs.get('rg_platform', 'ILLUMINA')}"
        cmd = ['bwa', 'mem', '-t', str(inputs.get('threads', 8)), '-R', rg, '-T', str(inputs.get('min_score', 30))]
        if inputs.get('mark_shorter_splits') is not False:
            cmd.append('-M')
        cmd.append(str(inputs.get('reference', '')))
        cmd.append(str(r1))
        if r2:
            cmd.append(str(r2))
        cmd.extend(['>', f"{inputs.get('output', '.')}/alignment.sam"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'reference': ('FASTA', {'description': 'Indexed reference FASTA'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'rg_id': ('STRING', {'default': '1', 'label': 'Read Group ID'}), 'rg_sample': ('STRING', {'default': 'sample', 'label': 'Sample Name'}), 'rg_platform': ('STRING', {'default': 'ILLUMINA', 'options': ['ILLUMINA', 'PACBIO', 'ONT', 'IONTORRENT'], 'label': 'Platform'}), 'mark_shorter_splits': ('BOOLEAN', {'default': True, 'label': 'Mark Shorter Splits', 'advanced': True}), 'min_score': ('INT', {'default': 30, 'min': 1, 'label': 'Min Score', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class BWAIndexDirNode(CommandNode):
    """Wrap BWA index directory for passing between nodes."""
    NODE_ID = 'bwa_index_dir'
    DISPLAY_NAME = 'BWA Index Directory'
    REQUIRED_CONDA_PACKAGES = ['bwa']
    CATEGORY = 'alignment'
    DESCRIPTION = 'Reference index directory output from BWA index'
    SEARCH_ALIASES = ['bwa index dir', 'index directory']
    RETURN_TYPES = ('INDEX_DIR',)
    RETURN_NAMES = ('index_dir',)
    REQUIRES_EXTERNAL_TOOLS = False
    COMMAND = ['cp', '-r', '{inputs.index_dir}', '{output}']

    async def run(self, **kwargs: Any) -> Any:
        index_dir = kwargs.get('index_dir') or kwargs.get('dir_path')
        if not index_dir:
            raise ValueError('No index_dir provided')
        src = Path(index_dir)
        if not src.exists():
            raise FileNotFoundError(f'Index directory not found: {src}')
        if not src.is_dir():
            raise NotADirectoryError(f'Index directory is not a directory: {src}')
        expected = ['.amb', '.ann', '.bwt', '.pac', '.sa']
        if not any((list(src.glob(f'*{suffix}')) for suffix in expected)):
            raise FileNotFoundError(f'BWA index files not found in {src}')
        return await super().run(**kwargs)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'index_dir': ('INDEX_DIR', {'description': 'BWA index directory'})}, 'optional': {}, 'hidden': {}}
