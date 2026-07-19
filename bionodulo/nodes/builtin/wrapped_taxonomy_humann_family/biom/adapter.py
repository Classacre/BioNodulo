"""Shared BIOM format contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.wrapped_taxonomy_humann_family.contracts import ToolsIUCCommandContract

class _BiomSummarizeTableContract(ToolsIUCCommandContract):
    """Summarize sample or observation data in a BIOM table."""

    LEGACY_NODE_ID = "biom_summarize_table"
    DISPLAY_NAME = "BIOM summarize table"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Summarize sample or observation data in a BIOM table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_summarize_table",
        "biom summarize-table",
        "summarize sample data",
        "summarize observation data",
        "microbiome table summary",
    ]
    RETURN_TYPES = ("TXT",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#summarize-table"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.txt"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "summarize-table",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        if inputs.get("qualitative", True):
            cmd.append("--qualitative")
        if inputs.get("observations", True):
            cmd.append("--observations")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.txt"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input BIOM table"}),
            },
            "optional": {
                "qualitative": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Present counts as unique observation ids rather than observation counts",
                    },
                ),
                "observations": (
                    "BOOLEAN",
                    {"default": True, "description": "Summarize over observations instead of samples"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BiomNormalizeTableContract(ToolsIUCCommandContract):
    """Normalize a BIOM table over samples or observations."""

    LEGACY_NODE_ID = "biom_normalize_table"
    DISPLAY_NAME = "BIOM normalize table"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Normalize a BIOM table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_normalize_table",
        "biom normalize-table",
        "relative abundance",
        "presence absence",
        "normalize microbiome table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#normalize-table"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True
    AXES = ["sample", "observation"]

    @classmethod
    def _axis(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("axis", "sample") or "sample")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.biom"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "normalize-table",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        if inputs.get("relative_abund", True):
            cmd.append("--relative-abund")
        if inputs.get("presence_absence", True):
            cmd.append("--presence-absence")
        cmd.extend(["--axis", cls._axis(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.biom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        axis = cls._axis(inputs)
        if axis not in cls.AXES:
            return f"axis must be one of: {', '.join(cls.AXES)}"
        if not inputs.get("relative_abund", True) and not inputs.get("presence_absence", True):
            return "At least one normalization mode must be enabled"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input BIOM table to normalize"}),
            },
            "optional": {
                "relative_abund": (
                    "BOOLEAN",
                    {"default": True, "description": "Convert table values to relative abundance"},
                ),
                "presence_absence": (
                    "BOOLEAN",
                    {"default": True, "description": "Convert table values to presence or absence"},
                ),
                "axis": (
                    "STRING",
                    {
                        "default": "sample",
                        "options": cls.AXES,
                        "description": "Normalize over samples or observations",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BiomSubsetTableContract(ToolsIUCCommandContract):
    """Subset a BIOM table by sample or observation IDs."""

    LEGACY_NODE_ID = "biom_subset_table"
    DISPLAY_NAME = "BIOM subset table"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Subset a BIOM table by sample or observation IDs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_subset_table",
        "biom subset-table",
        "sample IDs",
        "observation IDs",
        "subset microbiome table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#subset-table"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True
    AXES = ["sample", "observation"]

    @classmethod
    def _axis(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("axis", "sample") or "sample")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.biom"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "subset-table",
            "--input-json-fp",
            str(inputs.get("input_json_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
            "--axis",
            cls._axis(inputs),
            "--ids",
            str(inputs.get("ids", "")),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.biom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_json_fp", "")).strip():
            return "input_json_fp is required"
        if not str(inputs.get("ids", "")).strip():
            return "ids is required"
        axis = cls._axis(inputs)
        if axis not in cls.AXES:
            return f"axis must be one of: {', '.join(cls.AXES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_json_fp": ("FILE", {"description": "Input BIOM table to subset"}),
                "ids": ("FILE", {"description": "Single-column text or tabular file of IDs to retain"}),
            },
            "optional": {
                "axis": (
                    "STRING",
                    {
                        "default": "sample",
                        "options": cls.AXES,
                        "description": "Subset sample IDs or observation IDs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BiomFromUcContract(ToolsIUCCommandContract):
    """Create a BIOM table from a vsearch, uclust, or usearch UC file."""

    LEGACY_NODE_ID = "biom_from_uc"
    DISPLAY_NAME = "BIOM from UC"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Create a BIOM table from a vsearch, uclust, or usearch UC file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_from_uc",
        "biom from-uc",
        "UC file",
        "vsearch",
        "uclust",
        "usearch",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_commands.html#from-uc"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.biom"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "from-uc",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        _add_if_value(cmd, "--rep-set-fp", inputs.get("rep_set_fp"))
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.biom"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input vsearch, uclust, or usearch UC file"}),
            },
            "optional": {
                "rep_set_fp": (
                    "FASTA",
                    {
                        "default": "",
                        "description": "Optional representative sequences FASTA labeled with OTU identifiers",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BiomAddMetadataContract(ToolsIUCCommandContract):
    """Add sample and/or observation metadata to a BIOM table."""

    LEGACY_NODE_ID = "biom_add_metadata"
    DISPLAY_NAME = "BIOM add metadata"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Add sample and/or observation metadata to a BIOM table."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_add_metadata",
        "biom add-metadata",
        "sample metadata",
        "observation metadata",
        "taxonomy metadata",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/adding_metadata.html"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    @classmethod
    def _output_as_json(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("output_as_json", True))

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        suffix = "biom" if cls._output_as_json(inputs) else "h5"
        return f"{_out(inputs)}/output.{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "add-metadata",
            "--input-fp",
            str(inputs.get("input_fp", "")),
            "--output-fp",
            cls._output_path(inputs),
        ]
        for input_name, flag in (
            ("sample_metadata_fp", "--sample-metadata-fp"),
            ("observation_metadata_fp", "--observation-metadata-fp"),
            ("sc_separated", "--sc-separated"),
            ("sc_pipe_separated", "--sc-pipe-separated"),
            ("int_fields", "--int-fields"),
            ("float_fields", "--float-fields"),
            ("sample_header", "--sample-header"),
            ("observation_header", "--observation-header"),
        ):
            _add_if_value(cmd, flag, inputs.get(input_name))
        if cls._output_as_json(inputs):
            cmd.append("--output-as-json")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        filename = "output.biom" if cls._output_as_json(inputs) else "output.h5"
        return [out / filename]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        text_field_description = "Comma-separated BIOM metadata field list"
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input BIOM table"}),
            },
            "optional": {
                "sample_metadata_fp": ("TSV", {"default": "", "description": "Optional sample metadata table"}),
                "observation_metadata_fp": (
                    "TSV",
                    {"default": "", "description": "Optional observation metadata table"},
                ),
                "sc_separated": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to split on semicolons"},
                ),
                "sc_pipe_separated": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to split on semicolons and pipes"},
                ),
                "int_fields": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to cast as integers"},
                ),
                "float_fields": (
                    "STRING",
                    {"default": "", "description": f"{text_field_description} to cast as floating point numbers"},
                ),
                "sample_header": (
                    "STRING",
                    {"default": "", "description": "Comma-separated sample metadata field names"},
                ),
                "observation_header": (
                    "STRING",
                    {"default": "", "description": "Comma-separated observation metadata field names"},
                ),
                "output_as_json": (
                    "BOOLEAN",
                    {"default": True, "description": "Write output as JSON-formatted BIOM1 instead of HDF5"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BiomConvertContract(ToolsIUCCommandContract):
    """Convert between BIOM table formats and tabular text."""

    LEGACY_NODE_ID = "biom_convert"
    DISPLAY_NAME = "BIOM convert"
    REQUIRED_CONDA_PACKAGES = ["biom-format"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert between BIOM table formats and tabular text."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "BIOM",
        "biom-format",
        "biom_convert",
        "biom convert",
        "BIOM1",
        "BIOM2",
        "HDF5",
        "TSV-formatted table",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_fp",)
    REQUIRED_EXECUTABLES = ["biom"]
    DOCUMENTATION_URL = "https://biom-format.org/documentation/biom_conversion.html"
    CITATION_DOIS = [BIOM_FORMAT_DOI]
    CITATION_URLS = [f"{DOI_URL}{BIOM_FORMAT_DOI}"]
    CITATION_TEXT = BIOM_FORMAT_CITATION_TEXT
    VERSION = "2.1.17+galaxy0"
    SHELL = True

    INPUT_TYPES_OPTIONS = ["tsv", "biom"]
    OUTPUT_TYPES = ["tsv", "biom"]
    PROCESS_OBS_METADATA_OPTIONS = ["", "taxonomy", "naive", "sc_separated"]
    TSV_METADATA_FORMATTERS = ["naive", "sc_separated"]
    BIOM_TYPES = ["json", "hdf5"]
    TABLE_TYPES = [
        "OTU table",
        "Pathway table",
        "Function table",
        "Ortholog table",
        "Gene table",
        "Metabolite table",
        "Taxon table",
        "Table",
    ]

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "tsv") or "tsv")

    @classmethod
    def _output_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_type", "biom") or "biom")

    @classmethod
    def _biom_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("biom_type", "json") or "json")

    @classmethod
    def _table_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("table_type", "Table") or "Table")

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        if cls._output_type(inputs) == "tsv":
            suffix = "tsv"
        elif cls._biom_type(inputs) == "hdf5":
            suffix = "h5"
        else:
            suffix = "biom"
        return f"{_out(inputs)}/output.{suffix}"

    @classmethod
    def _setup_command(cls, inputs: dict[str, Any]) -> str:
        input_fp = str(inputs.get("input_fp", ""))
        if cls._input_type(inputs) == "tsv":
            return f"sed '1s/^\\([^#].*\\)/#\\1/' {shlex.quote(input_fp)} > input"
        return _shell_join(["ln", "-s", input_fp, "input"])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "biom",
            "convert",
            "--input-fp",
            "input",
            "--output-fp",
            cls._output_path(inputs),
        ]
        if cls._input_type(inputs) == "tsv":
            _add_if_value(cmd, "--process-obs-metadata", inputs.get("process_obs_metadata"))

        if cls._output_type(inputs) == "tsv":
            cmd.append("--to-tsv")
            header_key = inputs.get("header_key")
            if header_key:
                cmd.extend(["--header-key", str(header_key)])
                _add_if_value(cmd, "--output-metadata-id", inputs.get("output_metadata_id"))
                cmd.extend(["--tsv-metadata-formatter", str(inputs.get("tsv_metadata_formatter", "naive") or "naive")])
        else:
            cmd.extend(["--table-type", cls._table_type(inputs)])
            if cls._biom_type(inputs) == "hdf5":
                cmd.append("--to-hdf5")
                if inputs.get("collapsed_samples", False):
                    cmd.append("--collapsed-samples")
                if inputs.get("collapsed_observations", False):
                    cmd.append("--collapsed-observations")
            else:
                cmd.append("--to-json")
            _add_if_value(cmd, "--sample-metadata-fp", inputs.get("sample_metadata_fp"))
            _add_if_value(cmd, "--observation-metadata-fp", inputs.get("observation_metadata_fp"))

        return f"{cls._setup_command(inputs)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / Path(cls._output_path(inputs)).name]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_fp", "")).strip():
            return "input_fp is required"
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_OPTIONS:
            return f"input_type must be one of: {', '.join(cls.INPUT_TYPES_OPTIONS)}"
        process_obs_metadata = str(inputs.get("process_obs_metadata", "") or "")
        if process_obs_metadata not in cls.PROCESS_OBS_METADATA_OPTIONS:
            return f"process_obs_metadata must be one of: {', '.join(cls.PROCESS_OBS_METADATA_OPTIONS)}"
        output_type = cls._output_type(inputs)
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        if output_type == "biom":
            biom_type = cls._biom_type(inputs)
            if biom_type not in cls.BIOM_TYPES:
                return f"biom_type must be one of: {', '.join(cls.BIOM_TYPES)}"
            table_type = cls._table_type(inputs)
            if table_type not in cls.TABLE_TYPES:
                return f"table_type must be one of: {', '.join(cls.TABLE_TYPES)}"
        formatter = str(inputs.get("tsv_metadata_formatter", "naive") or "naive")
        if formatter not in cls.TSV_METADATA_FORMATTERS:
            return f"tsv_metadata_formatter must be one of: {', '.join(cls.TSV_METADATA_FORMATTERS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fp": ("FILE", {"description": "Input tabular table or BIOM table"}),
            },
            "optional": {
                "input_type": (
                    "STRING",
                    {
                        "default": "tsv",
                        "options": cls.INPUT_TYPES_OPTIONS,
                        "description": "Source format: tabular text or BIOM",
                    },
                ),
                "process_obs_metadata": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.PROCESS_OBS_METADATA_OPTIONS,
                        "description": "Process observation metadata when converting from tabular text",
                    },
                ),
                "output_type": (
                    "STRING",
                    {
                        "default": "biom",
                        "options": cls.OUTPUT_TYPES,
                        "description": "Target format: BIOM or TSV-formatted classic table",
                    },
                ),
                "header_key": (
                    "STRING",
                    {"default": "", "description": "Observation metadata key to include when writing TSV"},
                ),
                "output_metadata_id": (
                    "STRING",
                    {"default": "", "description": "TSV output metadata column name"},
                ),
                "tsv_metadata_formatter": (
                    "STRING",
                    {
                        "default": "naive",
                        "options": cls.TSV_METADATA_FORMATTERS,
                        "description": "Formatter for observation metadata when writing TSV",
                    },
                ),
                "table_type": (
                    "STRING",
                    {
                        "default": "Table",
                        "options": cls.TABLE_TYPES,
                        "description": "BIOM table semantic type",
                    },
                ),
                "biom_type": (
                    "STRING",
                    {
                        "default": "json",
                        "options": cls.BIOM_TYPES,
                        "description": "BIOM output representation: JSON BIOM1 or HDF5 BIOM2",
                    },
                ),
                "collapsed_samples": (
                    "BOOLEAN",
                    {"default": False, "description": "Use collapsed samples when writing HDF5 BIOM"},
                ),
                "collapsed_observations": (
                    "BOOLEAN",
                    {"default": False, "description": "Use collapsed observations when writing HDF5 BIOM"},
                ),
                "sample_metadata_fp": (
                    "TSV",
                    {"default": "", "description": "Optional sample metadata mapping file for BIOM output"},
                ),
                "observation_metadata_fp": (
                    "TSV",
                    {"default": "", "description": "Optional observation metadata mapping file for BIOM output"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
