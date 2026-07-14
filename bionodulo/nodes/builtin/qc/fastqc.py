"""fastqc — qc node(s). One tool per file (extracted from qc.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class FastQCNode(CommandNode):
    """Run FastQC quality control on FASTQ reads."""
    NODE_ID = 'fastqc'
    DISPLAY_NAME = 'FastQC'
    REQUIRED_CONDA_PACKAGES = ['fastqc']
    CATEGORY = 'qc'
    DESCRIPTION = 'Run FastQC to generate per-base quality plots and reports'
    SEARCH_ALIASES = ['fastqc', 'quality control', 'qc', 'reads qc']
    RETURN_TYPES = ('QC_REPORT_DIR',)
    RETURN_NAMES = ('report_dir',)
    REQUIRED_EXECUTABLES = ['fastqc']
    DOCUMENTATION_URL = 'https://www.bioinformatics.babraham.ac.uk/projects/fastqc/'
    VERSION = '0.12.1'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        report_dir = Path(output_dir) / cls.NODE_ID / 'report_dir.out'
        report_dir.mkdir(parents=True, exist_ok=True)
        return [report_dir]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        outdir = str(inputs.get('output', inputs.get('output_dir', '.')))
        outdir = f'{outdir}/report_dir.out'
        cmd = ['fastqc', '--threads', str(inputs.get('threads', 2)), '--outdir', outdir]
        if inputs.get('nogroup'):
            cmd.append('--nogroup')
        if inputs.get('kmers'):
            cmd.extend(['--kmers', str(inputs['kmers'])])
        if not inputs.get('extract', True):
            cmd.append('--noextract')
        if inputs.get('extract'):
            cmd.append('--extract')
        if inputs.get('format'):
            cmd.extend(['--format', str(inputs['format'])])
        if inputs.get('contaminants'):
            cmd.extend(['--contaminants', str(inputs['contaminants'])])
        if inputs.get('adapters'):
            cmd.extend(['--adapters', str(inputs['adapters'])])
        if inputs.get('limits'):
            cmd.extend(['--limits', str(inputs['limits'])])
        reads = inputs.get('reads', '')
        if isinstance(reads, list):
            cmd.extend(reads)
        else:
            cmd.append(str(reads))
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ_LIST', {'description': 'FASTQ read file(s)'}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'nogroup': ('BOOLEAN', {'default': False, 'description': 'Disable grouping of bases', 'advanced': True}), 'kmers': ('INT', {'default': 7, 'min': 2, 'max': 10, 'description': 'K-mer length', 'advanced': True}), 'extract': ('BOOLEAN', {'default': True, 'description': 'Extract ZIP archive', 'advanced': True}), 'format': ('STRING', {'default': '', 'description': 'Format (bam, sam, bismark)', 'advanced': True}), 'contaminants': ('STRING', {'default': '', 'description': 'Contaminants file', 'advanced': True}), 'adapters': ('STRING', {'default': '', 'description': 'Adapters file', 'advanced': True}), 'limits': ('STRING', {'default': '', 'description': 'Limits file', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
