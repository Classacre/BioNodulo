"""gridss — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class GRIDSSNode(CommandNode):
    """Call structural variants with GRIDSS assembly-based breakend detection."""
    NODE_ID = 'gridss'
    DISPLAY_NAME = 'GRIDSS SV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Call structural variants with GRIDSS assembly-based breakend detection.'
    SEARCH_ALIASES = ['gridss', 'breakend', 'bnd', 'assembly sv', 'structural variant', 'complex rearrangement']
    RETURN_TYPES = ('VCF_GZ', 'BAM')
    RETURN_NAMES = ('sv_vcf', 'assembly_bam')
    REQUIRED_EXECUTABLES = ['gridss']
    REQUIRED_CONDA_PACKAGES = ['gridss']
    DOCUMENTATION_URL = 'https://github.com/PapenfussLab/gridss'
    VERSION = '2.13.2'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'sv_vcf.vcf.gz', node_out / 'assembly_bam.bam']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        bams = cls._bam_inputs(inputs.get('bams'))
        if not bams:
            return 'At least one BAM is required'
        if not str(inputs.get('reference', '')).strip():
            return "Input 'reference' must not be empty"
        if int(inputs.get('threads', 0) or 0) < 1:
            return "Input 'threads' must be at least 1"
        labels = cls._label_inputs(inputs.get('labels'))
        if labels and len(labels) != len(bams):
            return 'Number of GRIDSS labels must match number of BAM inputs'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output = str(inputs.get('output', '.'))
        cmd = ['gridss', '--reference', str(inputs.get('reference', '')), '--output', f'{output}/sv_vcf.vcf.gz', '--assembly', f'{output}/assembly_bam.bam', '--threads', str(inputs.get('threads', 4)), '--workingdir', f'{output}/gridss_working']
        if inputs.get('blacklist'):
            cmd.extend(['--blacklist', str(inputs['blacklist'])])
        if cls._label_inputs(inputs.get('labels')):
            cmd.extend(['--labels', ','.join(cls._label_inputs(inputs.get('labels')))])
        if inputs.get('steps'):
            cmd.extend(['--steps', str(inputs['steps'])])
        if inputs.get('gridss_jar'):
            cmd.extend(['--jar', str(inputs['gridss_jar'])])
        if inputs.get('jvm_heap'):
            cmd.extend(['--jvmheap', str(inputs['jvm_heap'])])
        cmd.extend(cls._bam_inputs(inputs.get('bams')))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bams': ('BAM', {'description': 'One or more sorted, indexed BAM files'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'})}, 'optional': {'blacklist': ('BED', {'description': 'Regions to exclude from calling', 'advanced': True}), 'labels': ('STRING', {'default': '', 'description': 'Comma-separated sample labels', 'advanced': True}), 'steps': ('STRING', {'default': 'all', 'options': ['all', 'setupreference', 'preprocess', 'assemble', 'call']}), 'gridss_jar': ('FILE', {'description': 'Optional GRIDSS jar override', 'advanced': True}), 'jvm_heap': ('STRING', {'default': '', 'description': 'Optional JVM heap setting such as 31g', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _bam_inputs(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).replace('\n', ',').split(',') if part.strip()]

    @classmethod
    def _label_inputs(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value if str(item).strip()]
        return [part.strip() for part in str(value).replace('\n', ',').split(',') if part.strip()]
