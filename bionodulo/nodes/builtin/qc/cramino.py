"""cramino — qc node(s). One tool per file (extracted from bam_cram_utils.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
GALAXY_ALIAS = 'BioNodulo builtin'
CRAMINO_CITATION_DOI = '10.1093/bioinformatics/btad311'
CRAMINO_CITATION_TEXT = 'NanoPack2: population-scale evaluation of long-read sequencing data.'
BAMUTIL_CITATION_DOI = '10.1101/gr.176552.114'
BAMUTIL_CITATION_TEXT = 'GotCloud: a sequence analysis pipeline for high-quality variant calls.'
def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get('output', inputs.get('output_dir', '.')))
def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != '':
        cmd.extend([flag, str(value)])
def _common_output(node_id: str, filename: str, output_dir: str | Path) -> Path:
    out = Path(output_dir) / node_id
    out.mkdir(parents=True, exist_ok=True)
    return out / filename
def _cramino_metrics_name(inputs: dict[str, Any]) -> str:
    return {'json': 'metrics.json', 'tsv': 'metrics.tsv', 'text': 'metrics.txt'}.get(str(inputs.get('outfmt', 'text')), 'metrics.txt')
def _bamutil_diff_ext(inputs: dict[str, Any]) -> str:
    output_as = str(inputs.get('output_as', 'diff.txt'))
    return Path(output_as).suffix.lstrip('.') or 'txt'
def _path_stem(value: Any, fallback: str) -> str:
    stem = Path(str(value or '')).stem
    return stem or fallback


class CraminoNode(CommandNode):
    """Extract long-read BAM/CRAM QC metrics with Cramino."""
    NODE_ID = 'cramino'
    DISPLAY_NAME = 'Cramino'
    REQUIRED_CONDA_PACKAGES = ['cramino']
    CATEGORY = 'qc'
    DESCRIPTION = 'Extract summary QC metrics, histograms, and optional Arrow output from long-read BAM or CRAM files.'
    SEARCH_ALIASES = [GALAXY_ALIAS, 'cramino', 'BAM CRAM QC', 'long read QC', 'NanoPack2']
    RETURN_TYPES = ('STATS_FILE', 'FILE', 'TSV')
    RETURN_NAMES = ('metrics', 'arrow_output', 'histogram')
    REQUIRED_EXECUTABLES = ['cramino']
    DOCUMENTATION_URL = 'https://github.com/wdecoster/cramino'
    CITATION_DOIS = [CRAMINO_CITATION_DOI]
    CITATION_URLS = [f'https://doi.org/{CRAMINO_CITATION_DOI}']
    CITATION_TEXT = CRAMINO_CITATION_TEXT
    VERSION = '1.3.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        cmd = ['cramino', str(inputs.get('input_file', ''))]
        _add_if_value(cmd, '--reference', inputs.get('reference'))
        if inputs.get('ubam', True):
            cmd.append('--ubam')
        if inputs.get('spliced'):
            cmd.append('--spliced')
        if inputs.get('phased'):
            cmd.append('--phased')
        if inputs.get('karyotype'):
            cmd.append('--karyotype')
        _add_if_value(cmd, '--min-read-len', inputs.get('min_read_len'))
        cmd.extend(['--format', str(inputs.get('outfmt', 'text'))])
        if inputs.get('arrow'):
            cmd.extend(['--arrow', f'{out}/reads.arrow'])
        histtype = str(inputs.get('histtype', 'no'))
        if histtype == 'hist':
            cmd.append(f'--hist={out}/histogram.txt')
        elif histtype == 'hist_count':
            cmd.append(f'--hist-count={out}/histogram_counts.tsv')
        if histtype in {'hist', 'hist_count'} and inputs.get('scaled'):
            cmd.append('--scaled')
        cmd.extend(['>', f'{out}/{_cramino_metrics_name(inputs)}'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        outputs = [_common_output(cls.NODE_ID, _cramino_metrics_name(inputs), output_dir)]
        if inputs.get('arrow'):
            outputs.append(_common_output(cls.NODE_ID, 'reads.arrow', output_dir))
        histtype = str(inputs.get('histtype', 'no'))
        if histtype == 'hist':
            outputs.append(_common_output(cls.NODE_ID, 'histogram.txt', output_dir))
        elif histtype == 'hist_count':
            outputs.append(_common_output(cls.NODE_ID, 'histogram_counts.tsv', output_dir))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_file': ('BAM', {'description': 'BAM or CRAM file to inspect'})}, 'optional': {'reference': ('FASTA', {'description': 'Reference FASTA for CRAM decompression'}), 'ubam': ('BOOLEAN', {'default': True, 'description': 'Report metrics for all reads rather than aligned reads only'}), 'spliced': ('BOOLEAN', {'default': False, 'description': 'Report splice-site metrics'}), 'phased': ('BOOLEAN', {'default': False, 'description': 'Calculate phased-read and phase-block metrics'}), 'karyotype': ('BOOLEAN', {'default': False, 'description': 'Report normalized reads per chromosome'}), 'min_read_len': ('INT', {'default': '', 'min': 0, 'description': 'Minimum read length to include'}), 'outfmt': ('STRING', {'default': 'text', 'options': ['text', 'json', 'tsv'], 'description': 'Metrics output format'}), 'arrow': ('BOOLEAN', {'default': False, 'description': 'Write Arrow output for NanoPlot or NanoComp'}), 'histtype': ('STRING', {'default': 'no', 'options': ['no', 'hist', 'hist_count'], 'description': 'Generate a histogram plot data file or bin-count table'}), 'scaled': ('BOOLEAN', {'default': False, 'description': 'Scale histogram bins by total basepairs'})}, 'hidden': {'output': ('STRING', {})}}
