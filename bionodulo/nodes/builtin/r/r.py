"""r — r node(s). One tool per file (extracted from r_bioinformatics.py)."""
from __future__ import annotations
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class PheatmapNode(BaseNode):
    """Generate clustered heatmaps with pheatmap."""
    NODE_ID = 'r_pheatmap'
    DISPLAY_NAME = 'R Heatmap (pheatmap)'
    REQUIRED_CONDA_PACKAGES = ['r-base', 'r-pheatmap', 'r-rcolorbrewer', 'r-readr']
    CATEGORY = 'r'
    DESCRIPTION = 'Generate publication-quality clustered heatmaps with pheatmap'
    RETURN_TYPES = ('FILE',)
    RETURN_NAMES = ('plot_png',)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_R_PACKAGES = ['pheatmap', 'RColorBrewer', 'readr']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'data_csv': ('FILE', {'label': 'Data Matrix CSV'}), 'scale': ('STRING', {'default': 'row', 'options': ['none', 'row', 'column'], 'label': 'Scale'})}, 'optional': {'annotation_csv': ('FILE', {'label': 'Annotation CSV (optional)', 'advanced': True}), 'cluster_rows': ('BOOLEAN', {'default': True, 'label': 'Cluster rows', 'advanced': True}), 'cluster_cols': ('BOOLEAN', {'default': True, 'label': 'Cluster columns', 'advanced': True}), 'show_rownames': ('BOOLEAN', {'default': True, 'label': 'Show row names', 'advanced': True}), 'show_colnames': ('BOOLEAN', {'default': True, 'label': 'Show column names', 'advanced': True}), 'fontsize': ('INT', {'default': 10, 'min': 4, 'max': 24, 'step': 1, 'label': 'Font size', 'advanced': True}), 'width': ('INT', {'default': 800, 'min': 200, 'max': 4000, 'step': 50, 'display': 'slider', 'label': 'Width (px)', 'advanced': True}), 'height': ('INT', {'default': 600, 'min': 200, 'max': 4000, 'step': 50, 'display': 'slider', 'label': 'Height (px)', 'advanced': True})}}

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop('context', None)
        output_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        data_csv = kwargs['data_csv']
        scale = kwargs.get('scale', 'row')
        annotation_csv = kwargs.get('annotation_csv', '') or ''
        cluster_rows = kwargs.get('cluster_rows', True)
        cluster_cols = kwargs.get('cluster_cols', True)
        show_rownames = kwargs.get('show_rownames', True)
        show_colnames = kwargs.get('show_colnames', True)
        fontsize = kwargs.get('fontsize', 10)
        width = kwargs.get('width', 800)
        height = kwargs.get('height', 600)
        png_path = out_dir / 'heatmap.png'
        script_path = out_dir / 'heatmap.R'
        ann_arg = f'annotation_col = read.csv("{Path(annotation_csv).as_posix()}", row.names = 1),' if annotation_csv else ''
        script = textwrap.dedent(f'''            if (!requireNamespace("pheatmap", quietly = TRUE)) stop("Package 'pheatmap' is required but not installed. Install it with: install.packages('pheatmap')")\n            if (!requireNamespace("RColorBrewer", quietly = TRUE)) stop("Package 'RColorBrewer' is required but not installed. Install it with: install.packages('RColorBrewer')")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")\n            library(pheatmap)\n            library(RColorBrewer)\n            library(readr)\n\n            data <- as.matrix(read.csv("{Path(data_csv).as_posix()}", row.names = 1, check.names = FALSE))\n            {(f'ann <- read.csv("{Path(annotation_csv).as_posix()}", row.names = 1)' if annotation_csv else '')}\n\n            png("{png_path.as_posix()}", width = {width}, height = {height}, res = 100)\n            pheatmap(data,\n                scale = "{scale}",\n                cluster_rows = {str(cluster_rows).upper()},\n                cluster_cols = {str(cluster_cols).upper()},\n                show_rownames = {str(show_rownames).upper()},\n                show_colnames = {str(show_colnames).upper()},\n                fontsize = {fontsize},\n                color = colorRampPalette(rev(brewer.pal(n = 7, name = "RdYlBu")))(100),\n                {ann_arg}\n                main = "Heatmap"\n            )\n            dev.off()\n        ''')
        script_path.write_text(script, encoding='utf-8')
        cmd = ['Rscript', str(script_path)]
        if context is not None and hasattr(context, 'run_command'):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {'returncode': proc.returncode}
        if result.get('returncode', 0) != 0:
            raise RuntimeError(f"pheatmap script failed: {result.get('stderr', '')}")
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(png_path, label='pheatmap')
        return (str(png_path),)
