"""cnvkit — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class CNVkitBatchNode(CommandNode):
    """Run the CNVkit batch pipeline for copy-number analysis."""
    NODE_ID = 'cnvkit_batch'
    DISPLAY_NAME = 'CNVkit Batch Pipeline'
    CATEGORY = 'variant'
    DESCRIPTION = 'Complete CNVkit pipeline: coverage -> reference -> fix -> segment -> call. For targeted/WGS tumor/normal CNV detection.'
    SEARCH_ALIASES = ['cnvkit', 'cnv', 'copy number', 'batch', 'cbs']
    RETURN_TYPES = ('DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('cnr_files', 'cns_files')
    REQUIRED_EXECUTABLES = ['cnvkit.py']
    REQUIRED_CONDA_PACKAGES = ['cnvkit']
    DOCUMENTATION_URL = 'https://cnvkit.readthedocs.io/'
    VERSION = '0.9.12'
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'cnr_files', node_out / 'cns_files']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['cnvkit.py', 'batch', str(inputs.get('tumor_bams', '')), '--fasta', str(inputs.get('reference', '')), '--output-reference', f'{out_dir}/reference.cnn', '--output-dir', str(out_dir), '--processes', str(inputs.get('threads', 4))]
        if inputs.get('normal_bams'):
            cmd.extend(['--normal', str(inputs['normal_bams'])])
        if inputs.get('targets'):
            cmd.extend(['--targets', str(inputs['targets'])])
        if inputs.get('method'):
            cmd.extend(['--method', str(inputs['method'])])
        if inputs.get('diagram'):
            cmd.append('--diagram')
        if inputs.get('scatter'):
            cmd.append('--scatter')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'tumor_bams': ('BAM', {'description': 'Tumor BAM file(s)'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'normal_bams': ('BAM', {'description': 'Normal BAM for matched analysis'}), 'targets': ('BED', {'description': 'Target regions BED (exome capture baits)'}), 'method': ('STRING', {'default': 'hybrid', 'options': ['hybrid', 'amplicon', 'wgs']}), 'diagram': ('BOOLEAN', {'default': False, 'description': 'Generate diagram plots'}), 'scatter': ('BOOLEAN', {'default': False, 'description': 'Generate scatter plots'})}, 'hidden': {'output': ('STRING', {})}}


class CNVkitCallNode(CommandNode):
    """Convert CNVkit segment ratios to copy-number calls."""
    NODE_ID = 'cnvkit_call'
    DISPLAY_NAME = 'CNVkit Call'
    CATEGORY = 'variant'
    DESCRIPTION = 'Convert segmented CNV ratios to absolute copy number calls. Supports purity, ploidy, and BAF integration.'
    SEARCH_ALIASES = ['cnvkit', 'cnv call', 'copy number', 'segment', 'call']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('cnv_calls',)
    REQUIRED_EXECUTABLES = ['cnvkit.py']
    REQUIRED_CONDA_PACKAGES = ['cnvkit']
    DOCUMENTATION_URL = 'https://cnvkit.readthedocs.io/'
    VERSION = '0.9.12'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['cnvkit.py', 'call', str(inputs.get('cns_file', '')), '-o', f"{inputs.get('output', '.')}/cnv_calls.vcf"]
        if inputs.get('vcf'):
            cmd.extend(['--vcf', str(inputs['vcf'])])
        if inputs.get('sample_sex'):
            cmd.extend(['--sample-sex', str(inputs['sample_sex'])])
        if inputs.get('ploidy'):
            cmd.extend(['--ploidy', str(inputs['ploidy'])])
        if inputs.get('purity'):
            cmd.extend(['--purity', str(inputs['purity'])])
        if inputs.get('method'):
            cmd.extend(['--method', str(inputs['method'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'cns_file': ('FILE', {'description': 'CNVkit .cns segment file'})}, 'optional': {'vcf': ('VCF_GZ', {'description': 'SNV VCF for BAF integration'}), 'sample_sex': ('STRING', {'default': '', 'options': ['', 'male', 'female']}), 'ploidy': ('INT', {'default': 2, 'min': 1, 'max': 8}), 'purity': ('FLOAT', {'default': 1.0, 'min': 0.0, 'max': 1.0, 'step': 0.05, 'label': 'Tumor Purity'}), 'method': ('STRING', {'default': 'threshold', 'options': ['threshold', 'clonal', 'none']})}, 'hidden': {'output': ('STRING', {})}}


class CNVkitPlotNode(CommandNode):
    """Generate CNVkit scatter and heatmap PDF plots."""
    NODE_ID = 'cnvkit_plot'
    DISPLAY_NAME = 'CNVkit Plot'
    CATEGORY = 'variant'
    DESCRIPTION = 'Generate scatter plots and heatmaps from CNVkit copy number data.'
    SEARCH_ALIASES = ['cnvkit', 'cnv plot', 'copy number', 'scatter', 'heatmap', 'diagram']
    RETURN_TYPES = ('PDF_REPORT', 'PDF_REPORT')
    RETURN_NAMES = ('scatter_plot', 'heatmap_plot')
    REQUIRED_EXECUTABLES = ['cnvkit.py']
    REQUIRED_CONDA_PACKAGES = ['cnvkit']
    DOCUMENTATION_URL = 'https://cnvkit.readthedocs.io/'
    VERSION = '0.9.12'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cnr_file = str(inputs.get('cnr_file', ''))
        cns_file = str(inputs.get('cns_file', ''))
        scatter = ['cnvkit.py', 'scatter', cnr_file, '-s', cns_file, '-o', f'{out_dir}/scatter_plot.pdf']
        if inputs.get('chromosome'):
            scatter.extend(['-c', str(inputs['chromosome'])])
        if inputs.get('gene'):
            scatter.extend(['-g', str(inputs['gene'])])
        heatmap = ['cnvkit.py', 'heatmap', cns_file, '-o', f'{out_dir}/heatmap_plot.pdf']
        if inputs.get('chromosome'):
            heatmap.extend(['-c', str(inputs['chromosome'])])
        return scatter + ['&&'] + heatmap

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'cnr_file': ('FILE', {'description': 'CNVkit .cnr ratio file'}), 'cns_file': ('FILE', {'description': 'CNVkit .cns segment file'})}, 'optional': {'chromosome': ('STRING', {'default': '', 'description': 'Chromosome to plot'}), 'gene': ('STRING', {'default': '', 'description': 'Gene to highlight'})}, 'hidden': {'output': ('STRING', {})}}
