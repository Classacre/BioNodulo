"""dorado — long_read node(s). One tool per file (extracted from long_read.py)."""
from __future__ import annotations
from pathlib import Path
import re
from typing import Any
from bionodulo.nodes.command_node import CommandNode
def _safe_output_stem(value: Any, fallback: str) -> str:
    text = str(value or '').strip()
    if not text:
        text = fallback
    stem = Path(text).stem
    stem = re.sub('\\.(gz|bz2|xz|zip)$', '', stem)
    stem = re.sub('[^A-Za-z0-9_.-]+', '_', stem).strip('._-')
    return stem or fallback


class DoradoBasecallerNode(CommandNode):
    """Basecall Oxford Nanopore POD5 reads with Dorado."""
    NODE_ID = 'dorado_basecaller'
    DISPLAY_NAME = 'Dorado Basecaller'
    CATEGORY = 'long_read'
    DESCRIPTION = 'Basecall ONT POD5 reads with Dorado. Supports simplex, modified base calling (5mC, 6mA). GPU-accelerated.'
    SEARCH_ALIASES = ['dorado', 'basecaller', 'ont', 'nanopore', 'modified bases', 'methylation']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('basecalled_bam',)
    REQUIRED_EXECUTABLES = ['dorado']
    REQUIRED_CONDA_PACKAGES = ['dorado']
    DOCUMENTATION_URL = 'https://github.com/nanoporetech/dorado'
    VERSION = '0.9.6'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['dorado', 'basecaller', str(inputs.get('model', 'sup@latest')), str(inputs.get('pod5_dir', ''))]
        if inputs.get('modified_bases'):
            cmd.extend(['--modified-bases', *str(inputs['modified_bases']).split()])
        if inputs.get('kit_name'):
            cmd.extend(['--kit-name', str(inputs['kit_name'])])
        if inputs.get('trim'):
            cmd.extend(['--trim', str(inputs['trim'])])
        if inputs.get('min_qscore'):
            cmd.extend(['--min-qscore', str(inputs['min_qscore'])])
        if inputs.get('reference'):
            cmd.extend(['--reference', str(inputs['reference'])])
        cmd.extend(['>', f'{out_dir}/basecalled_bam.bam'])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'pod5_dir': ('DIRECTORY', {'description': 'Directory with POD5 signal files'}), 'model': ('STRING', {'default': 'sup@latest', 'description': 'Model (sup@latest, hac@latest, fast@latest)'})}, 'optional': {'modified_bases': ('STRING', {'default': '', 'description': "Modified bases to call (e.g., '5mC 6mA')"}), 'kit_name': ('STRING', {'default': '', 'description': 'Barcoding kit for demux'}), 'trim': ('STRING', {'default': 'all', 'options': ['all', 'primers', 'adapters', 'none']}), 'min_qscore': ('INT', {'default': 0, 'min': 0, 'max': 30}), 'reference': ('FASTA', {'description': 'Reference for alignment during basecalling'})}, 'hidden': {'output': ('STRING', {})}}


class DoradoCorrectNode(CommandNode):
    """Correct Oxford Nanopore reads with Dorado HERRO."""
    NODE_ID = 'dorado_correct'
    DISPLAY_NAME = 'Dorado Correct'
    CATEGORY = 'long_read'
    DESCRIPTION = 'Correct ONT reads with Dorado HERRO neural-network read correction.'
    SEARCH_ALIASES = ['dorado', 'correct', 'herro', 'read correction', 'nanopore', 'ont']
    RETURN_TYPES = ('FASTQ',)
    RETURN_NAMES = ('corrected_reads',)
    REQUIRED_EXECUTABLES = ['dorado']
    REQUIRED_CONDA_PACKAGES = ['dorado']
    DOCUMENTATION_URL = 'https://software-docs.nanoporetech.com/dorado/latest/secondary/correct/'
    VERSION = '0.9.6'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out_dir = Path(output_dir) / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return [out_dir / 'corrected_reads.fastq']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not str(inputs.get('reads', '') or '').strip():
            return 'reads is required.'
        if int(inputs.get('threads', 0) or 0) < 1:
            return 'threads must be at least 1.'
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['dorado', 'correct', '-t', str(inputs.get('threads', 4))]
        if inputs.get('device'):
            cmd.extend(['--device', str(inputs['device'])])
        cmd.extend([str(inputs.get('reads', '')), '>', f'{out_dir}/corrected_reads.fastq'])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Input ONT reads in FASTQ/FASTQ.GZ format'}), 'threads': ('INT', {'default': 8, 'min': 1, 'max': 128, 'display': 'slider'})}, 'optional': {'device': ('STRING', {'default': '', 'description': 'Dorado device, e.g. cuda:0, cuda:all, cpu'})}, 'hidden': {'output': ('STRING', {})}}


