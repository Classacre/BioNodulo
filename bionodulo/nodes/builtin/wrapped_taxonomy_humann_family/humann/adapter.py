"""Shared HUMAnN table utility contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.contracts import ToolsIUCCommandContract

class _HUMAnNJoinTablesContract(ToolsIUCCommandContract):
    """Join HUMAnN and MetaPhlAn tables into a multi-sample table."""

    LEGACY_NODE_ID = "humann_join_tables"
    DISPLAY_NAME = "HUMAnN Join Tables"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Join gene, pathway, or taxonomy HUMAnN/MetaPhlAn tables into one table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_join_tables",
        "Join merge",
        "gene table",
        "pathway table",
        "taxonomy table",
        "MetaPhlAn table",
        "multi-sample table",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_join_tables"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    @classmethod
    def _input_names(cls, inputs: dict[str, Any], tables: list[str]) -> list[str]:
        labels = _as_list(inputs.get("element_identifiers"))
        names: list[str] = []
        for index, table in enumerate(tables):
            label = labels[index] if index < len(labels) and labels[index] else table
            names.append(_safe_identifier(label))
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tables = _as_list(inputs.get("inputs"))
        input_names = cls._input_names(inputs, tables)
        commands = ["mkdir tmp_dir"]
        commands.extend(
            _shell_join(["ln", "-s", table, f"tmp_dir/{input_name}"])
            for table, input_name in zip(tables, input_names, strict=False)
        )
        commands.append(_shell_join(["humann_join_tables", "-i", "tmp_dir", "-o", f"{out}/joined_tables.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "joined_tables.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("inputs")):
            return "At least one HUMAnN or MetaPhlAn table is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "inputs": (
                    "TSV",
                    {"multiple": True, "description": "Gene, pathway, or taxonomy tables to join"},
                ),
            },
            "optional": {
                "element_identifiers": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Optional Galaxy element identifiers used to name joined samples",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNRenormTableContract(ToolsIUCCommandContract):
    """Renormalize HUMAnN gene and pathway tables."""

    LEGACY_NODE_ID = "humann_renorm_table"
    DISPLAY_NAME = "HUMAnN Renormalize Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Renormalize HUMAnN gene or pathway tables to CPM or relative abundance units."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_renorm_table",
        "Renormalize",
        "copies per million",
        "relative abundance",
        "community total",
        "levelwise total",
        "UNMAPPED",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_renorm_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    UNITS = ["cpm", "relab"]
    MODES = ["community", "levelwise"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/renormalized_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_renorm_table",
            "--input",
            str(inputs.get("input", "")),
            "-o",
            cls._output_path(inputs),
            "--units",
            str(inputs.get("units", "cpm")),
            "--mode",
            str(inputs.get("mode", "community")),
            "--special",
            "y" if inputs.get("special", True) else "n",
        ]
        if inputs.get("update_snames", True):
            cmd.append("--update-snames")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "renormalized_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN gene or pathway table is required"
        units = str(inputs.get("units", "cpm"))
        if units not in cls.UNITS:
            return f"Unsupported HUMAnN normalization units: {units}"
        mode = str(inputs.get("mode", "community"))
        if mode not in cls.MODES:
            return f"Unsupported HUMAnN normalization mode: {mode}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN gene or pathway table"}),
            },
            "optional": {
                "units": (
                    "STRING",
                    {
                        "default": "cpm",
                        "options": cls.UNITS,
                        "description": "Normalize to copies per million or relative abundance units",
                    },
                ),
                "mode": (
                    "STRING",
                    {
                        "default": "community",
                        "options": cls.MODES,
                        "description": "Normalize using community totals or per-level totals",
                    },
                ),
                "special": (
                    "BOOLEAN",
                    {"default": True, "description": "Include special features such as UNMAPPED and UNINTEGRATED"},
                ),
                "update_snames": (
                    "BOOLEAN",
                    {"default": True, "description": "Update sample-name RPK suffixes to the selected units"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNSplitTableContract(ToolsIUCCommandContract):
    """Split a merged HUMAnN table into one file per sample."""

    LEGACY_NODE_ID = "humann_split_table"
    DISPLAY_NAME = "HUMAnN Split Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Split a merged HUMAnN feature table into one table per sample."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_split_table",
        "Split",
        "merged table",
        "one file per sample",
        "taxonomy index",
        "PICRUSt",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("split_tables",)
    REQUIRED_EXECUTABLES = ["humann_split_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    TAXONOMY_LEVELS = ["Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/split_tables"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_split_table",
            "--input",
            str(inputs.get("input", "")),
            "-o",
            cls._output_path(inputs),
        ]
        taxonomy_index = inputs.get("taxonomy_index")
        if taxonomy_index is not None and str(taxonomy_index) != "":
            cmd.extend(["--taxonomy_index", str(taxonomy_index)])
        taxonomy_level = inputs.get("taxonomy_level")
        if taxonomy_level is not None and str(taxonomy_level) != "":
            cmd.extend(["--taxonomy_level", str(taxonomy_level)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "split_tables"
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "Merged HUMAnN table is required"
        taxonomy_level = str(inputs.get("taxonomy_level", ""))
        if taxonomy_level and taxonomy_level not in cls.TAXONOMY_LEVELS:
            return f"Unsupported HUMAnN taxonomy level: {taxonomy_level}"
        taxonomy_index = inputs.get("taxonomy_index")
        if taxonomy_index is not None and str(taxonomy_index) != "":
            try:
                parsed_index = int(taxonomy_index)
            except (TypeError, ValueError):
                return "Taxonomy index must be an integer"
            if parsed_index < 0:
                return "Taxonomy index must be zero or greater"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Merged HUMAnN gene or pathway table"}),
            },
            "optional": {
                "taxonomy_index": (
                    "INT",
                    {
                        "default": "",
                        "min": 0,
                        "description": "Index of the gene in taxonomy data when splitting PICRUSt-style tables",
                    },
                ),
                "taxonomy_level": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.TAXONOMY_LEVELS,
                        "description": "Taxonomy level to use for PICRUSt metagenome contribution output",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNSplitStratifiedTableContract(ToolsIUCCommandContract):
    """Split a stratified HUMAnN table into stratified and unstratified files."""

    LEGACY_NODE_ID = "humann_split_stratified_table"
    DISPLAY_NAME = "HUMAnN Split Stratified Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Split a stratified HUMAnN table into stratified and unstratified tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_split_stratified_table",
        "Split a HUMAnN table",
        "stratified table",
        "unstratified table",
        "gene families",
    ]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("stratified", "unstratified")
    REQUIRED_EXECUTABLES = ["humann_split_stratified_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/split_stratified"

    @staticmethod
    def _split_output_names(input_path: str) -> tuple[str, str]:
        name = Path(input_path).name
        for compression_suffix in (".gz", ".bz2"):
            if name.endswith(compression_suffix):
                name = name[: -len(compression_suffix)]
                break
        path = Path(name)
        extension = path.suffix or ".tsv"
        basename = path.stem if path.suffix else path.name
        if not basename:
            return ("stratified.tsv", "unstratified.tsv")
        return (f"{basename}_stratified{extension}", f"{basename}_unstratified{extension}")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                "humann_split_stratified_table",
                "--input",
                str(inputs.get("input", "")),
                "--output",
                cls._output_dir(inputs),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "split_stratified"
        out.mkdir(parents=True, exist_ok=True)
        stratified, unstratified = cls._split_output_names(str(inputs.get("input", "")))
        return [out / stratified, out / unstratified]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "Stratified HUMAnN table is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Stratified HUMAnN table"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNReduceTableContract(ToolsIUCCommandContract):
    """Reduce a joined HUMAnN table with a summary function."""

    LEGACY_NODE_ID = "humann_reduce_table"
    DISPLAY_NAME = "HUMAnN Reduce Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Reduce a joined HUMAnN table by applying a row-wise summary function."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_reduce_table",
        "Reduce",
        "joined HUMAnN table",
        "row-wise summary",
        "max sum mean min",
        "sort by value",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_reduce_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    FUNCTIONS = ["max", "sum", "mean", "min"]
    SORT_OPTIONS = ["name", "value", "level"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/reduced_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        return _shell_join(
            [
                "humann_reduce_table",
                "--input",
                str(inputs.get("input", "")),
                "-o",
                cls._output_path(inputs),
                "--function",
                str(inputs.get("function", "max")),
                "--sort-by",
                str(inputs.get("sort_by", "name")),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "reduced_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "Joined HUMAnN table is required"
        function = str(inputs.get("function", "max"))
        if function not in cls.FUNCTIONS:
            return f"Unsupported HUMAnN reduction function: {function}"
        sort_by = str(inputs.get("sort_by", "name"))
        if sort_by not in cls.SORT_OPTIONS:
            return f"Unsupported HUMAnN reduce sort option: {sort_by}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "Joined HUMAnN gene, pathway, or taxonomic table"}),
            },
            "optional": {
                "function": (
                    "STRING",
                    {
                        "default": "max",
                        "options": cls.FUNCTIONS,
                        "description": "Summary function to apply across each row",
                    },
                ),
                "sort_by": (
                    "STRING",
                    {
                        "default": "name",
                        "options": cls.SORT_OPTIONS,
                        "description": "Sort reduced rows by feature name, reduced value, or pathway level",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNRegroupTableContract(ToolsIUCCommandContract):
    """Regroup HUMAnN gene-family features into functional categories."""

    LEGACY_NODE_ID = "humann_regroup_table"
    DISPLAY_NAME = "HUMAnN Regroup Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Regroup HUMAnN gene-family features into functional categories."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_regroup_table",
        "Regroup",
        "gene families",
        "MetaCyc reactions",
        "UniRef90",
        "custom mapping",
        "UNGROUPED",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_regroup_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    FUNCTIONS = ["sum", "mean"]
    GROUPING_TYPES = ["standard", "large", "custom"]
    STANDARD_GROUPS = ["uniref90_rxn", "uniref50_rxn"]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/regrouped_table.tsv"

    @staticmethod
    def _yn(value: Any, default: bool = True) -> str:
        if value is None:
            value = default
        if isinstance(value, str):
            return "Y" if value.upper() == "Y" or value.lower() in {"true", "1", "yes"} else "N"
        return "Y" if bool(value) else "N"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_regroup_table",
            "--input",
            str(inputs.get("input", "")),
            "--output",
            cls._output_path(inputs),
            "--function",
            str(inputs.get("function", "sum")),
        ]
        grouping_type = str(inputs.get("grouping_type", "standard"))
        if grouping_type == "standard":
            cmd.extend(["--groups", str(inputs.get("groups", "uniref90_rxn"))])
        elif grouping_type == "large":
            cmd.extend(["--custom", str(inputs.get("grouping", ""))])
            if inputs.get("reversed", False):
                cmd.append("--reversed")
        else:
            cmd.extend(["--custom", str(inputs.get("custom", ""))])
            if inputs.get("reversed", False):
                cmd.append("--reversed")
        cmd.extend(
            [
                "--precision",
                str(inputs.get("precision", 3)),
                "--ungrouped",
                cls._yn(inputs.get("ungrouped"), default=True),
                "--protected",
                cls._yn(inputs.get("protected"), default=True),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "regrouped_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN gene families table is required"
        function = str(inputs.get("function", "sum"))
        if function not in cls.FUNCTIONS:
            return f"Unsupported HUMAnN regroup function: {function}"
        grouping_type = str(inputs.get("grouping_type", "standard"))
        if grouping_type not in cls.GROUPING_TYPES:
            return f"Unsupported HUMAnN grouping type: {grouping_type}"
        if grouping_type == "standard":
            groups = str(inputs.get("groups", "uniref90_rxn"))
            if groups not in cls.STANDARD_GROUPS:
                return f"Unsupported HUMAnN built-in grouping: {groups}"
        elif grouping_type == "large" and not str(inputs.get("grouping", "")).strip():
            return "HUMAnN utility mapping file is required"
        elif grouping_type == "custom" and not str(inputs.get("custom", "")).strip():
            return "Custom HUMAnN grouping file is required"
        try:
            precision = int(inputs.get("precision", 3))
        except (TypeError, ValueError):
            return "Precision must be an integer"
        if precision < 0:
            return "Precision must be zero or greater"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN gene families table"}),
            },
            "optional": {
                "function": (
                    "STRING",
                    {
                        "default": "sum",
                        "options": cls.FUNCTIONS,
                        "description": "Combine grouped features by sum or mean",
                    },
                ),
                "grouping_type": (
                    "STRING",
                    {
                        "default": "standard",
                        "options": cls.GROUPING_TYPES,
                        "description": "Use built-in, installed utility mapping, or custom grouping",
                    },
                ),
                "groups": (
                    "STRING",
                    {
                        "default": "uniref90_rxn",
                        "options": cls.STANDARD_GROUPS,
                        "description": "Built-in regrouping from UniRef families to MetaCyc reactions",
                        "displayOptions": {"show": {"grouping_type": ["standard"]}},
                    },
                ),
                "grouping": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Installed HUMAnN utility mapping file for large regrouping",
                        "displayOptions": {"show": {"grouping_type": ["large"]}},
                    },
                ),
                "custom": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Custom groups mapping file",
                        "displayOptions": {"show": {"grouping_type": ["custom"]}},
                    },
                ),
                "reversed": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Treat the mapping as feature-to-groups instead of groups-to-features",
                        "displayOptions": {"show": {"grouping_type": ["large", "custom"]}},
                    },
                ),
                "precision": (
                    "INT",
                    {"default": 3, "min": 0, "description": "Decimal places to round grouped abundances"},
                ),
                "ungrouped": (
                    "BOOLEAN",
                    {"default": True, "description": "Include UNGROUPED for features that did not map to a group"},
                ),
                "protected": (
                    "BOOLEAN",
                    {"default": True, "description": "Carry through protected features such as UNMAPPED"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNRenameTableContract(ToolsIUCCommandContract):
    """Attach readable names to HUMAnN table feature identifiers."""

    LEGACY_NODE_ID = "humann_rename_table"
    DISPLAY_NAME = "HUMAnN Rename Table"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Attach readable names to HUMAnN gene, pathway, or regrouped feature IDs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_rename_table",
        "Rename features",
        "feature names",
        "MetaCyc reactions",
        "UniRef90 name",
        "custom mapping",
        "NO_NAME",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_rename_table"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    RENAMING_TYPES = ["standard", "advanced", "custom"]
    STANDARD_NAMES = [
        "metacyc-rxn",
        "metacyc-pwy",
        "infogo1000",
        "kegg-module",
        "ec",
        "go",
        "pfam",
        "eggnog",
        "kegg-pathway",
        "kegg-orthology",
    ]

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/renamed_table.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_rename_table",
            "--input",
            str(inputs.get("input", "")),
            "-o",
            cls._output_path(inputs),
        ]
        renaming_type = str(inputs.get("renaming_type", "standard"))
        if renaming_type == "standard":
            cmd.extend(["--names", str(inputs.get("names", "metacyc-rxn"))])
        elif renaming_type == "advanced":
            cmd.extend(["--custom", str(inputs.get("advanced_names", ""))])
        else:
            cmd.extend(["--custom", str(inputs.get("custom", ""))])
        if inputs.get("simplify", False):
            cmd.append("--simplify")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "renamed_table.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN feature table is required"
        renaming_type = str(inputs.get("renaming_type", "standard"))
        if renaming_type not in cls.RENAMING_TYPES:
            return f"Unsupported HUMAnN renaming type: {renaming_type}"
        if renaming_type == "standard":
            names = str(inputs.get("names", "metacyc-rxn"))
            if names not in cls.STANDARD_NAMES:
                return f"Unsupported HUMAnN built-in name map: {names}"
        elif renaming_type == "advanced" and not str(inputs.get("advanced_names", "")).strip():
            return "HUMAnN utility name mapping file is required"
        elif renaming_type == "custom" and not str(inputs.get("custom", "")).strip():
            return "Custom HUMAnN name mapping file is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN gene, pathway, or regrouped feature table"}),
            },
            "optional": {
                "renaming_type": (
                    "STRING",
                    {
                        "default": "standard",
                        "options": cls.RENAMING_TYPES,
                        "description": "Use built-in, installed utility mapping, or custom name mapping",
                    },
                ),
                "names": (
                    "STRING",
                    {
                        "default": "metacyc-rxn",
                        "options": cls.STANDARD_NAMES,
                        "description": "Built-in feature namespace to rename",
                        "displayOptions": {"show": {"renaming_type": ["standard"]}},
                    },
                ),
                "advanced_names": (
                    "FILE",
                    {
                        "default": "",
                        "description": "Installed HUMAnN utility name mapping file",
                        "displayOptions": {"show": {"renaming_type": ["advanced"]}},
                    },
                ),
                "custom": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Custom two-column feature-to-name mapping file",
                        "displayOptions": {"show": {"renaming_type": ["custom"]}},
                    },
                ),
                "simplify": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove non-alphanumeric characters from names"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNUnpackPathwaysContract(ToolsIUCCommandContract):
    """Unpack HUMAnN pathway abundances to include contributing genes."""

    LEGACY_NODE_ID = "humann_unpack_pathways"
    DISPLAY_NAME = "HUMAnN Unpack Pathways"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add gene-family or EC abundance stratification to HUMAnN pathway abundance tables."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_unpack_pathways",
        "Unpack pathway abundances",
        "pathway abundance",
        "gene family abundance",
        "EC abundance",
        "reaction mapping",
        "remove taxonomy",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["humann_unpack_pathways"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/unpacked_pathways.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_unpack_pathways",
            "--input-genes",
            str(inputs.get("input_genes", "")),
            "--input-pathways",
            str(inputs.get("input_pathways", "")),
        ]
        gene_mapping = str(inputs.get("gene_mapping", "")).strip()
        if gene_mapping:
            cmd.extend(["--gene-mapping", gene_mapping])
        pathway_mapping = str(inputs.get("pathway_mapping", "")).strip()
        if pathway_mapping:
            cmd.extend(["--pathway-mapping", pathway_mapping])
        if inputs.get("remove_taxonomy", False):
            cmd.append("--remove-taxonomy")
        cmd.extend(["--output", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "unpacked_pathways.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_genes", "")).strip():
            return "HUMAnN gene family or EC abundance table is required"
        if not str(inputs.get("input_pathways", "")).strip():
            return "HUMAnN pathway abundance table is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_genes": ("TSV", {"description": "HUMAnN gene family or EC abundance table"}),
                "input_pathways": ("TSV", {"description": "HUMAnN pathway abundance table"}),
            },
            "optional": {
                "gene_mapping": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Optional gene-family-to-reaction mapping table",
                    },
                ),
                "pathway_mapping": (
                    "TSV",
                    {
                        "default": "",
                        "description": "Optional reaction-to-pathway mapping table",
                    },
                ),
                "remove_taxonomy": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove taxonomy stratification from unpacked pathway rows"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HUMAnNBarplotContract(ToolsIUCCommandContract):
    """Plot one stratified HUMAnN feature across samples."""

    LEGACY_NODE_ID = "humann_barplot"
    DISPLAY_NAME = "HUMAnN Barplot"
    REQUIRED_CONDA_PACKAGES = ["humann"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Plot a single stratified HUMAnN feature across samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HUMAnN",
        "humann_barplot",
        "Barplot",
        "stratified HUMAnN features",
        "focal feature",
        "top taxa",
        "Bray-Curtis",
        "metadata sorting",
    ]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("barplot",)
    REQUIRED_EXECUTABLES = ["humann_barplot"]
    DOCUMENTATION_URL = "https://huttenhower.sph.harvard.edu/humann/"
    CITATION_DOIS = HUMANN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in HUMANN_CITATION_DOIS]
    CITATION_TEXT = HUMANN_CITATION_TEXT
    VERSION = "3.9"
    SHELL = True
    SORT_OPTIONS = ["none", "sum", "dominant", "braycurtis", "braycurtis_w", "metadata"]
    SORT_ALIASES = {"brawcurtis": "braycurtis"}
    SCALING_OPTIONS = ["original", "logstack", "totalsum"]
    OUTPUT_FORMATS = ["pdf", "png", "svg"]
    INT_DEFAULTS = {
        "top_taxa": 18,
        "max_metalevels": 7,
        "legend_cols": 3,
        "legend_rows": 10,
    }
    FLOAT_DEFAULTS = {
        "height": 11.0,
        "width": 6.0,
        "legend_height": 1.0,
    }

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        output_format = str(inputs.get("format", "pdf") or "pdf").lower()
        return output_format if output_format in cls.OUTPUT_FORMATS else "pdf"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.{cls._output_format(inputs)}"

    @classmethod
    def _sort_values(cls, inputs: dict[str, Any]) -> list[str]:
        raw_sort = inputs.get("sort", ["none"])
        if raw_sort is None or raw_sort == "":
            values = ["none"]
        elif isinstance(raw_sort, (list, tuple)):
            values = [str(value) for value in raw_sort if str(value) != ""]
        else:
            values = str(raw_sort).split()
        return [cls.SORT_ALIASES.get(value, value) for value in values] or ["none"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "humann_barplot",
            "--input",
            str(inputs.get("input", "")),
        ]
        last_metadata = str(inputs.get("last_metadata", "")).strip()
        if last_metadata:
            cmd.extend(["--last-metadata", last_metadata])
        cmd.extend(
            [
                "--focal-feature",
                str(inputs.get("focal_feature", "")),
                "--top-taxa",
                str(inputs.get("top_taxa", 18)),
            ]
        )
        if inputs.get("as_genera", False):
            cmd.append("--as-genera")
        if inputs.get("exclude_unclassified", False):
            cmd.append("--exclude-unclassified")
        if inputs.get("remove_zeros", False):
            cmd.append("--remove-zeros")
        cmd.append("--sort")
        cmd.extend(cls._sort_values(inputs))
        taxa_colormap = str(inputs.get("taxa_colormap", "")).strip()
        if taxa_colormap:
            cmd.extend(["--taxa-colormap", taxa_colormap])
        focal_metadata = str(inputs.get("focal_metadata", "")).strip()
        if focal_metadata:
            cmd.extend(["--focal-metadata", focal_metadata])
        meta_colormap = str(inputs.get("meta_colormap", "")).strip()
        if meta_colormap:
            cmd.extend(["--meta-colormap", meta_colormap])
        cmd.extend(
            [
                "--max-metalevels",
                str(inputs.get("max_metalevels", 7)),
                "--scaling",
                str(inputs.get("scaling", "original")),
            ]
        )
        ymin = inputs.get("ymin", "")
        ymax = inputs.get("ymax", "")
        if str(ymin) != "" and str(ymax) != "":
            cmd.extend(["--ylims", str(ymin), str(ymax)])
        if inputs.get("no_grid", True):
            cmd.append("--no-grid")
        cmd.extend(
            [
                "--dimensions",
                str(inputs.get("height", 11.0)),
                str(inputs.get("width", 6.0)),
            ]
        )
        units = str(inputs.get("units", "")).strip()
        if units:
            cmd.extend(["--units", units])
        cmd.extend(
            [
                "--legend-cols",
                str(inputs.get("legend_cols", 3)),
                "--legend-rows",
                str(inputs.get("legend_rows", 10)),
                "--legend-height",
                str(inputs.get("legend_height", 1.0)),
                "--output",
                cls._output_path(inputs),
            ]
        )
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"output.{cls._output_format(inputs)}"]

    @staticmethod
    def _validate_nonnegative_int(value: Any, message: str) -> str | None:
        try:
            if isinstance(value, bool):
                return message
            parsed = int(value)
        except (TypeError, ValueError):
            return message
        if str(value) != str(parsed):
            return message
        return message if parsed < 0 else None

    @staticmethod
    def _validate_positive_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed <= 0 else None

    @staticmethod
    def _validate_nonnegative_float(value: Any, message: str) -> str | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return message
        return message if parsed < 0 else None

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "HUMAnN table is required"
        if not str(inputs.get("focal_feature", "")).strip():
            return "HUMAnN focal feature is required"
        sort_values = cls._sort_values(inputs)
        for sort_value in sort_values:
            if sort_value not in cls.SORT_OPTIONS:
                return f"Unsupported HUMAnN barplot sort method: {sort_value}"
        if any(sort_value in {"braycurtis", "braycurtis_w"} for sort_value in sort_values) and not inputs.get(
            "remove_zeros", False
        ):
            return "HUMAnN Bray-Curtis sorting requires remove_zeros"
        scaling = str(inputs.get("scaling", "original"))
        if scaling not in cls.SCALING_OPTIONS:
            return f"Unsupported HUMAnN barplot scaling: {scaling}"
        output_format = str(inputs.get("format", "pdf") or "pdf").lower()
        if output_format not in cls.OUTPUT_FORMATS:
            return f"Unsupported HUMAnN barplot output format: {output_format}"
        for key, message in (
            ("top_taxa", "Top taxa must be zero or greater"),
            ("max_metalevels", "Maximum metadata levels must be zero or greater"),
            ("legend_cols", "Legend columns must be zero or greater"),
            ("legend_rows", "Legend rows must be zero or greater"),
        ):
            error = cls._validate_nonnegative_int(inputs.get(key, cls.INT_DEFAULTS[key]), message)
            if error:
                return error
        for key, message in (
            ("height", "Plot height must be greater than zero"),
            ("width", "Plot width must be greater than zero"),
        ):
            error = cls._validate_positive_float(inputs.get(key, cls.FLOAT_DEFAULTS[key]), message)
            if error:
                return error
        error = cls._validate_nonnegative_float(
            inputs.get("legend_height", cls.FLOAT_DEFAULTS["legend_height"]),
            "Legend height must be zero or greater",
        )
        if error:
            return error
        ymin = inputs.get("ymin", "")
        ymax = inputs.get("ymax", "")
        if (str(ymin) == "") != (str(ymax) == ""):
            return "Both y-axis limits are required when setting y-axis limits"
        if str(ymin) != "" and str(ymax) != "":
            try:
                float(ymin)
                float(ymax)
            except (TypeError, ValueError):
                return "Y-axis limits must be numeric"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("TSV", {"description": "HUMAnN table with optional metadata"}),
                "focal_feature": ("STRING", {"description": "Feature ID of interest"}),
            },
            "optional": {
                "last_metadata": (
                    "STRING",
                    {"default": "", "description": "Name of the last metadata row before feature rows"},
                ),
                "top_taxa": ("INT", {"default": 18, "min": 0, "description": "Maximum taxa to highlight"}),
                "as_genera": ("BOOLEAN", {"default": False, "description": "Collapse species to genera"}),
                "exclude_unclassified": (
                    "BOOLEAN",
                    {"default": False, "description": "Exclude the unclassified stratum"},
                ),
                "remove_zeros": (
                    "BOOLEAN",
                    {"default": False, "description": "Remove samples with zero sum for the focal feature"},
                ),
                "sort": (
                    "STRING",
                    {
                        "default": ["none"],
                        "multiple": True,
                        "options": cls.SORT_OPTIONS,
                        "description": "Sample sorting methods evaluated in order",
                    },
                ),
                "taxa_colormap": (
                    "STRING",
                    {"default": "", "description": "Named matplotlib colormap or taxa color mapping file"},
                ),
                "focal_metadata": (
                    "STRING",
                    {"default": "", "description": "Metadata row to highlight or group by"},
                ),
                "meta_colormap": (
                    "STRING",
                    {"default": "", "description": "Named matplotlib colormap or metadata color mapping file"},
                ),
                "max_metalevels": (
                    "INT",
                    {"default": 7, "min": 0, "description": "Metadata levels to keep before collapsing rare levels"},
                ),
                "scaling": (
                    "STRING",
                    {
                        "default": "original",
                        "options": cls.SCALING_OPTIONS,
                        "description": "Scale total bar heights while preserving taxon proportions",
                    },
                ),
                "ymin": ("FLOAT", {"default": "", "description": "Minimum y-axis limit"}),
                "ymax": ("FLOAT", {"default": "", "description": "Maximum y-axis limit"}),
                "no_grid": ("BOOLEAN", {"default": True, "description": "Hide y-axis grid lines"}),
                "height": ("FLOAT", {"default": 11.0, "min": 0, "description": "Image height in inches"}),
                "width": ("FLOAT", {"default": 6.0, "min": 0, "description": "Image width in inches"}),
                "units": ("STRING", {"default": "", "description": "Y-axis abundance units"}),
                "legend_cols": ("INT", {"default": 3, "min": 0, "description": "Legend columns"}),
                "legend_rows": ("INT", {"default": 10, "min": 0, "description": "Legend rows"}),
                "legend_height": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "description": "Legend-to-data-axis height ratio"},
                ),
                "format": (
                    "STRING",
                    {
                        "default": "pdf",
                        "options": cls.OUTPUT_FORMATS,
                        "description": "Output plot format",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
