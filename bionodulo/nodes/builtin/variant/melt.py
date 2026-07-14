"""melt — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class MELTMobileElementsNode(CommandNode):
    """Call mobile element insertions with MELT Single mode."""
    NODE_ID = 'melt_mobile_elements'
    DISPLAY_NAME = 'MELT Mobile Elements'
    CATEGORY = 'variant'
    DESCRIPTION = 'Call mobile element insertions from BAM alignments with MELT Single mode.'
    SEARCH_ALIASES = ['melt', 'mobile element', 'mei', 'mobile element insertion', 'transposable element', 'retrotransposon']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('melt_output',)
    REQUIRED_EXECUTABLES = ['java']
    REQUIRED_CONDA_PACKAGES = []
    DOCUMENTATION_URL = 'https://melt.igs.umaryland.edu/'
    VERSION = '2'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        melt_output = node_out / cls._output_prefix(inputs)
        melt_output.mkdir(parents=True, exist_ok=True)
        return [melt_output]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for name in ('bam', 'reference', 'melt_jar', 'mei_list', 'genome_annotation', 'output_prefix'):
            if not str(inputs.get(name, '')).strip():
                return f"Input '{name}' must not be empty"
        if int(inputs.get('coverage', 0) or 0) < 1:
            return "Input 'coverage' must be at least 1"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.'))) / cls._output_prefix(inputs)
        return ['java', '-jar', str(inputs.get('melt_jar', '')), 'Single', '-bamfile', str(inputs.get('bam', '')), '-h', str(inputs.get('reference', '')), '-n', str(inputs.get('genome_annotation', '')), '-t', str(inputs.get('mei_list', '')), '-c', str(inputs.get('coverage', 30)), '-w', str(out_dir), '-exome', 'true' if inputs.get('exome', False) else 'false']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM file (sorted and indexed)'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'melt_jar': ('FILE', {'description': 'Path to MELT.jar'}), 'mei_list': ('FILE', {'description': 'MELT MEI list'}), 'genome_annotation': ('BED', {'description': 'MELT genome annotation file'}), 'output_prefix': ('STRING', {'default': 'sample', 'description': 'MELT sample/output prefix'}), 'coverage': ('INT', {'default': 30, 'min': 1, 'max': 500, 'display': 'slider'})}, 'optional': {'exome': ('BOOLEAN', {'default': False, 'description': 'Use MELT exome mode'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def _output_prefix(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output_prefix', 'sample')).strip()
