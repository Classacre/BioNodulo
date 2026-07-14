"""anndata — single_cell node(s). One tool per file (extracted from wrapped_core_data.py)."""
from __future__ import annotations
from bionodulo.nodes.builtin._wrapped_tool_utils import *
class _DatamashBaseNode(CommandNode):
    """Shared metadata and helpers for GNU Datamash Galaxy wrappers."""
    REQUIRED_CONDA_PACKAGES = ['datamash']
    CATEGORY = 'data_transform'
    RETURN_TYPES = ('TSV',)
    RETURN_NAMES = ('out_file',)
    DOCUMENTATION_URL = DATAMASH_DOCUMENTATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [DATAMASH_CITATION_URL]
    CITATION_TEXT = DATAMASH_CITATION_TEXT
    VERSION = '1.9'
    SHELL = True
    INPUT_EXT_OPTIONS = ['tabular', 'tsv', 'csv']

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('input_ext', 'tabular') or 'tabular')

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/out_file.tsv'

    @classmethod
    def _separator_args(cls, inputs: dict[str, Any]) -> list[str]:
        return ['-t', ','] if cls._input_ext(inputs) == 'csv' else []

    @classmethod
    def _redirect_stdin_stdout(cls, cmd: list[str], inputs: dict[str, Any]) -> str:
        cmd.extend(['>', cls._output_path(inputs)])
        input_file = shlex.quote(str(inputs.get('in_file', '')))
        return _shell_join(cmd).replace(' > ', f' < {input_file} > ')

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'out_file.tsv']

    @classmethod
    def _validate_common(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('in_file', '')).strip():
            return 'in_file is required'
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.INPUT_EXT_OPTIONS:
            return f"input_ext must be one of: {', '.join(cls.INPUT_EXT_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'in_file': ('TSV', {'description': 'Input tabular, TSV, or CSV dataset'})}, 'optional': {'input_ext': ('STRING', {'default': 'tabular', 'options': cls.INPUT_EXT_OPTIONS, 'description': 'Input file format'})}, 'hidden': {'output': ('STRING', {})}}


class AnnDataExportNode(CommandNode):
    """Export AnnData H5AD matrices and annotations to tabular files."""
    NODE_ID = 'anndata_export'
    DISPLAY_NAME = 'Export AnnData'
    REQUIRED_CONDA_PACKAGES = ['anndata', 'scanpy', 'loompy', 'pandas']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Export an AnnData H5AD matrix and annotations to tabular files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AnnData', 'anndata_export', 'Export AnnData', 'H5AD', 'write_csvs', 'obs annotations', 'var annotations', 'single-cell matrix export']
    RETURN_TYPES = ('TSV', 'TSV', 'TSV', 'TSV', 'TSV')
    RETURN_NAMES = ('tabular_x', 'tabular_obs', 'tabular_obsm', 'tabular_var', 'tabular_varm')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.write_csvs.html'
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}']
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = '0.11.4+galaxy3'
    SHELL = True
    OUTPUT_FILES = ['X.csv', 'obs.csv', 'obsm.csv', 'var.csv', 'varm.csv']

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return f'{_out(inputs)}/anndata_export.py'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        input_path = str(inputs.get('input', ''))
        return '\n'.join(['import anndata as ad', f"adata = ad.read_h5ad({input_path!r}, backed='r')", 'adata.write_csvs(\'.\', sep="\\t", skip_data=False)'])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = cls._script_path(inputs)
        return f"mkdir -p {shlex.quote(out)} && cat > {shlex.quote(script_path)} <<'PY'\n{cls._script_body(inputs)}\nPY\ncd {shlex.quote(out)} && python {shlex.quote(Path(script_path).name)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / filename for filename in cls.OUTPUT_FILES]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('H5AD', {'description': 'Annotated data matrix to export'})}, 'hidden': {'output': ('STRING', {})}}


