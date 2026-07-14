"""dss — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
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


class DSSDMRNode(CommandNode):
    """Detect differentially methylated regions with Bioconductor DSS."""
    NODE_ID = 'dss_dmr'
    DISPLAY_NAME = 'DSS DMR'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Detect differentially methylated regions from bisulfite methylation count tables using DSS.'
    SEARCH_ALIASES = ['DSS', 'DMR', 'differential methylation', 'bisulfite', 'methylation', 'epigenomics']
    RETURN_TYPES = ('BED', 'FILE')
    RETURN_NAMES = ('dmr', 'dmr_stats')
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-dss', 'r-readr']
    DOCUMENTATION_URL = 'https://bioconductor.org/packages/DSS/'
    VERSION = '2.48.0'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'methylation_files': ('STRING', {'description': 'Comma- or newline-separated DSS methylation count tables'}), 'sample_info': ('FILE', {'description': 'Sample metadata table'}), 'condition_column': ('STRING', {'default': 'condition', 'description': 'Column in sample_info containing conditions'}), 'sample_column': ('STRING', {'default': 'sample', 'description': 'Column in sample_info containing sample IDs'})}, 'optional': {'smoothing': ('BOOLEAN', {'default': True, 'description': 'Enable DSS smoothing'}), 'delta': ('FLOAT', {'default': 0.1, 'min': 0.0, 'max': 1.0, 'description': 'Minimum methylation difference'}), 'pvalue': ('FLOAT', {'default': 0.001, 'min': 0.0, 'max': 1.0, 'description': 'DMR p-value threshold'}), 'minlen': ('INT', {'default': 50, 'min': 1, 'description': 'Minimum DMR length'}), 'mincg': ('INT', {'default': 3, 'min': 1, 'description': 'Minimum CpG count'}), 'output_prefix': ('STRING', {'default': 'dss_dmr', 'description': 'Output filename stem'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if len(_split_path_list(inputs.get('methylation_files'))) < 2:
            return 'At least two methylation files are required'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_bed, output_stats = cls._output_paths(inputs, inputs.get('output', '.'))
        cmd = ['Rscript', str(DSS_DMR_SCRIPT), '--methylation-files', ','.join(_split_path_list(inputs.get('methylation_files'))), '--sample-info', str(inputs.get('sample_info', '')), '--condition-column', str(inputs.get('condition_column', 'condition')), '--sample-column', str(inputs.get('sample_column', 'sample')), '--output-bed', str(output_bed), '--output-stats', str(output_stats), '--delta', str(inputs.get('delta', 0.1)), '--pvalue', str(inputs.get('pvalue', 0.001)), '--minlen', str(inputs.get('minlen', 50)), '--mincg', str(inputs.get('mincg', 3))]
        if inputs.get('smoothing', True):
            cmd.append('--smoothing')
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._output_paths(inputs, node_out))

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        stem = _safe_output_stem(inputs.get('output_prefix'), 'dss_dmr')
        out_dir = Path(output_dir)
        return (out_dir / f'{stem}.dmr.bed', out_dir / f'{stem}.dmr_stats.tsv')
