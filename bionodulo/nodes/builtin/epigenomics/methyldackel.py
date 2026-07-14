"""methyldackel — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
DSS_DMR_SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'dss_dmr.R'
def _safe_output_stem(value: Any, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default
def _split_path_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace('\n', ',').split(',') if part.strip()]
def _split_window_sizes(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).replace(',', ' ').split() if part.strip()]
def _split_base_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple)) else [value]
    bases: list[str] = []
    for item in values:
        bases.extend((part.strip() for part in str(item).replace(',', ' ').split() if part.strip()))
    return bases


class MethylDackelNode(CommandNode):
    """Extract per-base methylation from alignments with MethylDackel."""
    NODE_ID = 'methyldackel'
    DISPLAY_NAME = 'MethylDackel'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Extract per-base methylation from alignments. Handles directional and non-directional protocols.'
    SEARCH_ALIASES = ['methyldackel', 'pileometh', 'methylation', 'bisulfite', 'cpg', 'extract']
    RETURN_TYPES = ('BED', 'BED')
    RETURN_NAMES = ('methylation_bedgraph', 'mbias_report')
    REQUIRED_EXECUTABLES = ['MethylDackel']
    REQUIRED_CONDA_PACKAGES = ['methyldackel']
    DOCUMENTATION_URL = 'https://github.com/dpryan79/MethylDackel'
    VERSION = '0.6.1'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        prefix = str(inputs.get('output_prefix', 'methyldackel'))
        output_prefix = f'{out_dir}/{prefix}'
        reference = str(inputs.get('reference', ''))
        bam = str(inputs.get('bam', ''))
        cmd = ['MethylDackel', 'mbias', reference, bam, output_prefix, '&&', 'MethylDackel', 'extract', reference, bam, '-o', output_prefix, '--bedGraph']
        if inputs.get('merge_context'):
            cmd.append('--mergeContext')
        if inputs.get('min_depth'):
            cmd.extend(['--minDepth', str(inputs['min_depth'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Sorted, indexed BAM from bisulfite aligner'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'output_prefix': ('STRING', {'default': 'methyldackel'})}, 'optional': {'merge_context': ('BOOLEAN', {'default': True, 'description': 'Merge strands into CpG'}), 'min_depth': ('INT', {'default': 1, 'min': 1, 'label': 'Min Coverage'})}, 'hidden': {'output': ('STRING', {})}}
