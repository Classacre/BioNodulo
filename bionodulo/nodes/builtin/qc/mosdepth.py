"""mosdepth — qc node(s). One tool per file (extracted from mosdepth.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
MOSDEPTH_CITATION_DOI = '10.1093/bioinformatics/btx699'
MOSDEPTH_CITATION_TEXT = 'Mosdepth: quick coverage calculation for genomes and exomes.'
def _out(inputs: dict[str, Any]) -> str:
    return str(inputs.get('output', inputs.get('output_dir', '.')))
def _has_value(value: Any) -> bool:
    return value is not None and str(value) != ''
def _add_if_value(cmd: list[str], flag: str, value: Any) -> None:
    if _has_value(value):
        cmd.extend([flag, str(value)])
def _as_bool(inputs: dict[str, Any], name: str, default: bool=False) -> bool:
    return bool(inputs.get(name, default))
def _window_mode(inputs: dict[str, Any]) -> str:
    mode = str(inputs.get('window_mode', 'no'))
    return mode if mode in {'no', 'window', 'bed'} else 'no'
def _split_labels(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).replace('\n', ',').split(',') if item.strip()]
def _quantize_from_repeat(inputs: dict[str, Any]) -> tuple[str, list[str]]:
    quantize = inputs.get('quantize')
    if not isinstance(quantize, (list, tuple)):
        return ('', [])
    depths: list[str] = []
    labels: list[str] = []
    for group in quantize:
        if not isinstance(group, dict):
            continue
        depth = group.get('quant_group_mindepth', group.get('min_depth'))
        if not _has_value(depth):
            continue
        depths.append(str(depth))
        label = group.get('quant_group_name', group.get('name'))
        if _has_value(label):
            labels.append(str(label))
    if not depths:
        return ('', labels)
    return (':'.join(depths) + ':', labels)
def _quantize_args(inputs: dict[str, Any]) -> tuple[str, list[str]]:
    depths, labels = _quantize_from_repeat(inputs)
    if not depths:
        depths = str(inputs.get('quantize_depths', '') or '')
        labels = _split_labels(inputs.get('quantize_labels'))
    if depths and (not depths.endswith(':')):
        depths = f'{depths}:'
    return (depths, labels)
def _has_thresholds(inputs: dict[str, Any]) -> bool:
    return _has_value(inputs.get('thresholds'))


class MosdepthNode(CommandNode):
    """Compute fast BAM/CRAM coverage depth summaries with mosdepth."""
    NODE_ID = 'mosdepth'
    DISPLAY_NAME = 'mosdepth'
    REQUIRED_CONDA_PACKAGES = ['mosdepth', 'gzip']
    CATEGORY = 'qc'
    DESCRIPTION = 'Calculate BAM or CRAM depth coverage summaries, per-base depth, region means, thresholds, and quantized coverage.'
    SEARCH_ALIASES = ['BioNodulo builtin', 'mosdepth', 'BAM CRAM depth', 'coverage depth', 'per-base coverage', 'genome coverage', 'exome coverage']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'BEDGRAPH', 'BED', 'BED', 'BED')
    RETURN_NAMES = ('global_distribution', 'summary', 'region_distribution', 'per_base_depth', 'regions_bed', 'quantized_bed', 'thresholds_bed')
    REQUIRED_EXECUTABLES = ['mosdepth', 'gunzip']
    DOCUMENTATION_URL = 'https://github.com/brentp/mosdepth'
    CITATION_DOIS = [MOSDEPTH_CITATION_DOI]
    CITATION_URLS = [f'https://doi.org/{MOSDEPTH_CITATION_DOI}']
    CITATION_TEXT = MOSDEPTH_CITATION_TEXT
    VERSION = '0.3.14'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out = _out(inputs)
        quantize_depths, quantize_labels = _quantize_args(inputs)
        cmd: list[str] = []
        for index, label in enumerate(quantize_labels):
            cmd.extend(['export', f'MOSDEPTH_Q{index}={label}', '&&'])
        cmd.extend(['mosdepth', '-t', str(inputs.get('threads', 1))])
        mode = _window_mode(inputs)
        if mode == 'window':
            cmd.extend(['--by', str(inputs.get('window_size', 400))])
        elif mode == 'bed':
            cmd.extend(['--by', str(inputs.get('region_file', ''))])
        if not _as_bool(inputs, 'per_base_coverage', False):
            cmd.append('--no-per-base')
        _add_if_value(cmd, '--chrom', inputs.get('chrom'))
        _add_if_value(cmd, '--flag', inputs.get('exclude_flag'))
        _add_if_value(cmd, '--include-flag', inputs.get('include_flag'))
        if inputs.get('mapq', 0) not in (None, '', 0):
            cmd.extend(['--mapq', str(inputs['mapq'])])
        if _as_bool(inputs, 'fast_mode', False) or inputs.get('no_fast') is False:
            cmd.append('--fast-mode')
        if _as_bool(inputs, 'fragment_mode', False):
            cmd.append('--fragment-mode')
        _add_if_value(cmd, '--thresholds', inputs.get('thresholds'))
        if _as_bool(inputs, 'use_median', False):
            cmd.append('--use-median')
        _add_if_value(cmd, '--read-groups', inputs.get('read_groups'))
        _add_if_value(cmd, '--quantize', quantize_depths)
        _add_if_value(cmd, '--min-frag-len', inputs.get('min_frag_len'))
        _add_if_value(cmd, '--max-frag-len', inputs.get('max_frag_len'))
        cmd.extend([f'{out}/output', str(inputs.get('input_alignment', ''))])
        if _as_bool(inputs, 'per_base_coverage', False):
            cmd.extend(['&&', 'gunzip', f'{out}/output.per-base.bed.gz'])
        if mode in {'bed', 'window'}:
            cmd.extend(['&&', 'gunzip', f'{out}/output.regions.bed.gz'])
        if _has_thresholds(inputs):
            cmd.extend(['&&', 'gunzip', f'{out}/output.thresholds.bed.gz'])
        if quantize_depths:
            cmd.extend(['&&', 'gunzip', f'{out}/output.quantized.bed.gz'])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / 'output.mosdepth.global.dist.txt', out / 'output.mosdepth.summary.txt']
        mode = _window_mode(inputs)
        if mode in {'bed', 'window'}:
            outputs.append(out / 'output.mosdepth.region.dist.txt')
        if _as_bool(inputs, 'per_base_coverage', False):
            outputs.append(out / 'output.per-base.bed')
        if mode in {'bed', 'window'}:
            outputs.append(out / 'output.regions.bed')
        quantize_depths, _ = _quantize_args(inputs)
        if quantize_depths:
            outputs.append(out / 'output.quantized.bed')
        if _has_thresholds(inputs):
            outputs.append(out / 'output.thresholds.bed')
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_alignment': ('BAM', {'description': 'Input BAM or CRAM mapped reads'})}, 'optional': {'threads': ('INT', {'default': 1, 'min': 1, 'max': 64, 'display': 'slider'}), 'per_base_coverage': ('BOOLEAN', {'default': False, 'description': 'Output per-base depth instead of summary-only mode'}), 'window_mode': ('STRING', {'default': 'no', 'options': ['no', 'window', 'bed'], 'description': 'Compute average depth by fixed window or BED regions'}), 'window_size': ('INT', {'default': 400, 'min': 2, 'description': 'Fixed window size for region depth'}), 'region_file': ('BED', {'default': '', 'description': 'BED regions for average depth', 'advanced': True}), 'chrom': ('STRING', {'default': '', 'description': 'Restrict depth calculations to one chromosome', 'advanced': True}), 'exclude_flag': ('INT', {'default': '', 'min': 0, 'description': 'Exclude reads with any of these SAM flag bits set', 'advanced': True}), 'include_flag': ('INT', {'default': '', 'min': 1, 'description': 'Only include reads with any of these SAM flag bits set', 'advanced': True}), 'mapq': ('INT', {'default': 0, 'min': 0, 'description': 'Minimum mapping quality', 'advanced': True}), 'fast_mode': ('BOOLEAN', {'default': False, 'description': 'Use mosdepth fast mode', 'advanced': True}), 'fragment_mode': ('BOOLEAN', {'default': False, 'description': 'Count coverage across full proper-pair fragments', 'advanced': True}), 'thresholds': ('STRING', {'default': '', 'description': 'Comma-separated depth thresholds for region output', 'advanced': True}), 'use_median': ('BOOLEAN', {'default': False, 'description': 'Use median region depth instead of mean', 'advanced': True}), 'read_groups': ('STRING', {'default': '', 'description': 'Comma-separated read group IDs to include', 'advanced': True}), 'quantize_depths': ('STRING', {'default': '', 'description': 'Colon-separated depth thresholds for quantized BED output', 'advanced': True}), 'quantize_labels': ('STRING', {'default': '', 'description': 'Comma-separated labels for quantized depth groups', 'advanced': True}), 'min_frag_len': ('INT', {'default': '', 'min': 0, 'description': 'Ignore reads with shorter insert sizes', 'advanced': True}), 'max_frag_len': ('INT', {'default': '', 'min': 0, 'description': 'Ignore reads with longer insert sizes', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