class DoradoDemuxNode(CommandNode):
    """Demultiplex Oxford Nanopore reads by barcode with Dorado."""
    NODE_ID = 'dorado_demux'
    DISPLAY_NAME = 'Dorado Demux'
    CATEGORY = 'long_read'
    DESCRIPTION = 'Demultiplex ONT reads into per-barcode files with Dorado.'
    SEARCH_ALIASES = ['dorado', 'demux', 'demultiplex', 'barcoding', 'barcode', 'nanopore']
    RETURN_TYPES = ('DIRECTORY', 'TSV')
    RETURN_NAMES = ('demux_dir', 'barcode_summary')
    REQUIRED_EXECUTABLES = ['dorado']
    REQUIRED_CONDA_PACKAGES = ['dorado']
    DOCUMENTATION_URL = 'https://software-docs.nanoporetech.com/dorado/latest/barcoding/barcoding/'
    VERSION = '0.9.6'
    SHELL = True
    EXPERIMENTAL = True
    _MODES = {'classify', 'split'}

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        mode = str(inputs.get('mode', 'classify') or 'classify')
        if mode not in cls._MODES:
            return f'Unsupported Dorado demux mode: {mode}'
        if int(inputs.get('threads', 0) or 0) < 0:
            return 'threads must be zero or greater.'
        kit_name = str(inputs.get('kit_name', '') or '').strip()
        sample_sheet = str(inputs.get('sample_sheet', '') or '').strip()
        barcode_arrangement = str(inputs.get('barcode_arrangement', '') or '').strip()
        barcode_sequences = str(inputs.get('barcode_sequences', '') or '').strip()
        if mode == 'classify' and (not kit_name) and (not barcode_arrangement):
            return 'kit_name is required when mode is classify.'
        if mode == 'split':
            if kit_name:
                return 'kit_name cannot be used when mode is split.'
            if sample_sheet or barcode_arrangement or barcode_sequences:
                return 'barcode classification options cannot be used when mode is split.'
        if inputs.get('sort_bam') and (not inputs.get('no_trim')):
            return 'sort_bam requires no_trim so mapped reads remain valid.'
        return True

    @classmethod
    def _planned_paths(cls, inputs: dict[str, Any], output_dir: str | Path) -> tuple[Path, Path]:
        node_out = Path(output_dir)
        fallback = f"{_safe_output_stem(inputs.get('reads'), 'dorado')}_demux"
        stem = _safe_output_stem(inputs.get('output_name'), fallback)
        demux_dir = node_out / stem
        return (demux_dir, demux_dir / 'barcode_summary.tsv')

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        out_dir = Path(str(inputs.get('output', '.')))
        demux_dir, _summary = cls._planned_paths(inputs, out_dir)
        mode = str(inputs.get('mode', 'classify') or 'classify')
        threads = int(inputs.get('threads', 0) or 0)
        cmd = ['dorado', 'demux', '--output-dir', str(demux_dir)]
        if mode == 'split':
            cmd.append('--no-classify')
        else:
            kit_name = str(inputs.get('kit_name', '') or '').strip()
            if kit_name:
                cmd.extend(['--kit-name', kit_name])
            if inputs.get('sample_sheet'):
                cmd.extend(['--sample-sheet', str(inputs['sample_sheet'])])
            if inputs.get('barcode_arrangement'):
                cmd.extend(['--barcode-arrangement', str(inputs['barcode_arrangement'])])
            if inputs.get('barcode_sequences'):
                cmd.extend(['--barcode-sequences', str(inputs['barcode_sequences'])])
        if inputs.get('emit_fastq'):
            cmd.append('--emit-fastq')
        if inputs.get('emit_summary'):
            cmd.append('--emit-summary')
        if inputs.get('no_trim'):
            cmd.append('--no-trim')
        if inputs.get('sort_bam'):
            cmd.append('--sort-bam')
        if inputs.get('recursive'):
            cmd.append('--recursive')
        if threads > 0:
            cmd.extend(['--threads', str(threads)])
        cmd.append(str(inputs.get('reads', '')))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return list(cls._planned_paths(inputs, node_out))

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FILE', {'description': 'Basecalled reads in BAM, FASTQ, or an input directory'}), 'mode': ('STRING', {'default': 'classify', 'options': ['classify', 'split']})}, 'optional': {'kit_name': ('STRING', {'default': '', 'description': 'Dorado barcode kit name for classification'}), 'sample_sheet': ('FILE', {'description': 'Optional Dorado sample sheet CSV'}), 'barcode_arrangement': ('FILE', {'description': 'Custom barcode arrangement TOML'}), 'barcode_sequences': ('FASTA', {'description': 'Custom barcode sequences FASTA'}), 'emit_fastq': ('BOOLEAN', {'default': False, 'description': 'Emit demultiplexed FASTQ instead of BAM'}), 'emit_summary': ('BOOLEAN', {'default': True, 'description': 'Emit per-read barcode summary'}), 'no_trim': ('BOOLEAN', {'default': False, 'description': 'Preserve barcode sequence and mapping tags'}), 'sort_bam': ('BOOLEAN', {'default': False, 'description': 'Sort and index mapped BAM outputs'}), 'recursive': ('BOOLEAN', {'default': False, 'description': 'Search input folders recursively'}), 'threads': ('INT', {'default': 0, 'min': 0, 'max': 128}), 'output_name': ('STRING', {'default': '', 'description': 'Optional output directory stem'})}, 'hidden': {'output': ('STRING', {})}}


