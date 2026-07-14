"""bracken — metagenomics node(s). One tool per file (extracted from metagenomics.py)."""
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


class BrackenNode(CommandNode):
    """Abundance estimation with Bracken."""
    NODE_ID = 'bracken'
    DISPLAY_NAME = 'Bracken'
    REQUIRED_CONDA_PACKAGES = ['bracken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Re-estimate taxonomic abundance from a Kraken report with Bracken.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'Bracken', 'est_abundance.py', 'Kraken report', 'taxonomy abundance', 'Kraken-style Bracken report']
    RETURN_TYPES = ('TSV', 'TSV', 'TXT')
    RETURN_NAMES = ('report', 'kraken_report', 'logfile')
    REQUIRED_EXECUTABLES = ['est_abundance.py']
    DOCUMENTATION_URL = 'https://github.com/jenniferlu717/Bracken/releases'
    CITATION_DOIS = [BRACKEN_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{BRACKEN_CITATION_DOI}']
    CITATION_TEXT = BRACKEN_CITATION_TEXT
    VERSION = '3.1'
    SHELL = True

    @classmethod
    def _out(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('output', '.'))

    @classmethod
    def _report_path(cls, out: str) -> str:
        return f'{out}/report.tsv'

    @classmethod
    def _kraken_report_path(cls, out: str) -> str:
        return f'{out}/kraken_report.tsv'

    @classmethod
    def _log_path(cls, out: str) -> str:
        return f'{out}/bracken.log'

    @classmethod
    def _kmer_distribution(cls, inputs: dict[str, Any]) -> str:
        if inputs.get('kmer_distr'):
            return str(inputs['kmer_distr'])
        if inputs.get('db'):
            read_length = str(inputs.get('read_length', 100))
            return f"{inputs['db']}/database{read_length}mers.kmer_distrib"
        return ''

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = cls._out(inputs)
        cmd = ['set', '-o', 'pipefail', '&&', 'est_abundance.py', '-i', str(inputs.get('report', inputs.get('input', ''))), '-k', cls._kmer_distribution(inputs), '-l', str(inputs.get('level', 'S')), '-t', str(inputs.get('threshold', 10)), '-o', cls._report_path(out), '--out-report', 'bracken.report']
        if inputs.get('logfile_output'):
            cmd.extend(['|', 'tee', cls._log_path(out)])
        rendered = _shell_join(cmd)
        if inputs.get('out_report'):
            rendered += ' && ' + _shell_join(['mv', 'bracken.report', cls._kraken_report_path(out)])
        return rendered

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'report.tsv']
        if inputs.get('out_report'):
            outputs.append(out / 'kraken_report.tsv')
        if inputs.get('logfile_output'):
            outputs.append(out / 'bracken.log')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get('report') and (not inputs.get('input')):
            return 'report is required'
        if not inputs.get('kmer_distr') and (not inputs.get('db')):
            return 'kmer_distr is required unless db is provided for legacy Kraken database compatibility'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'report': ('TSV', {'description': 'Kraken report file'})}, 'optional': {'kmer_distr': ('FILE', {'default': '', 'description': "Bracken k-mer distribution file (required unless 'db' is provided, from which it is derived)"}), 'db': ('DIRECTORY', {'default': '', 'description': 'Legacy Kraken database directory used to derive database{read_length}mers.kmer_distrib'}), 'read_length': ('STRING', {'default': '100', 'description': 'Legacy read length used with db'}), 'level': ('STRING', {'default': 'S', 'options': ['S2', 'S1', 'S', 'G', 'F', 'O', 'C', 'P', 'D'], 'description': 'Taxonomic level'}), 'threshold': ('INT', {'default': 10, 'description': 'Minimum Kraken-assigned reads required before final abundance estimation'}), 'out_report': ('BOOLEAN', {'default': False, 'description': 'Produce Kraken-style Bracken report'}), 'logfile_output': ('BOOLEAN', {'default': False, 'description': 'Add log file output'})}, 'hidden': {'output': ('STRING', {})}}
