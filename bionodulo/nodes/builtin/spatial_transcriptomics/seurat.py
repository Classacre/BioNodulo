"""seurat — spatial_transcriptomics node(s). One tool per file (extracted from spatial_transcriptomics.py)."""
from __future__ import annotations
from pathlib import Path
from typing import Any
from bionodulo.nodes.command_node import CommandNode


class SeuratSpatialNode(CommandNode):
    """Cluster spatial transcriptomics count matrices with Seurat."""
    NODE_ID = 'seurat_spatial'
    DISPLAY_NAME = 'Seurat Spatial'
    CATEGORY = 'spatial_transcriptomics'
    DESCRIPTION = 'Cluster spatial transcriptomics count matrices and export markers with Seurat.'
    SEARCH_ALIASES = ['seurat', 'spatial transcriptomics', 'visium', 'spatial clustering', 'markers']
    RETURN_TYPES = ('CSV', 'CSV', 'IMAGE')
    RETURN_NAMES = ('clusters', 'markers', 'spatial_plot')
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_CONDA_PACKAGES = ['r-base', 'r-seurat', 'r-ggplot2', 'r-patchwork']
    DOCUMENTATION_URL = 'https://satijalab.org/seurat/'
    VERSION = '5.0.0'
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(inputs.get('output', '.'))
        out_dir.mkdir(parents=True, exist_ok=True)
        sample_name = str(inputs.get('sample_name', 'sample') or 'sample')
        normalization_method = str(inputs.get('normalization_method', 'LogNormalize') or 'LogNormalize')
        dims = int(inputs.get('dims', 15) or 15)
        normalize_line = 'object <- SCTransform(object, verbose = FALSE)' if normalization_method.upper() == 'SCT' else 'object <- NormalizeData(object)'
        script = f"""\nlibrary(Seurat)\nlibrary(ggplot2)\nlibrary(patchwork)\n\ncounts <- Read10X(data.dir = '{inputs.get('count_matrix', '')}')\nobject <- CreateSeuratObject(counts = counts, project = '{sample_name}', min.features = {inputs.get('min_features', 200)})\n{normalize_line}\nobject <- FindVariableFeatures(object)\nobject <- ScaleData(object)\nobject <- RunPCA(object, verbose = FALSE)\nobject <- FindNeighbors(object, dims = 1:{dims})\nobject <- FindClusters(object, resolution = {inputs.get('resolution', 0.8)})\nobject <- RunUMAP(object, dims = 1:{dims})\n\ncluster_table <- data.frame(\n  barcode = colnames(object),\n  cluster = Idents(object)\n)\nmarkers <- FindAllMarkers(object, only.pos = TRUE)\nplot <- DimPlot(object, reduction = 'umap', group.by = 'seurat_clusters') +\n  ggtitle('Seurat spatial clusters') +\n  theme_minimal()\n\nwrite.csv(cluster_table, '{out_dir}/clusters.csv', row.names = FALSE)\nwrite.csv(markers, '{out_dir}/markers.csv', row.names = FALSE)\nggsave('{out_dir}/spatial_plot.png', plot = plot, width = 8, height = 6, dpi = 150)\nprint("Done")\n"""
        script_file = out_dir / 'seurat_spatial_run.R'
        script_file.write_text(script)
        return ['Rscript', str(script_file)]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / 'clusters.csv', node_out / 'markers.csv', node_out / 'spatial_plot.png']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'count_matrix': ('DIRECTORY', {'description': '10x feature-barcode matrix directory'}), 'image': ('FILE', {'description': 'Tissue image associated with the spatial sample'})}, 'optional': {'sample_name': ('STRING', {'default': 'sample'}), 'min_features': ('INT', {'default': 200, 'min': 0}), 'normalization_method': ('STRING', {'default': 'LogNormalize', 'options': ['LogNormalize', 'SCT']}), 'dims': ('INT', {'default': 15, 'min': 2, 'max': 50}), 'resolution': ('FLOAT', {'default': 0.8, 'min': 0.1, 'max': 2.0, 'step': 0.1})}, 'hidden': {'output': ('STRING', {})}}