class AnnDataImportNode(CommandNode):
    """Create AnnData H5AD objects from loom, tabular, 10x, MTX, UMI-tools, or annotated matrices."""
    NODE_ID = 'anndata_import'
    DISPLAY_NAME = 'Import Anndata'
    REQUIRED_CONDA_PACKAGES = ['anndata', 'scanpy', 'loompy', 'pandas']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Create an AnnData H5AD object from loom, tabular, 10x, MTX, UMI-tools, or annotated matrix inputs.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AnnData', 'anndata_import', 'Import Anndata', 'H5AD', 'read_loom', 'read_csv', 'read_10x_h5', 'read_10x_mtx', 'read_mtx', 'read_umi_tools', 'Matrix Market', 'UMI-tools']
    RETURN_TYPES = ('H5AD',)
    RETURN_NAMES = ('anndata',)
    REQUIRED_EXECUTABLES = ['python', 'gzip']
    DOCUMENTATION_URL = 'https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html'
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}']
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = '0.11.4+galaxy3'
    SHELL = True
    ADATA_FORMATS = ['loom', 'tabular', '10x_h5', 'mtx', 'umi_tools', 'custom']
    TENX_USES = ['no', 'legacy_10x', 'v3_10x']
    VAR_NAMES = ['gene_symbols', 'gene_ids']

    @classmethod
    def _adata_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('adata_format', 'loom') or 'loom')

    @classmethod
    def _tenx_use(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('tenx_use', 'no') or 'no')

    @classmethod
    def _bool_text(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return 'False' if value.lower() in {'false', '0', 'no'} else 'True'
        return 'True' if bool(value) else 'False'

    @classmethod
    def _delimiter(cls, inputs: dict[str, Any]) -> str:
        delimiter = str(inputs.get('delimiter', '\\t') or '\\t')
        if delimiter.lower() in {'tab', 'tabular', 'tsv', '\\t'}:
            return '\\t'
        return delimiter

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        adata_format = cls._adata_format(inputs)
        lines = ['import anndata as ad']
        if adata_format == 'loom':
            lines.extend(['adata = ad.read_loom(', f"    {str(inputs.get('input', ''))!r},", f"    sparse={cls._bool_text(inputs, 'sparse', True)},", f"    cleanup={cls._bool_text(inputs, 'cleanup', False)},", f"    X_name={str(inputs.get('x_name', 'spliced'))!r},", f"    obs_names={str(inputs.get('obs_names', 'CellID'))!r},", f"    var_names={str(inputs.get('var_names', 'Gene'))!r})"])
        elif adata_format == 'tabular':
            lines.extend(['from scipy.sparse import csr_matrix', f"adata = ad.read_csv({str(inputs.get('input', ''))!r}, delimiter={cls._delimiter(inputs)!r}, first_column_names={cls._bool_text(inputs, 'first_column_names', True)})", 'adata.X = csr_matrix(adata.X)'])
        elif adata_format == '10x_h5':
            lines.extend(['import scanpy as sc', f"adata = sc.read_10x_h5({str(inputs.get('input', ''))!r})"])
        elif adata_format == 'mtx':
            tenx_use = cls._tenx_use(inputs)
            if tenx_use == 'no':
                lines.append(f"adata = ad.read_mtx(filename={str(inputs.get('matrix', ''))!r})")
            else:
                lines.extend(['import scanpy as sc', f"adata = sc.read_10x_mtx('mtx', var_names={str(inputs.get('var_names', 'gene_symbols'))!r}, make_unique={cls._bool_text(inputs, 'make_unique', True)}, cache=False, gex_only={cls._bool_text(inputs, 'gex_only', True)})"])
        elif adata_format == 'umi_tools':
            lines.append("adata = ad.read_umi_tools('umi_tools_input.gz')")
        else:
            lines.extend(['import pandas as pd', f"adata = ad.read_mtx(filename={str(inputs.get('mtx', ''))!r})", 'adata = adata.transpose().copy()', f"obs = pd.read_csv({str(inputs.get('obs', ''))!r}, sep='\\t', index_col=0)", f"var = pd.read_csv({str(inputs.get('var', ''))!r}, sep='\\t', index_col=0)", 'if adata.shape[0] != obs.shape[0]:', '    raise ValueError(f"Mismatch: adata has {adata.shape[0]} cells, but obs has {obs.shape[0]} rows.")', 'if adata.shape[1] != var.shape[0]:', '    raise ValueError(f"Mismatch: adata has {adata.shape[1]} genes, but var has {var.shape[0]} rows.")', 'adata.obs = obs', 'adata.var = var'])
        lines.extend(["adata.write('anndata.h5ad', compression='gzip')", 'print(adata)'])
        return '\n'.join(lines)

    @classmethod
    def _stage_commands(cls, inputs: dict[str, Any]) -> list[str]:
        adata_format = cls._adata_format(inputs)
        if adata_format == 'umi_tools':
            return [f"gzip -c {shlex.quote(str(inputs.get('input', '')))} > umi_tools_input.gz"]
        if adata_format != 'mtx':
            return []
        tenx_use = cls._tenx_use(inputs)
        if tenx_use == 'no':
            return []
        commands = ['mkdir -p mtx', f"cp {shlex.quote(str(inputs.get('matrix', '')))} mtx/matrix.mtx"]
        if tenx_use == 'legacy_10x':
            commands.extend([f"cp {shlex.quote(str(inputs.get('genes', '')))} mtx/genes.tsv", f"cp {shlex.quote(str(inputs.get('barcodes', '')))} mtx/barcodes.tsv"])
        else:
            commands.extend(['gzip mtx/matrix.mtx', f"cp {shlex.quote(str(inputs.get('features', '')))} mtx/features.tsv", 'gzip mtx/features.tsv', f"cp {shlex.quote(str(inputs.get('barcodes', '')))} mtx/barcodes.tsv", 'gzip mtx/barcodes.tsv'])
        return commands

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f'mkdir -p {shlex.quote(out)}', f'cd {shlex.quote(out)}', *cls._stage_commands(inputs)]
        commands.append(f"cat > anndata_import.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_import.py")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / 'anndata.h5ad']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        adata_format = cls._adata_format(inputs)
        if adata_format not in cls.ADATA_FORMATS:
            return f"adata_format must be one of: {', '.join(cls.ADATA_FORMATS)}"
        if adata_format in {'loom', 'tabular', '10x_h5', 'umi_tools'} and (not str(inputs.get('input', '')).strip()):
            return f'input is required when adata_format is {adata_format}'
        if adata_format == 'mtx':
            if not str(inputs.get('matrix', '')).strip():
                return 'matrix is required when adata_format is mtx'
            tenx_use = cls._tenx_use(inputs)
            if tenx_use not in cls.TENX_USES:
                return f"tenx_use must be one of: {', '.join(cls.TENX_USES)}"
            if tenx_use == 'legacy_10x':
                if not str(inputs.get('genes', '')).strip():
                    return 'genes is required when tenx_use is legacy_10x'
                if not str(inputs.get('barcodes', '')).strip():
                    return 'barcodes is required when tenx_use is legacy_10x'
            if tenx_use == 'v3_10x':
                if not str(inputs.get('features', '')).strip():
                    return 'features is required when tenx_use is v3_10x'
                if not str(inputs.get('barcodes', '')).strip():
                    return 'barcodes is required when tenx_use is v3_10x'
        if adata_format == 'custom':
            for key in ('mtx', 'obs', 'var'):
                if not str(inputs.get(key, '')).strip():
                    return f'{key} is required when adata_format is custom'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'optional': {'adata_format': ('STRING', {'default': 'loom', 'options': cls.ADATA_FORMATS}), 'input': ('FILE', {'default': '', 'description': 'Input loom, tabular, 10x H5, or UMI-tools matrix'}), 'sparse': ('BOOLEAN', {'default': True}), 'cleanup': ('BOOLEAN', {'default': False}), 'x_name': ('STRING', {'default': 'spliced'}), 'obs_names': ('STRING', {'default': 'CellID'}), 'var_names': ('STRING', {'default': 'Gene', 'options': ['Gene', *cls.VAR_NAMES]}), 'delimiter': ('STRING', {'default': '\\t', 'options': ['\\t', ',']}), 'first_column_names': ('BOOLEAN', {'default': True}), 'matrix': ('FILE', {'default': '', 'description': 'Matrix Market file for MTX import'}), 'tenx_use': ('STRING', {'default': 'no', 'options': cls.TENX_USES}), 'genes': ('TSV', {'default': '', 'description': 'Cell Ranger v2 genes.tsv'}), 'features': ('TSV', {'default': '', 'description': 'Cell Ranger v3 features.tsv'}), 'barcodes': ('TSV', {'default': '', 'description': '10x barcodes.tsv'}), 'make_unique': ('BOOLEAN', {'default': True}), 'gex_only': ('BOOLEAN', {'default': True}), 'mtx': ('FILE', {'default': '', 'description': 'Custom Matrix Market count matrix'}), 'obs': ('TSV', {'default': '', 'description': 'Custom cell annotations'}), 'var': ('TSV', {'default': '', 'description': 'Custom gene annotations'})}, 'hidden': {'output': ('STRING', {})}}


