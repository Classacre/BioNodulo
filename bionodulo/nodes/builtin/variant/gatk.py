"""gatk — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class GatkHaplotypeCallerNode(CommandNode):
    """Call variants with GATK HaplotypeCaller."""
    NODE_ID = 'gatk_haplotype_caller'
    DISPLAY_NAME = 'GATK HaplotypeCaller'
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = 'variant'
    DESCRIPTION = 'Call germline SNPs and indels with GATK HaplotypeCaller'
    SEARCH_ALIASES = ['gatk', 'haplotypecaller', 'variant', 'snp', 'indel']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['gatk']
    DOCUMENTATION_URL = 'https://gatk.broadinstitute.org/hc/en-us/articles/360037225632-HaplotypeCaller'
    VERSION = '4.6.2.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['gatk', 'HaplotypeCaller', '-R', str(inputs.get('reference', '')), '-I', str(inputs.get('bam', '')), '-O', f"{inputs.get('output', '.')}/vcf.vcf.gz", '--native-pair-hmm-threads', str(inputs.get('threads', 4))]
        if inputs.get('emit_ref_confidence'):
            cmd.extend(['-ERC', str(inputs['emit_ref_confidence'])])
        if inputs.get('dbsnp'):
            cmd.extend(['--dbsnp', str(inputs['dbsnp'])])
        if inputs.get('stand_call_conf'):
            cmd.extend(['--standard-min-confidence-threshold-for-calling', str(inputs['stand_call_conf'])])
        if inputs.get('min_base_quality'):
            cmd.extend(['--min-base-quality-score', str(inputs['min_base_quality'])])
        if inputs.get('sample_ploidy'):
            cmd.extend(['-ploidy', str(inputs['sample_ploidy'])])
        if inputs.get('intervals'):
            cmd.extend(['-L', str(inputs['intervals'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM (sorted, indexed, with read groups)'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'emit_ref_confidence': ('STRING', {'default': 'GVCF', 'options': ['NONE', 'GVCF', 'BP_RESOLUTION'], 'label': 'Emit Ref Confidence', 'advanced': True}), 'dbsnp': ('VCF_GZ', {'description': 'Optional dbSNP VCF for annotation', 'advanced': True}), 'stand_call_conf': ('INT', {'default': 30, 'min': 0, 'max': 100, 'display': 'slider', 'label': 'Call Confidence Threshold', 'advanced': True}), 'min_base_quality': ('INT', {'default': 10, 'min': 0, 'label': 'Min Base Quality', 'advanced': True}), 'sample_ploidy': ('INT', {'default': 2, 'min': 1, 'max': 8, 'display': 'slider', 'label': 'Sample Ploidy', 'advanced': True}), 'intervals': ('STRING', {'default': '', 'description': 'Intervals to process (e.g., chr1:1-1000)', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class GatkGenotypeGVCFsNode(CommandNode):
    """Joint genotype sample GVCFs with GATK GenotypeGVCFs."""
    NODE_ID = 'gatk_genotype_gvcfs'
    DISPLAY_NAME = 'GATK GenotypeGVCFs'
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = 'variant'
    DESCRIPTION = 'Joint genotype GVCF files from multiple samples with GATK GenotypeGVCFs'
    SEARCH_ALIASES = ['gatk', 'genotypegvcfs', 'joint genotyping', 'gvcf', 'cohort genotyping']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('vcf',)
    REQUIRED_EXECUTABLES = ['gatk']
    DOCUMENTATION_URL = 'https://gatk.broadinstitute.org/hc/en-us/articles/360036899732-GenotypeGVCFs'
    VERSION = '4.6.2.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        gvcfs = inputs.get('gvcfs', [])
        if isinstance(gvcfs, str):
            gvcfs = [gvcf.strip() for gvcf in gvcfs.split(',') if gvcf.strip()]
        cmd = ['gatk', 'GenotypeGVCFs', '-R', str(inputs.get('reference', ''))]
        for gvcf in gvcfs:
            cmd.extend(['-V', str(gvcf)])
        if inputs.get('intervals'):
            cmd.extend(['-L', str(inputs['intervals'])])
        if inputs.get('dbsnp'):
            cmd.extend(['--dbsnp', str(inputs['dbsnp'])])
        if inputs.get('standard_min_confidence') is not None:
            cmd.extend(['--standard-min-confidence-threshold-for-calling', str(inputs['standard_min_confidence'])])
        cmd.extend(['-O', f"{inputs.get('output', '.')}/vcf.vcf.gz"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'gvcfs': ('VCF_GZ', {'description': 'Input GVCF files. Use comma-separated paths for multiple samples.'}), 'reference': ('FASTA', {'description': 'Reference FASTA (indexed)'})}, 'optional': {'intervals': ('STRING', {'default': '', 'description': 'Intervals to genotype (e.g., chr1:1-1000)', 'advanced': True}), 'dbsnp': ('VCF_GZ', {'description': 'Optional dbSNP VCF for annotation', 'advanced': True}), 'standard_min_confidence': ('INT', {'default': 30, 'min': 0, 'max': 100, 'display': 'slider', 'label': 'Call Confidence Threshold', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class GatkBaseRecalibratorNode(CommandNode):
    """Base quality score recalibration with GATK."""
    NODE_ID = 'gatk_base_recalibrator'
    DISPLAY_NAME = 'GATK BaseRecalibrator'
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    CATEGORY = 'variant'
    DESCRIPTION = 'Recalibrate base quality scores using known variants'
    SEARCH_ALIASES = ['gatk', 'bqsr', 'recalibrate', 'base quality']
    RETURN_TYPES = ('TABLE',)
    RETURN_NAMES = ('recal_table',)
    REQUIRED_EXECUTABLES = ['gatk']
    DOCUMENTATION_URL = 'https://gatk.broadinstitute.org/hc/en-us/articles/360036898312-BaseRecalibrator'
    VERSION = '4.5.0'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['gatk', 'BaseRecalibrator', '-I', str(inputs.get('bam', '')), '-R', str(inputs.get('reference', '')), '-O', f"{inputs.get('output', '.')}/recal_table.out"]
        known = inputs.get('known_sites', '')
        if known:
            if isinstance(known, list):
                for ks in known:
                    cmd.extend(['--known-sites', str(ks)])
            else:
                for ks in str(known).split(','):
                    ks = ks.strip()
                    if ks:
                        cmd.extend(['--known-sites', ks])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'known_sites': ('VCF_GZ', {'description': 'Known variants VCF (e.g., dbSNP, Mills). Use comma-separated paths for multiple sites.'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}


class GatkApplyBQSRNode(CommandNode):
    """Apply BQSR recalibration with GATK."""
    NODE_ID = 'gatk_apply_bqsr'
    DISPLAY_NAME = 'GATK ApplyBQSR'
    CATEGORY = 'variant'
    DESCRIPTION = 'Apply base quality score recalibration to a BAM file'
    SEARCH_ALIASES = ['gatk', 'apply bqsr', 'recalibrate']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('bam',)
    REQUIRED_EXECUTABLES = ['gatk']
    REQUIRED_CONDA_PACKAGES = ['gatk4']
    DOCUMENTATION_URL = 'https://gatk.broadinstitute.org/hc/en-us/articles/360037055952-ApplyBQSR'
    VERSION = '4.5.0'
    COMMAND = ['gatk', 'ApplyBQSR', '-R', '{inputs.reference}', '-I', '{inputs.bam}', '--bqsr-recal-file', '{inputs.recal_table}', '-O', '{output}/bam.bam']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'recal_table': (('TABLE', 'FILE'), {'description': 'Recalibration table from BaseRecalibrator'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}
