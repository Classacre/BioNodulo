"""kallisto — rna_seq node(s). One tool per file (extracted from rna_seq.py)."""
from __future__ import annotations
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode


class KallistoIndexNode(CommandNode):
    """Build Kallisto transcriptome index."""
    NODE_ID = 'kallisto_index'
    DISPLAY_NAME = 'Kallisto Index'
    REQUIRED_CONDA_PACKAGES = ['kallisto']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Build Kallisto k-mer index for transcriptome'
    SEARCH_ALIASES = ['kallisto', 'index', 'transcriptome', 'pseudoalign']
    RETURN_TYPES = ('INDEX_DIR',)
    RETURN_NAMES = ('index',)
    REQUIRED_EXECUTABLES = ['kallisto']
    DOCUMENTATION_URL = 'https://pachterlab.github.io/kallisto/'
    VERSION = '0.51.1'
    COMMAND = ['kallisto', 'index', '-i', '{output}/index.out', '-k', '{inputs.kmer}', '{inputs.transcripts}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'transcripts': ('FASTA', {'description': 'Transcriptome FASTA'}), 'kmer': ('INT', {'default': 31, 'min': 5, 'max': 31})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def reference_cache_id(cls, inputs: dict[str, Any]) -> Optional[str]:
        """Content-addressed id for this Kallisto index (perf §15 #3 / §40) —
        shared platform-wide; keys on transcriptome identity + version + k-mer."""
        from bionodulo.execution import reference_cache as _rc
        return _rc.compute_ref_id('kallisto', [_rc.file_identity(inputs.get('transcripts', '')), f'kallisto-{cls.VERSION}', f"k{inputs.get('kmer', 31)}"])


class KallistoQuantNode(CommandNode):
    """Quantify transcripts with Kallisto."""
    NODE_ID = 'kallisto_quant'
    DISPLAY_NAME = 'Kallisto Quant'
    REQUIRED_CONDA_PACKAGES = ['kallisto']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Pseudoalignment-based transcript quantification'
    SEARCH_ALIASES = ['kallisto', 'quant', 'expression', 'pseudoalign']
    RETURN_TYPES = ('ABUNDANCE',)
    RETURN_NAMES = ('abundance',)
    REQUIRED_EXECUTABLES = ['kallisto']
    DOCUMENTATION_URL = 'https://pachterlab.github.io/kallisto/'
    VERSION = '0.51.1'
    COMMAND = ['kallisto', 'quant', '-i', '{inputs.index}', '-o', '{output}', '-t', '{inputs.threads}', '{inputs.r1}', '{inputs.r2}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'index': ('FILE', {'description': 'Kallisto index file (.idx)'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'r1': ('FASTQ', {'description': 'Forward reads (R1)'}), 'r2': ('FASTQ', {'description': 'Reverse reads (R2)'}), 'bootstrap': ('INT', {'default': 100, 'min': 0, 'max': 1000, 'step': 10, 'display': 'slider'}), 'single_end': ('BOOLEAN', {'default': False, 'label': 'Single-end reads', 'advanced': True}), 'fragment_length': ('INT', {'default': 200, 'min': 1, 'label': 'Fragment Length', 'advanced': True}), 'sd': ('INT', {'default': 20, 'min': 1, 'label': 'Fragment SD', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Kallisto."""
        reads = kwargs.get('reads', [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs['r1'] = reads[0]
            kwargs['r2'] = reads[1]
        result = await super().run(**kwargs)
        import shutil
        from pathlib import Path
        output_dir = kwargs.get('output_dir') or (kwargs.get('context') and getattr(kwargs['context'], 'node_dir', '.'))
        if output_dir:
            node_out = Path(output_dir) / self.__class__.NODE_ID
            abundance = node_out / 'abundance.tsv'
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if abundance.exists() and outputs:
                outputs[0].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(abundance), str(outputs[0]))
        return result

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['kallisto', 'quant', '-i', str(inputs.get('index', '')), '-o', str(inputs.get('output', '.')), '-t', str(inputs.get('threads', 8))]
        if inputs.get('bootstrap'):
            cmd.extend(['-b', str(inputs['bootstrap'])])
        if inputs.get('single_end'):
            cmd.extend(['--single', '-l', str(inputs.get('fragment_length', 200)), '-s', str(inputs.get('sd', 20)), str(inputs.get('r1', ''))])
        else:
            cmd.extend([str(inputs.get('r1', '')), str(inputs.get('r2', ''))])
        return cmd
