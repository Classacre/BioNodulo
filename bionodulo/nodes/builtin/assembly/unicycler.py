"""unicycler — assembly node(s). One tool per file (extracted from assembly.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class UnicyclerNode(CommandNode):
    """Bacterial genome assembly with Unicycler."""
    NODE_ID = 'unicycler'
    DISPLAY_NAME = 'Unicycler'
    REQUIRED_CONDA_PACKAGES = ['unicycler']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Bacterial genome assembly from Illumina reads with optional long reads'
    SEARCH_ALIASES = ['unicycler', 'assemble', 'bacteria', 'hybrid']
    RETURN_TYPES = ('ASSEMBLY',)
    RETURN_NAMES = ('assembly',)
    REQUIRED_EXECUTABLES = ['unicycler']
    DOCUMENTATION_URL = 'https://github.com/rrwick/Unicycler'
    VERSION = '0.5.1'
    COMMAND = ['unicycler', '-1', '{inputs.r1}', '-2', '{inputs.r2}', '-o', '{output}', '-t', '{inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'threads': ('INT', {'default': 16, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'r1': ('FASTQ', {'description': 'Forward Illumina reads'}), 'r2': ('FASTQ', {'description': 'Reverse Illumina reads'}), 'long_reads': ('FASTQ', {'description': 'Optional long reads for hybrid assembly'}), 'mode': ('STRING', {'default': 'normal'}), 'unpaired': ('FASTQ', {'description': 'Optional unpaired reads'}), 'min_fasta_length': ('INT', {'default': 100, 'min': 1})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for Unicycler, then copy output."""
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
            actual = node_out / 'assembly.fasta'
            if actual.exists():
                shutil.copy2(str(actual), str(outputs[0]))
        return result

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['unicycler', '-1', str(inputs.get('r1', '')), '-2', str(inputs.get('r2', '')), '-o', str(inputs.get('output', '.')), '-t', str(inputs.get('threads', 16)), '--mode', str(inputs.get('mode', 'normal'))]
        if inputs.get('long_reads'):
            cmd.extend(['-l', str(inputs['long_reads'])])
        if inputs.get('unpaired'):
            cmd.extend(['-s', str(inputs['unpaired'])])
        if inputs.get('min_fasta_length') is not None:
            cmd.extend(['--min_fasta_length', str(inputs['min_fasta_length'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / 'assembly.fasta']
