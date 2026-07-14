"""vg — pangenomics node(s). One tool per file (extracted from pangenomics.py)."""
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


class VGConstructNode(CommandNode):
    """Construct variation graphs from a reference FASTA and VCF."""
    NODE_ID = 'vg_construct'
    DISPLAY_NAME = 'vg Construct'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Construct a variation graph from reference FASTA and VCF variants. Foundation for pangenome alignment.'
    SEARCH_ALIASES = ['vg', 'construct', 'variation graph', 'pangenome', 'graph genome']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('vg_graph',)
    REQUIRED_EXECUTABLES = ['vg']
    REQUIRED_CONDA_PACKAGES = ['vg']
    DOCUMENTATION_URL = 'https://github.com/vgteam/vg'
    VERSION = '1.62.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        vcf = str(inputs.get('vcf', ''))
        cmd = ['vg', 'construct', '-r', str(inputs.get('reference', '')), '-a', '-f', '-S']
        if vcf:
            cmd.extend(['-v' if vcf.endswith('.gz') else '-V', vcf])
        if inputs.get('region'):
            cmd.extend(['-R', str(inputs['region'])])
        if inputs.get('max_node_size'):
            cmd.extend(['-m', str(inputs['max_node_size'])])
        if inputs.get('progress'):
            cmd.append('-p')
        cmd.extend(['>', f'{out_dir}/vg_graph.vg'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'vg_graph.vg']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reference': ('FASTA', {'description': 'Reference FASTA'}), 'vcf': ('VCF_GZ', {'description': 'VCF with variants to embed'})}, 'optional': {'region': ('STRING', {'default': '', 'description': 'Region (e.g., chr1:1-1000000)'}), 'max_node_size': ('INT', {'default': 32, 'min': 1}), 'progress': ('BOOLEAN', {'default': True})}, 'hidden': {'output': ('STRING', {})}}


class VGIndexNode(CommandNode):
    """Build vg autoindex artifacts for graph read mapping."""
    NODE_ID = 'vg_index'
    DISPLAY_NAME = 'vg Autoindex'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Build vg autoindex files for Giraffe graph read mapping and downstream graph calling.'
    SEARCH_ALIASES = ['vg', 'autoindex', 'giraffe', 'gbz', 'minimizer', 'distance index', 'pangenome index']
    RETURN_TYPES = ('FILE', 'FILE', 'FILE', 'FILE', 'FILE')
    RETURN_NAMES = ('gbz_index', 'minimizer_index', 'zipcode_index', 'distance_index', 'xg_index')
    REQUIRED_EXECUTABLES = ['vg']
    REQUIRED_CONDA_PACKAGES = ['vg']
    DOCUMENTATION_URL = 'https://github.com/vgteam/vg/wiki/Automatic-indexing-for-read-mapping-and-downstream-inference'
    VERSION = '1.62.0'
    SHELL = True
    _WORKFLOWS = {'giraffe'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        workflow = str(inputs.get('workflow', 'giraffe') or 'giraffe')
        if workflow not in cls._WORKFLOWS:
            return f'Unsupported vg Autoindex workflow: {workflow}'
        if int(inputs.get('threads', 8) or 0) <= 0:
            return 'vg Autoindex threads must be greater than zero.'
        return True

    @classmethod
    def _prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        node_out = Path(output_dir)
        fallback_stem = _safe_output_stem(inputs.get('graph_gfa'), 'graph')
        stem = _safe_output_stem(inputs.get('output_prefix'), fallback_stem)
        return node_out / stem

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        prefix = cls._prefix(inputs, out_dir)
        workflow = str(inputs.get('workflow', 'giraffe') or 'giraffe')
        gbz_index = f'{prefix}.giraffe.gbz'
        xg_index = f'{prefix}.xg'
        cmd = ['vg', 'autoindex', '--workflow', workflow, '--gfa', str(inputs.get('graph_gfa', ''))]
        if inputs.get('reference'):
            cmd.extend(['--ref-fasta', str(inputs['reference'])])
        cmd.extend(['--prefix', str(prefix), '--threads', str(inputs.get('threads', 8))])
        if inputs.get('tmp_dir'):
            cmd.extend(['--tmp-dir', str(inputs['tmp_dir'])])
        if inputs.get('target_mem'):
            cmd.extend(['--target-mem', str(inputs['target_mem'])])
        cmd.extend(['&&', 'vg', 'convert', '-x', '--drop-haplotypes', gbz_index, '>', xg_index])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = cls._prefix(inputs, node_out)
        return [Path(f'{prefix}.giraffe.gbz'), Path(f'{prefix}.shortread.withzip.min'), Path(f'{prefix}.shortread.zipcodes'), Path(f'{prefix}.dist'), Path(f'{prefix}.xg')]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'graph_gfa': ('GFA', {'description': 'Input pangenome graph in GFA format'})}, 'optional': {'workflow': ('STRING', {'default': 'giraffe', 'options': ['giraffe']}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 128, 'display': 'slider'}), 'output_prefix': ('STRING', {'default': '', 'description': 'Optional output filename stem'}), 'reference': ('FASTA', {'description': 'Reference FASTA for named reference paths'}), 'tmp_dir': ('STRING', {'default': '', 'description': 'Optional temporary directory for vg autoindex'}), 'target_mem': ('STRING', {'default': '', 'description': 'Optional target memory limit, for example 64G'})}, 'hidden': {'output': ('STRING', {})}}


