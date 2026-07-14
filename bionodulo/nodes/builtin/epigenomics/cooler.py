"""cooler — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
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


class CoolerNode(CommandNode):
    """Create and process Hi-C contact matrices with cooler."""
    NODE_ID = 'cooler'
    DISPLAY_NAME = 'Cooler Matrix'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Create, zoomify, and balance Hi-C contact matrices in cooler format.'
    SEARCH_ALIASES = ['cooler', 'hic', 'contact matrix', 'cool', 'mcool', 'ice normalization']
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('mcool',)
    REQUIRED_EXECUTABLES = ['cooler']
    REQUIRED_CONDA_PACKAGES = ['cooler', 'cooltools']
    DOCUMENTATION_URL = 'https://cooler.readthedocs.io/'
    VERSION = '0.10.2'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        mode = inputs.get('mode', 'cload')
        chrom_sizes = str(inputs.get('chrom_sizes', ''))
        bin_size = str(inputs.get('bin_size', 10000))
        input_data = str(inputs.get('input_data', ''))
        threads = str(inputs.get('threads', 4))
        out_cool = f'{out_dir}/matrix.cool'
        out_mcool = f'{out_dir}/mcool.mcool'
        if mode == 'cload':
            cmd = ['cooler', 'cload', 'pairs', f'{chrom_sizes}:{bin_size}', input_data, out_cool]
            cmd.extend(['&&', 'cooler', 'zoomify', '-p', threads, '-o', out_mcool, out_cool])
            cmd.extend(['&&', 'cooler', 'balance', '-p', threads, out_mcool])
            return cmd
        if mode == 'csort':
            return ['cooler', 'csort', '-k2,2n', '-k4,4n', '-c1', '-c3', '-p', threads, chrom_sizes, input_data, f'{out_dir}/sorted.pairs.gz']
        return ['cooler', 'balance', '--cis-only', '-p', threads, input_data]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'mcool.mcool']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_data': ('FILE', {'description': 'Input depending on mode'}), 'mode': ('STRING', {'default': 'cload', 'options': ['cload', 'csort', 'balance']})}, 'optional': {'chrom_sizes': ('FILE', {'description': 'Chrom sizes (for cload/csort)'}), 'bin_size': ('INT', {'default': 10000, 'min': 100}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64})}, 'hidden': {'output': ('STRING', {})}}
