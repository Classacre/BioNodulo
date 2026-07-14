"""megahit — assembly node(s). One tool per file (extracted from assembly.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class MEGAHITNode(CommandNode):
    """De novo assembly with MEGAHIT (metagenomics)."""
    NODE_ID = 'megahit'
    DISPLAY_NAME = 'MEGAHIT'
    REQUIRED_CONDA_PACKAGES = ['megahit']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Ultra-fast metagenome assembler via succinct de Bruijn graph'
    SEARCH_ALIASES = ['megahit', 'assemble', 'metagenome', 'macro']
    RETURN_TYPES = ('CONTIGS',)
    RETURN_NAMES = ('contigs',)
    REQUIRED_EXECUTABLES = ['megahit']
    DOCUMENTATION_URL = 'https://github.com/voutcn/megahit'
    VERSION = '1.2.9'
    COMMAND = ['megahit', '-1', '{inputs.r1}', '-2', '{inputs.r2}', '-o', '{output}', '-t', '{inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'threads': ('INT', {'default': 16, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'r1': ('FASTQ', {'description': 'Forward reads (R1)'}), 'r2': ('FASTQ', {'description': 'Reverse reads (R2)'}), 'min_contig_len': ('INT', {'default': 200, 'min': 1}), 'k_list': ('STRING', {'default': '21,29,39,59,79,99,119,141'})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for MEGAHIT, then copy output."""
        reads = kwargs.get('reads', [])
        if isinstance(reads, (list, tuple)) and len(reads) >= 2:
            kwargs['r1'] = reads[0]
            kwargs['r2'] = reads[1]
        result = await super().run(**kwargs)
        import shutil
        node_out = Path(kwargs['output_dir'])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            actual = node_out / 'final.contigs.fa'
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['megahit', '-1', str(inputs.get('r1', '')), '-2', str(inputs.get('r2', '')), '-o', str(inputs.get('output', '.')), '-t', str(inputs.get('threads', 16))]
        if inputs.get('min_contig_len'):
            cmd.extend(['--min-contig-len', str(inputs['min_contig_len'])])
        if inputs.get('k_list'):
            cmd.extend(['-k-list', str(inputs['k_list'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / 'contigs.fasta']
