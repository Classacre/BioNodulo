"""bcftools — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class BcftoolsIndexNode(CommandNode):
    """Index a VCF/BCF file."""
    NODE_ID = 'bcftools_index'
    DISPLAY_NAME = 'bcftools Index'
    CATEGORY = 'variant'
    DESCRIPTION = 'Index a VCF.gz or BCF file for fast random access'
    SEARCH_ALIASES = ['bcftools', 'index', 'tbi', 'csi']
    RETURN_TYPES = ('VCF_INDEX',)
    RETURN_NAMES = ('index',)
    REQUIRED_EXECUTABLES = ['bcftools']
    REQUIRED_CONDA_PACKAGES = ['bcftools']
    DOCUMENTATION_URL = 'https://samtools.github.io/bcftools/bcftools.html'
    VERSION = '1.20'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bcftools', 'index', '--tbi' if inputs.get('tbi', True) else '--csi', '-f', str(inputs.get('vcf', ''))]
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf': ('VCF_GZ', {'description': 'Compressed VCF or BCF file'})}, 'optional': {'tbi': ('BOOLEAN', {'default': True, 'description': 'Use TBI format (vs CSI)'})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        vcf = kwargs.get('vcf', '')
        output_dir = kwargs.get('output_dir') or (kwargs.get('context') and getattr(kwargs['context'], 'node_dir', '.'))
        if vcf and output_dir:
            vcf_path = Path(vcf)
            tbi = vcf_path.with_suffix(vcf_path.suffix + '.tbi')
            csi = vcf_path.with_suffix(vcf_path.suffix + '.csi')
            index_file = tbi if tbi.exists() else csi
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if index_file.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(index_file), str(target))
        return result
