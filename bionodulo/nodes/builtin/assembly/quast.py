"""quast — assembly node(s). One tool per file (extracted from assembly.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class QuastNode(CommandNode):
    """Assess assembly quality with QUAST."""
    NODE_ID = 'quast'
    DISPLAY_NAME = 'QUAST'
    REQUIRED_CONDA_PACKAGES = ['quast']
    CATEGORY = 'assembly'
    DESCRIPTION = 'Quality Assessment Tool for Genome Assemblies'
    SEARCH_ALIASES = ['quast', 'quality', 'assembly qc', 'assess']
    RETURN_TYPES = ('HTML_REPORT',)
    RETURN_NAMES = ('report',)
    REQUIRED_EXECUTABLES = ['quast']
    DOCUMENTATION_URL = 'https://quast.sourceforge.net/'
    VERSION = '5.3.0'
    COMMAND = ['quast', '{inputs.assembly}', '-o', '{output}/report_dir.out', '-t', '{inputs.threads}']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'assembly': ('ASSEMBLY', {'description': 'Assembly FASTA file(s)'}), 'threads': ('INT', {'default': 4, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'reference': ('FASTA', {'description': 'Optional reference for comparison'}), 'gff': ('GFF', {'description': 'Optional gene annotations'})}, 'hidden': {'output': ('STRING', {})}}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['quast', str(inputs.get('assembly', '')), '-o', f"{str(inputs.get('output', '.'))}/report_dir.out", '-t', str(inputs.get('threads', 4))]
        if inputs.get('reference'):
            cmd.extend(['-r', str(inputs['reference'])])
        if inputs.get('gff'):
            cmd.extend(['--features', str(inputs['gff'])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list:
        od = Path(output_dir)
        return [od / cls.NODE_ID / 'report_dir.out' / 'report.html']
