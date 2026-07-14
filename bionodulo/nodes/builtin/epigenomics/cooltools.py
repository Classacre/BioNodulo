"""cooltools — epigenomics node(s). One tool per file (extracted from epigenomics.py)."""
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


class CooltoolsCompartmentsNode(CommandNode):
    """Call A/B compartments from balanced Hi-C contact matrices with cooltools."""
    NODE_ID = 'cooltools_compartments'
    DISPLAY_NAME = 'cooltools Compartments'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Call A/B compartments with cooltools eigs-cis from balanced Hi-C matrices.'
    SEARCH_ALIASES = ['cooltools', 'hic', 'compartments', 'eigs-cis', 'eigenvector', 'a/b compartments']
    RETURN_TYPES = ('TSV', 'FILE')
    RETURN_NAMES = ('compartment_track', 'eigenvalues')
    REQUIRED_EXECUTABLES = ['cooltools']
    REQUIRED_CONDA_PACKAGES = ['cooltools']
    DOCUMENTATION_URL = 'https://cooltools.readthedocs.io/en/latest/cli.html#eigs-cis'
    VERSION = '0.7.0'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        n_eigs = inputs.get('n_eigs', 3)
        if int(n_eigs if n_eigs is not None else 3) < 1:
            return 'n_eigs must be at least 1.'
        ignore_diags = inputs.get('ignore_diags', 0)
        if int(ignore_diags if ignore_diags is not None else 0) < 0:
            return 'ignore_diags must be zero or greater.'
        return True

    @classmethod
    def _out_prefix(cls, inputs: dict[str, Any], output_dir: str | Path) -> Path:
        return Path(output_dir) / _safe_output_stem(inputs.get('output_prefix'), 'compartments')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_prefix = cls._out_prefix(inputs, inputs.get('output', '.'))
        cmd = ['cooltools', 'eigs-cis']
        if inputs.get('phasing_track'):
            cmd.extend(['--phasing-track', str(inputs['phasing_track'])])
        if inputs.get('view_file'):
            cmd.extend(['--view', str(inputs['view_file'])])
        cmd.extend(['--n-eigs', str(inputs.get('n_eigs', 3))])
        if inputs.get('clr_weight_name'):
            cmd.extend(['--clr-weight-name', str(inputs['clr_weight_name'])])
        if inputs.get('ignore_diags'):
            cmd.extend(['--ignore-diags', str(inputs['ignore_diags'])])
        cmd.extend(['-o', str(out_prefix), str(inputs.get('cooler_uri', ''))])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        out_prefix = cls._out_prefix(inputs, node_out)
        return [Path(f'{out_prefix}.cis.vecs.tsv'), Path(f'{out_prefix}.cis.lam.txt')]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'cooler_uri': ('FILE', {'description': 'Balanced .cool/.mcool URI, optionally with ::resolutions/bin'})}, 'optional': {'phasing_track': ('TSV', {'description': 'BedGraph-like phasing track, optionally path::column'}), 'view_file': ('BED', {'description': 'Optional genomic view BED'}), 'n_eigs': ('INT', {'default': 3, 'min': 1, 'max': 10}), 'clr_weight_name': ('STRING', {'default': 'weight', 'description': 'Cooler balancing weight column'}), 'ignore_diags': ('INT', {'default': 0, 'min': 0}), 'output_prefix': ('STRING', {'default': 'compartments'})}, 'hidden': {'output': ('STRING', {})}}


