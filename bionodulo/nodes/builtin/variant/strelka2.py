"""strelka2 — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class Strelka2Node(CommandNode):
    """Call germline or somatic small variants with Strelka2."""
    NODE_ID = 'strelka2'
    DISPLAY_NAME = 'Strelka2'
    CATEGORY = 'variant'
    DESCRIPTION = 'Call germline or somatic small variants with Strelka2.'
    SEARCH_ALIASES = ['strelka2', 'strelka', 'small variant', 'somatic', 'germline', 'snp', 'indel']
    RETURN_TYPES = ('VCF_GZ', 'VCF_GZ')
    RETURN_NAMES = ('snv_vcf', 'indel_vcf')
    REQUIRED_EXECUTABLES = ['configureStrelkaGermlineWorkflow.py']
    REQUIRED_CONDA_PACKAGES = ['strelka']
    DOCUMENTATION_URL = 'https://github.com/Illumina/strelka'
    VERSION = '2.9.10'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', '.'))
        run_dir = f'{output}/strelka_run'
        mode = str(inputs.get('mode', 'germline') or 'germline').lower()
        if mode not in {'germline', 'somatic'}:
            mode = 'germline'
        threads = int(inputs.get('threads', 4) or 4)
        reference = shlex.quote(str(inputs.get('reference', '')))
        run_dir_q = shlex.quote(run_dir)
        output_q = shlex.quote(output)
        if mode == 'somatic':
            configure = ['configureStrelkaSomaticWorkflow.py', '--tumorBam', shlex.quote(str(inputs.get('bam', ''))), '--normalBam', shlex.quote(str(inputs.get('normal_bam', ''))), '--referenceFasta', reference, '--runDir', run_dir_q]
            snv_source = f'{run_dir}/results/variants/somatic.snvs.vcf.gz'
            indel_source = f'{run_dir}/results/variants/somatic.indels.vcf.gz'
        else:
            configure = ['configureStrelkaGermlineWorkflow.py', '--bam', shlex.quote(str(inputs.get('bam', ''))), '--referenceFasta', reference, '--runDir', run_dir_q]
            snv_source = f'{run_dir}/results/variants/variants.vcf.gz'
            indel_source = f'{run_dir}/results/variants/indels.vcf.gz'
        if inputs.get('exome'):
            configure.append('--exome')
        if inputs.get('call_regions'):
            configure.extend(['--callRegions', shlex.quote(str(inputs['call_regions']))])
        script = ' '.join(configure)
        script += f'\n{shlex.quote(run_dir)}/runWorkflow.py -m local -j {threads}'
        script += f'\ncp {shlex.quote(snv_source)} {output_q}/snv_vcf.vcf.gz'
        script += f'\ncp {shlex.quote(indel_source)} {output_q}/indel_vcf.vcf.gz'
        return ['bash', '-c', script]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Tumor or germline BAM (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'})}, 'optional': {'normal_bam': ('BAM', {'description': 'Matched normal BAM for somatic mode', 'advanced': True}), 'mode': ('STRING', {'default': 'germline', 'options': ['germline', 'somatic']}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'}), 'exome': ('BOOLEAN', {'default': False, 'description': 'Use exome-style calling parameters', 'advanced': True}), 'call_regions': ('BED', {'description': 'Optional bgzip/tabix-indexed BED call regions', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
