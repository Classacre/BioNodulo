"""bam — samtools node(s). One tool per file (extracted from samtools.py)."""
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


class GalaxyBamToSamNode(CommandNode):
    """Galaxy wrapper parity node for BAM-to-SAM conversion."""
    NODE_ID = 'bam_to_sam'
    DISPLAY_NAME = 'BAM-to-SAM'
    REQUIRED_CONDA_PACKAGES = ['samtools']
    CATEGORY = 'samtools'
    DESCRIPTION = 'Convert a BAM dataset to SAM text using the Galaxy BAM-to-SAM wrapper.'
    SEARCH_ALIASES = [GALAXY_ALIAS, 'samtools', 'bam_to_sam', 'BAM-to-SAM', 'BAM to SAM', 'converted SAM', 'header only']
    RETURN_TYPES = ('SAM',)
    RETURN_NAMES = ('output1',)
    REQUIRED_EXECUTABLES = ['samtools']
    DOCUMENTATION_URL = 'https://github.com/galaxyproject/tools-iuc/tree/main/tool_collections/samtools/bam_to_sam'
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = '2.0.7'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = str(inputs.get('output', inputs.get('output_dir', '.')))
        header = str(inputs.get('header', '-h'))
        cmd = ['samtools', 'view', '-o', f'{output}/output1.sam']
        if header:
            cmd.append(header)
        cmd.append(str(inputs.get('input1', '')))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'output1.sam']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if str(inputs.get('header', '-h')) not in {'-h', '-H', ''}:
            return 'header must be one of -h, -H, or an empty string'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input1': ('BAM', {'description': 'BAM file to convert to SAM'})}, 'optional': {'header': ('STRING', {'default': '-h', 'options': ['-h', '-H', ''], 'description': 'Include the full SAM output with header, return only the header, or omit the header'})}, 'hidden': {'output': ('STRING', {})}}
