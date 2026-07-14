"""nanoplot — long_read node(s). One tool per file (extracted from long_read.py)."""
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


class NanoPlotQCNode(CommandNode):
    """Generate long-read QC plots and summary statistics with NanoPlot."""
    NODE_ID = 'nanoplot'
    DISPLAY_NAME = 'NanoPlot QC'
    CATEGORY = 'long_read'
    DESCRIPTION = 'QC plots for ONT and PacBio data. Length, quality, yield histograms.'
    SEARCH_ALIASES = ['nanoplot', 'qc', 'nanopore', 'quality control', 'read stats']
    RETURN_TYPES = ('HTML_REPORT', 'STATS_FILE')
    RETURN_NAMES = ('qc_report', 'qc_stats')
    REQUIRED_EXECUTABLES = ['NanoPlot']
    REQUIRED_CONDA_PACKAGES = ['nanoplot']
    DOCUMENTATION_URL = 'https://github.com/wdecoster/NanoPlot'
    VERSION = '1.44.1'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out_dir = Path(output_dir) / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return [out_dir / 'NanoPlot-report.html', out_dir / 'NanoStats.txt']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['NanoPlot', '--outdir', str(out_dir), '--threads', str(inputs.get('threads', 4)), '--format', str(inputs.get('plot_format', 'png')), '--N50']
        if inputs.get('fastq'):
            cmd.extend(['--fastq', str(inputs['fastq'])])
        elif inputs.get('bam'):
            cmd.extend(['--bam', str(inputs['bam'])])
        elif inputs.get('summary'):
            cmd.extend(['--summary', str(inputs['summary'])])
        if inputs.get('max_length') and int(inputs['max_length']) > 0:
            cmd.extend(['--maxlength', str(inputs['max_length'])])
        if inputs.get('min_length') and int(inputs['min_length']) > 0:
            cmd.extend(['--minlength', str(inputs['min_length'])])
        if inputs.get('loglength'):
            cmd.append('--loglength')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'fastq': ('FASTQ', {'description': 'Input FASTQ (or use bam/summary)'})}, 'optional': {'bam': ('BAM', {'description': 'Input BAM (alternative)'}), 'summary': ('FILE', {'description': 'Sequencing summary from MinKNOW'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64}), 'plot_format': ('STRING', {'default': 'png', 'options': ['png', 'jpg', 'pdf']}), 'max_length': ('INT', {'default': 0, 'min': 0}), 'min_length': ('INT', {'default': 0, 'min': 0}), 'loglength': ('BOOLEAN', {'default': False, 'description': 'Log scale for lengths'})}, 'hidden': {'output': ('STRING', {})}}
