"""sniffles2 — variant node(s). One tool per file (extracted from variant.py)."""
from __future__ import annotations
import shlex
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class Sniffles2Node(CommandNode):
    """Call structural variants from long-read alignments with Sniffles2."""
    NODE_ID = 'sniffles2'
    DISPLAY_NAME = 'Sniffles2 SV Caller'
    CATEGORY = 'variant'
    DESCRIPTION = 'Long-read SV caller for PacBio HiFi and ONT. Supports tandem repeat annotation and phased SV output.'
    SEARCH_ALIASES = ['sniffles2', 'sniffles', 'structural variant', 'long-read sv', 'nanopore sv', 'pacbio sv', 'hifi sv']
    RETURN_TYPES = ('VCF_GZ',)
    RETURN_NAMES = ('sv_vcf',)
    REQUIRED_EXECUTABLES = ['sniffles']
    REQUIRED_CONDA_PACKAGES = ['sniffles']
    DOCUMENTATION_URL = 'https://github.com/fritzsedlazeck/Sniffles'
    VERSION = '2.5.3'

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['sniffles', '--input', str(inputs.get('bam', '')), '--vcf', f"{inputs.get('output', '.')}/sv_vcf.vcf.gz", '--reference', str(inputs.get('reference', '')), '--threads', str(inputs.get('threads', 4))]
        if inputs.get('tandem_repeats'):
            cmd.extend(['--tandem-repeats', str(inputs['tandem_repeats'])])
        if inputs.get('minsvlen'):
            cmd.extend(['--minsvlen', str(inputs['minsvlen'])])
        if inputs.get('minsupport'):
            cmd.extend(['--minsupport', str(inputs['minsupport'])])
        if inputs.get('phase'):
            cmd.append('--phase')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Sorted, indexed BAM from a long-read aligner'}), 'reference': ('FASTA', {'description': 'Reference FASTA'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'tandem_repeats': ('BED', {'description': 'Tandem repeat annotations', 'advanced': True}), 'minsvlen': ('INT', {'default': 50, 'min': 20, 'label': 'Min SV Length'}), 'minsupport': ('INT', {'default': 10, 'min': 1, 'label': 'Min Supporting Reads'}), 'phase': ('BOOLEAN', {'default': False, 'description': 'Output phased SVs'})}, 'hidden': {'output': ('STRING', {})}}


class Sniffles2CallNode(Sniffles2Node):
    """Workflow-compatible Sniffles2 structural variant caller alias."""
    NODE_ID = 'sniffles2_call'
    DISPLAY_NAME = 'Sniffles2 Call'
    DESCRIPTION = 'Call structural variants with Sniffles2 for multi-caller SV workflows.'
    SEARCH_ALIASES = ['sniffles2_call', 'sniffles2', 'sniffles', 'structural variant', 'sv caller', 'long-read sv', 'split-read sv']
