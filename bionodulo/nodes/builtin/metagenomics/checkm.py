"""checkm — metagenomics node(s). One tool per file (extracted from metagenomics.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any, Optional
from bionodulo.nodes.command_node import CommandNode, _shell_join
DOI_URL = 'https://doi.org/'
METAPHLAN_DOI = '10.1038/s41587-023-01688-w'
METAPHLAN_CITATION_TEXT = 'Extending and improving metagenomic taxonomic profiling with uncharacterized species using MetaPhlAn 4.'
HUMANN_CITATION_DOIS = ['10.7554/eLife.65088', '10.1371/journal.pcbi.1002358']
HUMANN_CITATION_TEXT = "bioBakery 3: a platform for analyzing meta'omic datasets; HUMAnN: the HMP Unified Metabolic Analysis Network."
KRAKEN2_CITATION_DOI = '10.1186/gb-2014-15-3-r46'
KRAKEN2_CITATION_TEXT = 'Kraken: ultrafast metagenomic sequence classification using exact alignments.'
BRACKEN_CITATION_DOI = '10.7717/peerj-cs.104'
BRACKEN_CITATION_TEXT = 'Bracken: estimating species abundance in metagenomics data.'
def _as_list(value: Any) -> list[str]:
    if value is None or value == '':
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != '']
    return [str(value)]
def _add_shell_redirect(cmd: list[str], output_path: str) -> None:
    cmd.extend(['>', output_path])
def _shell_join_allow_substitution(cmd: list[str]) -> str:
    parts: list[str] = []
    for token in cmd:
        parts.append(token if token.startswith('$(') else _shell_join([token]))
    return ' '.join(parts)


class CheckMNode(CommandNode):
    """Assess metagenomic bin quality with CheckM."""
    NODE_ID = 'checkm'
    DISPLAY_NAME = 'CheckM'
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Assess the quality of microbial genomes recovered from metagenomes'
    SEARCH_ALIASES = ['checkm', 'bin quality', 'completeness', 'contamination']
    RETURN_TYPES = ('STATS_FILE',)
    RETURN_NAMES = ('quality_report',)
    REQUIRED_EXECUTABLES = ['checkm']
    REQUIRED_CONDA_PACKAGES = ['checkm-genome']
    DOCUMENTATION_URL = 'https://github.com/Ecogenomics/CheckM'
    VERSION = '1.2.5'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        step = inputs.get('step', 'lineage_wf')
        cmd = ['checkm', step]
        if step == 'lineage_wf':
            cmd.extend(['-x', str(inputs.get('extension', 'fa')), '-t', str(inputs.get('threads', 8))])
            if inputs.get('pplacer_threads'):
                cmd.extend(['--pplacer_threads', str(inputs['pplacer_threads'])])
            if inputs.get('reduced_tree'):
                cmd.append('--reduced_tree')
            cmd.extend([str(inputs.get('bins', '')), f"{inputs.get('output', '.')}/bins.out"])
        elif step == 'qa':
            cmd.extend(['-o', str(inputs.get('qa_output', '1')), '-f', f"{inputs.get('output', '.')}/qa_output.out"])
            cmd.extend([str(inputs.get('markers_file', '')), str(inputs.get('output', '.'))])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bins': ('BINS', {'description': 'Directory with MAG bins (.fa files)'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'}), 'step': (['lineage_wf', 'qa'], {'default': 'lineage_wf'})}, 'optional': {'extension': ('STRING', {'default': 'fa', 'label': 'File Extension'}), 'pplacer_threads': ('INT', {'default': 1, 'min': 1, 'max': 64, 'label': 'pplacer Threads', 'advanced': True}), 'reduced_tree': ('BOOLEAN', {'default': False, 'label': 'Reduced Tree', 'advanced': True}), 'markers_file': ('FILE', {'description': 'Marker file for qa step', 'label': 'Markers File', 'advanced': True}), 'qa_output': ('STRING', {'default': '1', 'label': 'QA Output Format', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
