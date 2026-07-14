"""modify — single_cell node(s). One tool per file (extracted from wrapped_core_data.py)."""
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


class ModifyLoomNode(CommandNode):
    """Manipulate, export, and import Loom files using the Galaxy IUC AnnData wrapper helpers."""
    NODE_ID = 'modify_loom'
    DISPLAY_NAME = 'Loom operations'
    REQUIRED_CONDA_PACKAGES = ['anndata', 'scanpy', 'loompy', 'pandas']
    CATEGORY = 'single_cell'
    DESCRIPTION = 'Manipulate, export, and import Loom single-cell data files.'
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, 'Loom', 'modify_loom', 'Loom operations', 'loompy', 'loompy_to_tsv', 'tsv_to_loompy', 'H5AD to Loom', 'Loom layers', 'row attributes', 'column attributes', 'single-cell loom']
    RETURN_TYPES = ('LOOM', 'DIRECTORY', 'DIRECTORY')
    RETURN_NAMES = ('loomout', 'layer_tsvs', 'attribute_tsvs')
    REQUIRED_EXECUTABLES = ['python']
    DOCUMENTATION_URL = 'https://linnarssonlab.org/loompy/'
    CITATION_DOIS: list[str] = []
    CITATION_URLS = ['https://github.com/linnarsson-lab/loompy']
    CITATION_TEXT = 'Loompy provides Loom file creation, manipulation, layers, and row/column attributes for single-cell data.'
    VERSION = '0.11.4+galaxy3'
    SHELL = True
    OPERATIONS = ['manipulate', 'export', 'import']
    ADD_TYPES = ['cols', 'rows', 'layers']
    FILE_TYPES = ['ad', 'tab']

    @classmethod
    def _operation(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('operation', 'manipulate') or 'manipulate')

    @classmethod
    def _add_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('add_type', 'cols') or 'cols')

    @classmethod
    def _file_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get('file_type', 'ad') or 'ad')

    @staticmethod
    def _script(inputs: dict[str, Any], key: str, default: str) -> str:
        return str(inputs.get(key, default) or default)

    @classmethod
    def _import_script_body(cls, inputs: dict[str, Any]) -> str:
        return '\n'.join(['import anndata as ad', f"adata = ad.read_h5ad({str(inputs.get('anndata', ''))!r})", "adata.write_loom('converted.loom')"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f'mkdir -p {shlex.quote(out)}', f'cd {shlex.quote(out)}']
        operation = cls._operation(inputs)
        if operation == 'manipulate':
            commands.append(f"cp {shlex.quote(str(inputs.get('loom', '')))} converted.loom")
            cmd = ['python', cls._script(inputs, 'modify_loom_script', 'modify_loom.py'), '-f', 'converted.loom', '-a', cls._add_type(inputs)]
            add_type = cls._add_type(inputs)
            if add_type == 'cols':
                cmd.extend(['-c', str(inputs.get('cols', ''))])
            elif add_type == 'rows':
                cmd.extend(['-r', str(inputs.get('rows', ''))])
            else:
                cmd.append('-l')
                cmd.extend(_as_list(inputs.get('layers')))
            commands.append(_shell_join(cmd))
        elif operation == 'export':
            commands.append('mkdir -p output attributes')
            commands.append(_shell_join(['python', cls._script(inputs, 'loompy_to_tsv_script', 'loompy_to_tsv.py'), '-f', str(inputs.get('loom', ''))]))
        elif cls._file_type(inputs) == 'ad':
            commands.append(f"cat > modify_loom_import.py <<'PY'\n{cls._import_script_body(inputs)}\nPY\npython modify_loom_import.py")
        else:
            cmd = ['python', cls._script(inputs, 'tsv_to_loompy_script', 'tsv_to_loompy.py'), '-c', str(inputs.get('coldata', '')), '-r', str(inputs.get('rowdata', '')), '-f', str(inputs.get('mainmatrix', ''))]
            cmd.extend(_as_list(inputs.get('other_files')))
            commands.append(_shell_join(cmd))
        return ' && '.join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._operation(inputs) == 'export':
            layers = out / 'output'
            attributes = out / 'attributes'
            layers.mkdir(parents=True, exist_ok=True)
            attributes.mkdir(parents=True, exist_ok=True)
            return [layers, attributes]
        return [out / 'converted.loom']

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        operation = cls._operation(inputs)
        if operation not in cls.OPERATIONS:
            return f"operation must be one of: {', '.join(cls.OPERATIONS)}"
        if operation in {'manipulate', 'export'} and (not str(inputs.get('loom', '')).strip()):
            return f'loom is required when operation is {operation}'
        if operation == 'manipulate':
            add_type = cls._add_type(inputs)
            if add_type not in cls.ADD_TYPES:
                return f"add_type must be one of: {', '.join(cls.ADD_TYPES)}"
            if add_type == 'cols' and (not str(inputs.get('cols', '')).strip()):
                return 'cols is required when add_type is cols'
            if add_type == 'rows' and (not str(inputs.get('rows', '')).strip()):
                return 'rows is required when add_type is rows'
            if add_type == 'layers' and (not _as_list(inputs.get('layers'))):
                return 'layers is required when add_type is layers'
        if operation == 'import':
            file_type = cls._file_type(inputs)
            if file_type not in cls.FILE_TYPES:
                return f"file_type must be one of: {', '.join(cls.FILE_TYPES)}"
            if file_type == 'ad' and (not str(inputs.get('anndata', '')).strip()):
                return 'anndata is required when file_type is ad'
            if file_type == 'tab':
                for key in ('mainmatrix', 'coldata', 'rowdata'):
                    if not str(inputs.get(key, '')).strip():
                        return f'{key} is required when file_type is tab'
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'optional': {'operation': ('STRING', {'default': 'manipulate', 'options': cls.OPERATIONS}), 'loom': ('LOOM', {'default': '', 'description': 'Loom file to manipulate or export'}), 'add_type': ('STRING', {'default': 'cols', 'options': cls.ADD_TYPES}), 'cols': ('TSV', {'default': '', 'description': 'Column attributes to add'}), 'rows': ('TSV', {'default': '', 'description': 'Row attributes to add'}), 'layers': ('TSV', {'default': '', 'multiple': True, 'description': 'Layer matrix TSV files to add'}), 'file_type': ('STRING', {'default': 'ad', 'options': cls.FILE_TYPES}), 'anndata': ('H5AD', {'default': '', 'description': 'AnnData H5AD file to convert to Loom'}), 'mainmatrix': ('TSV', {'default': '', 'description': 'Main matrix TSV for tabular Loom import'}), 'other_files': ('TSV', {'default': '', 'multiple': True, 'description': 'Optional additional layer TSV files'}), 'coldata': ('TSV', {'default': '', 'description': 'Column attribute TSV'}), 'rowdata': ('TSV', {'default': '', 'description': 'Row attribute TSV'}), 'modify_loom_script': ('FILE', {'default': 'modify_loom.py'}), 'loompy_to_tsv_script': ('FILE', {'default': 'loompy_to_tsv.py'}), 'tsv_to_loompy_script': ('FILE', {'default': 'tsv_to_loompy.py'})}, 'hidden': {'output': ('STRING', {})}}
