"""Focused anndata manipulate node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_core_data_family.evidence import pin_contract

class AnnDataManipulateNode(CommandNode):
    """Manipulate AnnData H5AD objects using the Galaxy IUC AnnData wrapper operations."""

    NODE_ID = "anndata_manipulate"
    DISPLAY_NAME = "Manipulate AnnData"
    REQUIRED_CONDA_PACKAGES = ["anndata", "scanpy", "loompy", "pandas"]
    CATEGORY = "single_cell"
    DESCRIPTION = "Manipulate AnnData H5AD objects by concatenating, renaming, annotating, copying, splitting, or transposing."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AnnData",
        "anndata_manipulate",
        "Manipulate AnnData",
        "H5AD",
        "concatenate",
        "obs_names_make_unique",
        "var_names_make_unique",
        "rename_categories",
        "remove_keys",
        "flag_genes",
        "rename_obs",
        "rename_var",
        "strings_to_categoricals",
        "transpose",
        "add_annotation",
        "split_on_obs",
        "copy_obs",
        "copy_uns",
        "copy_embed",
        "copy_layers",
        "copy_X",
        "save_raw",
    ]
    RETURN_TYPES = ("H5AD", "DIRECTORY")
    RETURN_NAMES = ("anndata", "output_h5ad_split")
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = "https://anndata.readthedocs.io/en/latest/generated/anndata.AnnData.html"
    CITATION_DOIS = [ANNDATA_SCANPY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ANNDATA_SCANPY_CITATION_DOI}"]
    CITATION_TEXT = ANNDATA_SCANPY_CITATION_TEXT
    VERSION = "0.11.4+galaxy3"
    SHELL = True

    FUNCTIONS = [
        "concatenate",
        "obs_names_make_unique",
        "var_names_make_unique",
        "rename_categories",
        "remove_keys",
        "flag_genes",
        "rename_obs",
        "rename_var",
        "strings_to_categoricals",
        "transpose",
        "add_annotation",
        "split_on_obs",
        "copy_obs",
        "copy_uns",
        "copy_embed",
        "copy_layers",
        "copy_X",
        "save_raw",
    ]
    JOIN_OPTIONS = ["-", "_", " ", "/"]
    CONCAT_JOIN_OPTIONS = ["inner", "outer"]
    UNS_MERGE_OPTIONS = ["None", "same", "unique", "first", "only"]
    ANNOTATION_TARGETS = ["var", "obs"]

    @classmethod
    def _function(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("function", "concatenate") or "concatenate")

    @staticmethod
    def _bool_value(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.lower() not in {"false", "0", "no", ""}
        return bool(value)

    @staticmethod
    def _repeat_dicts(value: Any) -> list[dict[str, Any]]:
        if value is None or value == "":
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, (list, tuple)):
            rows: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, dict):
                    rows.append(item)
                else:
                    rows.append({"source_key": item})
            return rows
        return [{"source_key": value}]

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        lines = [
            "import anndata as ad",
            f"adata = ad.read_h5ad({str(inputs.get('input', ''))!r}, backed='r')",
            *cls._branch_script(inputs),
        ]
        if cls._function(inputs) != "split_on_obs":
            lines.extend(["adata.write('anndata.h5ad', compression='gzip')", "print(adata)"])
        return "\n".join(lines)

    @classmethod
    def _branch_script(cls, inputs: dict[str, Any]) -> list[str]:
        function = cls._function(inputs)
        if function == "concatenate":
            lines = ["adata = adata.to_memory()"]
            other_adatas = _as_list(inputs.get("other_adatas"))
            for index, path in enumerate(other_adatas):
                lines.append(f"adata_{index} = ad.read_h5ad({path!r}, backed='r').to_memory()")
            lines.append("adata = adata.concatenate(")
            for index, _path_value in enumerate(other_adatas):
                lines.append(f"    adata_{index},")
            lines.append(f"    join={str(inputs.get('join', 'inner') or 'inner')!r},")
            index_unique = str(inputs.get("index_unique", "-"))
            if index_unique != "":
                lines.append(f"    index_unique={index_unique!r},")
            else:
                lines.append("    index_unique=None,")
            uns_merge = str(inputs.get("uns_merge", "None") or "None")
            if uns_merge != "None":
                lines.append(f"    uns_merge={uns_merge!r},")
            else:
                lines.append("    uns_merge=None,")
            lines.append(f"    batch_key={str(inputs.get('batch_key', 'batch') or 'batch')!r})")
            return lines
        if function == "var_names_make_unique":
            return [f"adata.var_names_make_unique(join={str(inputs.get('join', '-') or '-')!r})"]
        if function == "obs_names_make_unique":
            return [f"adata.obs_names_make_unique(join={str(inputs.get('join', '-') or '-')!r})"]
        if function == "rename_categories":
            return cls._rename_categories_script(inputs)
        if function == "remove_keys":
            return cls._remove_keys_script(inputs)
        if function == "flag_genes":
            return cls._flag_genes_script(inputs)
        if function == "rename_obs":
            return cls._rename_axis_script(inputs, axis="obs")
        if function == "rename_var":
            return cls._rename_axis_script(inputs, axis="var")
        if function == "strings_to_categoricals":
            return ["adata.strings_to_categoricals()"]
        if function == "transpose":
            return ["adata = adata.to_memory()", "adata = adata.transpose()"]
        if function == "add_annotation":
            return cls._add_annotation_script(inputs)
        if function == "split_on_obs":
            return cls._split_on_obs_script(inputs)
        if function in {"copy_obs", "copy_uns", "copy_embed", "copy_layers"}:
            return cls._copy_keyed_script(inputs, function)
        if function == "copy_X":
            return cls._copy_x_script(inputs)
        if function == "save_raw":
            return ["adata = adata.to_memory()", "adata.raw = adata"]
        return []

    @classmethod
    def _rename_categories_script(cls, inputs: dict[str, Any]) -> list[str]:
        key = str(inputs.get("key", ""))
        categories = [value.strip() for value in str(inputs.get("categories", "")).split(",") if value.strip()]
        lines = [f"categories = {categories!r}"]
        if str(inputs.get("new_key", "no") or "no") != "yes":
            lines.append(f"adata.rename_categories(key={key!r}, categories=categories)")
            return lines
        key_name = str(inputs.get("key_name", ""))
        return [
            *lines,
            f"if {key!r} in adata.obs:",
            "    print('changing key in obs')",
            f"    adata.obs[{key_name!r}] = adata.obs[{key!r}]",
            f"    adata.rename_categories(key={key_name!r}, categories=categories)",
            f"elif {key!r} in adata.var:",
            "    print('changing key in var')",
            f"    adata.var[{key_name!r}] = adata.var[{key!r}]",
            f"    adata.rename_categories(key={key_name!r}, categories=categories)",
            "else:",
            "    print('changing key in uns')",
            f"    adata.uns[{key_name!r}] = adata.uns[{key!r}]",
            f"    adata.rename_categories(key={key_name!r}, categories=categories)",
        ]

    @staticmethod
    def _csv_values(value: Any) -> list[str]:
        return [item.strip() for item in str(value or "").split(",") if item.strip()]

    @classmethod
    def _remove_keys_script(cls, inputs: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        obs_keys = cls._csv_values(inputs.get("obs_keys"))
        if obs_keys:
            lines.append(f"adata.obs = adata.obs.drop(columns={obs_keys!r})")
        var_keys = cls._csv_values(inputs.get("var_keys"))
        if var_keys:
            lines.append(f"adata.var = adata.var.drop(columns={var_keys!r})")
        return lines

    @classmethod
    def _flag_genes_script(cls, inputs: dict[str, Any]) -> list[str]:
        lines: list[str] = []
        for flag in cls._repeat_dicts(inputs.get("gene_flags")):
            startswith = str(flag.get("startswith", ""))
            col_in = str(flag.get("col_in", "") or "")
            col_out = str(flag.get("col_out", ""))
            if col_in:
                lines.append(f"k_cat = adata.var[{col_in!r}].str.startswith({startswith!r})")
            else:
                lines.append(f"k_cat = adata.var_names.str.startswith({startswith!r})")
            lines.extend(
                [
                    "if k_cat.sum() > 0:",
                    f"    adata.var[{col_out!r}] = k_cat",
                    "else:",
                    f"    print(\"No genes starting with {startswith} found.\")",
                ]
            )
        return lines

    @classmethod
    def _rename_axis_script(cls, inputs: dict[str, Any], axis: str) -> list[str]:
        from_key = str(inputs.get(f"from_{axis}", ""))
        to_key = str(inputs.get(f"to_{axis}", ""))
        lines = [f"adata.{axis}[{to_key!r}] = adata.{axis}[{from_key!r}]"]
        if not cls._bool_value(inputs.get("keep_original"), default=False):
            lines.append(f"del adata.{axis}[{from_key!r}]")
        return lines

    @classmethod
    def _add_annotation_script(cls, inputs: dict[str, Any]) -> list[str]:
        target = str(inputs.get("var_obs", "var") or "var")
        new_annot = str(inputs.get("new_annot", ""))
        if target == "obs":
            return [
                "import pandas as pd",
                f"extra_annot_t = pd.read_csv({new_annot!r}, sep='\\t').reset_index(drop=True)",
                "obs_index = adata.obs.index",
                "obs = pd.concat([adata.obs.reset_index(drop=True), extra_annot_t], axis=1)",
                "obs.index = obs_index",
                "adata.obs = obs",
            ]
        return [
            "import pandas as pd",
            f"extra_annot_t = pd.read_csv({new_annot!r}, sep='\\t').reset_index(drop=True)",
            "var_index = adata.var_names",
            "var = pd.concat([adata.var.reset_index(drop=True), extra_annot_t], axis=1)",
            "var.index = var_index",
            "adata.var = var",
        ]

    @classmethod
    def _split_on_obs_script(cls, inputs: dict[str, Any]) -> list[str]:
        key = str(inputs.get("key", ""))
        return [
            "import os",
            "adata = adata.to_memory()",
            "res_dir = 'output_split'",
            "os.makedirs(res_dir, exist_ok=True)",
            f"for s, field_value in enumerate(adata.obs[{key!r}].unique()):",
            f"    ad_s = adata[adata.obs[{key!r}] == field_value].copy()",
            f"    ad_s.write(f\"{{res_dir}}/{key}_{{s}}.h5ad\", compression='gzip')",
        ]

    @classmethod
    def _copy_keyed_script(cls, inputs: dict[str, Any], function: str) -> list[str]:
        source = str(inputs.get("source_adata", ""))
        lines = [f"source_adata = ad.read_h5ad({source!r}, backed='r')"]
        container_by_function = {
            "copy_obs": "obs",
            "copy_uns": "uns",
            "copy_embed": "obsm",
            "copy_layers": "layers",
        }
        label_by_function = {
            "copy_obs": "Obs column",
            "copy_uns": "Uns key",
            "copy_embed": "Embedding key",
            "copy_layers": "Layer",
        }
        container = container_by_function[function]
        label = label_by_function[function]
        for row in cls._repeat_dicts(inputs.get("keys")):
            source_key = str(row.get("source_key", "") or "")
            target_key = str(row.get("target_key", "") or "") or source_key
            lines.extend(
                [
                    f"if {source_key!r} in source_adata.{container}:",
                    f"    adata.{container}[{target_key!r}] = source_adata.{container}[{source_key!r}]",
                    "else:",
                    f"    print(\"{label} {source_key} not found in source AnnData.\")",
                ]
            )
        return lines

    @classmethod
    def _copy_x_script(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get("source_adata", ""))
        target_key = str(inputs.get("target_key", "") or "")
        lines = [f"source_adata = ad.read_h5ad({source!r}, backed='r')"]
        if target_key:
            lines.append(f"adata.layers[{target_key!r}] = source_adata.X")
        else:
            lines.append("adata.X = source_adata.X")
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [f"mkdir -p {shlex.quote(out)}", f"cd {shlex.quote(out)}"]
        commands.append(f"cat > anndata_manipulate.py <<'PY'\n{cls._script_body(inputs)}\nPY\npython anndata_manipulate.py")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._function(inputs) == "split_on_obs":
            split_dir = out / "output_split"
            split_dir.mkdir(parents=True, exist_ok=True)
            return [split_dir]
        return [out / "anndata.h5ad"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        function = cls._function(inputs)
        if function not in cls.FUNCTIONS:
            return f"function must be one of: {', '.join(cls.FUNCTIONS)}"
        if function == "concatenate" and not _as_list(inputs.get("other_adatas")):
            return "other_adatas is required when function is concatenate"
        if function in {"obs_names_make_unique", "var_names_make_unique"}:
            if str(inputs.get("join", "-") or "-") not in cls.JOIN_OPTIONS:
                return f"join must be one of: {', '.join(cls.JOIN_OPTIONS)}"
        if function == "rename_categories":
            for key in ("key", "categories"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when function is rename_categories"
            if str(inputs.get("new_key", "no") or "no") == "yes" and not str(inputs.get("key_name", "")).strip():
                return "key_name is required when new_key is yes"
        if function == "flag_genes":
            if not cls._repeat_dicts(inputs.get("gene_flags")):
                return "gene_flags is required when function is flag_genes"
        if function == "rename_obs":
            for key in ("from_obs", "to_obs"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when function is rename_obs"
        if function == "rename_var":
            for key in ("from_var", "to_var"):
                if not str(inputs.get(key, "")).strip():
                    return f"{key} is required when function is rename_var"
        if function == "add_annotation":
            if str(inputs.get("var_obs", "var") or "var") not in cls.ANNOTATION_TARGETS:
                return f"var_obs must be one of: {', '.join(cls.ANNOTATION_TARGETS)}"
            if not str(inputs.get("new_annot", "")).strip():
                return "new_annot is required when function is add_annotation"
        if function == "split_on_obs" and not str(inputs.get("key", "")).strip():
            return "key is required when function is split_on_obs"
        if function in {"copy_obs", "copy_uns", "copy_embed", "copy_layers"}:
            if not str(inputs.get("source_adata", "")).strip():
                return f"source_adata is required when function is {function}"
            if not cls._repeat_dicts(inputs.get("keys")):
                return f"keys is required when function is {function}"
        if function == "copy_X" and not str(inputs.get("source_adata", "")).strip():
            return "source_adata is required when function is copy_X"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("H5AD", {"description": "Annotated data matrix to manipulate"}),
            },
            "optional": {
                "function": ("STRING", {"default": "concatenate", "options": cls.FUNCTIONS}),
                "other_adatas": (
                    "H5AD",
                    {"default": "", "multiple": True, "description": "Additional AnnData matrices for concatenation"},
                ),
                "join": ("STRING", {"default": "-", "options": [*cls.JOIN_OPTIONS, *cls.CONCAT_JOIN_OPTIONS]}),
                "batch_key": ("STRING", {"default": "batch"}),
                "uns_merge": ("STRING", {"default": "None", "options": cls.UNS_MERGE_OPTIONS}),
                "index_unique": ("STRING", {"default": "-", "options": ["", *cls.JOIN_OPTIONS]}),
                "key": ("STRING", {"default": "", "description": "Observation, variable, or unstructured annotation key"}),
                "categories": ("STRING", {"default": "", "description": "Comma-separated replacement categories"}),
                "new_key": ("STRING", {"default": "no", "options": ["yes", "no"]}),
                "key_name": ("STRING", {"default": ""}),
                "obs_keys": ("STRING", {"default": "", "description": "Comma-separated obs columns to remove"}),
                "var_keys": ("STRING", {"default": "", "description": "Comma-separated var columns to remove"}),
                "gene_flags": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Galaxy repeat-style flag definitions with startswith, col_in, and col_out",
                    },
                ),
                "from_obs": ("STRING", {"default": ""}),
                "to_obs": ("STRING", {"default": ""}),
                "from_var": ("STRING", {"default": ""}),
                "to_var": ("STRING", {"default": ""}),
                "keep_original": ("BOOLEAN", {"default": False}),
                "var_obs": ("STRING", {"default": "var", "options": cls.ANNOTATION_TARGETS}),
                "new_annot": ("TSV", {"default": "", "description": "Tabular annotations to append"}),
                "source_adata": ("H5AD", {"default": "", "description": "Source AnnData object for copy operations"}),
                "keys": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Galaxy repeat-style key mappings with source_key and optional target_key",
                    },
                ),
                "target_key": ("STRING", {"default": ""}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(AnnDataManipulateNode)

__all__ = ['AnnDataManipulateNode']
