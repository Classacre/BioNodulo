"""canu — assembly node(s). One tool per file (extracted from assembly.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class CanuNode(CommandNode):
    """De novo assembly with Canu (long reads)."""
    NODE_ID = 'canu'
    DISPLAY_NAME = 'Canu'
    REQUIRED_CONDA_PACKAGES = ['canu']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Long-read assembler for PacBio and Oxford Nanopore'
    SEARCH_ALIASES = ['canu', 'assemble', 'long reads', 'pacbio', 'ont']
    RETURN_TYPES = ('ASSEMBLY', 'CONTIGS')
    RETURN_NAMES = ('assembly', 'contigs')
    REQUIRED_EXECUTABLES = ['canu']
    DOCUMENTATION_URL = 'https://canu.readthedocs.io/'
    VERSION = '2.3'
    COMMAND = ['canu', '-p', '{inputs.prefix}', '-d', '{output}', 'genomeSize={inputs.genome_size}', '-pacbio-hifi', '{inputs.reads}', 'useGrid=false', 'maxThreads={inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'PacBio HiFi or ONT reads'}), 'genome_size': ('STRING', {'default': '5m', 'description': 'Estimated genome size (e.g., 5m, 3.2g)'}), 'threads': ('INT', {'default': 16, 'min': 1, 'max': 64, 'display': 'slider'}), 'prefix': ('STRING', {'default': 'assembly'})}, 'optional': {'read_type': ('STRING', {'default': 'pacbio-hifi'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        read_type = inputs.get('read_type', 'pacbio-hifi')
        return ['canu', '-p', str(inputs.get('prefix', 'assembly')), '-d', str(inputs.get('output', '.')), f"genomeSize={inputs.get('genome_size', '5m')}", f'-{read_type}', str(inputs.get('reads', '')), 'useGrid=false', f"maxThreads={inputs.get('threads', 16)}"]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / 'assembly.fasta', od / cls.NODE_ID / 'contigs.fasta']

    async def run(self, **kwargs: Any) -> Any:
        """Run Canu and copy assembly files to planned paths."""
        result = await super().run(**kwargs)
        import shutil
        node_out = Path(kwargs['output_dir'])
        base_output_dir = node_out.parent
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        prefix = kwargs.get('prefix', 'assembly')
        if outputs:
            outputs[0].parent.mkdir(parents=True, exist_ok=True)
            contigs = node_out / f'{prefix}.contigs.fasta'
            unitigs = node_out / f'{prefix}.unitigs.fasta'
            if contigs.exists() and len(outputs) > 0:
                shutil.copy2(str(contigs), str(outputs[0]))
            if unitigs.exists() and len(outputs) > 1:
                shutil.copy2(str(unitigs), str(outputs[1]))
        return result
