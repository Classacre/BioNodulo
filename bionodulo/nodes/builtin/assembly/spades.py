"""spades — assembly node(s). One tool per file (extracted from assembly.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SPAdesNode(CommandNode):
    """De novo genome assembly with SPAdes."""
    NODE_ID = 'spades'
    DISPLAY_NAME = 'SPAdes'
    REQUIRED_CONDA_PACKAGES = ['spades']
    CATEGORY = 'assembly'
    DESCRIPTION = 'De novo genome assembler for single-cell and isolate data'
    SEARCH_ALIASES = ['spades', 'assemble', 'de novo', 'genome']
    RETURN_TYPES = ('ASSEMBLY', 'CONTIGS')
    RETURN_NAMES = ('assembly', 'contigs')
    REQUIRED_EXECUTABLES = ['spades.py']
    DOCUMENTATION_URL = 'https://github.com/ablab/spades'
    VERSION = '4.2.0'
    COMMAND = ['spades.py', '-1', '{inputs.r1}', '-2', '{inputs.r2}', '-o', '{output}', '-t', '{inputs.threads}', '--memory', '{inputs.memory}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'threads': ('INT', {'default': 16, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads': ('FASTQ_LIST', {'description': 'Paired-end FASTQ reads [R1, R2]'}), 'r1': ('FASTQ', {'description': 'Forward reads (R1)'}), 'r2': ('FASTQ', {'description': 'Reverse reads (R2)'}), 'memory': ('INT', {'default': 128, 'min': 1, 'description': 'Memory limit in GB'}), 'careful': ('BOOLEAN', {'default': True, 'description': 'Reduce mismatch correction errors'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['spades.py', '-1', str(inputs.get('r1', '')), '-2', str(inputs.get('r2', '')), '-o', str(inputs.get('output', '.')), '-t', str(inputs.get('threads', 16)), '--memory', str(inputs.get('memory', 128))]
        if inputs.get('careful'):
            cmd.append('--careful')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / 'assembly.fasta', od / cls.NODE_ID / 'contigs.fasta']

    async def run(self, **kwargs: Any) -> Any:
        """Accept reads list and split into r1/r2 for SPAdes, then copy outputs."""
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
            scaffolds = node_out / 'scaffolds.fasta'
            contigs = node_out / 'contigs.fasta'
            if scaffolds.exists():
                shutil.copy2(str(scaffolds), str(outputs[0]))
            elif contigs.exists():
                shutil.copy2(str(contigs), str(outputs[0]))
        return result
