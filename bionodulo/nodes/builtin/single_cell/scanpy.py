"""scanpy — single_cell node(s). One tool per file (extracted from standard_viz_nodes.py)."""
from __future__ import annotations
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class ScanpyUmapNode(BaseNode):
    """Scanpy single-cell QC + UMAP embedding from a 10x matrix."""
    NODE_ID = 'scanpy_umap'
    DISPLAY_NAME = 'Scanpy UMAP + QC'
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Standard Scanpy single-cell pipeline: QC violins, PCA, neighbors, Leiden clusters, UMAP'
    SEARCH_ALIASES = ['scanpy', 'umap', 'single cell', 'leiden', 'cluster', 'violin', 'embedding']
    RETURN_TYPES = ('IMAGE', 'IMAGE')
    RETURN_NAMES = ('umap_png', 'qc_violin_png')
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES = ['scanpy', 'leidenalg', 'python-igraph']
    DOCUMENTATION_URL = 'https://scanpy.readthedocs.io/'

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'matrix_h5': ('FILE', {'label': '10x feature-barcode matrix (.h5)'})}, 'optional': {'min_genes': ('INT', {'default': 200, 'min': 0, 'max': 5000, 'label': 'Min genes / cell', 'advanced': True}), 'min_cells': ('INT', {'default': 3, 'min': 0, 'max': 1000, 'label': 'Min cells / gene', 'advanced': True}), 'n_pcs': ('INT', {'default': 30, 'min': 2, 'max': 100, 'label': 'PCs', 'advanced': True}), 'n_neighbors': ('INT', {'default': 15, 'min': 2, 'max': 100, 'label': 'Neighbors', 'advanced': True}), 'resolution': ('FLOAT', {'default': 1.0, 'min': 0.1, 'max': 3.0, 'step': 0.1, 'label': 'Leiden resolution', 'advanced': True})}}

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop('context', None)
        node_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = node_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        umap_png = out_dir / 'umap.png'
        violin_png = out_dir / 'qc_violin.png'
        script_path = out_dir / 'scanpy_umap.py'
        script_path.write_text(self._build_script(h5=str(kwargs['matrix_h5']), min_genes=int(kwargs.get('min_genes', 200) or 200), min_cells=int(kwargs.get('min_cells', 3) or 3), n_pcs=int(kwargs.get('n_pcs', 30) or 30), n_neighbors=int(kwargs.get('n_neighbors', 15) or 15), resolution=float(kwargs.get('resolution', 1.0) or 1.0), umap_png=str(umap_png), violin_png=str(violin_png)), encoding='utf-8')
        cmd = ['python', str(script_path)]
        if context is not None and hasattr(context, 'run_command'):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {'returncode': proc.returncode}
        if result.get('returncode', 0) != 0:
            raise RuntimeError(f"Scanpy UMAP failed: {result.get('stderr', '')}")
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(umap_png, label='UMAP (Leiden clusters)')
            context.register_preview(violin_png, label='QC violin')
        return (str(umap_png), str(violin_png))

    @staticmethod
    def _build_script(*, h5: str, min_genes: int, min_cells: int, n_pcs: int, n_neighbors: int, resolution: float, umap_png: str, violin_png: str) -> str:
        return textwrap.dedent(f'            import matplotlib\n            matplotlib.use("Agg")\n            import matplotlib.pyplot as plt\n            import scanpy as sc\n\n            sc.settings.verbosity = 1\n            adata = sc.read_10x_h5(r"{h5}")\n            adata.var_names_make_unique()\n\n            sc.pp.filter_cells(adata, min_genes={min_genes})\n            sc.pp.filter_genes(adata, min_cells={min_cells})\n            adata.var["mt"] = adata.var_names.str.upper().str.startswith("MT-")\n            sc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], percent_top=None, log1p=False, inplace=True)\n\n            sc.pl.violin(\n                adata, ["n_genes_by_counts", "total_counts", "pct_counts_mt"],\n                jitter=0.4, multi_panel=True, show=False,\n            )\n            plt.savefig(r"{violin_png}", dpi=150, bbox_inches="tight")\n            plt.close("all")\n\n            sc.pp.normalize_total(adata, target_sum=1e4)\n            sc.pp.log1p(adata)\n            sc.pp.highly_variable_genes(adata, n_top_genes=2000)\n            adata = adata[:, adata.var.highly_variable]\n            sc.pp.scale(adata, max_value=10)\n            sc.tl.pca(adata, n_comps=min({n_pcs}, adata.n_vars - 1, adata.n_obs - 1))\n            sc.pp.neighbors(adata, n_neighbors={n_neighbors}, n_pcs=min({n_pcs}, adata.obsm["X_pca"].shape[1]))\n            sc.tl.umap(adata)\n            try:\n                sc.tl.leiden(adata, resolution={resolution})\n                color = "leiden"\n            except Exception:\n                color = "total_counts"\n            sc.pl.umap(adata, color=color, show=False)\n            plt.savefig(r"{umap_png}", dpi=150, bbox_inches="tight")\n            plt.close("all")\n            ')
