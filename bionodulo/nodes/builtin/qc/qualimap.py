"""qualimap — qc node(s). One tool per file (extracted from qc.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class QualiMapNode(CommandNode):
    """Run QualiMap BAM QC analysis."""
    NODE_ID = 'qualimap_bamqc'
    DISPLAY_NAME = 'QualiMap BAM QC'
    CATEGORY = 'qc'
    DESCRIPTION = 'Comprehensive BAM quality analysis with QualiMap'
    SEARCH_ALIASES = ['qualimap', 'bamqc', 'bam qc', 'alignment qc']
    RETURN_TYPES = ('HTML_REPORT', 'QC_REPORT_DIR')
    RETURN_NAMES = ('report', 'report_dir')
    REQUIRED_EXECUTABLES = ['qualimap']
    REQUIRED_CONDA_PACKAGES = ['qualimap']
    DOCUMENTATION_URL = 'http://qualimap.conesalab.org/'
    VERSION = '2.3'

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        return [out / 'report.html', out / 'report_dir.out']

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ['qualimap', 'bamqc', '-bam', str(inputs.get('bam', '')), '-outdir', f"{str(inputs.get('output', inputs.get('output_dir', '.')))}/report_dir.out", '-nt', str(inputs.get('threads', 2))]
        if inputs.get('feature_file'):
            cmd.extend(['-gff', str(inputs['feature_file'])])
        if inputs.get('paint_chromosome_limits'):
            cmd.append('--paint-chromosome-limits')
        if inputs.get('collect_overlap_pairs'):
            cmd.append('--collect-overlap-pairs')
        return cmd

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'bam': ('BAM', {'description': 'Input BAM alignment file'}), 'threads': ('INT', {'default': 2, 'min': 1, 'max': 64, 'display': 'slider'})}, 'optional': {'feature_file': ('GFF_GTF', {'description': 'Optional GFF/GTF for feature coverage', 'advanced': True}), 'paint_chromosome_limits': ('BOOLEAN', {'default': False, 'advanced': True}), 'collect_overlap_pairs': ('BOOLEAN', {'default': False, 'advanced': True})}, 'hidden': {'output': ('STRING', {})}}

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        """Run QualiMap and normalize its report filename."""
        result = await super().run(**kwargs)
        outputs = result.get('outputs', {}) if isinstance(result, dict) else {}
        report = Path(str(outputs.get('report', '')))
        report_dir = Path(str(outputs.get('report_dir', '')))
        src = report_dir / 'qualimapReport.html'
        if src.exists():
            src.rename(report)
        return result


class QualiMapAliasNode(QualiMapNode):
    """Planner compatibility alias for QualiMap BAM QC."""
    NODE_ID = 'qualimap'
    DISPLAY_NAME = 'QualiMap'
    DESCRIPTION = 'Run QualiMap BAM quality control for alignment reports.'
    SEARCH_ALIASES = ['qualimap', 'bamqc', 'bam qc', 'alignment qc', 'quality report']
