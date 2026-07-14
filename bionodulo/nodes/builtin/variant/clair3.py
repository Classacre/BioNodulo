"""clair3 — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class Clair3Node(CommandNode):
    """Call small variants from long-read alignments with Clair3."""
    NODE_ID = 'clair3'
    DISPLAY_NAME = 'Clair3'
    CATEGORY = 'variant'
    DESCRIPTION = 'Call small variants from long-read BAM files with Clair3 deep-learning models.'
    SEARCH_ALIASES = ['clair3', 'nanopore', 'pacbio hifi', 'deep learning', 'long-read variant caller', 'small variant', 'snp', 'indel']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['run_clair3.sh']
    REQUIRED_CONDA_PACKAGES = ['clair3']
    DOCUMENTATION_URL = 'https://github.com/HKU-BAL/Clair3'
    VERSION = '2.0.1'
    _PLATFORMS = {'ont', 'hifi', 'ilmn'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        platform = str(inputs.get('platform', 'ont') or 'ont').lower()
        if platform not in cls._PLATFORMS:
            return f'Unsupported Clair3 platform: {platform}'
        if int(inputs.get('threads', 4) or 0) <= 0:
            return 'Clair3 threads must be greater than zero.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        cmd = ['run_clair3.sh', f"--bam_fn={inputs.get('bam', '')}", f"--ref_fn={inputs.get('reference', '')}", f"--threads={inputs.get('threads', 4)}", f"--platform={str(inputs.get('platform', 'ont') or 'ont').lower()}", f"--model_path={inputs.get('model_path', '')}", f"--output={inputs.get('output', '.')}"]
        if inputs.get('regions_bed'):
            cmd.append(f"--bed_fn={inputs['regions_bed']}")
        if inputs.get('candidate_vcf'):
            cmd.append(f"--vcf_fn={inputs['candidate_vcf']}")
        if inputs.get('contigs'):
            cmd.append(f"--ctg_name={inputs['contigs']}")
        if inputs.get('sample_name'):
            cmd.append(f"--sample_name={inputs['sample_name']}")
        if inputs.get('qual') is not None:
            cmd.append(f"--qual={inputs['qual']}")
        if inputs.get('chunk_size') is not None:
            cmd.append(f"--chunk_size={inputs['chunk_size']}")
        for key in ('include_all_ctgs', 'pileup_only', 'enable_phasing', 'haploid_precise', 'haploid_sensitive', 'enable_dwell_time'):
            if inputs.get(key):
                cmd.append(f'--{key}')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'merge_output.vcf.gz']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'}), 'model_path': ('DIRECTORY', {'description': 'Clair3 model directory for the selected platform'})}, 'optional': {'platform': ('STRING', {'default': 'ont', 'options': ['ont', 'hifi', 'ilmn']}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128, 'display': 'slider'}), 'regions_bed': ('BED', {'description': 'Optional regions BED', 'advanced': True}), 'candidate_vcf': ('VCF_GZ', {'description': 'Optional candidate VCF', 'advanced': True}), 'contigs': ('STRING', {'default': '', 'description': 'Optional comma-separated contig names', 'advanced': True}), 'sample_name': ('STRING', {'default': '', 'description': 'Optional sample name override', 'advanced': True}), 'qual': ('INT', {'default': 2, 'min': 0, 'advanced': True}), 'chunk_size': ('INT', {'default': 5000000, 'min': 1, 'advanced': True}), 'include_all_ctgs': ('BOOLEAN', {'default': False, 'advanced': True}), 'pileup_only': ('BOOLEAN', {'default': False, 'advanced': True}), 'enable_phasing': ('BOOLEAN', {'default': False, 'advanced': True}), 'haploid_precise': ('BOOLEAN', {'default': False, 'advanced': True}), 'haploid_sensitive': ('BOOLEAN', {'default': False, 'advanced': True}), 'enable_dwell_time': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
