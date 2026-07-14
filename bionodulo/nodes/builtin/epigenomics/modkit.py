"""modkit — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
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


class ModkitDMRNode(CommandNode):
    """Detect differentially methylated regions from modkit bedMethyl pileups."""
    NODE_ID = 'modkit_dmr'
    DISPLAY_NAME = 'Modkit DMR'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Detect differentially methylated regions between two modkit bedMethyl pileups.'
    SEARCH_ALIASES = ['modkit', 'dmr', 'dmr pair', 'differential methylation', 'methylation', 'bedmethyl']
    RETURN_TYPES = ('BED', 'FILE')
    RETURN_NAMES = ('dmr', 'log')
    REQUIRED_EXECUTABLES = ['modkit']
    REQUIRED_CONDA_PACKAGES = ['modkit']
    DOCUMENTATION_URL = 'https://nanoporetech.github.io/modkit/dmr.html'
    VERSION = '0.4.3'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'sample_a': ('BED', {'description': 'First bgzipped modkit bedMethyl pileup'}), 'sample_b': ('BED', {'description': 'Second bgzipped modkit bedMethyl pileup'}), 'reference': ('FASTA', {'description': 'Reference FASTA used for the pileups'}), 'base': ('STRING', {'default': 'C', 'description': 'Canonical base(s), comma- or space-separated'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 128})}, 'optional': {'index_a': ('FILE', {'description': 'Tabix index for sample_a'}), 'index_b': ('FILE', {'description': 'Tabix index for sample_b'}), 'regions': ('BED', {'description': 'Regions to test; omit for single-base analysis'}), 'segment': ('BED', {'description': 'Segments for region-free DMR segmentation'}), 'fine_grained': ('BOOLEAN', {'default': False, 'description': 'Report fine-grained DMR scores'}), 'output_prefix': ('STRING', {'default': 'modkit_dmr', 'description': 'Output filename stem'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        for field in ('sample_a', 'sample_b', 'reference'):
            if not str(inputs.get(field, '')).strip():
                return f'{field} is required'
        if not _split_base_list(inputs.get('base')):
            return 'At least one base is required'
        threads = inputs.get('threads', 1)
        if threads < 1:
            return 'threads must be at least 1'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_bed, output_log = cls._output_paths(inputs, inputs.get('output', '.'))
        cmd = ['modkit', 'dmr', 'pair', '-a', str(inputs.get('sample_a', ''))]
        if inputs.get('index_a'):
            cmd.extend(['--index-a', str(inputs['index_a'])])
        cmd.extend(['-b', str(inputs.get('sample_b', ''))])
        if inputs.get('index_b'):
            cmd.extend(['--index-b', str(inputs['index_b'])])
        cmd.extend(['-o', str(output_bed), '--ref', str(inputs.get('reference', ''))])
        for base in _split_base_list(inputs.get('base')):
            cmd.extend(['--base', base])
        cmd.extend(['--threads', str(inputs.get('threads', 4)), '--log-filepath', str(output_log)])
        if inputs.get('regions'):
            cmd.extend(['-r', str(inputs['regions'])])
        if inputs.get('segment'):
            cmd.extend(['--segment', str(inputs['segment'])])
        if inputs.get('fine_grained'):
            cmd.append('--fine-grained')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._output_paths(inputs, node_out))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        stem = _safe_output_stem(inputs.get('output_prefix'), 'modkit_dmr')
        out_dir = Path(output_dir)
        return (out_dir / f'{stem}.dmr.bed', out_dir / f'{stem}.dmr.log')
