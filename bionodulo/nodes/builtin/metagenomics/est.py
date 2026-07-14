"""est — metagenomics node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class BrackenEstAbundanceNode(CommandNode):
    """Re-estimate taxonomic abundance from a Kraken report with Bracken."""
    NODE_ID = 'est_abundance'
    DISPLAY_NAME = 'Bracken'
    REQUIRED_CONDA_PACKAGES = ['bracken']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Re-estimate taxonomic abundance from a Kraken report with Bracken.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Bracken', 'est_abundance', 'est_abundance.py', 'Kraken report', 'taxonomy abundance', 'Kraken-style Bracken report', 'Bayesian abundance']
    RETURN_TYPES = ('TSV', 'TSV', 'TXT')
    RETURN_NAMES = ('report', 'kraken_report', 'logfile')
    REQUIRED_EXECUTABLES = ['est_abundance.py']
    DOCUMENTATION_URL = 'https://github.com/jenniferlu717/Bracken'
    CITATION_DOIS = [BRACKEN_DOI]
    CITATION_URLS = [f'{DOI_URL}{BRACKEN_DOI}']
    CITATION_TEXT = BRACKEN_CITATION_TEXT
    VERSION = '3.1+galaxy0'
    SHELL = True
    LEVELS = ['S2', 'S1', 'S', 'G', 'F', 'O', 'C', 'P', 'D']

    @classmethod
    def _level(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('level', 'S') or 'S')

    @classmethod
    def _threshold(cls, inputs: dict[str, Any]) -> int:
        value = inputs.get('threshold', 10)
        if value is None or value == '':
            value = 10
        return int(value)

    @classmethod
    def _report_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/report.tsv'

    @classmethod
    def _kraken_report_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/kraken_report.tsv'

    @classmethod
    def _logfile_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/logfile.txt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ['set', '-o', 'pipefail', '&&', 'est_abundance.py', '-i', str(inputs.get('input', '')), '-k', str(inputs.get('kmer_distr', '')), '-l', cls._level(inputs), '-t', str(cls._threshold(inputs)), '-o', cls._report_path(inputs), '--out-report', 'bracken.report']
        if inputs.get('logfile_output', False):
            cmd.extend(['|', 'tee', cls._logfile_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'report.tsv']
        if inputs.get('out_report', False):
            outputs.append(out / 'kraken_report.tsv')
        if inputs.get('logfile_output', False):
            outputs.append(out / 'logfile.txt')
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        if not str(inputs.get('kmer_distr', '')).strip():
            return 'kmer_distr is required'
        level = cls._level(inputs)
        if level not in cls.LEVELS:
            return f"level must be one of: {', '.join(cls.LEVELS)}"
        try:
            threshold = cls._threshold(inputs)
        except (TypeError, ValueError):
            return 'threshold must be an integer'
        if threshold < 0:
            return 'threshold must be >= 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('TSV', {'description': 'Kraken report file'}), 'kmer_distr': ('FILE', {'description': 'Bracken k-mer distribution file matching the Kraken database and read length'})}, 'optional': {'level': ('STRING', {'default': 'S', 'options': cls.LEVELS, 'description': 'Taxonomic level to estimate abundance at'}), 'threshold': ('INT', {'default': 10, 'min': 0, 'description': 'Minimum Kraken-assigned read count for taxa considered in abundance estimation'}), 'out_report': ('BOOLEAN', {'default': False, 'description': 'Plan the optional Kraken-style Bracken report output'}), 'logfile_output': ('BOOLEAN', {'default': False, 'description': 'Capture Bracken stdout and stderr into a log file'})}, 'hidden': {'output': ('STRING', {})}}
