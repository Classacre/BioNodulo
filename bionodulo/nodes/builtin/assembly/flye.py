"""flye — assembly node(s). One tool per file (extracted from assembly.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class FlyeNode(CommandNode):
    """De novo assembly with Flye (long reads)."""
    NODE_ID = 'flye'
    DISPLAY_NAME = 'Flye'
    REQUIRED_CONDA_PACKAGES = ['flye']
    CATEGORY = 'assembly'
    DESCRIPTION = 'De novo assembly for single-molecule sequencing reads'
    SEARCH_ALIASES = ['flye', 'assemble', 'long reads', 'nanopore', 'repeat graph']
    RETURN_TYPES = ('ASSEMBLY',)
    RETURN_NAMES = ('assembly',)
    REQUIRED_EXECUTABLES = ['flye']
    DOCUMENTATION_URL = 'https://github.com/fenderglass/Flye'
    VERSION = '2.9.6'
    COMMAND = ['flye', '--{inputs.read_type}', '{inputs.reads}', '--out-dir', '{output}', '--threads', '{inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Long reads FASTQ'}), 'threads': ('INT', {'default': 16, 'min': 1, 'max': 64, 'display': 'slider'}), 'read_type': ('STRING', {'default': 'nano-hq'})}, 'optional': {'genome_size': ('STRING', {'default': '5m', 'description': 'Estimated genome size'}), 'iterations': ('INT', {'default': 1, 'min': 0, 'max': 5})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['flye', f"--{inputs.get('read_type', 'nano-hq')}", str(inputs.get('reads', '')), '--out-dir', str(inputs.get('output', '.')), '--threads', str(inputs.get('threads', 16))]
        if inputs.get('genome_size'):
            cmd.extend(['--genome-size', str(inputs['genome_size'])])
        if inputs.get('iterations'):
            cmd.extend(['--iterations', str(inputs['iterations'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / 'assembly.fasta']

    async def run(self, **kwargs: Any) -> Any:
        """Run Flye and copy assembly to planned path."""
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
