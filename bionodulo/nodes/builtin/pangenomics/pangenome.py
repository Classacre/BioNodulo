"""pangenome — pangenomics node(s). One tool per file (extracted from pangenomics.py)."""
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


class PangenomeSVNode(CommandNode):
    """Call structural variants from a pangenome graph against a reference path."""
    NODE_ID = 'pangenome_sv'
    DISPLAY_NAME = 'Pangenome SV'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Call structural variants from a pangenome graph against a reference and emit an indexed VCF.'
    SEARCH_ALIASES = ['pangenome', 'structural variants', 'sv', 'graph vcf', 'pangenome graph', 'vg deconstruct']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('sv_vcf',)
    REQUIRED_EXECUTABLES = ['vg', 'bcftools', 'bgzip', 'tabix']
    REQUIRED_CONDA_PACKAGES = ['vg', 'bcftools', 'htslib']
    DOCUMENTATION_URL = 'https://github.com/vgteam/vg'
    VERSION = '1.62.0'
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get('min_sv_length', 0) or 0) < 0:
            return 'Minimum SV length must be non-negative'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        prefix = out_dir / 'graph'
        xg_index = out_dir / 'graph.xg'
        output_vcf = out_dir / 'sv_vcf.vcf.gz'
        threads = int(inputs.get('threads', 0) or 0)
        min_sv_length = int(inputs.get('min_sv_length', 0) or 0)
        sample_name = str(inputs.get('sample_name', '') or '')
        cmd: list[str] = []
        if sample_name:
            samples_file = out_dir / 'samples.txt'
            cmd.extend(['printf', f"'{sample_name}\\n'", '>', str(samples_file), '&&'])
        cmd.extend(['vg', 'autoindex', '--workflow', 'giraffe', '--gfa', str(inputs.get('graph_gfa', '')), '--ref-fasta', str(inputs.get('reference', '')), '--prefix', str(prefix)])
        if threads > 0:
            cmd.extend(['--threads', str(threads)])
        cmd.extend(['&&', 'vg', 'deconstruct', str(xg_index)])
        if inputs.get('ref_path'):
            cmd.extend(['-P', str(inputs['ref_path'])])
        cmd.extend(['-a', '-e'])
        if threads > 0:
            cmd.extend(['-t', str(threads)])
        if min_sv_length > 0:
            cmd.extend(['|', 'bcftools', 'view', '-i', f'ABS(ILEN)>={min_sv_length} || ABS(strlen(ALT)-strlen(REF))>={min_sv_length}'])
        if sample_name:
            cmd.extend(['|', 'bcftools', 'reheader', '-s', str(out_dir / 'samples.txt')])
        cmd.extend(['|', 'bgzip'])
        if threads > 0:
            cmd.extend(['--threads', str(threads)])
        cmd.extend(['-c', '>', str(output_vcf), '&&', 'tabix', '-f', '-p', 'vcf', str(output_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'sv_vcf.vcf.gz']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'graph_gfa': ('GFA', {'description': 'Input pangenome graph in GFA format'}), 'reference': ('FASTA', {'description': 'Reference FASTA used to interpret graph paths'})}, 'optional': {'sample_name': ('STRING', {'default': '', 'description': 'Optional sample name for the output VCF'}), 'threads': ('INT', {'default': 8, 'min': 0, 'max': 64, 'display': 'slider'}), 'ref_path': ('STRING', {'default': '', 'description': 'Reference path to deconstruct'}), 'min_sv_length': ('INT', {'default': 50, 'min': 0, 'description': 'Minimum variant length to keep'})}, 'hidden': {'output': ('STRING', {})}}