class DoradoDuplexNode(CommandNode):
    """Run Dorado duplex basecalling for high-accuracy ONT reads."""
    NODE_ID = 'dorado_duplex'
    DISPLAY_NAME = 'Dorado Duplex'
    CATEGORY = 'long_read'
    DESCRIPTION = 'Duplex basecalling for Q30+ ONT accuracy. Both strands of same molecule sequenced.'
    SEARCH_ALIASES = ['dorado', 'duplex', 'ont', 'nanopore', 'double-strand', 'high accuracy']
    RETURN_TYPES = ('BAM',)
    RETURN_NAMES = ('duplex_bam',)
    REQUIRED_EXECUTABLES = ['dorado']
    REQUIRED_CONDA_PACKAGES = ['dorado']
    DOCUMENTATION_URL = 'https://github.com/nanoporetech/dorado'
    VERSION = '0.9.6'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['dorado', 'duplex', str(inputs.get('model', 'sup@latest')), str(inputs.get('pod5_dir', '')), '-t', str(inputs.get('threads', 4))]
        if inputs.get('modified_bases'):
            cmd.extend(['--modified-bases', *str(inputs['modified_bases']).split()])
        cmd.extend(['>', f'{out_dir}/duplex_bam.bam'])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'pod5_dir': ('DIRECTORY', {'description': 'POD5 signal files'}), 'model': ('STRING', {'default': 'sup@latest'})}, 'optional': {'modified_bases': ('STRING', {'default': '', 'description': 'Modified bases'}), 'threads': ('INT', {'default': 4, 'min': 1})}, 'hidden': {'output': ('STRING', {})}}
