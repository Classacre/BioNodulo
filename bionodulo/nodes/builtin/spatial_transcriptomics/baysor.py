"""baysor — spatial_transcriptomics node(s). One tool per file (extracted from spatial_transcriptomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class BaysorNode(CommandNode):
    """Run Baysor cell segmentation for molecular spatial data."""
    NODE_ID = 'baysor'
    DISPLAY_NAME = 'Baysor Segmentation'
    CATEGORY = 'spatial_transcriptomics'
    DESCRIPTION = 'Cell segmentation for MERFISH/Xenium high-resolution spatial transcriptomics.'
    SEARCH_ALIASES = ['baysor', 'segmentation', 'merfish', 'xenium', 'molecular spatial']
    RETURN_TYPES = ('CSV',)
    RETURN_NAMES = ('cell_segmentation',)
    REQUIRED_EXECUTABLES = ['baysor']
    REQUIRED_CONDA_PACKAGES = ['baysor']
    DOCUMENTATION_URL = 'https://github.com/kharchenkolab/Baysor'
    VERSION = '0.7.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['baysor', 'run', str(inputs.get('transcript_data', '')), '-x', str(inputs.get('x_col', 'x')), '-y', str(inputs.get('y_col', 'y')), '-g', str(inputs.get('gene_col', 'gene')), '-m', str(inputs.get('min_molecules', 30)), '-o', str(out_dir)]
        if inputs.get('z_col'):
            cmd.extend(['-z', str(inputs['z_col'])])
        if inputs.get('scale'):
            cmd.extend(['--scale', str(inputs['scale'])])
        if inputs.get('iters'):
            cmd.extend(['--iters', str(inputs['iters'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'cell_segmentation.csv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'transcript_data': ('CSV', {'description': 'Transcript coordinates CSV'}), 'x_col': ('STRING', {'default': 'x'}), 'y_col': ('STRING', {'default': 'y'}), 'gene_col': ('STRING', {'default': 'gene'}), 'min_molecules': ('INT', {'default': 30, 'min': 1})}, 'optional': {'z_col': ('STRING', {'default': '', 'description': 'Z column (3D)'}), 'scale': ('STRING', {'default': '', 'description': 'Cell scale estimate (um)'}), 'iters': ('INT', {'default': 500, 'min': 100})}, 'hidden': {'output': ('STRING', {})}}
