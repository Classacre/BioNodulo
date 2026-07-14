"""bedtools — chip_seq node(s). One tool per file (extracted from chip_seq.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default


class BEDToolsIntersectNode(CommandNode):
    """Intersect two BED/BAM files."""
    NODE_ID = 'bedtools_intersect'
    DISPLAY_NAME = 'BEDTools Intersect'
    CATEGORY = 'chip_seq'
    DESCRIPTION = 'Find overlapping intervals between two BED files'
    SEARCH_ALIASES = ['bedtools', 'intersect', 'overlap', 'bed']
    RETURN_TYPES = ('BED',)
    RETURN_NAMES = ('intersection',)
    REQUIRED_EXECUTABLES = ['bedtools']
    REQUIRED_CONDA_PACKAGES = ['bedtools']
    DOCUMENTATION_URL = 'https://bedtools.readthedocs.io/'
    VERSION = '2.31.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['bedtools', 'intersect', '-a', str(inputs.get('a', '')), '-b', str(inputs.get('b', ''))]
        if inputs.get('wa'):
            cmd.append('-wa')
        if inputs.get('wb'):
            cmd.append('-wb')
        if inputs.get('f') is not None:
            cmd.extend(['-f', str(inputs['f'])])
        if inputs.get('sorted'):
            cmd.append('-sorted')
        if inputs.get('v'):
            cmd.append('-v')
        if inputs.get('s'):
            cmd.append('-s')
        if inputs.get('wo'):
            cmd.append('-wo')
        cmd.extend(['>', f"{inputs.get('output', '.')}/intersection.bed"])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'a': ('BED', {'description': 'First BED/BAM/VCF/GFF file'}), 'b': ('BED', {'description': 'Second BED/BAM/VCF/GFF file'})}, 'optional': {'wa': ('BOOLEAN', {'default': False}), 'wb': ('BOOLEAN', {'default': False}), 'f': ('FLOAT', {'default': 1e-09, 'min': 0.0, 'max': 1.0, 'description': 'Minimum overlap fraction'}), 'sorted': ('BOOLEAN', {'default': False, 'label': 'Sorted', 'advanced': True}), 'v': ('BOOLEAN', {'default': False, 'label': 'Invert', 'advanced': True}), 's': ('BOOLEAN', {'default': False, 'label': 'Strand', 'advanced': True}), 'wo': ('BOOLEAN', {'default': False, 'label': 'Write overlap', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}


class BEDToolsCoverageNode(CommandNode):
    """Compute coverage of BED intervals."""
    NODE_ID = 'bedtools_coverage'
    DISPLAY_NAME = 'BEDTools Coverage'
    CATEGORY = 'chip_seq'
    DESCRIPTION = 'Compute read coverage over BED intervals'
    SEARCH_ALIASES = ['bedtools', 'coverage', 'depth', 'intervals']
    RETURN_TYPES = ('BED',)
    RETURN_NAMES = ('coverage',)
    REQUIRED_EXECUTABLES = ['bedtools']
    REQUIRED_CONDA_PACKAGES = ['bedtools']
    DOCUMENTATION_URL = 'https://bedtools.readthedocs.io/'
    VERSION = '2.31.1'
    SHELL = True
    COMMAND = ['bedtools', 'coverage', '-a', '{inputs.a}', '-b', '{inputs.b}', '>', '{output}/coverage.bed']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'a': ('BED', {'description': 'Intervals BED file'}), 'b': ('BAM', {'description': 'Reads BAM file'})}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}