class PangenomeStatsNode(CommandNode):
    """Compute pangenome growth statistics from graph and gene annotations."""
    NODE_ID = 'pangenome_stats'
    DISPLAY_NAME = 'Pangenome Stats'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Compute core, shell, and cloud pangenome statistics from annotated pangenome graphs.'
    SEARCH_ALIASES = ['pangenome', 'panacus', 'core genes', 'shell genes', 'cloud genes', 'rarefaction']
    RETURN_TYPES = ('JSON', 'FILE')
    RETURN_NAMES = ('stats', 'rarefaction')
    REQUIRED_EXECUTABLES = ['panacus']
    REQUIRED_CONDA_PACKAGES = ['panacus']
    DOCUMENTATION_URL = 'https://github.com/marschall-lab/panacus'
    VERSION = '0.3.3'
    SHELL = True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        core_threshold = float(inputs.get('core_threshold', 0.9) or 0.9)
        shell_threshold = float(inputs.get('shell_threshold', 0.1) or 0.1)
        if not 0 <= shell_threshold <= 1 or not 0 <= core_threshold <= 1:
            return 'Pangenome thresholds must be between 0 and 1'
        if core_threshold <= shell_threshold:
            return 'Core threshold must be greater than shell threshold'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        rarefaction = out_dir / 'rarefaction.tsv'
        stats = out_dir / 'stats.json'
        threads = int(inputs.get('threads', 0) or 0)
        cmd = ['panacus', 'histgrowth', str(inputs.get('graph', '')), '--gff', str(inputs.get('annotations', ''))]
        if inputs.get('groupby'):
            cmd.extend(['--groupby', str(inputs['groupby'])])
        if threads > 0:
            cmd.extend(['--threads', str(threads)])
        if inputs.get('include_html'):
            cmd.extend(['--html', str(out_dir / 'rarefaction.html')])
        cmd.extend(['>', str(rarefaction), '&&', 'python', '-m', 'bionodulo.nodes.scripts.pangenome_stats_summary', '--input', str(rarefaction), '--output', str(stats), '--core-threshold', str(float(inputs.get('core_threshold', 0.9) or 0.9)), '--shell-threshold', str(float(inputs.get('shell_threshold', 0.1) or 0.1))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'stats.json', node_out / 'rarefaction.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'graph': ('GFA', {'description': 'Input pangenome graph in GFA format'}), 'annotations': ('GFF', {'description': 'Gene annotations used for pangenome feature summaries'})}, 'optional': {'core_threshold': ('FLOAT', {'default': 0.9, 'min': 0.0, 'max': 1.0, 'step': 0.01}), 'shell_threshold': ('FLOAT', {'default': 0.1, 'min': 0.0, 'max': 1.0, 'step': 0.01}), 'groupby': ('FILE', {'description': 'Optional Panacus group-by or path grouping file'}), 'threads': ('INT', {'default': 4, 'min': 0, 'max': 64, 'display': 'slider'}), 'include_html': ('BOOLEAN', {'default': False, 'description': 'Also request Panacus HTML output'})}, 'hidden': {'output': ('STRING', {})}}


class PangenomeGeneNode(CommandNode):
    """Extract gene presence/absence matrices from pangenome annotations."""
    NODE_ID = 'pangenome_gene'
    DISPLAY_NAME = 'Pangenome Gene'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Extract gene presence/absence matrix and summary plot from pangenome annotations.'
    SEARCH_ALIASES = ['pangenome', 'panaroo', 'presence absence', 'orthologs', 'gene clusters']
    RETURN_TYPES = ('FILE', 'IMAGE')
    RETURN_NAMES = ('presence_matrix', 'pan_genome_plot')
    REQUIRED_EXECUTABLES = ['panaroo']
    REQUIRED_CONDA_PACKAGES = ['panaroo']
    DOCUMENTATION_URL = 'https://github.com/gtonkinhill/panaroo'
    VERSION = '1.5.0'
    SHELL = True
    _CLEAN_MODES = {'strict', 'moderate', 'sensitive'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not _split_path_list(inputs.get('annotations')):
            return 'At least one GFF annotation is required'
        clean_mode = str(inputs.get('clean_mode', 'strict') or 'strict')
        if clean_mode not in cls._CLEAN_MODES:
            return f'Unsupported Panaroo clean mode: {clean_mode}'
        core_threshold = float(inputs.get('core_threshold', 0) or 0)
        if not 0 <= core_threshold <= 1:
            return 'Core threshold must be between 0 and 1'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        presence_matrix = out_dir / 'presence_matrix.tsv'
        pan_genome_plot = out_dir / 'pan_genome_plot.svg'
        annotations = _split_path_list(inputs.get('annotations'))
        threads = int(inputs.get('threads', 0) or 0)
        core_threshold = float(inputs.get('core_threshold', 0) or 0)
        cmd = ['panaroo', '-i', *annotations, '-o', str(out_dir), '--clean-mode', str(inputs.get('clean_mode', 'strict') or 'strict')]
        if threads > 0:
            cmd.extend(['-t', str(threads)])
        if core_threshold > 0:
            cmd.extend(['--core_threshold', str(core_threshold)])
        if inputs.get('remove_invalid_genes'):
            cmd.append('--remove-invalid-genes')
        if inputs.get('merge_paralogs'):
            cmd.append('--merge_paralogs')
        cmd.extend(['&&', 'cp', str(out_dir / 'gene_presence_absence.Rtab'), str(presence_matrix), '&&', 'cp', str(inputs.get('orthologs', '')), str(out_dir / 'orthologs.tsv'), '&&', 'python', '-m', 'bionodulo.nodes.scripts.pangenome_gene_plot', '--input', str(presence_matrix), '--output', str(pan_genome_plot)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'presence_matrix.tsv', node_out / 'pan_genome_plot.svg']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'annotations': ('GFF', {'description': 'GFF annotation files; pass a list or comma-separated paths'}), 'orthologs': ('FILE', {'description': 'Ortholog or gene cluster table to retain with outputs'})}, 'optional': {'clean_mode': ('STRING', {'default': 'strict', 'options': ['strict', 'moderate', 'sensitive']}), 'threads': ('INT', {'default': 4, 'min': 0, 'max': 64, 'display': 'slider'}), 'core_threshold': ('FLOAT', {'default': 0.95, 'min': 0.0, 'max': 1.0, 'step': 0.01}), 'remove_invalid_genes': ('BOOLEAN', {'default': True}), 'merge_paralogs': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}
