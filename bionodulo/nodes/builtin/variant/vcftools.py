"""vcftools — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class VcfToolsFilterNode(CommandNode):
    """Filter VCF with VCFtools."""
    NODE_ID = 'vcftools_filter'
    DISPLAY_NAME = 'VCFtools Filter'
    CATEGORY = 'variant'
    DESCRIPTION = 'Filter VCF files using VCFtools'
    SEARCH_ALIASES = ['vcftools', 'filter', 'vcf', 'extract']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('filtered_vcf',)
    REQUIRED_EXECUTABLES = ['vcftools']
    REQUIRED_CONDA_PACKAGES = ['vcftools']
    DOCUMENTATION_URL = 'https://vcftools.github.io/index.html'
    VERSION = '0.1.17'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        vcf = str(inputs.get('vcf', ''))
        cmd = ['vcftools']
        if vcf.endswith('.gz'):
            cmd.extend(['--gzvcf', vcf])
        else:
            cmd.extend(['--vcf', vcf])
        if inputs.get('maf') is not None and float(inputs.get('maf', 0)) > 0:
            cmd.extend(['--maf', str(inputs['maf'])])
        if inputs.get('min_qual') is not None:
            cmd.extend(['--minQ', str(inputs['min_qual'])])
        if inputs.get('min_dp') is not None:
            cmd.extend(['--min-meanDP', str(inputs['min_dp'])])
        if inputs.get('max_missing') is not None:
            cmd.extend(['--max-missing', str(inputs['max_missing'])])
        if inputs.get('recode_info_all'):
            cmd.append('--recode-INFO-all')
        cmd.extend(['--recode', '--out', f"{inputs.get('output', '.')}/filtered_vcf"])
        return cmd

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        output_dir = kwargs.get('output_dir') or (kwargs.get('context') and getattr(kwargs['context'], 'node_dir', '.'))
        if output_dir:
            node_out = Path(output_dir) / self.__class__.NODE_ID
            actual = node_out / 'filtered_vcf.recode.vcf'
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            if actual.exists() and outputs:
                target = outputs[0]
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(actual), str(target))
        return result

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf': ('VCF', {'description': 'Input VCF file'})}, 'optional': {'maf': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'description': 'Minor allele frequency threshold', 'advanced': True}), 'min_qual': ('INT', {'default': 30, 'min': 0, 'label': 'Min Quality', 'advanced': True}), 'min_dp': ('INT', {'default': 10, 'min': 0, 'label': 'Min Depth', 'advanced': True}), 'max_missing': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'label': 'Max Missing', 'advanced': True}), 'recode_info_all': ('BOOLEAN', {'default': False, 'description': 'Recode all INFO fields', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