class CooltoolsInsulationNode(CommandNode):
    """Calculate Hi-C insulation scores and boundaries with cooltools."""
    NODE_ID = 'cooltools_insulation'
    DISPLAY_NAME = 'cooltools Insulation'
    CATEGORY = 'epigenomics'
    DESCRIPTION = 'Calculate diamond insulation scores and call insulating boundaries with cooltools.'
    SEARCH_ALIASES = ['cooltools', 'hic', 'insulation', 'boundaries', 'tad', 'domains']
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('insulation',)
    REQUIRED_EXECUTABLES = ['cooltools']
    REQUIRED_CONDA_PACKAGES = ['cooltools']
    DOCUMENTATION_URL = 'https://cooltools.readthedocs.io/en/latest/cli.html#insulation'
    VERSION = '0.7.0'

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        window_sizes = _split_window_sizes(inputs.get('window_sizes'))
        if not window_sizes:
            return 'At least one window size is required.'
        for window in window_sizes:
            if int(window) <= 0:
                return 'window sizes must be positive integers.'
        nproc = inputs.get('nproc', 1)
        if int(nproc if nproc is not None else 1) < 1:
            return 'nproc must be at least 1.'
        ignore_diags = inputs.get('ignore_diags', 0)
        if int(ignore_diags if ignore_diags is not None else 0) < 0:
            return 'ignore_diags must be zero or greater.'
        min_frac_valid_pixels = inputs.get('min_frac_valid_pixels', 0.66)
        if not 0 <= float(min_frac_valid_pixels if min_frac_valid_pixels is not None else 0.66) <= 1:
            return 'min_frac_valid_pixels must be between 0 and 1.'
        min_dist_bad_bin = inputs.get('min_dist_bad_bin', 0)
        if int(min_dist_bad_bin if min_dist_bad_bin is not None else 0) < 0:
            return 'min_dist_bad_bin must be zero or greater.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = inputs.get('output', '.')
        cmd = ['cooltools', 'insulation', '-p', str(inputs.get('nproc', 1)), '-o', f'{out_dir}/insulation.tsv']
        if inputs.get('view_file'):
            cmd.extend(['--view', str(inputs['view_file'])])
        if inputs.get('clr_weight_name'):
            cmd.extend(['--clr-weight-name', str(inputs['clr_weight_name'])])
        if inputs.get('ignore_diags'):
            cmd.extend(['--ignore-diags', str(inputs['ignore_diags'])])
        if inputs.get('min_frac_valid_pixels') is not None:
            cmd.extend(['--min-frac-valid-pixels', str(inputs.get('min_frac_valid_pixels'))])
        if inputs.get('min_dist_bad_bin'):
            cmd.extend(['--min-dist-bad-bin', str(inputs['min_dist_bad_bin'])])
        if inputs.get('threshold'):
            cmd.extend(['--threshold', str(inputs['threshold'])])
        if inputs.get('window_pixels'):
            cmd.append('--window-pixels')
        if inputs.get('append_raw_scores'):
            cmd.append('--append-raw-scores')
        if inputs.get('chunksize'):
            cmd.extend(['--chunksize', str(inputs['chunksize'])])
        cmd.append(str(inputs.get('cooler_uri', '')))
        cmd.extend(_split_window_sizes(inputs.get('window_sizes')))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'insulation.tsv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'cooler_uri': ('FILE', {'description': 'Balanced .cool/.mcool URI, optionally with ::resolutions/bin'}), 'window_sizes': ('STRING', {'default': '100000', 'description': 'Comma- or space-separated insulation windows'})}, 'optional': {'view_file': ('BED', {'description': 'Optional genomic view BED'}), 'nproc': ('INT', {'default': 1, 'min': 1, 'max': 64}), 'clr_weight_name': ('STRING', {'default': 'weight', 'description': 'Cooler balancing weight column'}), 'ignore_diags': ('INT', {'default': 0, 'min': 0}), 'min_frac_valid_pixels': ('FLOAT', {'default': 0.66, 'min': 0.0, 'max': 1.0}), 'min_dist_bad_bin': ('INT', {'default': 0, 'min': 0}), 'threshold': ('STRING', {'default': '0', 'description': 'Boundary threshold: Li, Otsu, or numeric'}), 'window_pixels': ('BOOLEAN', {'default': False}), 'append_raw_scores': ('BOOLEAN', {'default': False}), 'chunksize': ('INT', {'default': 20000000, 'min': 1})}, 'hidden': {'output': ('STRING', {})}}
