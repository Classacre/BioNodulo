"""Focused ampvis2 sample and taxonomy filtering nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_amplicon_trimming_family.evidence import pin_contract

from .io_adapter import Ampvis2LoadNode

class Ampvis2SubsetSamplesNode(CommandNode):
    """Subset ampvis2 samples by metadata variable values."""

    LEGACY_NODE_ID = "ampvis2_subset_samples"
    DISPLAY_NAME = "ampvis2 subset samples"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Subset ampvis2 samples by sample metadata values."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 subset samples",
        "amp_subset_samples",
        "amp_filter_samples",
        "sample metadata filtering",
        "metadata values",
        "rarefy samples",
        "remove absent OTUs",
    ]
    RETURN_TYPES = ("FILE", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_filter_samples.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _raw_values(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",")]

    @classmethod
    def _values(cls, inputs: dict[str, Any]) -> list[str]:
        return [value for value in cls._raw_values(inputs.get("vals")) if value]

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any = None) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ""):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < minimum:
            return f"{name} must be >= {minimum}"
        return True

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        values = cls._values(inputs)
        invert = "! " if inputs.get("invert") else ""
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "data <- amp_subset_samples(",
            "    data,",
            f'    {invert}{inputs.get("var", "")} %in% {cls._r_vector(values)},',
            f"    minreads = {inputs.get('minreads', 0) if inputs.get('minreads') not in (None, '') else 0},",
        ]
        if inputs.get("rarefy") not in (None, ""):
            lines.append(f"    rarefy = {inputs.get('rarefy')},")
        lines.extend(
            [
                f"    normalise = {cls._r_bool(inputs.get('normalise'), False)},",
                f"    removeAbsents = {cls._r_bool(inputs.get('removeAbsents'), True)}",
                ")",
                f'saveRDS(data, "{out}/ampvis.rds")',
                *Ampvis2LoadNode._metadata_list_lines(out),
                "data",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/subset_samples.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "ampvis.rds", out / "metadata_list.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        if not str(inputs.get("metadata_list", "")).strip():
            return "metadata_list is required"
        if not str(inputs.get("var", "")).strip():
            return "var is required"
        raw_values = cls._raw_values(inputs.get("vals"))
        if not raw_values:
            return "vals must include at least one metadata value"
        if any(not value for value in raw_values):
            return "metadata values must be non-empty"
        for name, minimum, default in (
            ("minreads", 0, 0),
            ("rarefy", 0, None),
        ):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset generated with ampvis2: load"}),
                "metadata_list": ("TSV", {"description": "Metadata list generated by ampvis2: load"}),
                "var": ("STRING", {"description": "Metadata variable used to select samples"}),
                "vals": (
                    "STRING_LIST",
                    {"multiple": True, "description": "Metadata values to include or exclude"},
                ),
            },
            "optional": {
                "invert": ("BOOLEAN", {"default": False, "description": "Invert the metadata value selection"}),
                "minreads": ("INT", {"default": 0, "min": 0, "description": "Minimum reads per sample before filtering"}),
                "rarefy": ("INT", {"default": "", "min": 0, "description": "Optional rarefaction depth after minreads filtering"}),
                "normalise": ("BOOLEAN", {"default": False, "description": "Transform OTU read counts to percent per sample"}),
                "removeAbsents": ("BOOLEAN", {"default": True, "description": "Remove OTUs absent after sample filtering"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2SubsetTaxaNode(CommandNode):
    """Subset ampvis2 data by taxonomy vector or selected taxa file."""

    LEGACY_NODE_ID = "ampvis2_subset_taxa"
    DISPLAY_NAME = "ampvis2 subset data"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Subset ampvis2 data by matching taxa across taxonomy ranks."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 subset data",
        "ampvis2 subset taxa",
        "amp_subset_taxa",
        "amp_filter_taxa",
        "taxonomy filtering",
        "selected taxonomy list",
        "remove taxa",
    ]
    RETURN_TYPES = ("FILE", "TSV")
    RETURN_NAMES = ("ampvis", "taxonomy_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_filter_taxa.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    SELECT_OPTIONS = ["option_input_file", "option_input_selected_file"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _raw_values(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        text = str(value).strip()
        if not text:
            return []
        return [part.strip() for part in text.split(",")]

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values if value) + ")"

    @classmethod
    def _select_param(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("select_param", "option_input_file") or "option_input_file")

    @classmethod
    def _tax_vector_lines(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._select_param(inputs) == "option_input_selected_file":
            return [
                f'file_path <- "{inputs.get("selected_taxonomy_list", "")}"',
                "lines <- readLines(file_path)",
                "tax_vector <- trimws(lines)",
            ]
        return [f"tax_vector <- {cls._r_vector(cls._raw_values(inputs.get('tax_vector')))}"]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "",
            *cls._tax_vector_lines(inputs),
            "data <- amp_subset_taxa(",
            "    data,",
            "    tax_vector = tax_vector,",
            f"    normalise = {cls._r_bool(inputs.get('normalise'), False)},",
            f"    remove = {cls._r_bool(inputs.get('remove'), False)}",
            ")",
            "",
            f'saveRDS(data, "{out}/ampvis.rds")',
            *Ampvis2LoadNode._taxonomy_list_lines(out),
            "data",
        ]
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/subset_taxa.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "ampvis.rds", out / "taxonomy_list.tsv"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        select_param = cls._select_param(inputs)
        if select_param not in cls.SELECT_OPTIONS:
            return f"select_param must be one of: {', '.join(cls.SELECT_OPTIONS)}"
        if select_param == "option_input_selected_file":
            if not str(inputs.get("selected_taxonomy_list", "")).strip():
                return "selected_taxonomy_list is required when select_param is option_input_selected_file"
        else:
            if not str(inputs.get("taxonomy_list", "")).strip():
                return "taxonomy_list is required when select_param is option_input_file"
            tax_values = cls._raw_values(inputs.get("tax_vector"))
            if not tax_values:
                return "tax_vector must include at least one taxon"
            if any(not value for value in tax_values):
                return "tax_vector values must be non-empty"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset generated with ampvis2: load"}),
                "select_param": (
                    "STRING",
                    {
                        "default": "option_input_file",
                        "options": cls.SELECT_OPTIONS,
                        "description": "Choose taxa from an ampvis2 taxonomy list or from an uploaded selected-taxa file",
                    },
                ),
            },
            "optional": {
                "taxonomy_list": ("TSV", {"default": "", "description": "Taxonomy list generated by ampvis2: load"}),
                "tax_vector": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Taxa to keep or remove when using the taxonomy list"},
                ),
                "selected_taxonomy_list": (
                    "TSV",
                    {"default": "", "description": "File containing selected taxa, one taxon per line"},
                ),
                "normalise": ("BOOLEAN", {"default": False, "description": "Transform OTU read counts to percent per sample"}),
                "remove": ("BOOLEAN", {"default": False, "description": "Remove selected taxa instead of keeping only them"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


pin_contract(Ampvis2SubsetSamplesNode)
pin_contract(Ampvis2SubsetTaxaNode)
