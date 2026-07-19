"""Shared Galaxy utility and collection contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_alignment_taxonomy_family.contracts import ToolsIUCBaseContract, ToolsIUCCommandContract

class _ColumnMakerContract(ToolsIUCCommandContract):
    """Compute expressions on tabular rows and add, insert, or replace columns."""

    LEGACY_NODE_ID = "Add_a_column1"
    DISPLAY_NAME = "Compute on rows"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Compute one or more expressions on each tabular row and add, insert, or replace columns."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "column_maker",
        "Add_a_column1",
        "Compute on rows",
        "computed columns",
        "append columns",
        "insert columns",
        "replace columns",
        "tabular expression",
        "data manipulation",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("out_file1",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = f"{DOI_URL}{COLUMN_MAKER_CITATION_DOI}"
    CITATION_DOIS = [COLUMN_MAKER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{COLUMN_MAKER_CITATION_DOI}"]
    CITATION_TEXT = COLUMN_MAKER_CITATION_TEXT
    VERSION = "2.1+galaxy0"
    SHELL = True

    ADD_COLUMN_MODES = ["", "I", "R"]
    HEADER_OPTIONS = ["no", "yes"]
    NON_COMPUTABLE_ACTIONS = [
        "--fail-on-non-computable",
        "--skip-non-computable",
        "--keep-non-computable",
        "--non-computable-blank",
        "--non-computable-default",
    ]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/out_file1.tsv"

    @classmethod
    def _actions_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/expressions.txt"

    @classmethod
    def _header_lines_select(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("header_lines_select", "no") or "no")

    @classmethod
    def _column_types(cls, inputs: dict[str, Any]) -> str:
        column_types = str(inputs.get("column_types", ""))
        if inputs.get("auto_col_types", True):
            return column_types
        return ",".join("str" for _ in column_types.split(","))

    @classmethod
    def _expression_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        expressions = inputs.get("expressions")
        if isinstance(expressions, (list, tuple)) and expressions:
            return [dict(item) for item in expressions if isinstance(item, dict)]
        return [
            {
                "cond": inputs.get("cond", "c3-c2"),
                "mode": inputs.get("add_column_mode", ""),
                "pos": inputs.get("pos", ""),
                "new_column_name": inputs.get("new_column_name", ""),
            }
        ]

    @classmethod
    def _action_spec(cls, item: dict[str, Any]) -> str:
        mode = str(item.get("mode", item.get("add_column_mode", "")) or "")
        pos = str(item.get("pos", "") or "")
        col_add_spec = "" if mode == "" else f"{pos}{mode}"
        return f"{item.get('cond', '')};{col_add_spec};{item.get('new_column_name', '')}"

    @classmethod
    def _action_specs(cls, inputs: dict[str, Any]) -> list[str]:
        return [cls._action_spec(item) for item in cls._expression_items(inputs)]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        write_actions = ["printf", "%s\\n", *cls._action_specs(inputs)]
        command = f"{_shell_join(['mkdir', '-p', out])} && {_shell_join(write_actions)} > {shlex.quote(cls._actions_path(inputs))}"
        py_cmd = [
            "python",
            str(inputs.get("script_path", "column_maker.py") or "column_maker.py"),
            "--column-types",
            cls._column_types(inputs),
        ]
        if inputs.get("avoid_scientific_notation"):
            py_cmd.append("--avoid-scientific-notation")
        if cls._header_lines_select(inputs) == "yes":
            py_cmd.append("--header")
        py_cmd.extend(["--file", cls._actions_path(inputs)])
        if inputs.get("fail_on_non_existent_columns", True):
            py_cmd.append("--fail-on-non-existent-columns")
        non_computable_action = str(
            inputs.get("non_computable_action", "--fail-on-non-computable") or "--fail-on-non-computable"
        )
        py_cmd.append(non_computable_action)
        if non_computable_action == "--non-computable-default":
            py_cmd.append(str(inputs.get("non_computable_default", "nan") or "nan"))
        py_cmd.extend([str(inputs.get("input", "")), cls._output_path(inputs)])
        return f"{command} && {_shell_join(py_cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "out_file1.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("column_types", "")).strip():
            return "column_types is required"
        if cls._header_lines_select(inputs) not in cls.HEADER_OPTIONS:
            return f"header_lines_select must be one of: {', '.join(cls.HEADER_OPTIONS)}"
        non_computable_action = str(
            inputs.get("non_computable_action", "--fail-on-non-computable") or "--fail-on-non-computable"
        )
        if non_computable_action not in cls.NON_COMPUTABLE_ACTIONS:
            return f"non_computable_action must be one of: {', '.join(cls.NON_COMPUTABLE_ACTIONS)}"
        for item in cls._expression_items(inputs):
            if not str(item.get("cond", "")).strip():
                return "cond is required for every expression"
            mode = str(item.get("mode", item.get("add_column_mode", "")) or "")
            if mode not in cls.ADD_COLUMN_MODES:
                return f"add_column_mode must be one of: {', '.join(cls.ADD_COLUMN_MODES)}"
            if mode in {"I", "R"}:
                try:
                    pos = int(item.get("pos", 0) or 0)
                except (TypeError, ValueError):
                    return "pos must be an integer when inserting or replacing"
                if pos < 1:
                    return "pos must be at least 1 when inserting or replacing"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Tabular dataset whose rows will receive computed columns"}),
                "column_types": (
                    "STRING",
                    {"description": "Comma-separated Python/Galaxy column types, for example str,int,int,str"},
                ),
            },
            "optional": {
                "expressions": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Galaxy repeat-style expression objects with cond, mode, pos, and new_column_name",
                    },
                ),
                "cond": ("STRING", {"default": "c3-c2", "description": "Single expression used when expressions is empty"}),
                "add_column_mode": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.ADD_COLUMN_MODES,
                        "description": "Append, insert, or replace mode for the single expression",
                    },
                ),
                "pos": ("INT", {"default": 1, "min": 1, "description": "1-based insert/replace column position"}),
                "new_column_name": (
                    "STRING",
                    {"default": "", "description": "Header name for the computed column when header mode is enabled"},
                ),
                "header_lines_select": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.HEADER_OPTIONS,
                        "description": "Whether the input has a header line with column names",
                    },
                ),
                "avoid_scientific_notation": (
                    "BOOLEAN",
                    {"default": False, "description": "Write fully expanded decimal values for new floating-point columns"},
                ),
                "auto_col_types": (
                    "BOOLEAN",
                    {"default": True, "description": "Use supplied Galaxy column types instead of treating all columns as str"},
                ),
                "fail_on_non_existent_columns": (
                    "BOOLEAN",
                    {"default": True, "description": "Fail if an expression references a missing column"},
                ),
                "non_computable_action": (
                    "STRING",
                    {
                        "default": "--fail-on-non-computable",
                        "options": cls.NON_COMPUTABLE_ACTIONS,
                        "description": "How to handle rows where an expression cannot be computed",
                    },
                ),
                "non_computable_default": (
                    "STRING",
                    {"default": "nan", "description": "Replacement value for --non-computable-default"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "column_maker.py",
                        "advanced": True,
                        "description": "Path to the Galaxy column_maker.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CalculateNumericParamContract(ToolsIUCBaseContract):
    """Calculate a Galaxy numeric workflow parameter from arithmetic components."""

    LEGACY_NODE_ID = "calculate_numeric_param"
    DISPLAY_NAME = "Calculate numeric parameter value"
    CATEGORY = "data_transform"
    DESCRIPTION = "Calculate an integer or floating-point parameter from simple arithmetic components."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "calculate_numeric_param",
        "Calculate numeric parameter value",
        "numeric parameter",
        "arithmetic parameter",
        "integer parameter",
        "float parameter",
        "workflow expression",
    ]
    RETURN_TYPES = ("FLOAT", "INT")
    RETURN_NAMES = ("float_param", "integer_param")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = CALCULATE_NUMERIC_PARAM_CITATION_URL
    CITATION_URLS = [CALCULATE_NUMERIC_PARAM_CITATION_URL]
    CITATION_TEXT = CALCULATE_NUMERIC_PARAM_CITATION_TEXT
    VERSION = "0.1.0"

    ARITHMETIC_OPERATORS = ["+", "-", "*", "/", "**", "%", ""]
    OUTPUT_TYPES = ["integer", "float"]
    _AST_OPERATORS = (
        ast.Expression,
        ast.BinOp,
        ast.Constant,
        ast.UnaryOp,
        ast.Add,
        ast.Sub,
        ast.Mult,
        ast.Div,
        ast.Pow,
        ast.Mod,
        ast.USub,
        ast.UAdd,
    )

    @classmethod
    def _component_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        components = inputs.get("components")
        if isinstance(components, (list, tuple)):
            return [dict(item) for item in components if isinstance(item, dict)]
        return []

    @classmethod
    def _component_value(cls, component: dict[str, Any]) -> Any:
        param_type = component.get("param_type")
        if isinstance(param_type, dict) and "component_value" in param_type:
            return param_type["component_value"]
        return component.get("component_value")

    @classmethod
    def _expression(cls, inputs: dict[str, Any]) -> str:
        parts: list[str] = []
        for component in cls._component_items(inputs):
            parts.append(str(cls._component_value(component)))
            operator = str(component.get("arith", "") or "")
            parts.append(operator)
            if operator == "":
                break
        return "".join(parts)

    @classmethod
    def _safe_eval(cls, expression: str) -> float:
        try:
            tree = ast.parse(expression, mode="eval")
        except SyntaxError as exc:
            raise ValueError("numeric expression is invalid") from exc
        for node in ast.walk(tree):
            if not isinstance(node, cls._AST_OPERATORS):
                raise ValueError("numeric expression contains an unsupported operation")
            if isinstance(node, ast.Constant) and not isinstance(node.value, (int, float)):
                raise ValueError("numeric expression contains a non-numeric value")
        return float(eval(compile(tree, "<calculate_numeric_param>", "eval"), {"__builtins__": {}}, {}))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        components = cls._component_items(inputs)
        if len(components) < 2:
            return "at least two components are required"
        output_type = str(inputs.get("output_type", "integer") or "integer")
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        for component in components:
            try:
                float(cls._component_value(component))
            except (TypeError, ValueError):
                return "component_value must be numeric"
            operator = str(component.get("arith", "") or "")
            if operator not in cls.ARITHMETIC_OPERATORS:
                return f"component arithmetic operator must be one of: {', '.join(cls.ARITHMETIC_OPERATORS)}"
        try:
            cls._safe_eval(cls._expression(inputs))
        except ZeroDivisionError:
            return "division by zero is not allowed"
        except ValueError as exc:
            return str(exc)
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "components": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "Galaxy repeat components with component_value and arithmetic operator",
                    },
                ),
            },
            "optional": {
                "component_value": ("FLOAT", {"default": 1.0, "description": "Single numeric component value"}),
                "arith": (
                    "STRING",
                    {
                        "default": "+",
                        "options": cls.ARITHMETIC_OPERATORS,
                        "description": "Arithmetic operator for the single component fallback",
                    },
                ),
                "output_type": (
                    "STRING",
                    {
                        "default": "integer",
                        "options": cls.OUTPUT_TYPES,
                        "description": "Galaxy output type selector",
                    },
                ),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[float, int]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        value = self._safe_eval(self._expression(kwargs))
        if str(kwargs.get("output_type", "integer") or "integer") == "integer":
            value = float(int(value))
        return (value, int(value))

class _ComposeTextParamContract(ToolsIUCBaseContract):
    """Compose a Galaxy text workflow parameter from repeated components."""

    LEGACY_NODE_ID = "compose_text_param"
    DISPLAY_NAME = "Compose text parameter value"
    CATEGORY = "data_transform"
    DESCRIPTION = "Concatenate text, integer, and float parameters into a workflow text value."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "compose_text_param",
        "Compose text parameter value",
        "workflow text parameter",
        "text parameter",
        "integer parameter",
        "float parameter",
        "concatenate parameter values",
    ]
    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("out1",)
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = COMPOSE_TEXT_PARAM_CITATION_URL
    CITATION_URLS = [COMPOSE_TEXT_PARAM_CITATION_URL]
    CITATION_TEXT = COMPOSE_TEXT_PARAM_CITATION_TEXT
    VERSION = "0.1.1"

    PARAM_TYPES = ["text", "integer", "float"]

    @classmethod
    def _component_items(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        components = inputs.get("components")
        if isinstance(components, (list, tuple)):
            return [dict(item) for item in components if isinstance(item, dict)]
        return []

    @classmethod
    def _param_type(cls, component: dict[str, Any]) -> str:
        param_type = component.get("param_type")
        if isinstance(param_type, dict) and "select_param_type" in param_type:
            return str(param_type["select_param_type"])
        return str(component.get("select_param_type", "text") or "text")

    @classmethod
    def _component_value(cls, component: dict[str, Any]) -> Any:
        param_type = component.get("param_type")
        if isinstance(param_type, dict) and "component_value" in param_type:
            return param_type["component_value"]
        return component.get("component_value")

    @classmethod
    def _composed_text(cls, inputs: dict[str, Any]) -> str:
        return "".join(str(cls._component_value(component)) for component in cls._component_items(inputs))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        components = cls._component_items(inputs)
        if not components:
            return "at least one component is required"
        for component in components:
            param_type = cls._param_type(component)
            if param_type not in cls.PARAM_TYPES:
                return f"select_param_type must be one of: {', '.join(cls.PARAM_TYPES)}"
            value = cls._component_value(component)
            if value is None:
                return "component_value is required"
            if param_type == "integer":
                try:
                    if int(value) != float(value):
                        return "integer component_value must be an integer"
                except (TypeError, ValueError):
                    return "integer component_value must be an integer"
            elif param_type == "float":
                try:
                    float(value)
                except (TypeError, ValueError):
                    return "float component_value must be numeric"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "components": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "Galaxy repeat components with select_param_type and component_value",
                    },
                ),
            },
            "optional": {
                "select_param_type": (
                    "STRING",
                    {
                        "default": "text",
                        "options": cls.PARAM_TYPES,
                        "description": "Parameter type for a single component fallback",
                    },
                ),
                "component_value": ("STRING", {"default": "", "description": "Single component value"}),
            },
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        return (self._composed_text(kwargs),)

class _CompressFileContract(ToolsIUCCommandContract):
    """Compress a dataset with gzip."""

    LEGACY_NODE_ID = "compress_file"
    DISPLAY_NAME = "Compress file(s)"
    REQUIRED_CONDA_PACKAGES = ["gzip"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Compress a dataset with gzip, preserving the original content in a .gz file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "compress_file",
        "Compress file(s)",
        "gzip compression",
        "gzip -cf",
        "gzipped output",
        "compress dataset",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_file",)
    REQUIRED_EXECUTABLES = ["gzip"]
    DOCUMENTATION_URL = COMPRESS_FILE_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COMPRESS_FILE_CITATION_URL]
    CITATION_TEXT = COMPRESS_FILE_CITATION_TEXT
    VERSION = "0.1.0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_file.gz"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["gzip", "-cf", str(inputs.get("input", "")), ">", cls._output_path(inputs)]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output_file.gz"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "Dataset to compress with gzip"}),
            },
            "optional": {},
            "hidden": {"output": ("STRING", {})},
        }

class _CollectionColumnJoinContract(ToolsIUCCommandContract):
    """Join multiple tabular collection elements on an identifier column."""

    LEGACY_NODE_ID = "collection_column_join"
    DISPLAY_NAME = "Column join"
    REQUIRED_CONDA_PACKAGES = ["coreutils"]
    CATEGORY = "data_transform"
    DESCRIPTION = "Join multiple tabular datasets together on an identifier field."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Column join",
        "collection_column_join",
        "join tabular datasets",
        "identifier column",
        "list collection",
        "coreutils join",
    ]
    RETURN_TYPES = ("TSV", "TXT")
    RETURN_NAMES = ("tabular_output", "script_output")
    REQUIRED_EXECUTABLES = ["sh", "awk", "sort", "join", "paste", "head", "tail"]
    DOCUMENTATION_URL = COLLECTION_COLUMN_JOIN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLLECTION_COLUMN_JOIN_CITATION_URL]
    CITATION_TEXT = COLLECTION_COLUMN_JOIN_CITATION_TEXT
    VERSION = "0.0.3"
    SHELL = True

    OPTIONAL_OUTPUTS = ["output_shell_script"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/tabular_output.tsv"

    @classmethod
    def _script_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/collection_column_join.sh"

    @classmethod
    def _script_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/script_output.txt"

    @classmethod
    def _include_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        raw = inputs.get("include_outputs")
        if isinstance(raw, str):
            return [item.strip() for item in raw.split(",") if item.strip()]
        return _as_list(raw)

    @classmethod
    def _include_shell_script(cls, inputs: dict[str, Any]) -> bool:
        return "output_shell_script" in cls._include_outputs(inputs)

    @classmethod
    def _tabular_items(cls, inputs: dict[str, Any]) -> list[dict[str, str]]:
        raw_items = inputs.get("input_tabular")
        if isinstance(raw_items, str):
            items: list[Any] = [item.strip() for item in raw_items.split(",") if item.strip()]
        elif isinstance(raw_items, (list, tuple)):
            items = list(raw_items)
        else:
            items = []

        normalized: list[dict[str, str]] = []
        for item in items:
            if isinstance(item, dict):
                path = next(
                    (
                        str(item[key])
                        for key in ("path", "file", "input", "location")
                        if item.get(key) is not None and str(item[key]).strip()
                    ),
                    "",
                )
                label = next(
                    (
                        str(item[key])
                        for key in ("element_identifier", "name", "identifier", "id")
                        if item.get(key) is not None and str(item[key]).strip()
                    ),
                    Path(path).name,
                )
            else:
                path = str(item)
                label = Path(path).name
            if path:
                normalized.append({"path": path, "label": label})
        return normalized

    @classmethod
    def _positive_int(cls, inputs: dict[str, Any], name: str, default: int) -> int:
        return int(inputs.get(name, default))

    @classmethod
    def _awk_text(cls, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    @classmethod
    def _shell_quote_always(cls, value: str) -> str:
        return "'" + value.replace("'", "'\"'\"'") + "'"

    @classmethod
    def _script_lines(cls, inputs: dict[str, Any]) -> list[str]:
        identifier_column = cls._positive_int(inputs, "identifier_column", 1)
        has_header = cls._positive_int(inputs, "has_header", 0)
        tail_offset = has_header + 1
        fill_char = str(inputs.get("fill_char", ".") or ".")
        old_col_in_header = bool(inputs.get("old_col_in_header", True))
        literal_tab = "\t"
        lines = [
            "#!/bin/sh",
            "touch header0.tmp &&",
            "touch output0.tmp &&",
        ]
        left_identifier_column = identifier_column
        items = cls._tabular_items(inputs)
        for index, item in enumerate(items):
            path = shlex.quote(item["path"])
            label = cls._awk_text(item["label"])
            if old_col_in_header:
                if has_header:
                    lines.extend(
                        [
                            (
                                f"head -n {has_header} {path} | awk '{{ n = split($0,arr,\"\\t\"); ctr=1; "
                                f"for(i=1;i<=n;i++){{ if( i != {identifier_column} ){{ if( ctr > 1) "
                                f"{{printf(\"\\t\")}}; printf( \"{label}_%s\", arr[i] ); ctr++ }} }}; "
                                'printf( "\\n" ); }\' > input_header.tmp &&'
                            ),
                            (
                                f"tail -n +{tail_offset} {path} | LC_ALL=C sort -t \"{literal_tab}\" -k "
                                f"{identifier_column} > input_file.tmp &&"
                            ),
                        ]
                    )
                else:
                    lines.extend(
                        [
                            (
                                f"awk '{{ n = split($0,arr,\"\\t\"); ctr=1; for(i=1;i<=n;i++){{ "
                                f"if( i != {identifier_column} ){{ if( ctr > 1) {{printf(\"\\t\")}}; "
                                f"printf( \"{label}_%s\", i ); ctr++ }} }}; exit }}' {path} > input_header.tmp &&"
                            ),
                            f"LC_ALL=C sort -t \"{literal_tab}\" -k {identifier_column} {path} > input_file.tmp &&",
                        ]
                    )
            elif has_header:
                lines.extend(
                    [
                        (
                            f"head -n {has_header} {path} | awk '{{ n = split($0,arr,\"\\t\"); ctr=1; "
                            f"for(i=1;i<=n;i++){{ if( i != {identifier_column} ){{ if( ctr > 1) "
                            f"{{printf(\"\\t\")}}; printf( \"{label}\" ); ctr++ }} }}; "
                            'printf( "\\n" ); }\' > input_header.tmp &&'
                        ),
                        (
                            f"tail -n +{tail_offset} {path} | LC_ALL=C sort -t \"{literal_tab}\" -k "
                            f"{identifier_column} > input_file.tmp &&"
                        ),
                    ]
                )
            else:
                lines.extend(
                    [
                        (
                            f"awk '{{ n = split($0,arr,\"\\t\"); ctr=1; for(i=1;i<=n;i++){{ "
                            f"if( i != {identifier_column} ){{ if( ctr > 1) {{printf(\"\\t\")}}; "
                            f"printf( \"{label}\"); ctr++ }} }}; exit }}' {path} > input_header.tmp &&"
                        ),
                        f"LC_ALL=C sort -t \"{literal_tab}\" -k {identifier_column} {path} > input_file.tmp &&",
                    ]
                )

            if index == 0:
                lines.append(f"mv input_file.tmp output{(index + 1) % 2}.tmp &&")
                if has_header:
                    lines.append(f"awk '{{ printf ${identifier_column}; exit }}' {path} > header{index % 2}.tmp &&")
                else:
                    lines.append(f'echo "#KEY" > header{index % 2}.tmp &&')
            else:
                lines.append(
                    f"LC_ALL=C join -o auto -a 1 -a 2 -1 {left_identifier_column} -2 {identifier_column} "
                    f"-t \"{literal_tab}\" -e {cls._shell_quote_always(fill_char)} output{index % 2}.tmp input_file.tmp "
                    f"> output{(index + 1) % 2}.tmp &&"
                )
                left_identifier_column = 1
            lines.append(
                f"paste -d \"{literal_tab}\" header{index % 2}.tmp input_header.tmp > "
                f"header{(index + 1) % 2}.tmp &&"
            )

        final_index = len(items) % 2
        lines.append(f'cat header{final_index}.tmp output{final_index}.tmp > "{cls._output_path(inputs)}"')
        return lines

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        script_path = cls._script_path(inputs)
        command = (
            f"mkdir -p {shlex.quote(_out(inputs))} && "
            f"cat > {shlex.quote(script_path)} <<'SH'\n"
            + "\n".join(cls._script_lines(inputs))
            + "\nSH\n"
        )
        if cls._include_shell_script(inputs):
            command += f"cp {shlex.quote(script_path)} {shlex.quote(cls._script_output_path(inputs))} && "
        command += f"cd {shlex.quote(_out(inputs))} && sh {shlex.quote(Path(script_path).name)}"
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "tabular_output.tsv"]
        if cls._include_shell_script(inputs):
            outputs.append(out / "script_output.txt")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if len(cls._tabular_items(inputs)) < 2:
            return "at least two input_tabular files are required"
        for name, default in (("identifier_column", 1), ("has_header", 0)):
            try:
                value = cls._positive_int(inputs, name, default)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < 0:
                return f"{name} must be greater than or equal to 0"
        if not str(inputs.get("fill_char", ".")).strip():
            return "fill_char is required"
        invalid_outputs = [output for output in cls._include_outputs(inputs) if output not in cls.OPTIONAL_OUTPUTS]
        if invalid_outputs:
            return f"include_outputs must be one of: {', '.join(cls.OPTIONAL_OUTPUTS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_tabular": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "Tabular collection elements with path and element_identifier metadata",
                    },
                ),
            },
            "optional": {
                "identifier_column": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "description": "One-based column used to join the input datasets",
                    },
                ),
                "has_header": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Number of header lines in each input file"},
                ),
                "old_col_in_header": (
                    "BOOLEAN",
                    {"default": True, "description": "Include original column names in generated headers"},
                ),
                "fill_char": ("STRING", {"default": ".", "description": "Placeholder for empty joined cells"}),
                "include_outputs": (
                    "STRING",
                    {
                        "is_list": True,
                        "default": [],
                        "options": cls.OPTIONAL_OUTPUTS,
                        "description": "Additional datasets to create",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CollectionElementIdentifiersContract(ToolsIUCBaseContract):
    """Extract top-level identifiers from collection metadata."""

    LEGACY_NODE_ID = "collection_element_identifiers"
    DISPLAY_NAME = "Extract element identifiers"
    CATEGORY = "data_transform"
    DESCRIPTION = "Extract top-level element identifiers from a list or list:paired collection."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "collection_element_identifiers",
        "Extract element identifiers",
        "dataset collection names",
        "element identifiers",
        "list collection",
        "list:paired collection",
        "sample names",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("output",)
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_EXECUTABLES: list[str] = []
    REQUIRED_CONDA_PACKAGES: list[str] = []
    DOCUMENTATION_URL = COLLECTION_ELEMENT_IDENTIFIERS_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COLLECTION_ELEMENT_IDENTIFIERS_CITATION_URL]
    CITATION_TEXT = COLLECTION_ELEMENT_IDENTIFIERS_CITATION_TEXT
    VERSION = "0.0.3"

    @classmethod
    def _items(cls, inputs: dict[str, Any]) -> list[Any]:
        collection = inputs.get("input_collection")
        if isinstance(collection, (list, tuple)):
            return list(collection)
        return []

    @classmethod
    def _identifier(cls, item: Any) -> str:
        if isinstance(item, str):
            return item
        if isinstance(item, dict):
            for key in ("element_identifier", "name", "identifier", "id"):
                value = item.get(key)
                if value is not None and str(value).strip():
                    return str(value)
        return ""

    @classmethod
    def _output_text(cls, inputs: dict[str, Any]) -> str:
        return "".join(f"{cls._identifier(item)}\n" for item in cls._items(inputs))

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        items = cls._items(inputs)
        if not items:
            return "input_collection is required"
        if any(not cls._identifier(item).strip() for item in items):
            return "each collection element requires an identifier"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_collection": (
                    "JSON",
                    {
                        "is_list": True,
                        "description": "List or list:paired collection elements with top-level identifiers",
                    },
                ),
            },
            "optional": {},
            "hidden": {},
        }

    async def run(self, **kwargs: Any) -> tuple[str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        return (self._output_text(kwargs),)

class _CalculateContrastThresholdContract(ToolsIUCCommandContract):
    """Calculate heatmap contrast thresholds from tag pileup CDT matrices."""

    LEGACY_NODE_ID = "calculate_contrast_threshold"
    DISPLAY_NAME = "Calculate Contrast threshold"
    REQUIRED_CONDA_PACKAGES = ["python", "numpy"]
    CATEGORY = "visualization"
    DESCRIPTION = "Calculate heatmap contrast thresholds from tag pileup CDT matrices."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "calculate_contrast_threshold",
        "Calculate Contrast threshold",
        "tag pileup CDT",
        "heatmap contrast",
        "contrast threshold",
        "calcThreshold.txt",
        "ChIP-QC",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("threshold_output",)
    REQUIRED_EXECUTABLES = ["python"]
    DOCUMENTATION_URL = CALCULATE_CONTRAST_THRESHOLD_DOCUMENTATION_URL
    CITATION_URLS = CALCULATE_CONTRAST_THRESHOLD_CITATION_URLS
    CITATION_TEXT = CALCULATE_CONTRAST_THRESHOLD_CITATION_TEXT
    VERSION = "1.0.0"
    SHELL = True

    QUANTILE_TYPE_OPTIONS = ["b_option", "t_option"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/threshold_output.txt"

    @classmethod
    def _quantile_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("quantile_type_selector", "b_option") or "b_option")

    @classmethod
    def _header_value(cls, inputs: dict[str, Any]) -> str:
        return "T" if inputs.get("header", True) else "F"

    @classmethod
    def _numeric_at_least(
        cls, inputs: dict[str, Any], name: str, default: int | float, minimum: int | float, *, integer: bool
    ) -> bool | str:
        raw = inputs.get(name, default)
        try:
            value = int(raw) if integer else float(raw)
        except (TypeError, ValueError):
            return f"{name} must be {'an integer' if integer else 'numeric'}"
        if value < minimum:
            return f"{name} must be greater than or equal to {minimum}"
        return True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "python",
            str(inputs.get("script_path", "calculate_contrast_threshold.py") or "calculate_contrast_threshold.py"),
            "-i",
            str(inputs.get("input_file", "")),
        ]
        if cls._quantile_type(inputs) == "t_option":
            cmd.extend(["-t", str(inputs.get("quantile2", 0.0))])
        else:
            cmd.extend(["-q", str(inputs.get("quantile", 95.0)), "-m", str(inputs.get("min_contrast", 0.0))])
        cmd.extend(
            [
                "-d",
                cls._header_value(inputs),
                "-s",
                str(inputs.get("start_col", 2)),
                "-r",
                str(inputs.get("row_num", 600)),
                "-l",
                str(inputs.get("col_num", 300)),
            ]
        )
        return (
            f"{_shell_join(['mkdir', '-p', out])} && "
            f"cd {shlex.quote(out)} && "
            f"{_shell_join(cmd)} && "
            f"{_shell_join(['cp', 'calcThreshold.txt', cls._output_path(inputs)])}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "threshold_output.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_file", "")).strip():
            return "input_file is required"
        quantile_type = cls._quantile_type(inputs)
        if quantile_type not in cls.QUANTILE_TYPE_OPTIONS:
            return f"quantile_type_selector must be one of: {', '.join(cls.QUANTILE_TYPE_OPTIONS)}"
        for name, default in [("start_col", 2), ("row_num", 600), ("col_num", 300)]:
            result = cls._numeric_at_least(inputs, name, default, 1, integer=True)
            if result is not True:
                return result
        if quantile_type == "t_option":
            result = cls._numeric_at_least(inputs, "quantile2", 0.0, 0, integer=False)
            if result is not True:
                return result
        else:
            try:
                quantile = float(inputs.get("quantile", 95.0))
            except (TypeError, ValueError):
                return "quantile must be numeric"
            if quantile < 0 or quantile > 100:
                return "quantile must be between 0 and 100"
            result = cls._numeric_at_least(inputs, "min_contrast", 0.0, 0, integer=False)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_file": ("TXT", {"description": "Tag pileup CDT data matrix"}),
            },
            "optional": {
                "header": ("BOOLEAN", {"default": True, "description": "Whether the input file has a header row"}),
                "start_col": ("INT", {"default": 2, "min": 1, "description": "1-based valid data start column"}),
                "col_num": ("INT", {"default": 300, "min": 1, "description": "Heatmap plot width in pixels"}),
                "row_num": ("INT", {"default": 600, "min": 1, "description": "Heatmap plot height in pixels"}),
                "quantile_type_selector": (
                    "STRING",
                    {
                        "default": "b_option",
                        "options": cls.QUANTILE_TYPE_OPTIONS,
                        "description": "Calculate thresholds from data or enforce an absolute threshold",
                    },
                ),
                "quantile": ("FLOAT", {"default": 95.0, "min": 0, "max": 100, "description": "Percentile threshold"}),
                "min_contrast": (
                    "FLOAT",
                    {
                        "default": 0.0,
                        "min": 0,
                        "description": "Minimum upper limit after quantile calculation",
                    },
                ),
                "quantile2": (
                    "FLOAT",
                    {"default": 0.0, "min": 0, "description": "Absolute tag threshold for t_option mode"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "calculate_contrast_threshold.py",
                        "advanced": True,
                        "description": "Path to the Galaxy calculate_contrast_threshold.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _CoverageReportContract(ToolsIUCCommandContract):
    """Create panel coverage reports from BAM alignments and target BED regions."""

    LEGACY_NODE_ID = "CoverageReport2"
    DISPLAY_NAME = "Panel Coverage Report"
    REQUIRED_CONDA_PACKAGES = [
        "perl-number-format",
        "r-base",
        "bedtools",
        "samtools",
        "tectonic",
        "libcurl",
        "openssl",
    ]
    CATEGORY = "qc"
    DESCRIPTION = "Create a PDF panel coverage report with mapping and target-region statistics."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CoverageReport2",
        "Panel Coverage Report",
        "coverage report",
        "mapping statistics",
        "target region coverage",
        "samtools flagstat",
        "coverageBed",
        "panel resequencing",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("output1",)
    REQUIRED_EXECUTABLES = ["perl", "coverageBed", "samtools", "Rscript", "tectonic"]
    DOCUMENTATION_URL = COVERAGE_REPORT_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [COVERAGE_REPORT_CITATION_URL]
    CITATION_TEXT = COVERAGE_REPORT_CITATION_TEXT
    VERSION = "0.0.5+galaxy0"
    SHELL = True

    POSITION_LEVEL_OPTIONS = ["", "-s", "-S", "-A", "-L"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output1.pdf"

    @classmethod
    def _position_level(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("PositionLevel", "") or "")

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        sample_name = str(inputs.get("sample_name", "") or "")
        if sample_name:
            return sample_name
        return Path(str(inputs.get("input1", "sample"))).name.rsplit(".", 1)[0]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "perl",
            str(inputs.get("script_path", "CoverageReport.pl") or "CoverageReport.pl"),
            "-b",
            str(inputs.get("input1", "")),
            "-t",
            str(inputs.get("input2", "")),
            "-o",
            cls._output_path(inputs),
        ]
        if inputs.get("perGene", True):
            cmd.append("-r")
        position_level = cls._position_level(inputs)
        if position_level:
            cmd.append(position_level)
        cmd.extend(
            [
                "-m",
                str(inputs.get("threshold", 40)),
                "-f",
                str(inputs.get("frac", 0.2)),
                "-n",
                cls._sample_name(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output1.pdf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input1", "")).strip():
            return "input1 is required"
        if not str(inputs.get("input2", "")).strip():
            return "input2 is required"
        try:
            threshold = int(inputs.get("threshold", 40))
        except (TypeError, ValueError):
            return "threshold must be an integer"
        if threshold < 0:
            return "threshold must be >= 0"
        try:
            frac = float(inputs.get("frac", 0.2))
        except (TypeError, ValueError):
            return "frac must be a number"
        if frac < 0:
            return "frac must be >= 0"
        if cls._position_level(inputs) not in cls.POSITION_LEVEL_OPTIONS:
            return f"PositionLevel must be one of: {', '.join(cls.POSITION_LEVEL_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input1": ("BAM", {"description": "Mapped reads BAM file"}),
                "input2": ("BED", {"description": "Target regions BED file"}),
            },
            "optional": {
                "threshold": (
                    "INT",
                    {"default": 40, "min": 0, "description": "Minimal coverage threshold"},
                ),
                "frac": (
                    "FLOAT",
                    {"default": 0.2, "min": 0, "description": "Fraction of average coverage used in the plot"},
                ),
                "perGene": (
                    "BOOLEAN",
                    {"default": True, "description": "Plot exon coverages grouped by gene in the target BED"},
                ),
                "PositionLevel": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.POSITION_LEVEL_OPTIONS,
                        "description": "Per-exon analysis mode for failed or all exons",
                    },
                ),
                "sample_name": (
                    "STRING",
                    {"default": "", "description": "Sample name printed in the report; defaults to the BAM basename"},
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "CoverageReport.pl",
                        "advanced": True,
                        "description": "Path to the Galaxy CoverageReport.pl helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ExtractGenomicDnaContract(ToolsIUCCommandContract):
    """Fetch genomic DNA from interval or GFF coordinates."""

    LEGACY_NODE_ID = "Extract genomic DNA 1"
    DISPLAY_NAME = "Extract Genomic DNA"
    REQUIRED_CONDA_PACKAGES = ["bx-python", "six", "ucsc-fatotwobit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Fetch genomic DNA in FASTA or interval format from coordinate datasets."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Extract genomic DNA 1",
        "Extract Genomic DNA",
        "extract_genomic_dna",
        "genomic coordinates",
        "interval",
        "GFF",
        "FASTA",
        "twoBit",
        "faToTwoBit",
        "reference genome",
    ]
    RETURN_TYPES = ("FASTA", "FILE")
    RETURN_NAMES = ("output_fasta", "output_interval")
    REQUIRED_EXECUTABLES = ["python", "faToTwoBit"]
    DOCUMENTATION_URL = EXTRACT_GENOMIC_DNA_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [EXTRACT_GENOMIC_DNA_CITATION_URL]
    CITATION_TEXT = EXTRACT_GENOMIC_DNA_CITATION_TEXT
    VERSION = "3.0.3+galaxy3"
    SHELL = True

    INPUT_FORMATS = ["interval", "gff"]
    INTERPRET_FEATURE_OPTIONS = ["yes", "no"]
    REFERENCE_GENOME_SOURCES = ["cached", "history"]
    OUTPUT_FORMATS = ["fasta", "interval"]
    FASTA_HEADER_TYPES = ["bedtools_getfasta_default", "char_delimited"]
    FASTA_HEADER_DELIMITERS = ["underscore", "semicolon", "comma", "tilde", "vertical_bar"]

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_format", "interval") or "interval")

    @classmethod
    def _columns(cls, inputs: dict[str, Any]) -> str:
        columns = str(inputs.get("columns", "") or "")
        if columns:
            return columns
        return "1,4,5,7" if cls._input_format(inputs) == "gff" else "1,2,3,6,4"

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_format", "fasta") or "fasta")

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "output.interval" if cls._output_format(inputs) == "interval" else "output.fasta"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = cls._input_format(inputs)
        output_format = cls._output_format(inputs)
        cmd = [
            "mkdir",
            "-p",
            f"{_out(inputs)}/output_dir",
            "&&",
            "python",
            str(inputs.get("script_path", "extract_genomic_dna.py") or "extract_genomic_dna.py"),
            "--input",
            str(inputs.get("input", "")),
            "--genome",
            str(inputs.get("genome", "")),
            "--input_format",
            input_format,
            "--columns",
            cls._columns(inputs),
        ]
        if input_format == "gff":
            cmd.extend(["--interpret_features", str(inputs.get("interpret_features", "yes") or "yes")])
        cmd.extend(
            [
                "--reference_genome_source",
                str(inputs.get("reference_genome_source", "cached") or "cached"),
                "--reference_genome",
                str(inputs.get("reference_genome", "")),
                "--output_format",
                output_format,
            ]
        )
        if output_format == "fasta":
            fasta_header_type = str(
                inputs.get("fasta_header_type", "bedtools_getfasta_default") or "bedtools_getfasta_default"
            )
            cmd.extend(["--fasta_header_type", fasta_header_type])
            if fasta_header_type == "char_delimited":
                cmd.extend(
                    [
                        "--fasta_header_delimiter",
                        str(inputs.get("fasta_header_delimiter", "underscore") or "underscore"),
                    ]
                )
        cmd.extend(["--output", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def _validate_columns(cls, columns: str, expected_count: int, message: str) -> bool | str:
        parts = columns.split(",")
        if len(parts) != expected_count:
            return message
        try:
            values = [int(part) for part in parts]
        except ValueError:
            return message
        if any(value < 1 for value in values):
            return message
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input is required"
        if not str(inputs.get("genome", "")).strip():
            return "genome is required"
        if not str(inputs.get("reference_genome", "")).strip():
            return "reference_genome is required"
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMATS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMATS)}"
        columns = cls._columns(inputs)
        if input_format == "gff":
            column_result = cls._validate_columns(
                columns,
                4,
                "columns must contain 4 comma-separated 1-based columns for gff input",
            )
        else:
            column_result = cls._validate_columns(
                columns,
                5,
                "columns must contain 5 comma-separated 1-based columns for interval input",
            )
        if column_result is not True:
            return column_result
        interpret_features = str(inputs.get("interpret_features", "yes") or "yes")
        if interpret_features not in cls.INTERPRET_FEATURE_OPTIONS:
            return f"interpret_features must be one of: {', '.join(cls.INTERPRET_FEATURE_OPTIONS)}"
        reference_genome_source = str(inputs.get("reference_genome_source", "cached") or "cached")
        if reference_genome_source not in cls.REFERENCE_GENOME_SOURCES:
            return f"reference_genome_source must be one of: {', '.join(cls.REFERENCE_GENOME_SOURCES)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMATS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        fasta_header_type = str(
            inputs.get("fasta_header_type", "bedtools_getfasta_default") or "bedtools_getfasta_default"
        )
        if fasta_header_type not in cls.FASTA_HEADER_TYPES:
            return f"fasta_header_type must be one of: {', '.join(cls.FASTA_HEADER_TYPES)}"
        fasta_header_delimiter = str(inputs.get("fasta_header_delimiter", "underscore") or "underscore")
        if fasta_header_delimiter not in cls.FASTA_HEADER_DELIMITERS:
            return f"fasta_header_delimiter must be one of: {', '.join(cls.FASTA_HEADER_DELIMITERS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FILE", {"description": "GFF or interval coordinate dataset"}),
                "genome": (
                    "STRING",
                    {"description": "Genome build key normally supplied by Galaxy dataset metadata"},
                ),
                "reference_genome": (
                    "FILE",
                    {"description": "Cached 2bit reference path or history FASTA reference"},
                ),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "interval",
                        "options": cls.INPUT_FORMATS,
                        "description": "Input coordinate format; Galaxy infers this from dataset datatype",
                    },
                ),
                "columns": (
                    "STRING",
                    {
                        "default": "1,2,3,6,4",
                        "description": "1-based chrom,start,end,strand,name columns for interval or chrom,start,end,strand for GFF",
                    },
                ),
                "interpret_features": (
                    "STRING",
                    {
                        "default": "yes",
                        "options": cls.INTERPRET_FEATURE_OPTIONS,
                        "description": "Group GFF entries into features before extracting sequences",
                    },
                ),
                "reference_genome_source": (
                    "STRING",
                    {
                        "default": "cached",
                        "options": cls.REFERENCE_GENOME_SOURCES,
                        "description": "Use a cached 2bit reference or convert a history FASTA with faToTwoBit",
                    },
                ),
                "output_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": cls.OUTPUT_FORMATS,
                        "description": "Write extracted sequences as FASTA or append sequence to interval rows",
                    },
                ),
                "fasta_header_type": (
                    "STRING",
                    {
                        "default": "bedtools_getfasta_default",
                        "options": cls.FASTA_HEADER_TYPES,
                        "description": "Header style for FASTA output",
                    },
                ),
                "fasta_header_delimiter": (
                    "STRING",
                    {
                        "default": "underscore",
                        "options": cls.FASTA_HEADER_DELIMITERS,
                        "description": "Delimiter used when FASTA headers are character-delimited",
                    },
                ),
                "script_path": (
                    "FILE",
                    {
                        "default": "extract_genomic_dna.py",
                        "advanced": True,
                        "description": "Path to the Galaxy extract_genomic_dna.py helper script",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BarcodeSplitterContract(ToolsIUCCommandContract):
    """Split FASTQ files into barcode-specific output files."""

    LEGACY_NODE_ID = "barcode_splitter"
    DISPLAY_NAME = "Barcode Splitter"
    REQUIRED_CONDA_PACKAGES = ["barcode_splitter"]
    CATEGORY = "sequence"
    DESCRIPTION = "Split FASTQ reads into barcode-specific files using one or more index reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Barcode Splitter",
        "barcode_splitter",
        "barcode demultiplexing",
        "index reads",
        "FASTQ splitting",
        "barcodes",
        "dual index",
        "split_all",
    ]
    RETURN_TYPES = ("TSV", "DIRECTORY")
    RETURN_NAMES = ("summary", "split_output")
    REQUIRED_EXECUTABLES = ["barcode_splitter"]
    DOCUMENTATION_URL = BARCODE_SPLITTER_CITATION_URL
    CITATION_DOIS = [BARCODE_SPLITTER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{BARCODE_SPLITTER_CITATION_DOI}", BARCODE_SPLITTER_CITATION_URL]
    CITATION_TEXT = BARCODE_SPLITTER_CITATION_TEXT
    VERSION = "0.18.4.0"
    SHELL = True

    RUN_TYPES = ["single", "paired", "flexible"]
    FORMATS = ["fastq", "fastqsanger", "fastqsolexa", "fastqillumina"]
    READ_TYPES = ["single", "forward", "reverse", "index", "singleindex", "forwardindex", "reverseindex"]
    INDEX_READ_TYPES = ["index", "singleindex", "forwardindex", "reverseindex"]

    @classmethod
    def _run_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("run_type", "single") or "single")

    @classmethod
    def _format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("format", "fastq") or "fastq")

    @classmethod
    def _split_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/split"

    @classmethod
    def _summary_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/summary.tsv"

    @classmethod
    def _idxfiles(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("idxfiles"))

    @classmethod
    def _flexible_seqfiles(cls, inputs: dict[str, Any]) -> list[dict[str, Any]]:
        raw = inputs.get("flexible_seqfiles") or []
        if isinstance(raw, dict):
            return [raw]
        if isinstance(raw, (list, tuple)):
            return [item for item in raw if isinstance(item, dict)]
        return []

    @classmethod
    def _single_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files = [str(inputs.get("snglinput", "")), *cls._idxfiles(inputs)]
        idx_positions = [pos for pos in range(2, len(files) + 1)]
        return files, idx_positions, bool(inputs.get("split_all", False))

    @classmethod
    def _paired_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files = [str(inputs.get("fwdinput", "")), str(inputs.get("revinput", "")), *cls._idxfiles(inputs)]
        idx_positions = [pos for pos in range(3, len(files) + 1)]
        return files, idx_positions, bool(inputs.get("split_all", False))

    @classmethod
    def _flexible_files(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        files: list[str] = []
        idx_positions: list[int] = []
        auto_split_all = bool(inputs.get("split_all", False))
        for index, item in enumerate(cls._flexible_seqfiles(inputs), start=1):
            readtype = str(item.get("readtype", "single") or "single")
            files.append(str(item.get("input", "")))
            if readtype in cls.INDEX_READ_TYPES:
                idx_positions.append(index)
                auto_split_all = True
        return files, idx_positions, auto_split_all

    @classmethod
    def _files_and_indexes(cls, inputs: dict[str, Any]) -> tuple[list[str], list[int], bool]:
        run_type = cls._run_type(inputs)
        if run_type == "paired":
            return cls._paired_files(inputs)
        if run_type == "flexible":
            return cls._flexible_files(inputs)
        return cls._single_files(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        files, idx_positions, auto_split_all = cls._files_and_indexes(inputs)
        split_dir = cls._split_dir(inputs)
        sequence_format = cls._format(inputs)
        cmd = [
            "mkdir",
            "-p",
            split_dir,
            "&&",
            "barcode_splitter",
            "--bcfile",
            str(inputs.get("bcfile", "")),
            "--mismatches",
            str(inputs.get("mismatches", 1)),
            "--galaxy",
        ]
        if inputs.get("barcodes_at_end", False):
            cmd.append("--barcodes_at_end")
        cmd.extend(["--prefix", f"{split_dir}/"])
        cmd.extend(files)
        cmd.append("--idxread")
        cmd.extend(str(position) for position in idx_positions)
        cmd.extend(["--format", sequence_format, "--suffix", f".{sequence_format}"])
        if auto_split_all:
            cmd.append("--split_all")
        cmd.extend([">", cls._summary_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        split_dir = out / "split"
        split_dir.mkdir(parents=True, exist_ok=True)
        return [out / "summary.tsv", split_dir]

    @classmethod
    def _validate_mismatches(cls, inputs: dict[str, Any]) -> bool | str:
        try:
            mismatches = int(inputs.get("mismatches", 1))
        except (TypeError, ValueError):
            return "mismatches must be an integer"
        if mismatches < 0 or mismatches > 2:
            return "mismatches must be between 0 and 2"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("bcfile", "")).strip():
            return "bcfile is required"
        run_type = cls._run_type(inputs)
        if run_type not in cls.RUN_TYPES:
            return f"run_type must be one of: {', '.join(cls.RUN_TYPES)}"
        mismatches_result = cls._validate_mismatches(inputs)
        if mismatches_result is not True:
            return mismatches_result
        sequence_format = cls._format(inputs)
        if sequence_format not in cls.FORMATS:
            return f"format must be one of: {', '.join(cls.FORMATS)}"
        if run_type == "single":
            if not str(inputs.get("snglinput", "")).strip():
                return "snglinput is required"
            if not cls._idxfiles(inputs):
                return "at least one index read is required"
        elif run_type == "paired":
            if not str(inputs.get("fwdinput", "")).strip():
                return "fwdinput is required"
            if not str(inputs.get("revinput", "")).strip():
                return "revinput is required"
            if not cls._idxfiles(inputs):
                return "at least one index read is required"
        else:
            seqfiles = cls._flexible_seqfiles(inputs)
            if not seqfiles:
                return "flexible_seqfiles must include at least one read"
            has_index = False
            for item in seqfiles:
                if not str(item.get("input", "")).strip():
                    return "flexible_seqfiles entries require input"
                readtype = str(item.get("readtype", "single") or "single")
                if readtype not in cls.READ_TYPES:
                    return f"readtype must be one of: {', '.join(cls.READ_TYPES)}"
                if readtype in cls.INDEX_READ_TYPES:
                    has_index = True
            if not has_index:
                return "at least one index read is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bcfile": (
                    "TSV",
                    {
                        "description": (
                            "Tab-delimited barcode table: sample identifier followed by one or more barcode columns"
                        ),
                    },
                ),
            },
            "optional": {
                "run_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": cls.RUN_TYPES,
                        "description": "Galaxy run interface: single-end, paired-end, or flexible read layout",
                    },
                ),
                "snglinput": ("FASTQ", {"default": "", "description": "Single-end read file for single run mode"}),
                "fwdinput": ("FASTQ", {"default": "", "description": "Forward read file for paired run mode"}),
                "revinput": ("FASTQ", {"default": "", "description": "Reverse read file for paired run mode"}),
                "idxfiles": (
                    "FASTQ_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Index read files supplied after the main read files",
                    },
                ),
                "idxreadnames": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy index read labels used for collection identifiers",
                    },
                ),
                "flexible_seqfiles": (
                    "JSON",
                    {
                        "default": [],
                        "is_list": True,
                        "description": "Flexible-mode read objects with input, readtype, and optional readname fields",
                    },
                ),
                "mismatches": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "max": 2,
                        "description": "Number of allowed mismatches per barcode",
                    },
                ),
                "barcodes_at_end": (
                    "BOOLEAN",
                    {"default": False, "description": "Match barcodes at the end of all index sequences"},
                ),
                "split_all": (
                    "BOOLEAN",
                    {"default": False, "description": "Also split index-only files into the output directory"},
                ),
                "format": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": cls.FORMATS,
                        "description": "FASTQ datatype extension used for discovered split files",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