class AnnDataInspectNode(CommandNode):
    """Inspect AnnData H5AD matrices, annotations, embeddings, and unstructured results."""
    NODE_ID = 'anndata_inspect'
    DISPLAY_NAME = 'Inspect AnnData'
    REQUIRED_CONDA_PACKAGES = ['anndata', 'scanpy', 'loompy', 'pandas']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Inspect AnnData H5AD matrices, annotations, embeddings, and unstructured analysis results.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AnnData', 'anndata_inspect', 'Inspect AnnData', 'H5AD', 'chunk_X', 'obs', 'var', 'uns', 'obsm', 'varm', 'rank_genes_groups', 'X_draw_graph']
    RETURN_TYPES = ('TXT', 'TSV', 'TSV', 'TSV', 'TSV', 'FILE', 'FILE', 'FILE', 'FILE', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'TSV', 'DIRECTORY', 'TSV', 'TSV')
    RETURN_NAMES = ('general', 'X', 'obs', 'var', 'chunk_X', 'uns_neighbors_connectivities', 'uns_neighbors_distances', 'uns_paga_connectivities', 'uns_paga_connectivities_tree', 'uns_pca_variance', 'uns_pca_variance_ratio', 'uns_rank_genes_groups_names', 'uns_rank_genes_groups_scores', 'uns_rank_genes_groups_logfoldchanges', 'uns_rank_genes_groups_pvals', 'uns_rank_genes_groups_pvals_adj', 'obsm_X_pca', 'obsm_X_umap', 'obsm_X_tsne', 'obsm_X_draw_graph', 'obsm_X_diffmap', 'varm_PCs')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html'
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}']
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = '0.11.4+galaxy3'
    SHELL = True
    INFO_OPTIONS = ['general', 'obs', 'var', 'X', 'chunk_X', 'uns', 'obsm', 'varm']
    CHUNK_OPTIONS = ['random', 'specified']
    UNS_OPTIONS = ['neighbors', 'paga', 'pca', 'rank_genes_groups']
    OBSM_OPTIONS = ['X_pca', 'X_umap', 'X_tsne', 'X_draw_graph', 'X_diffmap']
    VARM_OPTIONS = ['PCs']

    @classmethod
    def _info(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('info', 'general') or 'general')

    @classmethod
    def _bool_text(cls, inputs: dict[str, Any], key: str, default: bool) -> str:
        value = inputs.get(key, default)
        if isinstance(value, str):
            return 'False' if value.lower() in {'false', '0', 'no'} else 'True'
        return 'True' if bool(value) else 'False'

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _common_script_prefix(cls, inputs: dict[str, Any]) -> list[str]:
        return ['import anndata as ad', 'import pandas as pd', 'from scipy import io', 'pd.options.display.precision = 15', f"adata = ad.read_h5ad({str(inputs.get('input', ''))!r}, backed='r')"]

    @classmethod
    def _specified_chunk_select(cls, inputs: dict[str, Any]) -> list[int]:
        return [int(value.strip()) for value in str(inputs.get('chunk_list', '')).split(',') if value.strip()]

    @classmethod
    def _branch_script(cls, inputs: dict[str, Any]) -> list[str]:
        info = cls._info(inputs)
        if info == 'general':
            return [f"with open({cls._path(inputs, 'general.txt')!r}, 'w', encoding='utf-8') as f:", '    print(adata, file=f)']
        if info == 'X':
            return [f"adata.to_df().to_csv({cls._path(inputs, 'X.tsv')!r}, sep='\\t')"]
        if info == 'obs':
            return [f"adata.obs.to_csv({cls._path(inputs, 'obs.tsv')!r}, sep='\\t')"]
        if info == 'var':
            return [f"adata.var.to_csv({cls._path(inputs, 'var.tsv')!r}, sep='\\t')"]
        if info == 'chunk_X':
            if str(inputs.get('chunk_info', 'random') or 'random') == 'specified':
                lines = [f'X = adata.chunk_X(select={cls._specified_chunk_select(inputs)!r})']
            else:
                lines = [f"X = adata.chunk_X(select={int(inputs.get('chunk_size', 1000) or 1000)}, replace={cls._bool_text(inputs, 'chunk_replace', True)})"]
            lines.append(f"pd.DataFrame(X).to_csv({cls._path(inputs, 'chunk_X.tsv')!r}, sep='\\t')")
            return lines
        if info == 'uns':
            uns_info = str(inputs.get('uns_info', 'neighbors') or 'neighbors')
            if uns_info == 'neighbors':
                return [f"io.mmwrite({cls._path(inputs, 'uns_neighbors_connectivities.mtx')!r}, adata.obsp['connectivities'])", f"io.mmwrite({cls._path(inputs, 'uns_neighbors_distances.mtx')!r}, adata.obsp['distances'])"]
            if uns_info == 'paga':
                return [f"io.mmwrite({cls._path(inputs, 'uns_paga_connectivities.mtx')!r}, adata.uns['paga']['connectivities'])", f"io.mmwrite({cls._path(inputs, 'uns_paga_connectivities_tree.mtx')!r}, adata.uns['paga']['connectivities_tree'])"]
            if uns_info == 'pca':
                return [f"pd.DataFrame(adata.uns['pca']['variance']).to_csv({cls._path(inputs, 'uns_pca_variance.tsv')!r}, sep='\\t', index=False)", f"pd.DataFrame(adata.uns['pca']['variance_ratio']).to_csv({cls._path(inputs, 'uns_pca_variance_ratio.tsv')!r}, sep='\\t', index=False)"]
            return [f"pd.DataFrame(adata.uns['rank_genes_groups']['logfoldchanges']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_logfoldchanges.tsv')!r}, sep='\\t', index=False)", f"pd.DataFrame(adata.uns['rank_genes_groups']['names']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_names.tsv')!r}, sep='\\t', index=False)", f"pd.DataFrame(adata.uns['rank_genes_groups']['pvals']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_pvals.tsv')!r}, sep='\\t', index=False)", f"pd.DataFrame(adata.uns['rank_genes_groups']['pvals_adj']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_pvals_adj.tsv')!r}, sep='\\t', index=False)", f"pd.DataFrame(adata.uns['rank_genes_groups']['scores']).to_csv({cls._path(inputs, 'uns_rank_genes_groups_scores.tsv')!r}, sep='\\t', index=False)"]
        if info == 'obsm':
            obsm_info = str(inputs.get('obsm_info', 'X_pca') or 'X_pca')
            if obsm_info == 'X_draw_graph':
                return ['for key in adata.obsm.keys():', "    if key.startswith('X_draw_graph'):", f"        pd.DataFrame(adata.obsm[key]).to_csv(f'{cls._path(inputs, 'obsm_X_draw_graph')}/{{key}}.tsv', sep='\\t', index=False)"]
            filename = f'obsm_{obsm_info}.tsv'
            return [f"pd.DataFrame(adata.obsm[{obsm_info!r}]).to_csv({cls._path(inputs, filename)!r}, sep='\\t', index=False)"]
        return [f"pd.DataFrame(adata.varm['PCs']).to_csv({cls._path(inputs, 'varm_PCs.tsv')!r}, sep='\\t', index=False)"]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        return '\n'.join([*cls._common_script_prefix(inputs), *cls._branch_script(inputs)])

    @classmethod
    def _pre_commands(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._info(inputs) == 'obsm' and str(inputs.get('obsm_info', 'X_pca') or 'X_pca') == 'X_draw_graph':
            return [f"mkdir -p {shlex.quote(cls._path(inputs, 'obsm_X_draw_graph'))}"]
        return []

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f'mkdir -p {shlex.quote(out)}', f'cd {shlex.quote(out)}', *cls._pre_commands(inputs)]
        commands.append(f"cat > anndata_inspect.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_inspect.py")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        info = cls._info(inputs)
        if info == 'general':
            return [out / 'general.txt']
        if info == 'X':
            return [out / 'X.tsv']
        if info == 'obs':
            return [out / 'obs.tsv']
        if info == 'var':
            return [out / 'var.tsv']
        if info == 'chunk_X':
            return [out / 'chunk_X.tsv']
        if info == 'uns':
            uns_info = str(inputs.get('uns_info', 'neighbors') or 'neighbors')
            if uns_info == 'neighbors':
                return [out / 'uns_neighbors_connectivities.mtx', out / 'uns_neighbors_distances.mtx']
            if uns_info == 'paga':
                return [out / 'uns_paga_connectivities.mtx', out / 'uns_paga_connectivities_tree.mtx']
            if uns_info == 'pca':
                return [out / 'uns_pca_variance.tsv', out / 'uns_pca_variance_ratio.tsv']
            return [out / 'uns_rank_genes_groups_names.tsv', out / 'uns_rank_genes_groups_scores.tsv', out / 'uns_rank_genes_groups_logfoldchanges.tsv', out / 'uns_rank_genes_groups_pvals.tsv', out / 'uns_rank_genes_groups_pvals_adj.tsv']
        if info == 'obsm':
            obsm_info = str(inputs.get('obsm_info', 'X_pca') or 'X_pca')
            if obsm_info == 'X_draw_graph':
                directory = out / 'obsm_X_draw_graph'
                directory.mkdir(parents=True, exist_ok=True)
                return [directory]
            return [out / f'obsm_{obsm_info}.tsv']
        return [out / 'varm_PCs.tsv']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        info = cls._info(inputs)
        if info not in cls.INFO_OPTIONS:
            return f"info must be one of: {', '.join(cls.INFO_OPTIONS)}"
        if info == 'chunk_X':
            chunk_info = str(inputs.get('chunk_info', 'random') or 'random')
            if chunk_info not in cls.CHUNK_OPTIONS:
                return f"chunk_info must be one of: {', '.join(cls.CHUNK_OPTIONS)}"
            if chunk_info == 'specified' and (not str(inputs.get('chunk_list', '')).strip()):
                return 'chunk_list is required when chunk_info is specified'
        if info == 'uns' and str(inputs.get('uns_info', 'neighbors') or 'neighbors') not in cls.UNS_OPTIONS:
            return f"uns_info must be one of: {', '.join(cls.UNS_OPTIONS)}"
        if info == 'obsm' and str(inputs.get('obsm_info', 'X_pca') or 'X_pca') not in cls.OBSM_OPTIONS:
            return f"obsm_info must be one of: {', '.join(cls.OBSM_OPTIONS)}"
        if info == 'varm' and str(inputs.get('varm_info', 'PCs') or 'PCs') not in cls.VARM_OPTIONS:
            return f"varm_info must be one of: {', '.join(cls.VARM_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('H5AD', {'description': 'Annotated data matrix to inspect'})}, 'optional': {'info': ('STRING', {'default': 'general', 'options': cls.INFO_OPTIONS}), 'chunk_info': ('STRING', {'default': 'random', 'options': cls.CHUNK_OPTIONS}), 'chunk_size': ('INT', {'default': 1000, 'min': 1}), 'chunk_replace': ('BOOLEAN', {'default': True}), 'chunk_list': ('STRING', {'default': ''}), 'uns_info': ('STRING', {'default': 'neighbors', 'options': cls.UNS_OPTIONS}), 'obsm_info': ('STRING', {'default': 'X_pca', 'options': cls.OBSM_OPTIONS}), 'varm_info': ('STRING', {'default': 'PCs', 'options': cls.VARM_OPTIONS})}, 'hidden': {'output': ('STRING', {})}}


