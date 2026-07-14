"""krona — metagenomics node(s). One tool per file (extracted from standard_viz_nodes.py)."""
from __future__ import annotations
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class KronaTaxonomyNode(BaseNode):
    """Interactive Krona taxonomy chart from a Kraken2-style classification."""
    NODE_ID = 'krona'
    DISPLAY_NAME = 'Krona Taxonomy Chart'
    CATEGORY = 'metagenomics'
    DESCRIPTION = 'Interactive Krona sunburst of taxonomic classifications (the metagenomics standard)'
    SEARCH_ALIASES = ['krona', 'taxonomy', 'sunburst', 'metagenomics', 'abundance', 'kraken']
    RETURN_TYPES = ('HTML_REPORT',)
    RETURN_NAMES = ('krona_html',)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ['ktImportTaxonomy']
    REQUIRED_CONDA_PACKAGES = ['krona']
    DOCUMENTATION_URL = 'https://github.com/marbl/Krona/wiki'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'classification': ('FILE', {'label': 'Kraken2 classifications', 'description': 'Per-read Kraken2 output'})}, 'optional': {'query_column': ('INT', {'default': 2, 'min': 1, 'max': 50, 'label': 'Read-ID column', 'advanced': True}), 'taxid_column': ('INT', {'default': 3, 'min': 1, 'max': 50, 'label': 'TaxID column', 'advanced': True}), 'output_name': ('STRING', {'default': 'krona.html', 'label': 'Output filename', 'advanced': True})}}

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop('context', None)
        node_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = node_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        classification = kwargs['classification']
        q_col = int(kwargs.get('query_column', 2) or 2)
        t_col = int(kwargs.get('taxid_column', 3) or 3)
        out_name = str(kwargs.get('output_name', 'krona.html') or 'krona.html')
        out_path = out_dir / out_name
        cmd = self.render_command(classification=str(classification), query_column=q_col, taxid_column=t_col, output=str(out_path))
        if context is not None and hasattr(context, 'run_command'):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {'returncode': proc.returncode}
        if result.get('returncode', 0) != 0:
            raise RuntimeError(f"Krona failed: {result.get('stderr', '')}")
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(out_path, label='Krona Taxonomy')
        return (str(out_path),)

    @staticmethod
    def render_command(*, classification: str, query_column: int, taxid_column: int, output: str) -> list[str]:
        return ['ktImportTaxonomy', '-q', str(query_column), '-t', str(taxid_column), '-o', output, classification]
