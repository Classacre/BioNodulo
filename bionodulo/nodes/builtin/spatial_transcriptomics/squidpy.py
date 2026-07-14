"""squidpy — spatial_transcriptomics node(s). One tool per file (extracted from spatial_transcriptomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SquidpyQCNode(CommandNode):
    """Run Visium QC and spatial neighborhood analysis with Squidpy."""
    NODE_ID = 'squidpy_qc'
    DISPLAY_NAME = 'Squidpy QC'
    CATEGORY = 'spatial_transcriptomics'
    DESCRIPTION = 'Visium QC, preprocessing, spatial neighborhood analysis, and visualization with Squidpy.'
    SEARCH_ALIASES = ['squidpy', 'spatial', 'visium', 'quality control', 'spatial analysis']
    RETURN_TYPES = ('H5AD', 'IMAGE')
    RETURN_NAMES = ('adata', 'spatial_plot')
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES = ['squidpy', 'scanpy', 'anndata', 'matplotlib']
    DOCUMENTATION_URL = 'https://squidpy.readthedocs.io/'
    VERSION = '1.6.5'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get('output', '.'))
        out_dir.mkdir(parents=True, exist_ok=True)
        visium_path = str(inputs.get('visium_path', ''))
        script = f"""\nimport squidpy as sq\nimport scanpy as sc\nimport matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n\nadata = sc.read_visium('{visium_path}', load_images=False)  # QC/clustering: skip tissue images (demo Visium data omits spatial/tissue_hires_image.png)\nadata.var_names_make_unique()\nadata.var["mt"] = adata.var_names.str.startswith("MT-")\nsc.pp.calculate_qc_metrics(adata, qc_vars=["mt"], inplace=True)\nsc.pp.filter_cells(adata, min_counts={inputs.get('min_counts', 500)})\nsc.pp.filter_genes(adata, min_cells={inputs.get('min_cells', 3)})\nadata = adata[adata.obs["pct_counts_mt"] < {inputs.get('max_mt_pct', 20.0)}]\nsc.pp.normalize_total(adata, target_sum=1e4)\nsc.pp.log1p(adata)\nsc.pp.highly_variable_genes(adata, n_top_genes={inputs.get('n_hvg', 2000)})\nsc.pp.scale(adata, max_value=10)\nsc.pp.pca(adata, n_comps={inputs.get('n_pcs', 15)})\nsc.pp.neighbors(adata)\nsc.tl.leiden(adata, resolution={inputs.get('resolution', 0.8)})\nsc.tl.umap(adata)\nsq.gr.spatial_neighbors(adata)\nsq.gr.nhood_enrichment(adata, cluster_key="leiden")\nadata.write('{out_dir}/adata.h5ad')\n\nfig, axes = plt.subplots(1, 2, figsize=(14, 6))\nsq.pl.spatial_scatter(adata, color='leiden', ax=axes[0], show=False)\nsc.pl.umap(adata, color='leiden', ax=axes[1], show=False)\nplt.tight_layout()\nplt.savefig('{out_dir}/spatial_plot.png', dpi=150)\nprint("Done")\n"""
        script_file = out_dir / 'squidpy_run.py'
        script_file.write_text(script)
        return ['python', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'adata.h5ad', node_out / 'spatial_plot.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'visium_path': ('DIRECTORY', {'description': 'Space Ranger output directory'})}, 'optional': {'min_counts': ('INT', {'default': 500, 'min': 0}), 'min_cells': ('INT', {'default': 3, 'min': 1}), 'max_mt_pct': ('FLOAT', {'default': 20.0, 'min': 0.0, 'max': 100.0}), 'n_hvg': ('INT', {'default': 2000, 'min': 100}), 'n_pcs': ('INT', {'default': 15, 'min': 2, 'max': 50}), 'resolution': ('FLOAT', {'default': 0.8, 'min': 0.1, 'max': 2.0, 'step': 0.1})}, 'hidden': {'output': ('STRING', {})}}


class SquidpyNode(SquidpyQCNode):
    """Compatibility wrapper for the original Squidpy roadmap node ID."""
    NODE_ID = 'squidpy'
    DISPLAY_NAME = 'Squidpy'
    DESCRIPTION = 'Run Visium QC, preprocessing, and spatial analysis with Squidpy.'
    SEARCH_ALIASES = ['squidpy', 'spatial', 'visium', 'quality control', 'spatial analysis']
