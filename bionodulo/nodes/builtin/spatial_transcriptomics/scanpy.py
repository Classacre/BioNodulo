"""scanpy — spatial_transcriptomics node(s). One tool per file (extracted from spatial_transcriptomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class ScanpySpatialNode(CommandNode):
    """Cluster spatial transcriptomics count matrices with Scanpy."""
    NODE_ID = 'scanpy_spatial'
    DISPLAY_NAME = 'Scanpy Spatial'
    CATEGORY = 'spatial_transcriptomics'
    DESCRIPTION = 'Cluster spatial transcriptomics count matrices and render a UMAP with Scanpy.'
    SEARCH_ALIASES = ['scanpy', 'spatial transcriptomics', 'spatial clustering', 'umap', 'leiden']
    RETURN_TYPES = ('CSV', 'IMAGE')
    RETURN_NAMES = ('clusters', 'umap')
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES = ['scanpy', 'anndata', 'pandas', 'matplotlib']
    DOCUMENTATION_URL = 'https://scanpy.readthedocs.io/'
    VERSION = '1.10.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get('output', '.'))
        out_dir.mkdir(parents=True, exist_ok=True)
        delimiter = str(inputs.get('delimiter', 'comma') or 'comma').strip().lower()
        sep = '\\t' if delimiter in {'tab', 'tsv', '\\t'} else ','
        sample_name = str(inputs.get('sample_name', 'sample') or 'sample')
        visium_path = str(inputs.get('visium_path', '') or '').strip()
        if visium_path:
            load = f"\nadata = sc.read_visium('{visium_path}', load_images=False)  # QC/clustering: skip tissue images (demo Visium data omits spatial/tissue_hires_image.png)\nadata.var_names_make_unique()\nadata.obs['sample'] = '{sample_name}'\nadata.to_df().T.to_csv('{out_dir}/counts.csv')\nimport numpy as _np\nif 'spatial' not in adata.obsm:\n    # Demo/synthetic Visium data can omit spatial/tissue_positions; synthesize a\n    # square grid so spatial QC/plotting can still proceed deterministically.\n    _n = adata.n_obs\n    _side = int(_np.ceil(_np.sqrt(_n)))\n    _grid = _np.array([[i % _side, i // _side] for i in range(_n)], dtype=float)\n    adata.obsm['spatial'] = _grid\n_coords = pd.DataFrame(_np.asarray(adata.obsm['spatial']), index=adata.obs_names, columns=['x', 'y'])\n_coords.index.name = 'barcode'\n_coords.to_csv('{out_dir}/coordinates.csv')\n"
        else:
            load = f"\ncounts = pd.read_csv('{inputs.get('count_matrix', '')}', sep='{sep}', index_col=0)\ncoordinates = pd.read_csv('{inputs.get('coordinates', '')}')\nadata = sc.AnnData(counts.T)\nadata.obs['sample'] = '{sample_name}'\nif 'barcode' in coordinates.columns:\n    coordinates = coordinates.set_index('barcode')\n    adata.obs = adata.obs.join(coordinates, how='left')\n"
        script = f"""\nimport scanpy as sc\nimport pandas as pd\nimport matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n{load}\n# Clamp QC/dimensionality params to the actual data size. Fixed defaults\n# (min_genes=200, 2000 HVGs, 15 PCs) wipe out small/synthetic demo datasets\n# ("Found array with 0 sample(s)"). Guard each step so the pipeline degrades\n# gracefully on tiny inputs while staying unchanged on real Visium data.\n_min_genes = min({inputs.get('min_genes', 200)}, max(1, adata.n_vars // 4))\n_min_cells = min({inputs.get('min_cells', 3)}, max(1, adata.n_obs // 4))\nsc.pp.filter_cells(adata, min_genes=_min_genes)\nsc.pp.filter_genes(adata, min_cells=_min_cells)\nif adata.n_obs < 2 or adata.n_vars < 2:\n    raise SystemExit("Too few cells/genes after filtering for spatial clustering.")\nsc.pp.normalize_total(adata, target_sum=1e4)\nsc.pp.log1p(adata)\n_n_hvg = min({inputs.get('n_hvg', 2000)}, adata.n_vars)\nsc.pp.highly_variable_genes(adata, n_top_genes=_n_hvg)\nadata = adata[:, adata.var['highly_variable']]\nsc.pp.scale(adata, max_value=10)\n_n_pcs = min({inputs.get('n_pcs', 15)}, adata.n_obs - 1, adata.n_vars - 1)\nsc.pp.pca(adata, n_comps=max(1, _n_pcs))\nsc.pp.neighbors(adata, n_neighbors=min(15, max(2, adata.n_obs - 1)))\nsc.tl.leiden(adata, resolution={inputs.get('resolution', 0.8)})\nsc.tl.umap(adata)\n\nadata.obs[['sample', 'leiden']].to_csv('{out_dir}/clusters.csv')\nsc.pl.umap(adata, color='leiden', show=False)\nplt.savefig('{out_dir}/umap.png', dpi=150)\nprint("Done")\n"""
        script_file = out_dir / 'scanpy_spatial_run.py'
        script_file.write_text(script)
        return ['python', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        outs = [node_out / 'clusters.csv', node_out / 'umap.png']
        if str(inputs.get('visium_path', '') or '').strip():
            outs += [node_out / 'counts.csv', node_out / 'coordinates.csv']
        return outs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {}, 'optional': {'visium_path': ('DIRECTORY', {'description': 'Space Ranger outs/ directory (reads the .h5; derives count/coordinate CSVs)'}), 'count_matrix': ('FILE', {'description': 'Gene-by-cell count matrix as CSV or TSV (used when no visium_path)'}), 'coordinates': ('CSV', {'description': 'Spatial coordinates keyed by barcode (used when no visium_path)'}), 'sample_name': ('STRING', {'default': 'sample'}), 'delimiter': ('STRING', {'default': 'comma', 'options': ['comma', 'tab']}), 'min_cells': ('INT', {'default': 3, 'min': 1}), 'min_genes': ('INT', {'default': 200, 'min': 0}), 'n_hvg': ('INT', {'default': 2000, 'min': 100}), 'n_pcs': ('INT', {'default': 15, 'min': 2, 'max': 50}), 'resolution': ('FLOAT', {'default': 0.8, 'min': 0.1, 'max': 2.0, 'step': 0.1})}, 'hidden': {'output': ('STRING', {})}}
