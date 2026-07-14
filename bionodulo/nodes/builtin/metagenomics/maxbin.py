"""maxbin — metagenomics node(s). One tool per file (extracted from metagenomics.py)."""
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


class MaxBinNode(CommandNode):
    """Metagenomic binning with MaxBin."""
    NODE_ID = 'maxbin'
    DISPLAY_NAME = 'MaxBin2'
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Unsupervised metagenomic binning using expectation maximization'
    SEARCH_ALIASES = ['maxbin', 'binning', 'metagenome', 'mags']
    RETURN_TYPES = ('BINS',)
    RETURN_NAMES = ('bins',)
    REQUIRED_EXECUTABLES = ['run_MaxBin.pl']
    REQUIRED_CONDA_PACKAGES = ['maxbin2']
    DOCUMENTATION_URL = 'https://sourceforge.net/projects/maxbin/'
    VERSION = '2.2.7'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['run_MaxBin.pl', '-contig', str(inputs.get('contigs', '')), '-out', f"{inputs.get('output', '.')}/bins.out", '-reads', str(inputs.get('reads', '')), '-thread', str(inputs.get('threads', 8))]
        if inputs.get('abund'):
            cmd.extend(['-abund', str(inputs['abund'])])
        if inputs.get('min_prob') is not None:
            cmd.extend(['-min_prob', str(inputs['min_prob'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'contigs': ('CONTIGS', {'description': 'Metagenomic contigs FASTA'}), 'reads': ('FASTQ', {'description': 'Metagenomic reads FASTQ'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'abund': ('FILE', {'description': 'Optional abundance file'}), 'min_prob': ('FLOAT', {'default': 0.5, 'min': 0.0, 'max': 1.0})}, 'hidden': {'output': ('STRING', {})}}
