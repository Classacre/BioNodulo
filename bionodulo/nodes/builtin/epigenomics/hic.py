"""hic — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
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


class HICProNode(CommandNode):
    """Run the HiC-Pro pipeline for Hi-C read processing."""
    NODE_ID = 'hic_pro'
    DISPLAY_NAME = 'HiC-Pro Pipeline'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Complete Hi-C processing: alignment, valid pairs, dedup, contact matrices, ICE normalization.'
    SEARCH_ALIASES = ['hic-pro', 'hic', '3d genome', 'chromatin contacts', 'contact matrix']
    RETURN_TYPES = ('DIRECTORY',)
    RETURN_NAMES = ('hic_results',)
    REQUIRED_EXECUTABLES = ['HiC-Pro']
    REQUIRED_CONDA_PACKAGES = ['hic-pro']
    DOCUMENTATION_URL = 'https://github.com/nservant/HiC-Pro'
    VERSION = '3.1.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get('output', '.'))
        out_dir.mkdir(parents=True, exist_ok=True)
        config_file = out_dir / 'hicpro_config.txt'
        config_file.write_text('\n'.join([f"N_CPU = {inputs.get('threads', 8)}", f"REFERENCE_GENOME = {inputs.get('genome_fasta', '')}", f"GENOME_SIZE = {inputs.get('chrom_sizes', '')}", f"BOWTIE2_IDX_PATH = {inputs.get('bowtie2_index_dir', '')}", 'PAIR1_EXT = _R1', 'PAIR2_EXT = _R2', f"MIN_MAPQ = {inputs.get('min_mapq', 10)}", f"BIN_SIZE = {inputs.get('bin_sizes', '5000 10000 20000 40000 100000 1000000')}", f"MAX_ITER = {inputs.get('max_iter', 100)}"]) + '\n')
        return ['HiC-Pro', '-i', str(inputs.get('input_dir', '')), '-o', str(out_dir), '-c', str(config_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'hic_results']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_dir': ('DIRECTORY', {'description': 'FASTQ directory (_R1/_R2 naming)'}), 'genome_fasta': ('FASTA', {'description': 'Reference FASTA'}), 'bowtie2_index_dir': ('DIRECTORY', {'description': 'Bowtie2 index directory'}), 'chrom_sizes': ('FILE', {'description': 'Chromosome sizes file'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 64})}, 'optional': {'min_mapq': ('INT', {'default': 10, 'min': 0}), 'bin_sizes': ('STRING', {'default': '5000 10000 20000 40000 100000 1000000'}), 'max_iter': ('INT', {'default': 100, 'min': 1, 'label': 'ICE Max Iter'})}, 'hidden': {'output': ('STRING', {})}}
