"""multiqc — qc node(s). One tool per file (extracted from qc.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class MultiQCNode(CommandNode):
    """Aggregate QC reports with MultiQC."""
    NODE_ID = 'multiqc'
    DISPLAY_NAME = 'MultiQC'
    REQUIRED_CONDA_PACKAGES = ['multiqc']
    CATEGORY = 'qc'
    DESCRIPTION = 'Aggregate multiple QC reports into a single HTML report'
    SEARCH_ALIASES = ['multiqc', 'aggregate qc', 'report', 'summary']
    RETURN_TYPES = ('MULTIQC_REPORT',)
    RETURN_NAMES = ('report',)
    REQUIRED_EXECUTABLES = ['multiqc']
    DOCUMENTATION_URL = 'https://multiqc.info/'
    VERSION = '1.33'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        filename = str(inputs.get('filename') or 'report')
        if not filename.lower().endswith('.html'):
            filename = f'{filename}.html'
        return [Path(output_dir) / cls.NODE_ID / filename]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        reports = inputs.get('reports', '')
        if isinstance(reports, str):
            reports = [reports]
        search_paths: list[str] = []
        seen: set[str] = set()
        for entry in reports:
            raw = str(entry).strip()
            if not raw:
                continue
            p = Path(raw)
            target = str(p if p.is_dir() else p.parent)
            if target and target not in seen:
                seen.add(target)
                search_paths.append(target)
        if not search_paths:
            search_paths = [str(r) for r in reports if str(r).strip()]
        filename_param = str(inputs.get('filename') or 'report')
        if filename_param.lower().endswith('.html'):
            filename_param = filename_param[:-5]
        cmd = ['multiqc', *search_paths, '--outdir', str(inputs.get('output', inputs.get('output_dir', '.'))), '--filename', filename_param]
        if inputs.get('title'):
            cmd.extend(['--title', str(inputs['title'])])
        if inputs.get('comment'):
            cmd.extend(['--comment', str(inputs['comment'])])
        if inputs.get('force'):
            cmd.append('--force')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'reports': ('FILE_LIST', {'description': 'Directory or list containing QC report files'})}, 'optional': {'title': ('STRING', {'default': 'BioNodulo QC Report', 'label': 'Report Title'}), 'comment': ('STRING', {'default': '', 'multiline': True, 'label': 'Comment', 'advanced': True}), 'force': ('BOOLEAN', {'default': False, 'label': 'Overwrite', 'advanced': True}), 'filename': ('STRING', {'default': 'report', 'label': 'Output Filename (without extension)', 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}
