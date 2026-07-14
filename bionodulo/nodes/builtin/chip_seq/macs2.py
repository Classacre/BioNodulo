"""macs2 — chip_seq node(s). One tool per file (extracted from chip_seq.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, default: str) -> str:
    stem = '_'.join(str(value or '').strip().split())
    stem = ''.join((char if char.isalnum() or char in '._-' else '_' for char in stem))
    stem = stem.strip('._-')
    return stem or default


class MACS2CallpeakNode(CommandNode):
    """Call peaks from ChIP-seq data with MACS2."""
    NODE_ID = 'macs2_callpeak'
    DISPLAY_NAME = 'MACS2 Callpeak'
    REQUIRED_CONDA_PACKAGES = ['macs2']
    CATEGORY = 'chip_seq'
    DESCRIPTION = 'Model-based Analysis of ChIP-Seq: identify transcription factor binding sites'
    SEARCH_ALIASES = ['macs2', 'peak calling', 'chip-seq', 'binding sites']
    RETURN_TYPES = ('NARROW_PEAK', 'BEDGRAPH')
    RETURN_NAMES = ('peaks', 'signal')
    REQUIRED_EXECUTABLES = ['macs2']
    DOCUMENTATION_URL = 'https://github.com/macs3-project/MACS'
    VERSION = '2.2.9.2'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['macs2', 'callpeak', '-t', str(inputs.get('treatment', '')), '-n', str(inputs.get('name', 'peaks')), '--outdir', str(inputs.get('output', '.')), '-g', str(inputs.get('genome_size', 'hs')), '--bdg']
        if inputs.get('control'):
            cmd.extend(['-c', str(inputs['control'])])
        fmt = inputs.get('format', 'BAM')
        if fmt:
            cmd.extend(['-f', str(fmt)])
        if inputs.get('qvalue') is not None:
            cmd.extend(['-q', str(inputs['qvalue'])])
        if inputs.get('pvalue') is not None:
            cmd.extend(['-p', str(inputs['pvalue'])])
        if inputs.get('broad'):
            cmd.append('--broad')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'treatment': ('BAM', {'description': 'Treatment/ChIP BAM file'}), 'name': ('STRING', {'default': 'peaks'}), 'genome_size': ('STRING', {'default': 'hs', 'description': 'hs, mm, dm, ce, or numeric bp'})}, 'optional': {'control': ('BAM', {'description': 'Control/input BAM file'}), 'qvalue': ('FLOAT', {'default': 0.05, 'min': 0.0, 'max': 1.0}), 'format': ('STRING', {'default': 'BAM'}), 'pvalue': ('FLOAT', {'default': None, 'min': 0.0, 'max': 1.0, 'label': 'p-value', 'advanced': True}), 'broad': ('BOOLEAN', {'default': False, 'label': 'Broad Peaks', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs):
        import shutil
        from pathlib import Path
        result = await super().run(**kwargs)
        output_dir = kwargs.get('output_dir') or (kwargs.get('context') and getattr(kwargs['context'], 'node_dir', '.'))
        name = kwargs.get('name', 'peaks')
        if output_dir:
            node_out = Path(output_dir) / self.__class__.NODE_ID
            outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_dir)
            peaks_src = node_out / f'{name}_peaks.narrowPeak'
            if peaks_src.exists() and len(outputs) > 0:
                outputs[0].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(peaks_src), str(outputs[0]))
            signal_src = node_out / f'{name}_treat_pileup.bdg'
            if signal_src.exists() and len(outputs) > 1:
                outputs[1].parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(signal_src), str(outputs[1]))
        return result


class MACS2BdgPeakNode(CommandNode):
    """Call peaks from MACS2 bedGraph signal tracks."""
    NODE_ID = 'macs2_bdgpeak'
    DISPLAY_NAME = 'MACS2 BdgPeak'
    CATEGORY = 'chip_seq'
    DESCRIPTION = 'Call peaks from bedGraph signal tracks, optionally computing fold-enrichment from treatment and control tracks.'
    SEARCH_ALIASES = ['macs2', 'bdgpeakcall', 'bdgcmp', 'bedgraph peaks', 'chip-seq', 'atac-seq']
    RETURN_TYPES = ('BED',)
    RETURN_NAMES = ('peaks',)
    REQUIRED_EXECUTABLES = ['macs2']
    REQUIRED_CONDA_PACKAGES = ['macs2']
    DOCUMENTATION_URL = 'https://macs3-project.github.io/MACS/docs/bdgpeakcall.html'
    VERSION = '2.2.9.2'
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'treatment_bdg': ('FILE', {'description': 'Treatment bedGraph signal track'})}, 'optional': {'control_bdg': ('FILE', {'default': '', 'description': 'Control bedGraph track for bdgcmp fold enrichment'}), 'method': ('STRING', {'default': 'bdgpeakcall', 'options': ['bdgpeakcall', 'bdgcmp'], 'description': 'Run direct peak calling or only compute a bdgcmp score track'}), 'cutoff': ('FLOAT', {'default': 2.0, 'min': 0.0, 'description': 'bdgpeakcall cutoff'}), 'min_length': ('INT', {'default': 200, 'min': 1, 'description': 'Minimum peak length'}), 'max_gap': ('INT', {'default': 75, 'min': 0, 'description': 'Maximum gap to merge nearby regions'}), 'name': ('STRING', {'default': 'macs2_bdgpeak', 'description': 'Output filename stem'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        method = str(inputs.get('method', 'bdgpeakcall') or 'bdgpeakcall').lower()
        if method not in {'bdgpeakcall', 'bdgcmp'}:
            return f'Unsupported MACS2 bedGraph mode: {method}'
        if method == 'bdgcmp' and (not str(inputs.get('control_bdg', '') or '').strip()):
            return 'control_bdg is required when method is bdgcmp'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output_dir = str(inputs.get('output', '.'))
        stem = _safe_output_stem(inputs.get('name'), 'macs2_bdgpeak')
        method = str(inputs.get('method', 'bdgpeakcall') or 'bdgpeakcall').lower()
        treatment_bdg = str(inputs.get('treatment_bdg', ''))
        output_bed = f'{output_dir}/{stem}.bed'
        control_bdg = str(inputs.get('control_bdg', '') or '').strip()
        if method == 'bdgcmp':
            return cls._render_bdgcmp(treatment_bdg, control_bdg, output_bed)
        peak_input = treatment_bdg
        cmd: list[str] = []
        if control_bdg:
            peak_input = f'{output_dir}/{stem}_FE.bdg'
            cmd.extend(cls._render_bdgcmp(treatment_bdg, control_bdg, peak_input))
            cmd.append('&&')
        cmd.extend(['macs2', 'bdgpeakcall', '-i', peak_input, '-c', str(inputs.get('cutoff', 2.0)), '-l', str(inputs.get('min_length', 200)), '-g', str(inputs.get('max_gap', 75)), '-o', output_bed])
        return cmd

    @classmethod
    def _render_bdgcmp(cls, treatment_bdg: str, control_bdg: str, output_path: str) -> list[str]:
        return ['macs2', 'bdgcmp', '-t', treatment_bdg, '-c', control_bdg, '-m', 'FE', '-o', output_path]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        stem = _safe_output_stem(inputs.get('name'), 'macs2_bdgpeak')
        return [node_out / f'{stem}.bed']
