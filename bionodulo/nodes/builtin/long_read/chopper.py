"""chopper — long_read node(s). One tool per file (extracted from long_read.py)."""
from __future__ import annotations
from pathlib import Path
import re
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class ChopperFilterNode(CommandNode):
    """Filter and trim Oxford Nanopore reads with Chopper."""
    NODE_ID = 'chopper_filter'
    DISPLAY_NAME = 'Chopper Filter'
    CATEGORY = 'long_read'
    DESCRIPTION = 'Filter and trim ONT reads by quality, length. Replaces NanoFilt.'
    SEARCH_ALIASES = ['chopper', 'nanopore', 'filter', 'trim', 'quality filter']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('filtered_reads',)
    REQUIRED_EXECUTABLES = ['chopper']
    REQUIRED_CONDA_PACKAGES = ['chopper']
    DOCUMENTATION_URL = 'https://github.com/wdecoster/chopper'
    VERSION = '0.9.2'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['chopper', '-i', str(inputs.get('reads', ''))]
        if inputs.get('min_quality'):
            cmd.extend(['-q', str(inputs['min_quality'])])
        if inputs.get('min_length'):
            cmd.extend(['-l', str(inputs['min_length'])])
        if inputs.get('max_length') and int(inputs['max_length']) > 0:
            cmd.extend(['--maxlength', str(inputs['max_length'])])
        if inputs.get('headcrop'):
            cmd.extend(['--headcrop', str(inputs['headcrop'])])
        if inputs.get('tailcrop'):
            cmd.extend(['--tailcrop', str(inputs['tailcrop'])])
        if inputs.get('threads'):
            cmd.extend(['-t', str(inputs['threads'])])
        cmd.extend(['>', f'{out_dir}/filtered_reads.fastq.gz'])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Input FASTQ (can be gzipped)'})}, 'optional': {'min_quality': ('INT', {'default': 10, 'min': 0, 'max': 30, 'label': 'Min Quality'}), 'min_length': ('INT', {'default': 1000, 'min': 0, 'label': 'Min Read Length'}), 'max_length': ('INT', {'default': 0, 'min': 0, 'label': 'Max Length (0=off)'}), 'headcrop': ('INT', {'default': 0, 'min': 0, 'label': 'Head Crop (bp)'}), 'tailcrop': ('INT', {'default': 0, 'min': 0, 'label': 'Tail Crop (bp)'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
