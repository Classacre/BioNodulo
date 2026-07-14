"""sam — samtools node(s). One tool per file (extracted from samtools.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
GALAXY_ALIAS = 'BioNodulo builtin'
SAMTOOLS_CITATION_DOIS = ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btp352']
SAMTOOLS_CITATION_URLS = [f'https://doi.org/{doi}' for doi in SAMTOOLS_CITATION_DOIS]
SAMTOOLS_CITATION_TEXT = 'Twelve years of SAMtools and BCFtools; The Sequence Alignment/Map format and SAMtools.'
SAMTOOLS_GALAXY_CITATION_DOIS = ['10.1093/gigascience/giab008', '10.1093/bioinformatics/btr076']
SAMTOOLS_GALAXY_CITATION_URLS = [f'https://doi.org/{doi}' for doi in SAMTOOLS_GALAXY_CITATION_DOIS]
SAMTOOLS_GALAXY_CITATION_TEXT = 'Twelve years of SAMtools and BCFtools; Improving SNP discovery by Base Alignment Quality.'
def _safe_stem(value: str, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default
def _bam_output_stem(inputs: dict[str, Any], default: str) -> str:
    if inputs.get('output_name'):
        return _safe_stem(str(inputs['output_name']), default)
    bam = str(inputs.get('bam', '') or '')
    if not bam:
        return default
    stem = Path(bam).name
    for suffix in ('.bam', '.sam', '.cram'):
        if stem.lower().endswith(suffix):
            stem = stem[:-len(suffix)]
            break
    processing_suffixes = ('.markdup', '.dedup', '.sorted', '.coordinate', '.fixmate', '.name_collated', '.collated')
    changed = True
    while changed:
        changed = False
        for suffix in processing_suffixes:
            if stem.lower().endswith(suffix):
                stem = stem[:-len(suffix)]
                changed = True
                break
    return _safe_stem(stem, default)
def _as_list(value: Any) -> list[str]:
    if value is None or value == '':
        return []
    if isinstance(value, (list, tuple)):
        return [str(v) for v in value if str(v) != '']
    return [str(value)]
def _flag_sum(value: Any) -> int:
    total = 0
    for item in _as_list(value):
        for part in item.split(','):
            if part.strip():
                total += int(part.strip())
    return total
def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if value is not None and str(value) != '':
        cmd.extend([flag, str(value)])
def _additional_threads(inputs: dict[str, Any], default: int=1) -> int:
    return max(int(inputs.get('threads', default) or default) - 1, 0)
def _sort_memory(inputs: dict[str, Any], default_mb: int=768) -> str:
    memory_mb = int(inputs.get('memory_mb', default_mb) or default_mb)
    return f'{max(memory_mb * 75 // 100, 1)}M'


class GalaxySamToBamNode(CommandNode):
    """Galaxy wrapper parity node for SAM-to-BAM conversion."""
    NODE_ID = 'sam_to_bam'
    DISPLAY_NAME = 'SAM-to-BAM'
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = 'samtools'
    DESCRIPTION = 'Convert a SAM dataset into sorted BAM format using the Galaxy SAM-to-BAM wrapper.'
    SEARCH_ALIASES = [GALAXY_ALIAS, 'samtools', 'sam_to_bam', 'SAM-to-BAM', 'SAM to BAM', 'converted BAM', 'reference sequence']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('output1',)
    REQUIRED_EXECUTABLES = ['samtools']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tool_collections/samtools/sam_to_bam'
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = '2.1.5'
    SHELL = True
    REFERENCE_OPTIONS = ['history', 'cached']

    @classmethod
    def _reference_setup_and_index(cls, inputs: dict[str, Any]) -> tuple[list[str], str]:
        addref_select = str(inputs.get('addref_select', 'history') or 'history')
        if addref_select == 'cached':
            cached_ref_path = str(inputs.get('cached_ref_path', ''))
            return ([], f'{cached_ref_path}.fai')
        ref = str(inputs.get('ref', ''))
        return (['ln', '-s', ref, 'reference.fa', '&&', 'samtools', 'faidx', 'reference.fa', '&&'], 'reference.fa.fai')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', inputs.get('output_dir', '.')))
        setup, reference_index = cls._reference_setup_and_index(inputs)
        addthreads = str(_additional_threads(inputs))
        return [*setup, 'samtools', 'view', '-b', '-@', addthreads, '-t', reference_index, str(inputs.get('input', '')), '|', 'samtools', 'sort', '-O', 'bam', '-@', addthreads, '-m', _sort_memory(inputs), '-o', f'{output}/output1.bam', '-T', '${TMPDIR:-.}']

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'output1.bam']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        addref_select = str(inputs.get('addref_select', 'history') or 'history')
        if addref_select not in cls.REFERENCE_OPTIONS:
            return f"addref_select must be one of: {', '.join(cls.REFERENCE_OPTIONS)}"
        if addref_select == 'history' and (not str(inputs.get('ref', '') or '').strip()):
            return 'ref is required when addref_select is history'
        if addref_select == 'cached' and (not str(inputs.get('cached_ref_path', '') or '').strip()):
            return 'cached_ref_path is required when addref_select is cached'
        threads_value = inputs.get('threads', 1)
        if threads_value in (None, ''):
            threads_value = 1
        try:
            threads = int(threads_value)
        except (TypeError, ValueError):
            return 'threads must be an integer'
        if threads <= 0:
            return 'threads must be greater than 0'
        memory_value = inputs.get('memory_mb', 768)
        if memory_value in (None, ''):
            memory_value = 768
        try:
            memory_mb = int(memory_value)
        except (TypeError, ValueError):
            return 'memory_mb must be an integer'
        if memory_mb <= 0:
            return 'memory_mb must be greater than 0'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('SAM', {'description': 'SAM file to convert to BAM'}), 'addref_select': ('STRING', {'default': 'history', 'options': cls.REFERENCE_OPTIONS, 'description': 'Use a reference FASTA from history or a cached built-in reference'})}, 'optional': {'ref': ('FASTA', {'description': 'Reference FASTA used when addref_select is history'}), 'cached_ref_path': ('FILE', {'description': 'Path to cached reference FASTA used when addref_select is cached', 'advanced': True}), 'threads': ('INT', {'default': 1, 'min': 1, 'max': 64, 'display': 'slider'}), 'memory_mb': ('INT', {'default': 768, 'min': 1, 'description': 'Memory per sort thread in MB', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