class AnnDataManipulateNode(CommandNode):
    """Manipulate AnnData H5AD objects using the Galaxy IUC AnnData wrapper operations."""
    NODE_ID = 'anndata_manipulate'
    DISPLAY_NAME = 'Manipulate AnnData'
    REQUIRED_CONDA_PACKAGES = ['anndata', 'scanpy', 'loompy', 'pandas']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Manipulate AnnData H5AD objects by concatenating, renaming, annotating, copying, splitting, or transposing.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'AnnData', 'anndata_manipulate', 'Manipulate AnnData', 'H5AD', 'concatenate', 'obs_names_make_unique', 'var_names_make_unique', 'rename_categories', 'remove_keys', 'flag_genes', 'rename_obs', 'rename_var', 'strings_to_categoricals', 'transpose', 'add_annotation', 'split_on_obs', 'copy_obs', 'copy_uns', 'copy_embed', 'copy_layers', 'copy_X', 'save_raw']
    RETURN_TYPES = ('H5AD', 'DIRECTORY')
    RETURN_NAMES = ('anndata', 'output_h5ad_split')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html'
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f'{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}']
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = '0.11.4+galaxy3'
    SHELL = True
    FUNCTIONS = ['concatenate', 'obs_names_make_unique', 'var_names_make_unique', 'rename_categories', 'remove_keys', 'flag_genes', 'rename_obs', 'rename_var', 'strings_to_categoricals', 'transpose', 'add_annotation', 'split_on_obs', 'copy_obs', 'copy_uns', 'copy_embed', 'copy_layers', 'copy_X', 'save_raw']
    JOIN_OPTIONS = ['-', '_', ' ', '/']
    CONCAT_JOIN_OPTIONS = ['inner', 'outer']
    UNS_MERGE_OPTIONS = ['None', 'same', 'unique', 'first', 'only']
    ANNOTATION_TARGETS = ['var', 'obs']

    @classmethod
    def _function(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('function', 'concatenate') or 'concatenate')

    @staticmethod
    def _bool_value(value: Any, default: bool=False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() not in {'false', '0', 'no', ''}
        return bool(value)

    @staticmethod
    def _repeat_dicts(value: Any) -> list[dict[str, Any]]:
        if value is None or value == '':
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, (list, tuple)):
            rows: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, dict):
                    rows.append(item)
                else:
                    rows.append({'source_key': item})
            return rows
        return [{'source_key': value}]

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f'{_out(inputs)}/{filename}'

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        lines = ['import anndata as ad', f"adata = ad.read_h5ad({str(inputs.get('input', ''))!r}, backed='r')", *cls._branch_script(inputs)]
        if cls._function(inputs) != 'split_on_obs':
            lines.extend(["adata.write('anndata.h5ad', compression='gzip')", 'print(adata)'])
        return '\n'.join(lines)

    @classmethod
    def _branch_script(cls, inputs: dict[str, Any]) -> list[str]:
        function = cls._function(inputs)
        if function == 'concatenate':
            lines = ['adata = adata.to_memory()']
            other_adatas = _as_list(inputs.get('other_adatas'))
            for index, path in enumerate(other_adatas):
                lines.append(f"adata_{index} = ad.read_h5ad({path!r}, backed='r').to_memory()")
            lines.append('adata = adata.concatenate(')
            for index, _path_value in enumerate(other_adatas):
                lines.append(f'    adata_{index},')
            lines.append(f"    join={str(inputs.get('join', 'inner') or 'inner')!r},")
            index_unique = str(inputs.get('index_unique', '-'))
            if index_unique != '':
                lines.append(f'    index_unique={index_unique!r},')
            else:
                lines.append('    index_unique=None,')
            uns_merge = str(inputs.get('uns_merge', 'None') or 'None')
            if uns_merge != 'None':
                lines.append(f'    uns_merge={uns_merge!r},')
            else:
                lines.append('    uns_merge=None,')
            lines.append(f"    batch_key={str(inputs.get('batch_key', 'batch') or 'batch')!r})")
            return lines
        if function == 'var_names_make_unique':
            return [f"adata.var_names_make_unique(join={str(inputs.get('join', '-') or '-')!r})"]
        if function == 'obs_names_make_unique':
            return [f"adata.obs_names_make_unique(join={str(inputs.get('join', '-') or '-')!r})"]
        if function == 'rename_categories':
            return cls._rename_categories_script(inputs)
        if function == 'remove_keys':
            return cls._remove_keys_script(inputs)
        if function == 'flag_genes':
            return cls._flag_genes_script(inputs)
        if function == 'rename_obs':
            return cls._rename_axis_script(inputs, axis='obs')
        if function == 'rename_var':
            return cls._rename_axis_script(inputs, axis='var')
        if function == 'strings_to_categoricals':
            return ['adata.strings_to_categoricals()']
        if function == 'transpose':
            return ['adata = adata.to_memory()', 'adata = adata.transpose()']
        if function == 'add_annotation':
            return cls._add_annotation_script(inputs)
        if function == 'split_on_obs':
            return cls._split_on_obs_script(inputs)
        if function in {'copy_obs', 'copy_uns', 'copy_embed', 'copy_layers'}:
            return cls._copy_keyed_script(inputs, function)
        if function == 'copy_X':
            return cls._copy_x_script(inputs)
        if function == 'save_raw':
            return ['adata = adata.to_memory()', 'adata.raw = adata']
        return []

    @classmethod
    def _rename_categories_script(cls, inputs: dict[str, Any]) -> list[str]:
        key = str(inputs.get('key', ''))
        categories = [value.strip() for value in str(inputs.get('categories', '')).split(',') if value.strip()]
        lines = [f'categories = {categories!r}']
        if str(inputs.get('new_key', 'no') or 'no') != 'yes':
            lines.append(f'adata.rename_categories(key={key!r}, categories=categories)')
            return lines
        key_name = str(inputs.get('key_name', ''))
        return [*lines, f'if {key!r} in adata.obs:', "    print('changing key in obs')", f'    adata.obs[{key_name!r}] = adata.obs[{key!r}]', f'    adata.rename_categories(key={key_name!r}, categories=categories)', f'elif {key!r} in adata.var:', "    print('changing key in var')", f'    adata.var[{key_name!r}] = adata.var[{key!r}]', f'    adata.rename_categories(key={key_name!r}, categories=categories)', 'else:', "    print('changing key in uns')", f'    adata.uns[{key_name!r}] = adata.uns[{key!r}]', f'    adata.rename_categories(key={key_name!r}, categories=categories)']

    @staticmethod
    def _csv_values(value: Any) -> list[str]:
        return [item.strip() for item in str(value or '').split(',') if item.strip()]

    @classmethod
    def _remove_keys_script(cls, inputs: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        obs_keys = cls._csv_values(inputs.get('obs_keys'))
        if obs_keys:
            lines.append(f'adata.obs = adata.obs.drop(columns={obs_keys!r})')
        var_keys = cls._csv_values(inputs.get('var_keys'))
        if var_keys:
            lines.append(f'adata.var = adata.var.drop(columns={var_keys!r})')
        return lines

    @classmethod
    def _flag_genes_script(cls, inputs: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for flag in cls._repeat_dicts(inputs.get('gene_flags')):
            startswith = str(flag.get('startswith', ''))
            col_in = str(flag.get('col_in', '') or '')
            col_out = str(flag.get('col_out', ''))
            if col_in:
                lines.append(f'k_cat = adata.var[{col_in!r}].str.startswith({startswith!r})')
            else:
                lines.append(f'k_cat = adata.var_names.str.startswith({startswith!r})')
            lines.extend(['if k_cat.sum() > 0:', f'    adata.var[{col_out!r}] = k_cat', 'else:', f'    print("No genes starting with {startswith} found.")'])
        return lines

    @classmethod
    def _rename_axis_script(cls, inputs: dict[str, Any], axis: str) -> list[str]:
        from_key = str(inputs.get(f'from_{axis}', ''))
        to_key = str(inputs.get(f'to_{axis}', ''))
        lines = [f'adata.{axis}[{to_key!r}] = adata.{axis}[{from_key!r}]']
        if not cls._bool_value(inputs.get('keep_original'), default=False):
            lines.append(f'del adata.{axis}[{from_key!r}]')
        return lines

    @classmethod
    def _add_annotation_script(cls, inputs: dict[str, Any]) -> list[str]:
        target = str(inputs.get('var_obs', 'var') or 'var')
        new_annot = str(inputs.get('new_annot', ''))
        if target == 'obs':
            return ['import pandas as pd', f"extra_annot_t = pd.read_csv({new_annot!r}, sep='\\t').reset_index(drop=True)", 'obs_index = adata.obs.index', 'obs = pd.concat([adata.obs.reset_index(drop=True), extra_annot_t], axis=1)', 'obs.index = obs_index', 'adata.obs = obs']
        return ['import pandas as pd', f"extra_annot_t = pd.read_csv({new_annot!r}, sep='\\t').reset_index(drop=True)", 'var_index = adata.var_names', 'var = pd.concat([adata.var.reset_index(drop=True), extra_annot_t], axis=1)', 'var.index = var_index', 'adata.var = var']

    @classmethod
    def _split_on_obs_script(cls, inputs: dict[str, Any]) -> list[str]:
        key = str(inputs.get('key', ''))
        return ['import os', 'adata = adata.to_memory()', "res_dir = 'output_split'", 'os.makedirs(res_dir, exist_ok=True)', f'for s, field_value in enumerate(adata.obs[{key!r}].unique()):', f'    ad_s = adata[adata.obs[{key!r}] == field_value].copy()', f"""    ad_s.write(f"{{res_dir}}/{key}_{{s}}.h5ad", compression='gzip')"""]

    @classmethod
    def _copy_keyed_script(cls, inputs: dict[str, Any], function: str) -> list[str]:
        source = str(inputs.get('source_adata', ''))
        lines = [f"source_adata = ad.read_h5ad({source!r}, backed='r')"]
        container_by_function = {'copy_obs': 'obs', 'copy_uns': 'uns', 'copy_embed': 'obsm', 'copy_layers': 'layers'}
        label_by_function = {'copy_obs': 'Obs column', 'copy_uns': 'Uns key', 'copy_embed': 'Embedding key', 'copy_layers': 'Layer'}
        container = container_by_function[function]
        label = label_by_function[function]
        for row in cls._repeat_dicts(inputs.get('keys')):
            source_key = str(row.get('source_key', '') or '')
            target_key = str(row.get('target_key', '') or '') or source_key
            lines.extend([f'if {source_key!r} in source_adata.{container}:', f'    adata.{container}[{target_key!r}] = source_adata.{container}[{source_key!r}]', 'else:', f'    print("{label} {source_key} not found in source AnnData.")'])
        return lines

    @classmethod
    def _copy_x_script(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get('source_adata', ''))
        target_key = str(inputs.get('target_key', '') or '')
        lines = [f"source_adata = ad.read_h5ad({source!r}, backed='r')"]
        if target_key:
            lines.append(f'adata.layers[{target_key!r}] = source_adata.X')
        else:
            lines.append('adata.X = source_adata.X')
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f'mkdir -p {shlex.quote(out)}', f'cd {shlex.quote(out)}']
        commands.append(f"cat > anndata_manipulate.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_manipulate.py")
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._function(inputs) == 'split_on_obs':
            split_dir = out / 'output_split'
            split_dir.mkdir(parents=True, exist_ok=True)
            return [split_dir]
        return [out / 'anndata.h5ad']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get('input', '')).strip():
            return 'input is required'
        function = cls._function(inputs)
        if function not in cls.FUNCTIONS:
            return f"function must be one of: {', '.join(cls.FUNCTIONS)}"
        if function == 'concatenate' and (not _as_list(inputs.get('other_adatas'))):
            return 'other_adatas is required when function is concatenate'
        if function in {'obs_names_make_unique', 'var_names_make_unique'}:
            if str(inputs.get('join', '-') or '-') not in cls.JOIN_OPTIONS:
                return f"join must be one of: {', '.join(cls.JOIN_OPTIONS)}"
        if function == 'rename_categories':
            for key in ('key', 'categories'):
                if not str(inputs.get(key, '')).strip():
                    return f'{key} is required when function is rename_categories'
            if str(inputs.get('new_key', 'no') or 'no') == 'yes' and (not str(inputs.get('key_name', '')).strip()):
                return 'key_name is required when new_key is yes'
        if function == 'flag_genes':
            if not cls._repeat_dicts(inputs.get('gene_flags')):
                return 'gene_flags is required when function is flag_genes'
        if function == 'rename_obs':
            for key in ('from_obs', 'to_obs'):
                if not str(inputs.get(key, '')).strip():
                    return f'{key} is required when function is rename_obs'
        if function == 'rename_var':
            for key in ('from_var', 'to_var'):
                if not str(inputs.get(key, '')).strip():
                    return f'{key} is required when function is rename_var'
        if function == 'add_annotation':
            if str(inputs.get('var_obs', 'var') or 'var') not in cls.ANNOTATION_TARGETS:
                return f"var_obs must be one of: {', '.join(cls.ANNOTATION_TARGETS)}"
            if not str(inputs.get('new_annot', '')).strip():
                return 'new_annot is required when function is add_annotation'
        if function == 'split_on_obs' and (not str(inputs.get('key', '')).strip()):
            return 'key is required when function is split_on_obs'
        if function in {'copy_obs', 'copy_uns', 'copy_embed', 'copy_layers'}:
            if not str(inputs.get('source_adata', '')).strip():
                return f'source_adata is required when function is {function}'
            if not cls._repeat_dicts(inputs.get('keys')):
                return f'keys is required when function is {function}'
        if function == 'copy_X' and (not str(inputs.get('source_adata', '')).strip()):
            return 'source_adata is required when function is copy_X'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input': ('H5AD', {'description': 'Annotated data matrix to manipulate'})}, 'optional': {'function': ('STRING', {'default': 'concatenate', 'options': cls.FUNCTIONS}), 'other_adatas': ('H5AD', {'default': '', 'multiple': True, 'description': 'Additional AnnData matrices for concatenation'}), 'join': ('STRING', {'default': '-', 'options': [*cls.JOIN_OPTIONS, *cls.CONCAT_JOIN_OPTIONS]}), 'batch_key': ('STRING', {'default': 'batch'}), 'uns_merge': ('STRING', {'default': 'None', 'options': cls.UNS_MERGE_OPTIONS}), 'index_unique': ('STRING', {'default': '-', 'options': ['', *cls.JOIN_OPTIONS]}), 'key': ('STRING', {'default': '', 'description': 'Observation, variable, or unstructured annotation key'}), 'categories': ('STRING', {'default': '', 'description': 'Comma-separated replacement categories'}), 'new_key': ('STRING', {'default': 'no', 'options': ['yes', 'no']}), 'key_name': ('STRING', {'default': ''}), 'obs_keys': ('STRING', {'default': '', 'description': 'Comma-separated obs columns to remove'}), 'var_keys': ('STRING', {'default': '', 'description': 'Comma-separated var columns to remove'}), 'gene_flags': ('JSON', {'default': [], 'is_list': True, 'description': 'Galaxy repeat-style flag definitions with startswith, col_in, and col_out'}), 'from_obs': ('STRING', {'default': ''}), 'to_obs': ('STRING', {'default': ''}), 'from_var': ('STRING', {'default': ''}), 'to_var': ('STRING', {'default': ''}), 'keep_original': ('BOOLEAN', {'default': False}), 'var_obs': ('STRING', {'default': 'var', 'options': cls.ANNOTATION_TARGETS}), 'new_annot': ('TSV', {'default': '', 'description': 'Tabular annotations to append'}), 'source_adata': ('H5AD', {'default': '', 'description': 'Source AnnData object for copy operations'}), 'keys': ('JSON', {'default': [], 'is_list': True, 'description': 'Galaxy repeat-style key mappings with source_key and optional target_key'}), 'target_key': ('STRING', {'default': ''})}, 'hidden': {'output': ('STRING', {})}}
