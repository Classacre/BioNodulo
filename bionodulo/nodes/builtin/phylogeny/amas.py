"""amas — phylogeny node(s). One tool per file (extracted from wrapped_phylogeny_assembly.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *


class AMASSummaryNode(CommandNode):
    """Summarize sequence alignments with AMAS summary."""
    NODE_ID = 'amas_summary'
    DISPLAY_NAME = 'AMAS Summary'
    REQUIRED_CONDA_PACKAGES = ['amas']
    CATEGORY = 'phylogeny'
    DESCRIPTION = 'Calculate alignment summary statistics and optional per-taxon summaries with AMAS.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AMAS', 'amas summary', 'alignment summary', 'alignment manipulation', 'phylogenomics', 'missing data', 'parsimony informative sites']
    RETURN_TYPES = ('TEXT', 'DIRECTORY')
    RETURN_NAMES = ('summary_out', 'taxon_summaries')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://github.com/marekborowiec/AMAS'
    CITATION_DOIS = [AMAS_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{AMAS_CITATION_DOI}']
    CITATION_TEXT = AMAS_CITATION_TEXT
    VERSION = '1.0'
    SHELL = True

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get('input_format', '') or '')
        if input_format == 'nex':
            return 'nexus'
        if input_format in {'fasta', 'phylip', 'phylip-int', 'nexus', 'nexus-int'}:
            return input_format
        input_files = _as_list(inputs.get('input_files'))
        suffix = Path(input_files[0]).suffix.lower() if input_files else ''
        return {'.nex': 'nexus', '.nexus': 'nexus', '.phy': 'phylip', '.phylip': 'phylip'}.get(suffix, 'fasta')

    @classmethod
    def _tool_directory(cls, inputs: dict[str, Any]) -> str:
        tool_directory = inputs.get('tool_directory')
        if tool_directory:
            return shlex.quote(str(tool_directory))
        return '"${BIONODULO_AMAS_TOOL_DIR:-.}"'

    @classmethod
    def _input_labels(cls, inputs: dict[str, Any]) -> list[str]:
        files = _as_list(inputs.get('input_files'))
        labels = _as_list(inputs.get('input_labels'))
        if not labels:
            labels = _as_list(inputs.get('element_identifiers'))
        if not labels:
            labels = [Path(path).name for path in files]
        if len(labels) < len(files):
            labels.extend((Path(path).name for path in files[len(labels):]))
        return labels

    @classmethod
    def _safe_input_names(cls, inputs: dict[str, Any]) -> list[str]:
        return [_safe_identifier(label) for label in cls._input_labels(inputs)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files = _as_list(inputs.get('input_files'))
        safe_names = cls._safe_input_names(inputs)
        input_format = cls._input_format(inputs)
        tool_directory = cls._tool_directory(inputs)
        parts = ['set -eu', f"IN_FORMAT=$(python {tool_directory}/check_interleaved.py {' '.join((shlex.quote(path) for path in files))} --format {shlex.quote(input_format)})"]
        parts.extend((f'ln -sf {shlex.quote(path)} {shlex.quote(safe_name)}' for path, safe_name in zip(files, safe_names, strict=False)))
        amas_parts = ['python', '-m', 'amas.AMAS', 'summary']
        if inputs.get('by_taxon'):
            amas_parts.append('--by-taxon')
        amas_parts.append('--in-files')
        amas_parts.extend(safe_names)
        amas_parts.extend(['--in-format', '${IN_FORMAT}', '--data-type', str(inputs.get('data_type', 'dna')), '--cores', '${GALAXY_SLOTS:-1}'])
        if inputs.get('check_align'):
            amas_parts.append('--check-align')
        command = ' '.join((shlex.quote(part) for part in amas_parts))
        command = command.replace("'${IN_FORMAT}'", '"${IN_FORMAT}"')
        command = command.replace("'${GALAXY_SLOTS:-1}'", '"${GALAXY_SLOTS:-1}"')
        parts.append(command)
        if inputs.get('by_taxon'):
            taxon_dir = f'{_out(inputs)}/taxon_summaries'
            parts.extend([f'mkdir -p {shlex.quote(taxon_dir)}', f"find . -maxdepth 1 -name '*-seq-summary.txt' -exec mv {{}} {shlex.quote(taxon_dir)}/ \\;"])
        return ' && '.join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'summary.txt']
        if inputs.get('by_taxon'):
            taxon_dir = out / 'taxon_summaries'
            taxon_dir.mkdir(parents=True, exist_ok=True)
            outputs.append(taxon_dir)
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_files': ('ALIGNMENT', {'list': True, 'description': 'One or more pre-aligned FASTA, PHYLIP, or NEXUS alignment files'}), 'data_type': ('STRING', {'default': 'dna', 'options': ['dna', 'aa'], 'description': 'Nucleotide or protein alignment'})}, 'optional': {'input_format': ('STRING', {'default': 'fasta', 'options': ['fasta', 'phylip', 'phylip-int', 'nexus', 'nexus-int', 'nex'], 'description': 'Input alignment format; NEXUS can be supplied as nex or nexus'}), 'by_taxon': ('BOOLEAN', {'default': False, 'description': 'Also emit per-taxon summaries for each input alignment'}), 'check_align': ('BOOLEAN', {'default': False, 'description': 'Check that input sequences are aligned before summarising'}), 'input_labels': ('STRING', {'default': '', 'list': True, 'description': 'Optional Galaxy element identifiers used for safe symlink names', 'advanced': True})}, 'hidden': {'output': ('STRING', {}), 'tool_directory': ('STRING', {})}}
