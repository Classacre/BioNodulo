"""salmon — rna_seq node(s). One tool per file (extracted from rna_seq.py)."""
from __future__ import annotations
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode


class SalmonIndexNode(CommandNode):
    """Build Salmon transcriptome index."""
    NODE_ID = 'salmon_index'
    DISPLAY_NAME = 'Salmon Index'
    REQUIRED_CONDA_PACKAGES = ['salmon']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Build Salmon quasi-mapping index for transcripts'
    SEARCH_ALIASES = ['salmon', 'index', 'transcriptome', 'quant']
    RETURN_TYPES = ('INDEX_DIR',)
    RETURN_NAMES = ('index',)
    REQUIRED_EXECUTABLES = ['salmon']
    DOCUMENTATION_URL = 'https://salmon.readthedocs.io/'
    VERSION = '1.11.2'
    COMMAND = ['salmon', 'index', '-t', '{inputs.transcripts}', '-i', '{output}/index.out', '-p', '{inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'transcripts': ('FASTA', {'description': 'Transcriptome FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'kmer': ('INT', {'default': 31, 'min': 5, 'max': 32})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this Salmon index (perf §15 #3 / §40) —
        shared platform-wide; keys on the transcriptome identity + salmon
        version + k-mer size."""
        from bionodulo.execution import reference_cache as _rc
        return _rc.compute_ref_id('salmon', [_rc.file_identity(inputs.get('transcripts', '')), f'salmon-{cls.VERSION}', f"k{inputs.get('kmer', 31)}"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['salmon', 'index', '-t', str(inputs.get('transcripts', '')), '-i', f"{inputs.get('output', '.')}/index.out", '-p', str(inputs.get('threads', 4))]
        if inputs.get('kmer'):
            cmd.extend(['-k', str(inputs['kmer'])])
        return cmd


class SalmonQuantNode(CommandNode):
    """Quantify transcripts with Salmon."""
    NODE_ID = 'salmon_quant'
    DISPLAY_NAME = 'Salmon Quant'
    REQUIRED_CONDA_PACKAGES = ['salmon']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Transcript-level quantification with Salmon'
    SEARCH_ALIASES = ['salmon', 'quant', 'expression', 'tpm', 'counts']
    RETURN_TYPES = ('COUNTS',)
    RETURN_NAMES = ('counts',)
    REQUIRED_EXECUTABLES = ['salmon']
    DOCUMENTATION_URL = 'https://salmon.readthedocs.io/'
    VERSION = '1.11.2'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reads = inputs.get('reads', [])
        if isinstance(reads, str):
            reads = [reads]
        r1 = reads[0] if len(reads) > 0 else inputs.get('r1', '')
        r2 = reads[1] if len(reads) > 1 else inputs.get('r2', '')
        lib_type = inputs.get('lib_type', 'A')
        cmd = ['salmon', 'quant', '-i', str(inputs.get('index', '')), '-l', str(lib_type), '-o', str(inputs.get('output', inputs.get('output_dir', '.'))), '-p', str(inputs.get('threads', 8))]
        if r1 and r2:
            cmd.extend(['-1', str(r1), '-2', str(r2)])
        elif r1:
            cmd.extend(['-r', str(r1)])
        if inputs.get('gc_bias'):
            cmd.append('--gcBias')
        if inputs.get('seq_bias'):
            cmd.append('--seqBias')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'index': ('INDEX_DIR', {'description': 'Salmon index directory'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'r1': ('FASTQ', {'description': 'Forward reads (R1)'}), 'r2': ('FASTQ', {'description': 'Reverse reads (R2)'}), 'lib_type': ('STRING', {'default': 'A', 'options': ['A', 'ISF', 'ISR', 'IU', 'U', 'SF', 'SR'], 'label': 'Library Type', 'advanced': True}), 'gc_bias': ('BOOLEAN', {'default': True, 'label': 'GC Bias Correction', 'advanced': True}), 'seq_bias': ('BOOLEAN', {'default': True, 'label': 'Seq Bias Correction', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> Any:
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        output_dir = kwargs.get('output_dir') or (kwargs.get('context') and getattr(kwargs['context'], 'node_dir', '.'))
        if output_dir:
            node_out = Path(output_dir) / self.__class__.NODE_ID
            quant = node_out / 'quant.sf'
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if quant.exists() and outputs:
                outputs[0].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(quant), str(outputs[0]))
        return result
