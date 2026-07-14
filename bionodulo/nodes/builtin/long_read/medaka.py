"""medaka — long_read node(s). One tool per file (extracted from long_read.py)."""
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


class MedakaConsensusNode(CommandNode):
    """Polish Oxford Nanopore draft assemblies with Medaka."""
    NODE_ID = 'medaka_consensus'
    DISPLAY_NAME = 'Medaka Consensus'
    CATEGORY = 'long_read'
    DESCRIPTION = 'Neural network polishing of ONT assemblies. Corrects indel and substitution errors.'
    SEARCH_ALIASES = ['medaka', 'polish', 'consensus', 'nanopore', 'assembly polish']
    RETURN_TYPES = ('FASTA',)
    RETURN_NAMES = ('polished_assembly',)
    REQUIRED_EXECUTABLES = ['medaka_consensus']
    REQUIRED_CONDA_PACKAGES = ['medaka']
    DOCUMENTATION_URL = 'https://github.com/nanoporetech/medaka'
    VERSION = '2.0.1'
    SHELL = True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out_dir = Path(output_dir) / cls.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        return [out_dir / 'consensus.fasta']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get('output', '.')
        cmd = ['medaka_consensus', '-i', str(inputs.get('reads', '')), '-d', str(inputs.get('draft', '')), '-o', str(out_dir), '-t', str(inputs.get('threads', 4))]
        if inputs.get('model'):
            cmd.extend(['-m', str(inputs['model'])])
        if inputs.get('bam'):
            cmd.extend(['-b', str(inputs['bam'])])
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reads': ('FASTQ', {'description': 'Input FASTQ reads'}), 'draft': ('FASTA', {'description': 'Draft assembly to polish'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'model': ('STRING', {'default': 'r1041_e82_400_sup_v5.0.0', 'description': 'Medaka model'}), 'bam': ('BAM', {'description': 'Pre-aligned BAM'})}, 'hidden': {'output': ('STRING', {})}}


class MedakaNode(MedakaConsensusNode):
    """Compatibility wrapper for the original Medaka roadmap node ID."""
    NODE_ID = 'medaka'
    DISPLAY_NAME = 'Medaka'
    DESCRIPTION = 'Polish Oxford Nanopore draft assemblies with Medaka.'
    SEARCH_ALIASES = ['medaka', 'medaka consensus', 'polish', 'consensus', 'nanopore', 'assembly polish']
