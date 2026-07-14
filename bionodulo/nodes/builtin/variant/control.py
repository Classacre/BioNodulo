"""control — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class ControlFREECNode(CommandNode):
    """Call copy-number variants with Control-FREEC."""
    NODE_ID = 'control_freec'
    DISPLAY_NAME = 'Control-FREEC'
    CATEGORY = 'variant'
    DESCRIPTION = 'CNV caller with tumor purity and ploidy estimation. Supports WGS/WES with or without matched normal.'
    SEARCH_ALIASES = ['control-freec', 'freec', 'cnv', 'copy number', 'allelic imbalance']
    RETURN_TYPES = ('FILE', 'FILE')
    RETURN_NAMES = ('cnv_profile', 'baf_profile')
    REQUIRED_EXECUTABLES = ['freec']
    REQUIRED_CONDA_PACKAGES = ['control-freec']
    DOCUMENTATION_URL = 'http://boevalab.com/FREEC/'
    VERSION = '11.6'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get('output', '.')))
        out_dir.mkdir(parents=True, exist_ok=True)
        config_file = out_dir / 'freec_config.txt'
        lines = ['[general]', f"chrLenFile = {inputs.get('chrom_lengths', '')}", f"ploidy = {inputs.get('ploidy', 2)}", f"window = {inputs.get('window', 50000)}", f"chrFiles = {inputs.get('chrom_dir', '')}", f'outputDir = {out_dir}', f"maxThreads = {inputs.get('threads', 4)}", '[sample]', f"mateFile = {inputs.get('tumor_bam', '')}", 'inputFormat = BAM', 'mateOrientation = FR']
        if inputs.get('normal_bam'):
            lines.extend(['[control]', f"mateFile = {inputs['normal_bam']}", 'inputFormat = BAM', 'mateOrientation = FR'])
        config_file.write_text('\n'.join(lines) + '\n')
        return ['freec', '-conf', str(config_file)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'tumor_bam': ('BAM', {'description': 'Tumor BAM (sorted, indexed)'}), 'chrom_lengths': ('FILE', {'description': 'Chromosome length file'}), 'chrom_dir': ('DIRECTORY', {'description': 'Per-chromosome FASTA directory'}), 'window': ('INT', {'default': 50000, 'min': 1000}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'normal_bam': ('BAM', {'description': 'Normal BAM for matched analysis'}), 'ploidy': ('INT', {'default': 2, 'min': 1, 'max': 8})}, 'hidden': {'output': ('STRING', {})}}
