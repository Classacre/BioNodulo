"""deeptools — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
DSS_DMR_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'dss_dmr.R'
def _safe_output_stem(value: Any, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default
def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace('\n', ',').split(',') if part.strip()]
def _split_window_sizes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(',', ' ').split() if part.strip()]
def _split_base_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    bases: list[str] = []
    for item in values:
        bases.extend((part.strip() for part in str(item).replace(',', ' ').split() if part.strip()))
    return bases


class DeepToolsBamCoverageNode(CommandNode):
    """Convert BAM alignments to bigWig coverage tracks with deepTools."""
    NODE_ID = 'deeptools_bamcoverage'
    DISPLAY_NAME = 'deepTools bamCoverage'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Convert BAM to bigWig coverage tracks. Supports CPM, RPGC, BPM normalization.'
    SEARCH_ALIASES = ['deeptools', 'bamcoverage', 'bigwig', 'coverage', 'chip-seq', 'atac-seq']
    RETURN_TYPES = ('BIGWIG',)
    RETURN_NAMES = ('coverage_bw',)
    REQUIRED_EXECUTABLES = ['bamCoverage']
    REQUIRED_CONDA_PACKAGES = ['deeptools']
    DOCUMENTATION_URL = 'https://deeptools.readthedocs.io/'
    VERSION = '3.5.6'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = inputs.get('output', '.')
        cmd = ['bamCoverage', '-b', str(inputs.get('bam', '')), '-o', f'{output}/coverage_bw.bw', '-p', str(inputs.get('threads', 4)), '--binSize', str(inputs.get('bin_size', 10))]
        normalize_using = inputs.get('normalize_using', 'CPM')
        if normalize_using and normalize_using != 'None':
            cmd.extend(['--normalizeUsing', str(normalize_using)])
        if inputs.get('effective_genome_size'):
            cmd.extend(['--effectiveGenomeSize', str(inputs['effective_genome_size'])])
        if inputs.get('center_reads'):
            cmd.append('--centerReads')
        if inputs.get('ignore_duplicates'):
            cmd.append('--ignoreDuplicates')
        if inputs.get('extend_reads'):
            cmd.extend(['--extendReads', str(inputs['extend_reads'])])
        if inputs.get('blacklist'):
            cmd.extend(['--blackListFileName', str(inputs['blacklist'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Sorted, indexed BAM'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64}), 'normalize_using': ('STRING', {'default': 'CPM', 'options': ['CPM', 'BPM', 'RPGC', 'RPKM', 'None']})}, 'optional': {'bin_size': ('INT', {'default': 10, 'min': 1}), 'effective_genome_size': ('INT', {'default': 0, 'min': 0, 'label': 'Eff. Genome Size (0=auto)'}), 'center_reads': ('BOOLEAN', {'default': False}), 'ignore_duplicates': ('BOOLEAN', {'default': True}), 'extend_reads': ('INT', {'default': 0, 'min': 0, 'label': 'Extend Reads (0=auto)'}), 'blacklist': ('BED', {'description': 'Blacklist regions'})}, 'hidden': {'output': ('STRING', {})}}


class DeepToolsComputeMatrixNode(CommandNode):
    """Prepare signal matrices around genomic features for deepTools plots."""
    NODE_ID = 'deeptools_compute_matrix'
    DISPLAY_NAME = 'deepTools computeMatrix'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Prepare signal matrices around genomic features for heatmap/profile plots.'
    SEARCH_ALIASES = ['deeptools', 'computematrix', 'heatmap matrix', 'signal profile']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('matrix',)
    REQUIRED_EXECUTABLES = ['computeMatrix']
    REQUIRED_CONDA_PACKAGES = ['deeptools']
    DOCUMENTATION_URL = 'https://deeptools.readthedocs.io/'
    VERSION = '3.5.6'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        mode = str(inputs.get('mode', 'reference-point'))
        cmd = ['computeMatrix', mode, '-S', str(inputs.get('bigwig', '')), '-R', str(inputs.get('regions', '')), '-o', f'{out_dir}/matrix.gz', '-p', str(inputs.get('threads', 4)), '--binSize', str(inputs.get('bin_size', 10))]
        if mode == 'reference-point':
            cmd.extend(['--referencePoint', str(inputs.get('reference_point', 'TSS')), '-b', str(inputs.get('before_region', 3000)), '-a', str(inputs.get('after_region', 3000))])
        else:
            cmd.extend(['-b', str(inputs.get('before_region', 3000)), '-a', str(inputs.get('after_region', 3000)), '--regionBodyLength', str(inputs.get('region_body_length', 5000))])
        if inputs.get('skip_zeros'):
            cmd.append('--skipZeros')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bigwig': ('BIGWIG', {'description': 'bigWig file(s)'}), 'regions': ('BED', {'description': 'Regions BED'}), 'mode': ('STRING', {'default': 'reference-point', 'options': ['reference-point', 'scale-regions']}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64})}, 'optional': {'reference_point': ('STRING', {'default': 'TSS', 'options': ['TSS', 'TES', 'center']}), 'before_region': ('INT', {'default': 3000, 'min': 0}), 'after_region': ('INT', {'default': 3000, 'min': 0}), 'region_body_length': ('INT', {'default': 5000, 'min': 0}), 'skip_zeros': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}


class DeepToolsPlotHeatmapNode(CommandNode):
    """Generate heatmap and profile images from deepTools matrix output."""
    NODE_ID = 'deeptools_plot_heatmap'
    DISPLAY_NAME = 'deepTools Plot Heatmap'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Publication-quality heatmaps and profile plots from computeMatrix output.'
    SEARCH_ALIASES = ['deeptools', 'plotheatmap', 'heatmap', 'profile plot']
    RETURN_TYPES = ('IMAGE', 'IMAGE')
    RETURN_NAMES = ('heatmap', 'profile_plot')
    REQUIRED_EXECUTABLES = ['plotHeatmap']
    REQUIRED_CONDA_PACKAGES = ['deeptools']
    DOCUMENTATION_URL = 'https://deeptools.readthedocs.io/'
    VERSION = '3.5.6'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        matrix = str(inputs.get('matrix', ''))
        heatmap = ['plotHeatmap', '-m', matrix, '--heatmapHeight', str(inputs.get('heatmap_height', 25)), '--heatmapWidth', str(inputs.get('heatmap_width', 15)), '--colorMap', str(inputs.get('colormap', 'RdBu_r')), '--outFileName', f'{out_dir}/heatmap.png']
        sort_regions = inputs.get('sort_regions')
        if sort_regions and sort_regions != 'no':
            heatmap.extend(['--sortRegions', str(sort_regions)])
        if inputs.get('kmeans') and int(inputs['kmeans']) > 0:
            heatmap.extend(['--kmeans', str(inputs['kmeans'])])
        plot_title = inputs.get('plot_title')
        if plot_title:
            heatmap.extend(['--plotTitle', str(plot_title)])
        profile = ['plotProfile', '-m', matrix, '--outFileName', f'{out_dir}/profile_plot.png']
        if plot_title:
            profile.extend(['--plotTitle', str(plot_title)])
        return heatmap + ['&&'] + profile

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'heatmap.png', node_out / 'profile_plot.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'matrix': ('FILE', {'description': 'Matrix from computeMatrix'})}, 'optional': {'heatmap_height': ('INT', {'default': 25, 'min': 5}), 'heatmap_width': ('INT', {'default': 15, 'min': 5}), 'colormap': ('STRING', {'default': 'RdBu_r', 'options': ['RdBu_r', 'hot', 'coolwarm', 'viridis']}), 'sort_regions': ('STRING', {'default': 'no', 'options': ['no', 'descend', 'ascend', 'mean']}), 'kmeans': ('INT', {'default': 0, 'min': 0, 'max': 20, 'label': 'K-means (0=off)'}), 'plot_title': ('STRING', {'default': ''})}, 'hidden': {'output': ('STRING', {})}}


class DeepToolsPlotProfileNode(CommandNode):
    """Generate average profile plots from deepTools matrix output."""
    NODE_ID = 'deeptools_plot_profile'
    DISPLAY_NAME = 'deepTools Plot Profile'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Plot average signal profiles from deepTools computeMatrix output.'
    SEARCH_ALIASES = ['deeptools', 'plotprofile', 'profile plot', 'average profile', 'signal profile']
    RETURN_TYPES = ('IMAGE',)
    RETURN_NAMES = ('profile',)
    REQUIRED_EXECUTABLES = ['plotProfile']
    REQUIRED_CONDA_PACKAGES = ['deeptools']
    DOCUMENTATION_URL = 'https://deeptools.readthedocs.io/'
    VERSION = '3.5.6'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['plotProfile', '-m', str(inputs.get('matrix', '')), '--outFileName', f'{out_dir}/profile.png']
        plot_title = inputs.get('plot_title')
        if plot_title:
            cmd.extend(['--plotTitle', str(plot_title)])
        plot_type = inputs.get('plot_type', 'lines')
        if plot_type:
            cmd.extend(['--plotType', str(plot_type)])
        if inputs.get('plot_height'):
            cmd.extend(['--plotHeight', str(inputs['plot_height'])])
        if inputs.get('plot_width'):
            cmd.extend(['--plotWidth', str(inputs['plot_width'])])
        if inputs.get('per_group'):
            cmd.append('--perGroup')
        for input_name, flag in (('colors', '--colors'), ('samples_label', '--samplesLabel'), ('regions_label', '--regionsLabel'), ('y_axis_label', '--yAxisLabel'), ('start_label', '--startLabel'), ('end_label', '--endLabel')):
            value = inputs.get(input_name)
            if value:
                cmd.extend([flag, str(value)])
        legend_location = inputs.get('legend_location', 'best')
        if legend_location:
            cmd.extend(['--legendLocation', str(legend_location)])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'profile.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'matrix': ('FILE', {'description': 'Matrix from computeMatrix'})}, 'optional': {'plot_title': ('STRING', {'default': ''}), 'plot_type': ('STRING', {'default': 'lines', 'options': ['lines', 'fill', 'se', 'std', 'overlapped_lines', 'heatmap']}), 'plot_height': ('FLOAT', {'default': 0.0, 'min': 0.0}), 'plot_width': ('FLOAT', {'default': 0.0, 'min': 0.0}), 'per_group': ('BOOLEAN', {'default': False}), 'colors': ('STRING', {'default': '', 'description': 'Space-separated matplotlib color names'}), 'samples_label': ('STRING', {'default': ''}), 'regions_label': ('STRING', {'default': ''}), 'y_axis_label': ('STRING', {'default': ''}), 'start_label': ('STRING', {'default': ''}), 'end_label': ('STRING', {'default': ''}), 'legend_location': ('STRING', {'default': 'best', 'options': ['best', 'upper-right', 'upper-left', 'lower-left', 'lower-right', 'none']})}, 'hidden': {'output': ('STRING', {})}}
