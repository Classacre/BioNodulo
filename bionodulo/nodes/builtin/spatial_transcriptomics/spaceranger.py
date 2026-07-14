"""spaceranger — spatial_transcriptomics node(s). One tool per file (extracted from spatial_transcriptomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SpaceRangerNode(CommandNode):
    """Run Space Ranger count for 10x Genomics Visium data."""
    NODE_ID = 'spaceranger_count'
    DISPLAY_NAME = 'Space Ranger Count'
    CATEGORY = 'spatial_transcriptomics'
    DESCRIPTION = 'Process 10x Genomics Visium: alignment, feature-barcode counting, tissue detection.'
    SEARCH_ALIASES = ['spaceranger', '10x visium', 'spatial transcriptomics', 'visium']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('spaceranger_out',)
    REQUIRED_EXECUTABLES = ['spaceranger']
    REQUIRED_CONDA_PACKAGES = ['spaceranger']
    DOCUMENTATION_URL = 'https://support.10xgenomics.com/spatial-gene-expression'
    VERSION = '3.1.1'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['spaceranger', 'count', '--id', str(inputs.get('sample_id', 'sample')), '--transcriptome', str(inputs.get('transcriptome', '')), '--fastqs', str(inputs.get('fastqs_dir', '')), '--sample', str(inputs.get('sample_prefix', '')), '--image', str(inputs.get('he_image', '')), '--slide', str(inputs.get('slide', '')), '--area', str(inputs.get('area', '')), '--localcores', str(inputs.get('threads', 8)), '--localmem', str(inputs.get('memory', 32)), '--output-dir', str(out_dir)]
        if inputs.get('create_bam'):
            cmd.append('--create-bam=true')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        sample_id = str(inputs.get('sample_id', 'sample'))
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / sample_id]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sample_id': ('STRING', {'description': 'Sample ID'}), 'transcriptome': ('DIRECTORY', {'description': 'Space Ranger reference'}), 'fastqs_dir': ('DIRECTORY', {'description': 'FASTQ directory'}), 'sample_prefix': ('STRING', {'description': 'Sample name prefix in FASTQs'}), 'he_image': ('FILE', {'description': 'H&E tissue image (TIFF)'}), 'slide': ('STRING', {'description': 'Slide serial (e.g., V19L01-041)'}), 'area': ('STRING', {'description': 'Capture area (A1, B1, C1, D1)'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64}), 'memory': ('INT', {'default': 32, 'min': 8, 'max': 256, 'label': 'Memory (GB)'})}, 'optional': {'create_bam': ('BOOLEAN', {'default': False})}, 'hidden': {'output': ('STRING', {})}}


class SpaceRangerCompatibilityNode(SpaceRangerNode):
    """Compatibility wrapper for the original Space Ranger roadmap node ID."""
    NODE_ID = 'spaceranger'
    DISPLAY_NAME = 'Space Ranger'
    DESCRIPTION = 'Process 10x Genomics Visium data with Space Ranger count.'
    SEARCH_ALIASES = ['spaceranger', 'space ranger', '10x visium', 'spatial transcriptomics', 'visium']