class VGMapNode(CommandNode):
    """Map reads to variation graphs with vg map or giraffe."""
    NODE_ID = 'vg_map'
    DISPLAY_NAME = 'vg Map/Giraffe'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Map reads to a variation graph using vg map or vg giraffe. Produces GAM alignments.'
    SEARCH_ALIASES = ['vg', 'map', 'giraffe', 'pangenome align', 'graph alignment', 'gam']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('gam_alignment',)
    REQUIRED_EXECUTABLES = ['vg']
    REQUIRED_CONDA_PACKAGES = ['vg']
    DOCUMENTATION_URL = 'https://github.com/vgteam/vg'
    VERSION = '1.62.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        mapper = inputs.get('mapper', 'giraffe')
        reads = str(inputs.get('reads', ''))
        reads2 = str(inputs.get('reads2', ''))
        threads = str(inputs.get('threads', 8))
        if mapper == 'giraffe':
            cmd = ['vg', 'giraffe', '-Z', str(inputs.get('gbz_index', '')), '-m', str(inputs.get('minimizer_index', '')), '-z', str(inputs.get('zipcode_index', '')), '-d', str(inputs.get('distance_index', '')), '-f', reads, '-p', '-t', threads]
            if reads2:
                cmd.extend(['-f', reads2])
        else:
            cmd = ['vg', 'map', '-x', str(inputs.get('xg_index', '')), '-g', str(inputs.get('gcsa_index', '')), '-f', reads, '-t', threads, '-p']
            if reads2:
                cmd.extend(['-f', reads2])
            if inputs.get('min_identity'):
                cmd.extend(['--min-ident', str(inputs['min_identity'])])
        cmd.extend(['>', str(out_dir / 'gam_alignment.gam')])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'gam_alignment.gam']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Forward/single-end FASTQ'}), 'mapper': ('STRING', {'default': 'giraffe', 'options': ['giraffe', 'map']}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reads2': ('FASTQ', {'description': 'Reverse FASTQ (paired)'}), 'gbz_index': ('FILE', {'description': 'Giraffe GBZ index'}), 'minimizer_index': ('FILE', {'description': 'Minimizer index'}), 'zipcode_index': ('FILE', {'description': 'Zipcodes index'}), 'distance_index': ('FILE', {'description': 'Distance index'}), 'xg_index': ('FILE', {'description': 'XG index (for vg map)'}), 'gcsa_index': ('FILE', {'description': 'GCSA index (for vg map)'}), 'min_identity': ('FLOAT', {'default': 0.5, 'min': 0.0, 'max': 1.0, 'step': 0.05})}, 'hidden': {'output': ('STRING', {})}}


class VGCallNode(CommandNode):
    """Call variants from graph alignments with vg."""
    NODE_ID = 'vg_call'
    DISPLAY_NAME = 'vg Call Variants'
    CATEGORY = 'pangenomics'
    DESCRIPTION = 'Call variants from graph alignments (GAM) using vg pack + vg call. Produces VCF.'
    SEARCH_ALIASES = ['vg', 'call', 'variant calling', 'pangenome', 'graph caller']
    RETURN_TYPES = ('VCF',)
    RETURN_NAMES = ('calls_vcf',)
    REQUIRED_EXECUTABLES = ['vg']
    REQUIRED_CONDA_PACKAGES = ['vg']
    DOCUMENTATION_URL = 'https://github.com/vgteam/vg'
    VERSION = '1.62.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        pack = out_dir / 'aln.pack'
        calls_vcf = out_dir / 'calls_vcf.vcf'
        graph = str(inputs.get('xg_graph', ''))
        threads = str(inputs.get('threads', 4))
        cmd = ['vg', 'pack', '-x', graph, '-g', str(inputs.get('gam', '')), '-o', str(pack), '-t', threads, '&&', 'vg', 'call', graph, '-k', str(pack), '-t', threads, '-v']
        if inputs.get('ref_path'):
            cmd.extend(['-p', str(inputs['ref_path'])])
        if inputs.get('sample'):
            cmd.extend(['-s', str(inputs['sample'])])
        cmd.extend(['>', str(calls_vcf)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'calls_vcf.vcf']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'xg_graph': ('FILE', {'description': 'Input XG graph index'}), 'gam': ('FILE', {'description': 'Graph alignments in GAM format'}), 'threads': ('INT', {'default': 4, 'min': 1})}, 'optional': {'ref_path': ('STRING', {'default': '', 'description': 'Reference path for VCF coordinates'}), 'sample': ('STRING', {'default': '', 'description': 'Sample name for genotype calls'})}, 'hidden': {'output': ('STRING', {})}}
