"""abricate — annotation node(s). One tool per file (extracted from wrapped_assembly_typing.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class ABRicateNode(CommandNode):
    """Mass screen contigs for antimicrobial resistance and virulence genes with ABRicate."""
    NODE_ID = 'abricate'
    DISPLAY_NAME = 'ABRicate'
    REQUIRED_CONDA_PACKAGES = ['abricate']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Mass screen contigs for antimicrobial resistance and virulence genes with ABRicate.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ABRicate', 'abricate', 'antimicrobial resistance', 'AMR genes', 'virulence genes', 'ResFinder', 'CARD', 'PlasmidFinder', 'VFDB']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('report',)
    REQUIRED_EXECUTABLES = ['abricate']
    DOCUMENTATION_URL = ABRICATE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ABRICATE_CITATION_URL]
    CITATION_TEXT = ABRICATE_CITATION_TEXT
    VERSION = '1.4.0'
    SHELL = True
    DATABASES = ['argannot', 'card', 'ecoh', 'ncbi', 'resfinder', 'plasmidfinder', 'vfdb', 'megares', 'ecoli_vf', 'upec_expec_vf']

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/report.tsv'

    @classmethod
    def _percent_range(cls, inputs: dict[str, Any], name: str, default: float) -> bool | str:
        try:
            value = float(inputs.get(name, default))
        except (TypeError, ValueError):
            return f'{name} must be a number'
        if value < 0 or value > 100:
            return f'{name} must be between 0 and 100'
        return True

    @classmethod
    def _format_number(cls, value: Any, default: float) -> str:
        parsed = float(value if value not in (None, '') else default)
        return str(int(parsed)) if parsed.is_integer() else str(parsed)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sample_name = _safe_element_identifier(str(inputs.get('file_input', '')))
        cmd = ['abricate', sample_name]
        if inputs.get('no_header'):
            cmd.append('--noheader')
        cmd.append(f"--minid={cls._format_number(inputs.get('min_dna_id'), 80)}")
        cmd.append(f"--mincov={cls._format_number(inputs.get('min_cov'), 80)}")
        cmd.append(f"--db={str(inputs.get('db', 'ncbi') or 'ncbi')}")
        return f"ln -sf {shlex.quote(str(inputs.get('file_input', '')))} {shlex.quote(sample_name)} && {_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'report.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('file_input', '')).strip():
            return 'file_input is required'
        db = str(inputs.get('db', 'ncbi') or 'ncbi')
        if db not in cls.DATABASES:
            return f"db must be one of: {', '.join(cls.DATABASES)}"
        for name in ['min_dna_id', 'min_cov']:
            result = cls._percent_range(inputs, name, 80)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'file_input': ('FILE', {'description': 'FASTA, GenBank, or EMBL contigs to screen for AMR and virulence genes'})}, 'optional': {'db': ('STRING', {'default': 'ncbi', 'options': cls.DATABASES, 'description': 'ABRicate AMR, plasmid, or virulence database to search'}), 'no_header': ('BOOLEAN', {'default': False, 'description': 'Suppress the ABRicate tabular header'}), 'min_dna_id': ('FLOAT', {'default': 80, 'min': 0, 'max': 100, 'description': 'Minimum nucleotide percent identity'}), 'min_cov': ('FLOAT', {'default': 80, 'min': 0, 'max': 100, 'description': 'Minimum gene percent coverage'})}, 'hidden': {'output': ('STRING', {})}}


class ABRicateListNode(CommandNode):
    """List ABRicate databases available in the local installation."""
    NODE_ID = 'abricate_list'
    DISPLAY_NAME = 'ABRicate List'
    REQUIRED_CONDA_PACKAGES = ['abricate']
    CATEGORY = 'annotation'
    DESCRIPTION = 'List ABRicate databases available in the local installation.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ABRicate', 'abricate', 'ABRicate databases', 'abricate --list', 'AMR database list', 'ResFinder database']
    RETURN_TYPES = ('TXT',)
    RETURN_NAMES = ('report',)
    REQUIRED_EXECUTABLES = ['abricate']
    DOCUMENTATION_URL = ABRICATE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ABRICATE_CITATION_URL]
    CITATION_TEXT = ABRICATE_CITATION_TEXT
    VERSION = '1.4.0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/databases.txt'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return f'abricate --list > {shlex.quote(cls._output_path(inputs))}'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'databases.txt']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {}, 'optional': {}, 'hidden': {'output': ('STRING', {})}}


class ABRicateSummaryNode(CommandNode):
    """Combine ABRicate reports into a gene presence and coverage matrix."""
    NODE_ID = 'abricate_summary'
    DISPLAY_NAME = 'ABRicate Summary'
    REQUIRED_CONDA_PACKAGES = ['abricate']
    CATEGORY = 'annotation'
    DESCRIPTION = 'Combine ABRicate reports into a gene presence and coverage matrix.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'ABRicate', 'abricate', 'ABRicate Summary', 'presence absence matrix', 'gene coverage matrix', 'abricate --summary', 'AMR report summary']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('summary',)
    REQUIRED_EXECUTABLES = ['abricate']
    DOCUMENTATION_URL = ABRICATE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [ABRICATE_CITATION_URL]
    CITATION_TEXT = ABRICATE_CITATION_TEXT
    VERSION = '1.4.0'
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/summary.tsv'

    @classmethod
    def _reports_dir(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/reports'

    @classmethod
    def _reports(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get('abricate_reports'))

    @classmethod
    def _labels(cls, inputs: dict[str, Any], reports: list[str]) -> list[str]:
        labels = _as_list(inputs.get('abricate_report_labels'))
        if len(labels) != len(reports):
            return [Path(report).name for report in reports]
        return labels

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        reports = cls._reports(inputs)
        labels = cls._labels(inputs, reports)
        reports_dir = cls._reports_dir(inputs)
        commands = [f'mkdir -p {shlex.quote(reports_dir)}']
        for report, label in zip(reports, labels):
            link_name = _safe_element_identifier(label)
            commands.append(f"ln -sf {shlex.quote(report)} {shlex.quote(f'{reports_dir}/{link_name}')}")
        commands.append(f"cd {shlex.quote(reports_dir)} && abricate --summary '*' > {shlex.quote(cls._output_path(inputs))}")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'summary.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        reports = cls._reports(inputs)
        if not reports:
            return 'at least one ABRicate report is required'
        labels = _as_list(inputs.get('abricate_report_labels'))
        if labels and len(labels) != len(reports):
            return 'abricate_report_labels must match the number of reports'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'abricate_reports': ('TSV_LIST', {'multiple': True, 'description': 'ABRicate tabular reports to combine with abricate --summary'})}, 'optional': {'abricate_report_labels': ('STRING_LIST', {'default': [], 'multiple': True, 'description': 'Optional sample labels matching the report order; defaults to input filenames'})}, 'hidden': {'output': ('STRING', {})}}
