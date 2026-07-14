"""vcf — pangenomics node(s). One tool per file (extracted from pangenomics.py)."""
from __future__ import annotations
from pathlib import Path
import re
import shlex
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _split_path_list(value: Any) -> list[str]:
    if isinstance(value, list | tuple):
        return [str(item) for item in value if str(item)]
    return [item for item in re.split('[\\s,]+', str(value or '')) if item]
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class VCFDecomposeNode(CommandNode):
    """Decompose complex pangenome VCF records into primitive alleles."""
    NODE_ID = 'vcf_decompose'
    DISPLAY_NAME = 'VCF Decompose'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Decompose complex variants in a pangenome VCF into primitive, normalized records.'
    SEARCH_ALIASES = ['vcf', 'decompose', 'pangenome vcf', 'primitive variants', 'vcflib', 'normalize']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('decomposed_vcf',)
    REQUIRED_EXECUTABLES = ['vcfdecompose', 'bgzip', 'tabix']
    REQUIRED_CONDA_PACKAGES = ['vcflib', 'htslib']
    DOCUMENTATION_URL = 'https://github.com/vcflib/vcflib'
    VERSION = '1.0.9'
    SHELL = True
    _MODES = {'decompose', 'normalize'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get('mode', 'normalize') or 'normalize')
        if mode not in cls._MODES:
            return f'Unsupported VCF decompose mode: {mode}'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        output_vcf = out_dir / 'decomposed_vcf.vcf.gz'
        mode = str(inputs.get('mode', 'normalize') or 'normalize')
        threads = int(inputs.get('threads', 0) or 0)
        cmd = ['vcfdecompose']
        if inputs.get('keep_info'):
            cmd.append('-k')
        cmd.append(str(inputs.get('vcf', '')))
        if mode == 'normalize':
            cmd.extend(['|', 'vcfallelicprimitives'])
            if inputs.get('keep_info'):
                cmd.append('-kg')
            if inputs.get('reference'):
                cmd.extend(['-t', 'DECOMPOSED', '-f', str(inputs.get('reference', ''))])
        cmd.extend(['|', 'bgzip'])
        if threads > 0:
            cmd.extend(['--threads', str(threads)])
        cmd.extend(['-c', '>', str(output_vcf), '&&', 'tabix', '-f', '-p', 'vcf', str(output_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'decomposed_vcf.vcf.gz']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'vcf': ('VCF_GZ', {'description': 'Input pangenome or complex-variant VCF'}), 'reference': ('FASTA', {'description': 'Reference FASTA for primitive allele normalization'})}, 'optional': {'mode': ('STRING', {'default': 'normalize', 'options': ['decompose', 'normalize']}), 'keep_info': ('BOOLEAN', {'default': True, 'description': 'Preserve INFO fields where possible'}), 'threads': ('INT', {'default': 0, 'min': 0, 'max': 64, 'display': 'slider'})}, 'hidden': {'output': ('STRING', {})}}
