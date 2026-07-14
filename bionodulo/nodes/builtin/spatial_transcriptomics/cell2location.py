"""cell2location — spatial_transcriptomics node(s). One tool per file (extracted from spatial_transcriptomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class Cell2locationNode(CommandNode):
    """Deconvolute spatial spots into cell type proportions."""
    NODE_ID = 'cell2location'
    DISPLAY_NAME = 'Cell2location'
    CATEGORY = 'spatial_transcriptomics'
    DESCRIPTION = 'Deconvolute spatial transcriptomics spots into cell type proportions using scRNA-seq reference.'
    SEARCH_ALIASES = ['cell2location', 'spatial deconvolution', 'cell type mapping', 'cell2loc']
    RETURN_TYPES = ('H5AD', 'IMAGE')
    RETURN_NAMES = ('spatial_deconv', 'celltype_map')
    REQUIRED_EXECUTABLES = ['python']
    REQUIRED_CONDA_PACKAGES = ['cell2location', 'torch', 'scanpy', 'anndata']
    DOCUMENTATION_URL = 'https://cell2location.readthedocs.io/'
    VERSION = '0.1.7'
    SHELL = True
    EXPERIMENTAL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get('output', '.'))
        out_dir.mkdir(parents=True, exist_ok=True)
        script = f"""\nimport cell2location\nimport scanpy as sc\nimport matplotlib\nmatplotlib.use('Agg')\nimport matplotlib.pyplot as plt\n\nadata_vis = sc.read_h5ad('{inputs.get('visium_adata', '')}')\nadata_ref = sc.read_h5ad('{inputs.get('scrna_adata', '')}')\n\nfrom cell2location.models import RegressionModel\nRegressionModel.setup_anndata(adata_ref, labels_key='{inputs.get('cell_type_key', 'cell_type')}')\nmod = RegressionModel(adata_ref)\nmod.train(max_epochs={inputs.get('ref_epochs', 250)})\nadata_ref = mod.export_posterior(adata_ref)\ninf_aver = adata_ref.varm['means_per_cluster_mu_fg']\n\nfrom cell2location.models import Cell2location\nCell2location.setup_anndata(adata_vis)\nmod = Cell2location(adata_vis, cell_state_df=inf_aver,\n                    N_cells_per_location={inputs.get('n_cells_per_spot', 30)})\nmod.train(max_epochs={inputs.get('deconv_epochs', 30000)})\nadata_vis = mod.export_posterior(adata_vis)\nadata_vis.write('{out_dir}/spatial_deconv.h5ad')\nadata_vis.obsm['q05_cell_abundance_w_sf'].to_csv('{out_dir}/celltype_map.csv')\nprint("Done")\n"""
        script_file = out_dir / 'cell2location_run.py'
        script_file.write_text(script)
        return ['python', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'spatial_deconv.h5ad', node_out / 'celltype_map.csv']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'visium_adata': ('H5AD', {'description': 'Visium AnnData'}), 'scrna_adata': ('H5AD', {'description': 'scRNA-seq reference with cell types'}), 'cell_type_key': ('STRING', {'default': 'cell_type'})}, 'optional': {'ref_epochs': ('INT', {'default': 250, 'min': 10}), 'deconv_epochs': ('INT', {'default': 30000, 'min': 1000}), 'n_cells_per_spot': ('INT', {'default': 30, 'min': 1})}, 'hidden': {'output': ('STRING', {})}}
