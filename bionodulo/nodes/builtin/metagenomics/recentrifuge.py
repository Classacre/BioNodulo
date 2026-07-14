"""recentrifuge — metagenomics node(s). One tool per file (extracted from wrapped_taxonomy_humann.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class RecentrifugeNode(CommandNode):
    """Run Recentrifuge comparative metagenomics analysis."""
    NODE_ID = 'recentrifuge'
    DISPLAY_NAME = 'Recentrifuge'
    REQUIRED_CONDA_PACKAGES = ['recentrifuge']
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Robust comparative analysis and contamination removal for metagenomics.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Recentrifuge', 'robust contamination removal', 'comparative analysis', 'metagenomics', 'Centrifuge', 'Kraken', 'CLARK', 'LMAT', 'generic classifier']
    RETURN_TYPES = ('HTML_REPORT', 'TEXT', 'TSV', 'TSV', 'FILE')
    RETURN_NAMES = ('html_report', 'logfile', 'data_table', 'stat_table', 'xlsx_report')
    REQUIRED_EXECUTABLES = ['rcf']
    DOCUMENTATION_URL = 'https://github.com/khyox/recentrifuge'
    CITATION_DOIS = ['10.1371/journal.pcbi.1006967']
    CITATION_URLS = [f'{DOI_URL}10.1371/journal.pcbi.1006967']
    CITATION_TEXT = 'Recentrifuge: Robust comparative analysis and contamination removal for metagenomics.'
    VERSION = '1.16.1'
    SHELL = True
    _FILETYPE_FLAGS = {'centrifuge': ('-f', '.out', 'SHEL'), 'clark': ('-r', '.csv', 'SHEL'), 'generic': ('-g', '', 'GENERIC'), 'lmat': ('-l', '', 'LMAT'), 'kraken': ('-k', '.krk', 'KRAKEN')}

    @classmethod
    def _input_identifier(cls, value: str) -> str:
        return sub('[^\\s\\w\\-]', '_', value)

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], input_files: list[str]) -> list[str]:
        filetype = str(inputs.get('filetype', 'centrifuge'))
        _flag, extension, _scoring = cls._FILETYPE_FLAGS.get(filetype, cls._FILETYPE_FLAGS['centrifuge'])
        labels = _as_list(inputs.get('element_identifiers'))
        names: list[str] = []
        for index, input_file in enumerate(input_files):
            label = labels[index] if index < len(labels) and labels[index] else Path(input_file).name
            names.append(f'{cls._input_identifier(label)}{extension}')
        return names

    @classmethod
    def _log_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/logfile.txt'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_files = _as_list(inputs.get('input_file'))
        if not input_files:
            return 'At least one taxonomy input file is required'
        if not str(inputs.get('database_name', '')).strip():
            return 'NCBI taxonomy database is required'
        filetype = str(inputs.get('filetype', ''))
        if filetype == 'generic' and (not str(inputs.get('format', '')).strip()):
            return 'Generic input mode requires a format string'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        filetype = str(inputs.get('filetype', 'centrifuge'))
        input_flag, _extension, default_scoring = cls._FILETYPE_FLAGS.get(filetype, cls._FILETYPE_FLAGS['centrifuge'])
        input_files = _as_list(inputs.get('input_file'))
        input_names = cls._input_names(inputs, input_files)
        commands = ['mkdir -p input_dir']
        commands.extend((_shell_join(['ln', '-s', input_file, f'input_dir/{input_name}']) for input_file, input_name in zip(input_files, input_names, strict=False)))
        cmd = ['rcf', '-n', str(inputs.get('database_name', '')), input_flag, 'input_dir']
        if filetype == 'generic':
            cmd.extend(['--format', str(inputs.get('format', ''))])
        cmd.extend(['-e', str(inputs.get('extra', 'CSV')), '-o', 'output'])
        if inputs.get('nohtml', False):
            cmd.append('--nohtml')
        _add_if_value(cmd, '--controls', inputs.get('controls'))
        cmd.extend(['--scoring', str(inputs.get('scoring') or default_scoring)])
        _add_if_value(cmd, '--minscore', inputs.get('minscore_value'))
        _add_if_value(cmd, '--mintaxa', inputs.get('mintaxa'))
        _add_if_value(cmd, '--exclude', inputs.get('exclude_taxa_name'))
        _add_if_value(cmd, '--include', inputs.get('include_taxa_name'))
        if inputs.get('avoidcross', False):
            cmd.append('--avoidcross')
        _add_if_value(cmd, '--ctrlminscore', inputs.get('ctrlminscore'))
        _add_if_value(cmd, '--ctrlmintaxa', inputs.get('ctrlmintaxa'))
        cmd.extend(['--summary', str(inputs.get('summary', 'ADD'))])
        if inputs.get('takeoutroot', False):
            cmd.append('--takeoutroot')
        if inputs.get('nokollapse', False):
            cmd.append('--nokollapse')
        if inputs.get('strain', False):
            cmd.append('--strain')
        if inputs.get('sequential', False):
            cmd.append('--sequential')
        if inputs.get('no_logfile', False):
            _add_shell_redirect(cmd, cls._log_path(inputs))
        else:
            cmd.extend(['|', 'tee', cls._log_path(inputs)])
        commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs: list[Path] = []
        if not inputs.get('nohtml', False):
            outputs.append(out / 'output.rcf.html')
        if not inputs.get('no_logfile', False):
            outputs.append(out / 'logfile.txt')
        extra = str(inputs.get('extra', 'CSV'))
        if extra == 'TSV':
            outputs.extend([out / 'output.rcf.data.tsv', out / 'output.rcf.stat.tsv'])
        elif extra in {'FULL', 'DYNOMICS'}:
            outputs.append(out / 'output.rcf.xlsx')
        else:
            outputs.extend([out / 'output.rcf.data.csv', out / 'output.rcf.stat.csv'])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        filetypes = ['centrifuge', 'clark', 'generic', 'lmat', 'kraken']
        scoring_options = ['', 'SHEL', 'LENGTH', 'LOGLENGTH', 'NORMA', 'LMAT', 'CLARK_C', 'CLARK_G', 'KRAKEN', 'GENERIC']
        return {'required': {'input_file': ('TSV', {'multiple': True, 'description': 'One or more tabular classifier outputs for Recentrifuge'}), 'filetype': ('STRING', {'default': 'centrifuge', 'options': filetypes, 'description': 'Input classifier output type: Centrifuge, CLARK, Generic, LMAT, or Kraken'}), 'database_name': ('DIRECTORY', {'description': 'NCBI taxonomy database directory containing nodes.dmp and names.dmp'})}, 'optional': {'element_identifiers': ('STRING', {'default': [], 'multiple': True, 'description': 'Optional sample labels used for linked Recentrifuge input filenames'}), 'format': ('STRING', {'default': '', 'description': 'Generic classifier format string such as TYP:csv,TID:1,LEN:3,SCO:6,UNC:0', 'displayOptions': {'show': {'filetype': ['generic']}}}), 'extra': ('STRING', {'default': 'CSV', 'options': ['CSV', 'DYNOMICS', 'FULL', 'TSV'], 'description': 'Additional Recentrifuge output format'}), 'nohtml': ('BOOLEAN', {'default': False, 'description': 'Suppress the HTML report output'}), 'no_logfile': ('BOOLEAN', {'default': False, 'description': 'Suppress the Galaxy logfile output'}), 'controls': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'scoring': ('STRING', {'default': '', 'options': scoring_options, 'description': 'Override Recentrifuge scoring; blank uses the wrapper default for the input type'}), 'minscore_value': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'mintaxa': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'exclude_taxa_name': ('STRING', {'default': '', 'description': 'Comma-separated NCBI tax IDs to exclude', 'advanced': True}), 'include_taxa_name': ('STRING', {'default': '', 'description': 'Comma-separated NCBI tax IDs to include', 'advanced': True}), 'avoidcross': ('BOOLEAN', {'default': False, 'description': 'Avoid cross analysis', 'advanced': True}), 'ctrlminscore': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'ctrlmintaxa': ('INT', {'default': 0, 'min': 0, 'advanced': True}), 'summary': ('STRING', {'default': 'ADD', 'options': ['ADD', 'ONLY', 'AVOID'], 'description': 'Add, only show, or avoid summary samples'}), 'takeoutroot': ('BOOLEAN', {'default': False, 'description': 'Remove counts directly assigned to root', 'advanced': True}), 'nokollapse': ('BOOLEAN', {'default': False, 'description': 'Show the cellular organisms taxon', 'advanced': True}), 'strain': ('BOOLEAN', {'default': False, 'description': 'Use strain-level resolution', 'advanced': True}), 'sequential': ('BOOLEAN', {'default': False, 'description': 'Deactivate parallel processing', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
