"""BioNodulo built-in wrapped tool nodes split by tool family."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

class Ampvis2AlphaDiversityNode(CommandNode):
    """Calculate ampvis2 alpha-diversity tables and plots."""

    NODE_ID = "ampvis2_alpha_diversity"
    DISPLAY_NAME = "ampvis2 alpha diversity"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Calculate alpha-diversity indices for samples in an ampvis2 RDS dataset."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 alpha diversity",
        "amp_alphadiv",
        "alpha-diversity indices",
        "microbiome alpha diversity",
        "vegan diversity",
        "rarefaction",
    ]
    RETURN_TYPES = ("TSV", "PDF")
    RETURN_NAMES = ("alphadiv", "alphadiv_plot")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_alphadiv.html"
    CITATION_DOIS = AMPVIS2_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in AMPVIS2_CITATION_DOIS]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    MEASURE_OPTIONS = ["uniqueotus", "shannon", "simpson", "invsimpson"]
    DEFAULT_MEASURES = ["uniqueotus", "shannon", "simpson", "invsimpson"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _measures(cls, inputs: dict[str, Any]) -> list[str]:
        measures = _as_list(inputs.get("measure"))
        return measures if measures else cls.DEFAULT_MEASURES.copy()

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        measures = ", ".join(f'"{measure}"' for measure in cls._measures(inputs))
        rarefy = inputs.get("rarefy")
        rarefy_line = f"\n    , rarefy = {rarefy}" if rarefy not in (None, "") else ""
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                "",
                f'd <- readRDS("{inputs.get("data", "")}")',
                "table <- amp_alphadiv(d,",
                f"    measure = c({measures}),",
                f"    richness = {cls._r_bool(inputs.get('richness'), False)}{rarefy_line}",
                ")",
                "plot <- amp_alphadiv(d,",
                f"    measure = c({measures}),",
                f"    richness = {cls._r_bool(inputs.get('richness'), False)}{rarefy_line},",
                "    plot = TRUE,",
                f'    plot_group_by = "{inputs.get("group_by", "")}",',
                f"    plot_scatter = {cls._r_bool(inputs.get('plot_scatter'), False)}",
                ")",
                f"write.table(table, file='{out}/alphadiv.tsv', quote=FALSE, sep='\\t', row.names=FALSE)",
                f'ggsave("{out}/alphadiv_plot.{out_format}",',
                "    plot = plot,",
                ",\n".join(ggsave_options),
                ")",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/alpha_diversity.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "alphadiv.tsv", out / f"alphadiv_plot.{cls._out_format(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        measures = _as_list(inputs.get("measure"))
        if "measure" in inputs and not measures:
            return "at least one alpha-diversity measure is required"
        unsupported_measures = [measure for measure in measures if measure not in cls.MEASURE_OPTIONS]
        if unsupported_measures:
            return f"measure contains unsupported values: {', '.join(unsupported_measures)}"
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name, minimum, default in (
            ("rarefy", 0, None),
            ("plot_width", 1, None),
            ("plot_height", 1, None),
        ):
            raw = inputs.get(name, default)
            if raw in (None, ""):
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number"
            if value < minimum:
                return f"{name} must be >= {minimum}"
            if name == "rarefy" and not float(value).is_integer():
                return "rarefy must be an integer"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset generated with ampvis2: load"}),
            },
            "optional": {
                "measure": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_MEASURES.copy(),
                        "multiple": True,
                        "options": cls.MEASURE_OPTIONS,
                        "description": "Alpha-diversity measures to include",
                    },
                ),
                "richness": ("BOOLEAN", {"default": False, "description": "Calculate Chao1 and ACE sample richness estimates"}),
                "rarefy": (
                    "INT",
                    {"default": "", "min": 0, "description": "Rarefy species richness to this value before calculating indices"},
                ),
                "group_by": ("STRING", {"default": "", "description": "Metadata field for grouping the plot"}),
                "plot_scatter": ("BOOLEAN", {"default": False, "description": "Generate a scatter plot instead of a boxplot"}),
                "out_format": (
                    "STRING",
                    {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"},
                ),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2BoxplotNode(CommandNode):
    """Generate ampvis2 boxplots of abundant taxa."""

    NODE_ID = "ampvis2_boxplot"
    DISPLAY_NAME = "ampvis2 boxplot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate boxplots of abundant taxa from an ampvis2 RDS dataset."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 boxplot",
        "amp_boxplot",
        "taxa boxplot",
        "abundant taxa",
        "microbiome boxplot",
        "amplicon abundance plot",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_boxplot.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    SORT_OPTIONS = ["median", "mean", "sum"]
    PLOT_TYPES = ["boxplot", "point"]
    TAX_SHOW_MODES = ["number", "explicit"]
    TAX_EMPTY_OPTIONS = ["remove", "best", "OTU"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            return cls._r_vector(_as_list(inputs.get("tax_show")))
        return str(inputs.get("tax_show", 20) or 20)

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        tax_add = _as_list(inputs.get("tax_add"))
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'd <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_boxplot(",
            "    d,",
        ]
        if str(inputs.get("group_by", "")).strip():
            lines.append(f'    group_by = "{inputs.get("group_by")}",')
        lines.extend(
            [
                f'    sort_by = "{inputs.get("sort_by", "median") or "median"}",',
                f'    plot_type = "{inputs.get("plot_type", "boxplot") or "boxplot"}",',
                f"    point_size = {inputs.get('point_size', 1)},",
                f'    tax_aggregate = "{inputs.get("tax_aggregate", "Genus") or "Genus"}",',
                f"    tax_add = {cls._r_vector(tax_add) if tax_add else 'NULL'},",
                f"    tax_show = {cls._tax_show(inputs)},",
                f'    tax_empty = "{inputs.get("tax_empty", "best") or "best"}",',
                f"    plot_flip = {cls._r_bool(inputs.get('plot_flip'), False)},",
                f"    plot_log = {cls._r_bool(inputs.get('plot_log'), False)},",
            ]
        )
        if inputs.get("adjust_zero") not in (None, ""):
            lines.append(f"    adjust_zero = {inputs.get('adjust_zero')},")
        lines.extend(
            [
                f"    normalise = {cls._r_bool(inputs.get('normalise'), False)}",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/boxplot.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float, default: Any) -> bool | str:
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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("sort_by", cls.SORT_OPTIONS, "median"),
            ("plot_type", cls.PLOT_TYPES, "boxplot"),
            ("tax_aggregate", cls.TAX_LEVELS, "Genus"),
            ("tax_show_mode", cls.TAX_SHOW_MODES, "number"),
            ("tax_empty", cls.TAX_EMPTY_OPTIONS, "best"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get("tax_add")) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            if not _as_list(inputs.get("tax_show")):
                return "tax_show must include at least one taxon when tax_show_mode is explicit"
        else:
            validation = cls._validate_number(inputs, "tax_show", 1, 20)
            if validation is not True:
                return validation
        for name, minimum, default in (
            ("point_size", 0, 1),
            ("adjust_zero", 1, None),
            ("plot_width", 1, None),
            ("plot_height", 1, None),
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "group_by": ("STRING", {"default": "", "description": "Discrete metadata variable used to group samples"}),
                "sort_by": (
                    "STRING",
                    {"default": "median", "options": cls.SORT_OPTIONS, "description": "Statistic used to sort boxplots"},
                ),
                "plot_type": ("STRING", {"default": "boxplot", "options": cls.PLOT_TYPES, "description": "Plot geometry"}),
                "point_size": ("INT", {"default": 1, "min": 0, "description": "Point size"}),
                "tax_aggregate": (
                    "STRING",
                    {"default": "Genus", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to aggregate OTUs"},
                ),
                "tax_add": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.TAX_LEVELS,
                        "description": "Additional taxonomic levels to display",
                    },
                ),
                "tax_show_mode": (
                    "STRING",
                    {"default": "number", "options": cls.TAX_SHOW_MODES, "description": "Limit displayed taxa by count or explicit list"},
                ),
                "taxonomy_list": (
                    "TSV",
                    {"default": "", "description": "Taxonomy list generated by ampvis2: load for explicit taxon selection"},
                ),
                "tax_show": ("STRING", {"default": 20, "description": "Number of taxa or explicit taxa to display"}),
                "tax_empty": (
                    "STRING",
                    {"default": "best", "options": cls.TAX_EMPTY_OPTIONS, "description": "How to show OTUs without taxonomy"},
                ),
                "plot_flip": ("BOOLEAN", {"default": False, "description": "Flip plot axes"}),
                "plot_log": ("BOOLEAN", {"default": False, "description": "Use log10 scale"}),
                "adjust_zero": (
                    "INT",
                    {"default": "", "min": 1, "description": "Value added to abundances before median calculations"},
                ),
                "normalise": ("BOOLEAN", {"default": False, "description": "Transform OTU read counts to percent per sample"}),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2CoreNode(CommandNode):
    """Create ampvis2 core community plots."""

    NODE_ID = "ampvis2_core"
    DISPLAY_NAME = "ampvis2 core community analysis"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Create core-community plots for grouped ampvis2 samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 core community analysis",
        "amp_core",
        "core community plot",
        "core taxa",
        "abundant OTUs",
        "microbiome core community",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_core.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    MARGIN_PLOT_OPTIONS = ["x", "y", "xy", ""]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                f'data <- readRDS("{inputs.get("data", "")}")',
                "plot <- amp_core(",
                "    data,",
                f"    group_by = {cls._r_vector(_as_list(inputs.get('group_by')))},",
                f"    core_pct = {inputs.get('core_pct', 80)},",
                f'    margin_plots = "{inputs.get("margin_plots", "xy") if inputs.get("margin_plots", "xy") is not None else "xy"}",',
                f"    margin_plot_values_size = {inputs.get('margin_plot_values_size', 3)},",
                f"    widths = c({inputs.get('widths', 5)}, 1),",
                f"    heights = c(1, {inputs.get('heights', 5)})",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/core.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_number(
        cls,
        inputs: dict[str, Any],
        name: str,
        minimum: int | float,
        default: Any,
        maximum: int | float | None = None,
    ) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ""):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < minimum or (maximum is not None and value > maximum):
            if maximum is not None:
                return f"{name} must be between {minimum} and {maximum}"
            return f"{name} must be >= {minimum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        if not _as_list(inputs.get("group_by")):
            return "at least one group_by metadata variable is required"
        margin_plots = str(inputs.get("margin_plots", "xy") or "")
        if margin_plots not in cls.MARGIN_PLOT_OPTIONS:
            return f"margin_plots must be one of: {', '.join(cls.MARGIN_PLOT_OPTIONS)}"
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name, minimum, default, maximum in (
            ("core_pct", 0, 80, 100),
            ("margin_plot_values_size", 0, 3, None),
            ("widths", 1, 5, None),
            ("heights", 1, 5, None),
            ("plot_width", 1, None, None),
            ("plot_height", 1, None, None),
        ):
            validation = cls._validate_number(inputs, name, minimum, default, maximum)
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
                "group_by": (
                    "STRING_LIST",
                    {
                        "multiple": True,
                        "description": "Metadata variables containing the desired grouping of samples",
                    },
                ),
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "core_pct": (
                    "FLOAT",
                    {"default": 80, "min": 0, "max": 100, "description": "Percent threshold for defining abundant core OTUs"},
                ),
                "margin_plots": (
                    "STRING",
                    {"default": "xy", "options": cls.MARGIN_PLOT_OPTIONS, "description": "Margin plots to show"},
                ),
                "margin_plot_values_size": (
                    "INT",
                    {"default": 3, "min": 0, "description": "Value label size in margin plots; 0 disables labels"},
                ),
                "widths": ("INT", {"default": 5, "min": 1, "description": "Relative width of main and y margin plots"}),
                "heights": ("INT", {"default": 5, "min": 1, "description": "Relative height of main and x margin plots"}),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2ExportFastaNode(CommandNode):
    """Export sequences from ampvis2 datasets as FASTA."""

    NODE_ID = "ampvis2_export_fasta"
    DISPLAY_NAME = "ampvis2 export fasta"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Export sequences from an ampvis2 RDS dataset as FASTA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 export fasta",
        "amp_export_fasta",
        "export FASTA",
        "amplicon sequences",
        "taxonomy FASTA headers",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_export_fasta.html"
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
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.fasta"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                f'data <- readRDS("{inputs.get("data", "")}")',
                f'amp_export_fasta(data, filename = "{cls._output_path(inputs)}", tax = {cls._r_bool(inputs.get("tax"), False)})',
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/export_fasta.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset containing sequence information"}),
            },
            "optional": {
                "tax": ("BOOLEAN", {"default": False, "description": "Append taxonomic strings to FASTA headers"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2ExportOtuNode(CommandNode):
    """Export OTU, taxonomy, metadata, and phyloseq artifacts from ampvis2."""

    NODE_ID = "ampvis2_export_otu"
    DISPLAY_NAME = "ampvis2 export otu"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Export OTU, taxonomy, metadata, and phyloseq tables from an ampvis2 object."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 export otu",
        "amp_export_otutable",
        "OTU table export",
        "taxonomy mapping",
        "metadata mapping",
        "phyloseq object",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "FILE")
    RETURN_NAMES = ("otu_long", "otu_short", "tax", "meta", "phyloseq")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_export_otutable.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    OUTPUT_OPTIONS = ["otu_long", "otu_short", "tax", "meta", "phyloseq"]
    DEFAULT_OUTPUTS = ["otu_short", "tax", "meta"]
    OUTPUT_FILES = {
        "otu_long": "otu_long.tsv",
        "otu_short": "otu_short.tsv",
        "tax": "tax.tsv",
        "meta": "meta.tsv",
        "phyloseq": "phyloseq.rds",
    }

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        outputs = _as_list(inputs.get("output_selection"))
        return outputs if outputs else cls.DEFAULT_OUTPUTS.copy()

    @classmethod
    def _path(cls, inputs: dict[str, Any], output_name: str) -> str:
        return f"{_out(inputs)}/{cls.OUTPUT_FILES[output_name]}"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        norm = cls._r_bool(inputs.get("norm"), False)
        otu_source = "data_norm$abund" if norm == "TRUE" else "data$abund"
        norm_lines = ["data_norm <- normaliseTo100(data)"] if norm == "TRUE" else []
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                "library(phyloseq)",
                "library(tibble)",
                "",
                f'data <- readRDS("{inputs.get("data", "")}")',
                "",
                'amp_export_otutable(data, filename = "tmp_otu", sep = "\\t", extension = "tsv", normalise = '
                f"{norm})",
                "",
                "tax_table <- data$tax",
                "tax_table <- tax_table[,c(8,(ncol(tax_table)-6):(ncol(tax_table) - 1))]",
                f'write.table(tax_table, "{cls._path(inputs, "tax")}", sep = "\\t", row.names=FALSE, quote = FALSE)',
                "",
                *norm_lines,
                f"otu_table <- {otu_source}",
                "otu_table <- cbind(OTU = rownames(otu_table), otu_table)",
                f'write.table(otu_table, "{cls._path(inputs, "otu_short")}", sep = "\\t", row.names=FALSE, quote = FALSE)',
                "",
                "meta_data = data$metadata",
                f'write.table(meta_data, "{cls._path(inputs, "meta")}", sep = "\\t", row.names = FALSE, quote = FALSE)',
                "",
                "otu_table <- apply(otu_table, 2, as.numeric)",
                "meta_data[] <- lapply(meta_data, as.character)",
                "OTU <- otu_table(otu_table, taxa_are_rows = TRUE)",
                "TAX <- tax_table(tax_table)",
                "META <- sample_data(meta_data)",
                'colnames(TAX) <- c("Kingdom", "Phylum", "Class", "Order", "Family", "Genus", "Species")',
                "physeq <- phyloseq(OTU, TAX, META)",
                f'saveRDS(physeq, "{cls._path(inputs, "phyloseq")}")',
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/export_otu.R"
        commands = [
            f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT",
            _shell_join(["Rscript", script_path]),
            _shell_join(["mv", "tmp_otu.tsv", cls._path(inputs, "otu_long")]),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILES[output] for output in cls._selected_outputs(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        outputs = _as_list(inputs.get("output_selection"))
        if "output_selection" in inputs and not outputs:
            return "at least one output_selection value is required"
        unsupported_outputs = [output for output in outputs if output not in cls.OUTPUT_OPTIONS]
        if unsupported_outputs:
            return f"output_selection contains unsupported values: {', '.join(unsupported_outputs)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset"}),
            },
            "optional": {
                "norm": ("BOOLEAN", {"default": False, "description": "Transform OTU read counts to percent per sample"}),
                "output_selection": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS.copy(),
                        "multiple": True,
                        "options": cls.OUTPUT_OPTIONS,
                        "description": "Output files to emit",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2FrequencyNode(CommandNode):
    """Generate ampvis2 frequency versus read-abundance plots."""

    NODE_ID = "ampvis2_frequency"
    DISPLAY_NAME = "ampvis2 frequency plot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate frequency versus read-abundance barplots from an ampvis2 RDS dataset."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 frequency plot",
        "amp_frequency",
        "frequency plot",
        "read abundance frequency",
        "microbiome frequency",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_frequency.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    TAX_EMPTY_OPTIONS = ["remove", "best", "OTU"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_frequency(",
            "    data,",
        ]
        if str(inputs.get("group_by", "")).strip():
            lines.append(f'    group_by = "{inputs.get("group_by")}",')
        lines.extend(
            [
                f'    tax_empty = "{inputs.get("tax_empty", "best") or "best"}",',
                f'    tax_aggregate = "{inputs.get("tax_aggregate", "OTU") or "OTU"}",',
                f"    weight = {cls._r_bool(inputs.get('weight'), True)},",
                f"    normalise = {cls._r_bool(inputs.get('normalise'), True)},",
                "    detailed_output = FALSE",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/frequency.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float) -> bool | str:
        raw = inputs.get(name)
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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("tax_empty", cls.TAX_EMPTY_OPTIONS, "best"),
            ("tax_aggregate", cls.TAX_LEVELS, "OTU"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        for name in ("plot_width", "plot_height"):
            validation = cls._validate_number(inputs, name, 1)
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "group_by": ("STRING", {"default": "", "description": "Discrete metadata variable used to group samples"}),
                "tax_empty": (
                    "STRING",
                    {"default": "best", "options": cls.TAX_EMPTY_OPTIONS, "description": "How to show OTUs without taxonomy"},
                ),
                "tax_aggregate": (
                    "STRING",
                    {"default": "OTU", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to aggregate OTUs"},
                ),
                "weight": ("BOOLEAN", {"default": True, "description": "Weight the frequency by abundance"}),
                "normalise": ("BOOLEAN", {"default": True, "description": "Transform OTU read counts to percent per sample"}),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2HeatmapNode(CommandNode):
    """Generate ampvis2 heatmaps from grouped metadata and taxonomy."""

    NODE_ID = "ampvis2_heatmap"
    DISPLAY_NAME = "ampvis2 heatmap"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate ampvis2 heatmaps from metadata-grouped samples and aggregated OTUs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 heatmap",
        "amp_heatmap",
        "microbiome heatmap",
        "amplicon heatmap",
        "taxonomy abundance heatmap",
    ]
    RETURN_TYPES = ("PDF", "TSV")
    RETURN_NAMES = ("plot", "plot_raw")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_heatmap.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    TAX_EMPTY_OPTIONS = ["remove", "best", "OTU"]
    TAX_SHOW_MODES = ["number", "explicit"]
    NORMALISE_BY_MODES = ["no", "variable", "sample"]
    SORT_BY_MODES = ["no", "group", "sample"]
    PLOT_FUNCTIONS_MODES = ["no", "midasfieldguide", "file"]
    PLOT_COLOR_SCALES = ["sqrt", "log10"]
    MEASURE_OPTIONS = ["mean", "max", "median"]
    OUT_FORMATS = ["pdf", "png", "svg", "tabular"]
    MIDAS_FUNCTIONS = ["MiDAS", "Filamentous", "AOB", "NOB", "GAO"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            return cls._r_vector(_as_list(inputs.get("tax_show")))
        return str(inputs.get("tax_show", 10) or 10)

    @classmethod
    def _plot_functions(cls, inputs: dict[str, Any]) -> list[str]:
        mode = str(inputs.get("plot_functions_mode", "no") or "no")
        if mode == "midasfieldguide":
            functions = _as_list(inputs.get("functions"))
            return functions if functions else cls.MIDAS_FUNCTIONS.copy()
        if mode == "file":
            return _as_list(inputs.get("functions"))
        return []

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        output_name = "raw" if out_format == "tabular" else "plot"
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'd <- readRDS("{inputs.get("data", "")}")',
            f"{output_name} <- amp_heatmap(",
            "    d,",
        ]
        if str(inputs.get("group_by", "")).strip():
            lines.append(f'    group_by = "{inputs.get("group_by")}",')
        if str(inputs.get("facet_by", "")).strip():
            lines.append(f'    facet_by = "{inputs.get("facet_by")}",')
        tax_add = _as_list(inputs.get("tax_add"))
        lines.extend(
            [
                f"    normalise = {cls._r_bool(inputs.get('normalise'), True)},",
                f'    tax_aggregate = "{inputs.get("tax_aggregate", "Phylum") or "Phylum"}",',
                f"    tax_add = {cls._r_vector(tax_add) if tax_add else 'NULL'},",
                f"    tax_show = {cls._tax_show(inputs)},",
                f"    showRemainingTaxa = {cls._r_bool(inputs.get('showRemainingTaxa'), False)},",
                f'    tax_empty = "{inputs.get("tax_empty", "best") or "best"}",',
            ]
        )
        if inputs.get("order_x_by"):
            lines.append('    order_x_by = "cluster",')
        if inputs.get("order_y_by"):
            lines.append('    order_y_by = "cluster",')
        plot_values = cls._r_bool(inputs.get("plot_values"), True)
        lines.append(f"    plot_values = {plot_values},")
        if plot_values == "TRUE":
            lines.append(f"    plot_values_size = {inputs.get('plot_values_size', 4) or 4},")
        lines.extend(
            [
                f'    plot_colorscale = "{inputs.get("plot_colorscale", "log10") or "log10"}",',
                f"    plot_na = {cls._r_bool(inputs.get('plot_na'), False)},",
                f'    measure = "{inputs.get("measure", "mean") or "mean"}",',
            ]
        )
        if inputs.get("min_abundance") not in (None, ""):
            lines.append(f"    min_abundance = {inputs.get('min_abundance')},")
        else:
            lines.append("    min_abundance = 0.1,")
        if inputs.get("max_abundance") not in (None, ""):
            lines.append(f"    max_abundance = {inputs.get('max_abundance')},")
        if str(inputs.get("sort_by_mode", "no") or "no") != "no" and str(inputs.get("sort_by", "")).strip():
            lines.append(f'    sort_by = "{inputs.get("sort_by")}",')
        if str(inputs.get("normalise_by_mode", "no") or "no") == "no":
            lines.append("    normalise_by = NULL,")
        elif str(inputs.get("normalise_by", "")).strip():
            lines.append(f'    normalise_by = "{inputs.get("normalise_by")}",')
        if str(inputs.get("scale_by", "")).strip():
            lines.append(f'    scale_by = "{inputs.get("scale_by")}",')
        lines.extend(
            [
                f'    color_vector = c("{inputs.get("color_palette_start", "") or ""}", "{inputs.get("color_palette_end", "") or ""}"),',
                f"    textmap = {'TRUE' if out_format == 'tabular' else 'FALSE'},",
            ]
        )
        plot_functions_mode = str(inputs.get("plot_functions_mode", "no") or "no")
        if plot_functions_mode != "no":
            lines.append("    plot_functions = TRUE,")
            if plot_functions_mode == "file":
                lines.append(
                    f'    function_data = read.table("{inputs.get("function_data", "")}", header = TRUE, sep = "\\t"),'
                )
            lines.append(f"    functions = {cls._r_vector(cls._plot_functions(inputs))},")
        lines.extend(
            [
                "    rel_widths = c(0.75, 0.25)",
                ")",
            ]
        )
        if out_format == "tabular":
            lines.append(f'write.table(raw, file = "{out}/plot_raw.tsv", sep = "\\t")')
        else:
            lines.extend(
                [
                    f'ggsave("{out}/plot.{out_format}",',
                    "    print(plot),",
                    ",\n".join(ggsave_options),
                    ")",
                ]
            )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/heatmap.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = cls._out_format(inputs)
        if out_format == "tabular":
            return [out / "plot_raw.tsv"]
        return [out / f"plot.{out_format}"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("normalise_by_mode", cls.NORMALISE_BY_MODES, "no"),
            ("tax_aggregate", cls.TAX_LEVELS, "Phylum"),
            ("tax_show_mode", cls.TAX_SHOW_MODES, "number"),
            ("tax_empty", cls.TAX_EMPTY_OPTIONS, "best"),
            ("plot_colorscale", cls.PLOT_COLOR_SCALES, "log10"),
            ("measure", cls.MEASURE_OPTIONS, "mean"),
            ("sort_by_mode", cls.SORT_BY_MODES, "no"),
            ("plot_functions_mode", cls.PLOT_FUNCTIONS_MODES, "no"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get("tax_add")) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            if not _as_list(inputs.get("tax_show")):
                return "tax_show must include at least one taxon when tax_show_mode is explicit"
        else:
            validation = cls._validate_number(inputs, "tax_show", 1, 10)
            if validation is not True:
                return validation
        for name, minimum, default in (
            ("plot_values_size", 1, 4),
            ("min_abundance", 0, 0.1),
            ("max_abundance", 0, None),
            ("plot_width", 1, None),
            ("plot_height", 1, None),
        ):
            validation = cls._validate_number(inputs, name, minimum, default)
            if validation is not True:
                return validation
        plot_functions_mode = str(inputs.get("plot_functions_mode", "no") or "no")
        if plot_functions_mode == "file":
            if not str(inputs.get("function_data", "")).strip():
                return "function_data is required when plot_functions_mode is file"
            if not _as_list(inputs.get("functions")):
                return "functions must include at least one value when plot_functions_mode is file"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": ("FILE", {"description": "Ampvis2 RDS dataset generated with ampvis2: load"}),
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "group_by": ("STRING", {"default": "", "description": "Categorical metadata variable used to group samples"}),
                "facet_by": ("STRING", {"default": "", "description": "Categorical metadata variable used to facet samples"}),
                "normalise": ("BOOLEAN", {"default": True, "description": "Transform OTU read counts to percent per sample"}),
                "normalise_by_mode": (
                    "STRING",
                    {"default": "no", "options": cls.NORMALISE_BY_MODES, "description": "Normalise by no value, a metadata value, or a sample"},
                ),
                "normalise_by": (
                    "STRING",
                    {"default": "", "description": "Metadata value or sample used for normalising counts"},
                ),
                "tax_aggregate": (
                    "STRING",
                    {"default": "Phylum", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to aggregate OTUs"},
                ),
                "tax_add": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.TAX_LEVELS,
                        "description": "Additional taxonomic levels to display",
                    },
                ),
                "tax_show_mode": (
                    "STRING",
                    {"default": "number", "options": cls.TAX_SHOW_MODES, "description": "Limit displayed taxa by count or explicit list"},
                ),
                "taxonomy_list": (
                    "TSV",
                    {"default": "", "description": "Taxonomy list generated by ampvis2: load for explicit taxon selection"},
                ),
                "tax_show": ("STRING", {"default": 10, "description": "Number of taxa or explicit taxa to show"}),
                "showRemainingTaxa": (
                    "BOOLEAN",
                    {"default": False, "description": "Display a row with the sum of taxa outside the selected taxa"},
                ),
                "tax_empty": (
                    "STRING",
                    {"default": "best", "options": cls.TAX_EMPTY_OPTIONS, "description": "How to show OTUs without taxonomy"},
                ),
                "order_x_by": ("BOOLEAN", {"default": False, "description": "Cluster the heatmap x axis"}),
                "order_y_by": ("BOOLEAN", {"default": False, "description": "Cluster the heatmap y axis"}),
                "plot_values": ("BOOLEAN", {"default": True, "description": "Plot abundance values on the heatmap"}),
                "plot_values_size": ("INT", {"default": 4, "min": 1, "description": "Size of plotted abundance values"}),
                "plot_colorscale": (
                    "STRING",
                    {"default": "log10", "options": cls.PLOT_COLOR_SCALES, "description": "Scale used for coloring abundances"},
                ),
                "plot_na": (
                    "BOOLEAN",
                    {"default": False, "description": "Color missing values with the lowest color in the scale"},
                ),
                "measure": (
                    "STRING",
                    {"default": "mean", "options": cls.MEASURE_OPTIONS, "description": "Statistic shown across sample groups"},
                ),
                "min_abundance": ("FLOAT", {"default": 0.1, "min": 0, "description": "Lower abundance color clamp"}),
                "max_abundance": ("FLOAT", {"default": "", "min": 0, "description": "Upper abundance color clamp"}),
                "sort_by_mode": (
                    "STRING",
                    {"default": "no", "options": cls.SORT_BY_MODES, "description": "Sort heatmap by no value, group, or sample"},
                ),
                "sort_by": ("STRING", {"default": "", "description": "Group or sample used to sort most abundant taxa"}),
                "color_palette_start": ("STRING", {"default": "", "description": "Start color for the heatmap"}),
                "color_palette_end": ("STRING", {"default": "", "description": "End color for the heatmap"}),
                "scale_by": ("STRING", {"default": "", "description": "Metadata variable used to scale abundances"}),
                "plot_functions_mode": (
                    "STRING",
                    {
                        "default": "no",
                        "options": cls.PLOT_FUNCTIONS_MODES,
                        "description": "Show Genus-level functional information from MiDAS or a table",
                    },
                ),
                "function_data": ("TSV", {"default": "", "description": "Functional information table with Genus in the first column"}),
                "functions": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Function columns to display next to Genus-level OTUs",
                    },
                ),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot or table output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2LoadNode(CommandNode):
    """Load OTU, ASV, BIOM, or phyloseq data into an ampvis2 object."""

    NODE_ID = "ampvis2_load"
    DISPLAY_NAME = "ampvis2 load"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Load OTU, ASV, BIOM, or phyloseq data into an ampvis2 RDS object."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 load",
        "amp_load",
        "OTU table",
        "ASV table",
        "BIOM",
        "phyloseq",
        "metadata list",
        "taxonomy list",
    ]
    RETURN_TYPES = ("FILE", "TSV", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out", "taxonomy_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_load.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    OTUTABLE_TYPES = ["tabular", "dada2_sequencetable", "biom1", "biom2", "phyloseq"]
    WRITE_LIST_OPTIONS = ["tax", "metadata"]
    DEFAULT_WRITE_LISTS = ["tax", "metadata"]
    LIST_OUTPUT_FILES = {
        "tax": "taxonomy_list.tsv",
        "metadata": "metadata_list.tsv",
    }

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _otutable_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("otutable_type", "tabular") or "tabular")

    @classmethod
    def _selected_write_lists(cls, inputs: dict[str, Any]) -> list[str]:
        if "write_lists" in inputs:
            return _as_list(inputs.get("write_lists"))
        return cls.DEFAULT_WRITE_LISTS.copy()

    @classmethod
    def _staging_commands(cls, inputs: dict[str, Any]) -> list[str]:
        otutable_type = cls._otutable_type(inputs)
        commands = []
        if otutable_type in {"biom1", "biom2"}:
            commands.append(_shell_join(["ln", "-s", str(inputs.get("otutable", "")), "otutable.biom"]))
        elif otutable_type != "phyloseq":
            if inputs.get("asv_otu_col_empty"):
                commands.append(
                    _shell_join(["sed", "-e", "1 s/^\\t/ASV\\t/", str(inputs.get("otutable", "")), ">", "otutable.tsv"])
                )
            else:
                commands.append(_shell_join(["ln", "-s", str(inputs.get("otutable", "")), "otutable.tsv"]))
        if str(inputs.get("taxonomy", "")).strip():
            if inputs.get("asv_otu_col_empty"):
                commands.append(
                    _shell_join(["sed", "-e", "1 s/^\\t/ASV\\t/", str(inputs.get("taxonomy", "")), ">", "taxonomy.tsv"])
                )
            else:
                commands.append(_shell_join(["ln", "-s", str(inputs.get("taxonomy", "")), "taxonomy.tsv"]))
        return commands

    @classmethod
    def _metadata_lines(cls, inputs: dict[str, Any]) -> list[str]:
        metadata = str(inputs.get("metadata", "")).strip()
        if not metadata:
            return []
        return [
            f'metadata <- read.table("{metadata}", header = TRUE, sep = "\\t", colClasses = "character", check.names=F)',
            'if(colnames(metadata)[1] == ""){',
            '    colnames(metadata)[1] <- "SampleID"',
            "}",
            'if(exists("SampleID", where = metadata)){',
            '    rownames(metadata) <- metadata[["SampleID"]]',
            "}else{",
            "    rownames(metadata) <- metadata[[1]]",
            "}",
            "",
        ]

    @classmethod
    def _amp_load_otutable_line(cls, inputs: dict[str, Any]) -> str:
        otutable_type = cls._otutable_type(inputs)
        if otutable_type == "phyloseq":
            return "    otutable = otutable,"
        if otutable_type in {"biom1", "biom2"}:
            return '    otutable = "otutable.biom",'
        return '    otutable = "otutable.tsv",'

    @classmethod
    def _amp_load_lines(cls, inputs: dict[str, Any]) -> list[str]:
        lines = [
            "data <- amp_load(",
            cls._amp_load_otutable_line(inputs),
        ]
        if str(inputs.get("metadata", "")).strip():
            lines.append("    metadata = metadata,")
        if str(inputs.get("taxonomy", "")).strip():
            lines.append('    taxonomy = "taxonomy.tsv",')
        if str(inputs.get("fasta", "")).strip():
            lines.append(f'    fasta = "{inputs.get("fasta")}",')
        if str(inputs.get("tree", "")).strip():
            lines.append(f'    tree = "{inputs.get("tree")}",')
        if str(inputs.get("otutable_OTUcolname", "")).strip():
            lines.append(f'    otutable_OTUcolname = c("{inputs.get("otutable_OTUcolname")}"),')
        if str(inputs.get("taxonomy_OTUcolname", "")).strip():
            lines.append(f'    taxonomy_OTUcolname = c("{inputs.get("taxonomy_OTUcolname")}"),')
        lines.extend(
            [
                f"    pruneSingletons = {cls._r_bool(inputs.get('pruneSingletons'), False)}",
                ")",
            ]
        )
        return lines

    @classmethod
    def _asv_sequence_lines(cls, inputs: dict[str, Any]) -> list[str]:
        if not inputs.get("asv_sequences"):
            return []
        return [
            "",
            "library(ape, quietly = TRUE)",
            "",
            'seq <- as.DNAbin(strsplit(rownames(data$abund), ""))',
            'names(seq) <- paste0("ASV", seq_along(seq))',
            "data$refseq <- seq",
            "data <- matchOTUs(data, seq)",
        ]

    @classmethod
    def _metadata_list_lines(cls, out: str) -> list[str]:
        return [
            "classes <- sapply(data$metadata, class)",
            'data$metadata[is.na(data$metadata)] <- "NA"',
            "for(name in names(data$metadata)){",
            '    if(classes[[name]] == "character" && all(data$metadata[[name]] == rownames(data$metadata))){',
            "        sample_names <- TRUE;",
            "    }else{",
            "        sample_names <- FALSE;",
            "    }",
            "    for(m in unique(data$metadata[[name]])){",
            f'        write(paste(name, m, sample_names, classes[[name]], sep="\\t"), file="{out}/metadata_list.tsv", append=T);',
            "    }",
            "}",
        ]

    @classmethod
    def _taxonomy_list_lines(cls, out: str) -> list[str]:
        return [
            "for(level in colnames(data$tax)){",
            "    for(u in unique(data$tax[level])){",
            f'        write(paste(u, level, sep="\\t"), file="{out}/taxonomy_list.tsv", append=T)',
            "    }",
            "}",
        ]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = [
            "library(ampvis2, quietly = TRUE)",
            "library(readr, quietly = TRUE)",
            "",
            *cls._metadata_lines(inputs),
        ]
        if cls._otutable_type(inputs) == "phyloseq":
            lines.extend(
                [
                    f'otutable <- readRDS("{inputs.get("otutable", "")}")',
                    "print(class(otutable))",
                    "",
                ]
            )
        lines.extend(cls._amp_load_lines(inputs))
        lines.extend(cls._asv_sequence_lines(inputs))
        if cls._r_bool(inputs.get("guess_column_types"), True) == "TRUE":
            lines.extend(
                [
                    "",
                    "data$metadata <- readr::type_convert(data$metadata, guess_integer=TRUE)",
                ]
            )
        lines.extend(
            [
                "",
                f'saveRDS(data, "{out}/ampvis.rds")',
            ]
        )
        for list_name in cls._selected_write_lists(inputs):
            if list_name == "metadata":
                lines.extend(["", *cls._metadata_list_lines(out)])
            elif list_name == "tax":
                lines.extend(["", *cls._taxonomy_list_lines(out)])
        lines.extend(["", "data"])
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/load.R"
        commands = [
            *cls._staging_commands(inputs),
            f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT",
            _shell_join(["Rscript", script_path]),
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "ampvis.rds"]
        selected_lists = set(cls._selected_write_lists(inputs))
        outputs.extend(
            out / cls.LIST_OUTPUT_FILES[list_name]
            for list_name in ("metadata", "tax")
            if list_name in selected_lists
        )
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("otutable", "")).strip():
            return "otutable is required"
        otutable_type = cls._otutable_type(inputs)
        if otutable_type not in cls.OTUTABLE_TYPES:
            return f"otutable_type must be one of: {', '.join(cls.OTUTABLE_TYPES)}"
        unsupported_lists = [name for name in _as_list(inputs.get("write_lists")) if name not in cls.WRITE_LIST_OPTIONS]
        if unsupported_lists:
            return f"write_lists contains unsupported values: {', '.join(unsupported_lists)}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "otutable": ("FILE", {"description": "OTU, ASV, BIOM, or phyloseq dataset"}),
            },
            "optional": {
                "otutable_type": (
                    "STRING",
                    {
                        "default": "tabular",
                        "options": cls.OTUTABLE_TYPES,
                        "description": "Galaxy datatype of the OTU table input",
                    },
                ),
                "asv_sequences": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat ASV identifiers as ASV sequences and store them in the ampvis2 object"},
                ),
                "metadata": ("TSV", {"default": "", "description": "Optional sample metadata table"}),
                "guess_column_types": (
                    "BOOLEAN",
                    {"default": True, "description": "Guess metadata column types with readr::type_convert"},
                ),
                "taxonomy": ("TSV", {"default": "", "description": "Optional taxonomy table"}),
                "fasta": ("FASTA", {"default": "", "description": "Optional FASTA file containing OTU or ASV sequences"}),
                "tree": ("FILE", {"default": "", "description": "Optional phylogenetic tree in Newick format"}),
                "pruneSingletons": ("BOOLEAN", {"default": False, "description": "Remove singleton OTUs"}),
                "write_lists": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_WRITE_LISTS.copy(),
                        "multiple": True,
                        "options": cls.WRITE_LIST_OPTIONS,
                        "description": "Auxiliary metadata and taxonomy list outputs for downstream ampvis2 tools",
                    },
                ),
                "asv_otu_col_empty": (
                    "BOOLEAN",
                    {"default": False, "description": "Replace an empty OTU/ASV column header with ASV before loading"},
                ),
                "otutable_OTUcolname": (
                    "STRING",
                    {"default": "", "description": "OTU column name in the OTU table"},
                ),
                "taxonomy_OTUcolname": (
                    "STRING",
                    {"default": "", "description": "OTU column name in the taxonomy table"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2MergeAmpvis2Node(CommandNode):
    """Merge multiple ampvis2 RDS datasets into one ampvis2 object."""

    NODE_ID = "ampvis2_merge_ampvis2"
    DISPLAY_NAME = "ampvis2 merge ampvis2 data sets"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Merge multiple ampvis2 RDS datasets into a single ampvis2 object."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 merge ampvis2 data sets",
        "amp_merge_ampvis2",
        "merge ampvis2 objects",
        "RDS merge",
        "by reference sequence",
        "DNA reference sequences",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_merge_ampvis2.html"
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
    def _data_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("data"))

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output.rds"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any]) -> str:
        data_lines = [f'    readRDS("{data_file}"),' for data_file in cls._data_files(inputs)]
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                "merged <- amp_merge_ampvis2(",
                *data_lines,
                f"    by_refseq = {cls._r_bool(inputs.get('by_refseq'), True)}",
                ")",
                f'saveRDS(merged, "{cls._output_path(inputs)}")',
                "merged",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/merge_ampvis2.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.rds"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._data_files(inputs):
            return "at least one ampvis2 data set is required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data": (
                    "FILE",
                    {"multiple": True, "description": "Ampvis2 RDS datasets generated with ampvis2: load"},
                ),
            },
            "optional": {
                "by_refseq": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Merge by exact DNA reference sequence matches and use those sequences as output names",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2MergeReplicatesNode(CommandNode):
    """Merge replicate samples in an ampvis2 object by metadata group."""

    NODE_ID = "ampvis2_mergereplicates"
    DISPLAY_NAME = "ampvis2 merge replicates"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Merge replicate samples in an ampvis2 RDS dataset by averaging OTU abundances."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 merge replicates",
        "amp_mergereplicates",
        "amp_merge_replicates",
        "replicate samples",
        "average OTU abundances",
        "metadata groups",
    ]
    RETURN_TYPES = ("FILE", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_merge_replicates.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    ROUND_OPTIONS = ["", "up", "down"]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        round_value = str(inputs.get("round", "") or "")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "data <- amp_mergereplicates(",
            "    data,",
            f'    merge_var = "{inputs.get("merge_var", "")}"{"," if round_value else ""}',
        ]
        if round_value:
            lines.append(f'    round = "{round_value}"')
        lines.extend(
            [
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
        script_path = f"{out}/mergereplicates.R"
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
        if not str(inputs.get("merge_var", "")).strip():
            return "merge_var is required"
        round_value = str(inputs.get("round", "") or "")
        if round_value not in cls.ROUND_OPTIONS:
            return f"round must be one of: {', '.join(cls.ROUND_OPTIONS)}"
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
                "merge_var": ("STRING", {"description": "Discrete metadata variable defining replicate sample groups"}),
            },
            "optional": {
                "round": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.ROUND_OPTIONS,
                        "description": "Round merged read count decimals up, down, or not at all",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2OctaveNode(CommandNode):
    """Generate ampvis2 octave plots for sequencing-depth assessment."""

    NODE_ID = "ampvis2_octave"
    DISPLAY_NAME = "ampvis2 octave plot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate octave plots to assess alpha diversity sequencing depth."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 octave plot",
        "amp_octave",
        "octave plot",
        "alpha diversity",
        "sequencing depth",
        "read count bins",
        "microbiome diversity",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_octave.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    SCALE_OPTIONS = ["fixed", "free", "free_x", "free_y"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'd <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_octave(",
            "    d,",
            f'    tax_aggregate = "{inputs.get("tax_aggregate", "OTU") or "OTU"}",',
        ]
        if str(inputs.get("group_by", "")).strip():
            lines.extend(
                [
                    f'    group_by = "{inputs.get("group_by")}",',
                    f'    scales = "{inputs.get("scales", "fixed") or "fixed"}",',
                ]
            )
        lines.extend(
            [
                "    num_threads = 1",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/octave.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float) -> bool | str:
        raw = inputs.get(name)
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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("tax_aggregate", cls.TAX_LEVELS, "OTU"),
            ("scales", cls.SCALE_OPTIONS, "fixed"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        for name in ("plot_width", "plot_height"):
            validation = cls._validate_number(inputs, name, 1)
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "tax_aggregate": (
                    "STRING",
                    {"default": "OTU", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to aggregate OTUs"},
                ),
                "group_by": ("STRING", {"default": "", "description": "Discrete metadata variable used to group samples"}),
                "scales": (
                    "STRING",
                    {"default": "fixed", "options": cls.SCALE_OPTIONS, "description": "Facet axis scale behavior when grouping samples"},
                ),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2OrdinateNode(CommandNode):
    """Generate ampvis2 ordination plots for microbial community comparisons."""

    NODE_ID = "ampvis2_ordinate"
    DISPLAY_NAME = "ampvis2 ordination plot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate ampvis2 ordination plots for comparing microbial communities."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 ordination plot",
        "amp_ordinate",
        "ordination",
        "vegan ordination",
        "PCA",
        "RDA",
        "CCA",
        "NMDS",
        "PCoA",
        "microbial communities",
    ]
    RETURN_TYPES = ("PDF", "PDF")
    RETURN_NAMES = ("plot", "screeplot")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_ordinate.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TYPE_OPTIONS = ["PCA", "RDA", "CA", "CCA", "DCA", "NMDS", "MMDS"]
    DISTMEASURE_OPTIONS = [
        "wunifrac",
        "unifrac",
        "jsd",
        "manhattan",
        "euclidean",
        "canberra",
        "bray",
        "kulczynski",
        "jaccard",
        "gower",
        "altGower",
        "morisita",
        "horn",
        "mountford",
        "raup",
        "binomial",
        "chao",
        "cao",
        "mahalanobis",
        "clark",
        "chisq",
        "chord",
        "hellinger",
        "aitchison",
        "robust.aitchison",
    ]
    TRANSFORM_OPTIONS = [
        "none",
        "total",
        "max",
        "freq",
        "normalize",
        "range",
        "standardize",
        "pa",
        "chi.square",
        "hellinger",
        "log",
        "sqrt",
    ]
    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    TAX_EMPTY_OPTIONS = ["remove", "best", "OTU"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _type(cls, inputs: dict[str, Any]) -> str:
        value = str(inputs.get("type", "PCA") or "PCA")
        return value if value in cls.TYPE_OPTIONS else "PCA"

    @classmethod
    def _transform(cls, inputs: dict[str, Any]) -> str:
        transform = str(inputs.get("transform", "") or "")
        if transform:
            return transform
        if cls._type(inputs) in {"NMDS", "MMDS"}:
            return "none"
        return "hellinger"

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def _validate_number(
        cls,
        inputs: dict[str, Any],
        name: str,
        minimum: int | float,
        default: Any = None,
        maximum: int | float | None = None,
    ) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ""):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if value < minimum:
            return f"{name} must be >= {minimum}"
        if maximum is not None and value > maximum:
            return f"{name} must be <= {maximum}"
        return True

    @classmethod
    def _add_optional_string_line(cls, lines: list[str], inputs: dict[str, Any], name: str) -> None:
        value = str(inputs.get(name, "") or "")
        if value.strip():
            lines.append(f'    {name} = "{value}",')

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ordination_type = cls._type(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "details <- amp_ordinate(",
            "    data,",
            f"    filter_species = {inputs.get('filter_species', 0.1) if inputs.get('filter_species') not in (None, '') else 0.1},",
            f'    type = "{ordination_type}",',
        ]
        if ordination_type in {"MMDS", "NMDS"}:
            lines.append(f'    distmeasure = "{inputs.get("distmeasure", "bray") or "bray"}",')
        lines.append(f'    transform = "{cls._transform(inputs)}",')
        if ordination_type in {"RDA", "CCA"}:
            lines.append(f"    constrain = {cls._r_vector(_as_list(inputs.get('constrain')))},")
        lines.append(f"    print_caption = {cls._r_bool(inputs.get('print_caption'), False)},")
        for name in (
            "sample_color_by",
            "sample_shape_by",
            "sample_colorframe",
            "sample_colorframe_label",
            "sample_label_by",
        ):
            cls._add_optional_string_line(lines, inputs, name)
        if str(inputs.get("sample_trajectory", "") or "").strip():
            lines.append(f'    sample_trajectory = "{inputs.get("sample_trajectory")}",')
        cls._add_optional_string_line(lines, inputs, "sample_trajectory_group")
        if cls._r_bool(inputs.get("species_plot"), False) == "TRUE":
            lines.extend(
                [
                    "    species_plot = TRUE,",
                    f"    species_nlabels = {inputs.get('species_nlabels', 10) or 10},",
                    f'    species_label_taxonomy = "{inputs.get("species_label_taxonomy", "Genus") or "Genus"}",',
                    f"    species_label_size = {inputs.get('species_label_size', 3) or 3},",
                ]
            )
        cls._add_optional_string_line(lines, inputs, "envfit_factor")
        cls._add_optional_string_line(lines, inputs, "envfit_numeric")
        lines.extend(
            [
                f"    envfit_signif_level = {inputs.get('envfit_signif_level', 0.005) if inputs.get('envfit_signif_level') not in (None, '') else 0.005},",
                f"    repel_labels = {cls._r_bool(inputs.get('repel_labels'), False)},",
                f"    opacity = {inputs.get('opacity', 0.8) if inputs.get('opacity') not in (None, '') else 0.8},",
                f'    tax_empty = "{inputs.get("tax_empty", "best") or "best"}",',
                "    detailed_output = TRUE",
                ")",
                "plot <- details$plot",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        if inputs.get("output_screeplot"):
            lines.append(f'ggsave("{out}/screeplot.{out_format}", print(details$screeplot), device = "{out_format}")')
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/ordinate.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        out_format = cls._out_format(inputs)
        outputs = [out / f"plot.{out_format}"]
        if inputs.get("output_screeplot"):
            outputs.append(out / f"screeplot.{out_format}")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("type", cls.TYPE_OPTIONS, "PCA"),
            ("distmeasure", cls.DISTMEASURE_OPTIONS, "bray"),
            ("transform", cls.TRANSFORM_OPTIONS, cls._transform(inputs)),
            ("species_label_taxonomy", cls.TAX_LEVELS, "Genus"),
            ("tax_empty", cls.TAX_EMPTY_OPTIONS, "best"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        if cls._type(inputs) in {"RDA", "CCA"} and not _as_list(inputs.get("constrain")):
            return "constrain must include at least one metadata variable for RDA/CCA"
        for name, minimum, default, maximum in (
            ("filter_species", 0, 0.1, None),
            ("species_nlabels", 1, 10, None),
            ("species_label_size", 1, 3, None),
            ("envfit_signif_level", 0, 0.005, 1),
            ("opacity", 0, 0.8, 1),
            ("plot_width", 1, None, None),
            ("plot_height", 1, None, None),
        ):
            validation = cls._validate_number(inputs, name, minimum, default, maximum)
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "filter_species": ("FLOAT", {"default": 0.1, "min": 0, "description": "Remove low-abundance OTUs below this percent threshold"}),
                "type": (
                    "STRING",
                    {"default": "PCA", "options": cls.TYPE_OPTIONS, "description": "Ordination method"},
                ),
                "distmeasure": (
                    "STRING",
                    {"default": "bray", "options": cls.DISTMEASURE_OPTIONS, "description": "Distance measure for NMDS/MMDS"},
                ),
                "transform": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.TRANSFORM_OPTIONS,
                        "description": "Abundance transformation before ordination; blank uses Galaxy's method-specific default",
                    },
                ),
                "constrain": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "description": "Metadata variables constraining RDA/CCA analyses"},
                ),
                "print_caption": ("BOOLEAN", {"default": False, "description": "Auto-generate a figure caption"}),
                "sample_color_by": ("STRING", {"default": "", "description": "Metadata variable used to color sample points"}),
                "sample_shape_by": ("STRING", {"default": "", "description": "Metadata variable used to shape sample points"}),
                "sample_colorframe": ("STRING", {"default": "", "description": "Metadata variable used to frame sample points"}),
                "sample_colorframe_label": ("STRING", {"default": "", "description": "Metadata variable used to label sample frames"}),
                "sample_label_by": ("STRING", {"default": "", "description": "Metadata variable used to label sample points"}),
                "sample_trajectory": ("STRING", {"default": "", "description": "Metadata variable used to draw sample trajectories"}),
                "sample_trajectory_group": ("STRING", {"default": "", "description": "Metadata variable grouping sample trajectories"}),
                "species_plot": ("BOOLEAN", {"default": False, "description": "Plot species points"}),
                "species_nlabels": (
                    "INT",
                    {"default": 10, "min": 1, "description": "Number of extreme species labels to plot"},
                ),
                "species_label_taxonomy": (
                    "STRING",
                    {"default": "Genus", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to label species points"},
                ),
                "species_label_size": ("INT", {"default": 3, "min": 1, "description": "Species label text size"}),
                "envfit_factor": ("STRING", {"default": "", "description": "Categorical metadata variable to fit onto the ordination"}),
                "envfit_numeric": ("STRING", {"default": "", "description": "Numeric metadata variable to fit as arrows"}),
                "envfit_signif_level": (
                    "FLOAT",
                    {"default": 0.005, "min": 0, "max": 1, "description": "Significance threshold for envfit results"},
                ),
                "repel_labels": ("BOOLEAN", {"default": False, "description": "Repel labels to reduce overlap"}),
                "opacity": ("FLOAT", {"default": 0.8, "min": 0, "max": 1, "description": "Point and color-frame opacity"}),
                "tax_empty": (
                    "STRING",
                    {"default": "best", "options": cls.TAX_EMPTY_OPTIONS, "description": "How to show OTUs without taxonomy"},
                ),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
                "output_screeplot": ("BOOLEAN", {"default": False, "description": "Also output the ordination screeplot"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2OtuNetworkNode(CommandNode):
    """Generate ampvis2 OTU network plots connecting taxa and samples."""

    NODE_ID = "ampvis2_otu_network"
    DISPLAY_NAME = "ampvis2 OTU network plot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate network plots connecting taxa and samples from an ampvis2 RDS dataset."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 OTU network plot",
        "amp_otu_network",
        "OTU network",
        "taxa sample network",
        "ggnet2",
        "microbiome network",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_otu_network.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    TAX_EMPTY_OPTIONS = ["remove", "best", "OTU"]
    TAX_SHOW_MODES = ["number", "explicit"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            return cls._r_vector(_as_list(inputs.get("tax_show")))
        return str(inputs.get("tax_show", 10) or 10)

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        tax_add = _as_list(inputs.get("tax_add"))
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_otu_network(",
            "    data,",
            f"    min_abundance = {inputs.get('min_abundance', 0) if inputs.get('min_abundance') not in (None, '') else 0},",
        ]
        if str(inputs.get("color_by", "") or "").strip():
            lines.append(f'    color_by = "{inputs.get("color_by")}",')
        lines.extend(
            [
                f'    tax_aggregate = "{inputs.get("tax_aggregate", "Phylum") or "Phylum"}",',
                f"    tax_add = {cls._r_vector(tax_add) if tax_add else 'NULL'},",
                f"    tax_show = {cls._tax_show(inputs)},",
                "    tax_class = NULL,",
                f'    tax_empty = "{inputs.get("tax_empty", "best") or "best"}",',
                f"    normalise = {cls._r_bool(inputs.get('normalise'), True)}",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/otu_network.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("tax_aggregate", cls.TAX_LEVELS, "Phylum"),
            ("tax_show_mode", cls.TAX_SHOW_MODES, "number"),
            ("tax_empty", cls.TAX_EMPTY_OPTIONS, "best"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get("tax_add")) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            if not _as_list(inputs.get("tax_show")):
                return "tax_show must include at least one taxon when tax_show_mode is explicit"
        else:
            validation = cls._validate_number(inputs, "tax_show", 1, 10)
            if validation is not True:
                return validation
        for name, minimum, default in (
            ("min_abundance", 0, 0),
            ("plot_width", 1, None),
            ("plot_height", 1, None),
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "min_abundance": (
                    "FLOAT",
                    {"default": 0, "min": 0, "description": "Minimum per-sample taxa abundance"},
                ),
                "color_by": ("STRING", {"default": "", "description": "Metadata variable used to color samples"}),
                "tax_aggregate": (
                    "STRING",
                    {"default": "Phylum", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to aggregate OTUs"},
                ),
                "tax_add": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.TAX_LEVELS,
                        "description": "Additional taxonomic levels to display",
                    },
                ),
                "tax_show_mode": (
                    "STRING",
                    {"default": "number", "options": cls.TAX_SHOW_MODES, "description": "Limit displayed taxa by count or explicit list"},
                ),
                "taxonomy_list": (
                    "TSV",
                    {"default": "", "description": "Taxonomy list generated by ampvis2: load for explicit taxon selection"},
                ),
                "tax_show": ("STRING", {"default": 10, "description": "Number of taxa or explicit taxa to display"}),
                "tax_empty": (
                    "STRING",
                    {"default": "best", "options": cls.TAX_EMPTY_OPTIONS, "description": "How to show OTUs without taxonomy"},
                ),
                "normalise": ("BOOLEAN", {"default": True, "description": "Transform OTU read counts to percent per sample"}),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2RankAbundanceNode(CommandNode):
    """Generate ampvis2 rank-abundance curves by sample group."""

    NODE_ID = "ampvis2_rankabundance"
    DISPLAY_NAME = "ampvis2 rank abundance plot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate rank-abundance curves from grouped ampvis2 samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 rank abundance plot",
        "amp_rankabundance",
        "rank abundance curve",
        "cumulative read abundance",
        "OTU rank abundance",
        "microbiome diversity",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_rankabundance.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    , {option} = {value}")
        return "\n".join(
            [
                "library(ampvis2, quietly = TRUE)",
                f'data <- readRDS("{inputs.get("data", "")}")',
                "plot <- amp_rankabundance(",
                "    data,",
                f'    group_by = "{inputs.get("group_by", "")}",',
                f"    showSD = {cls._r_bool(inputs.get('showSD'), True)},",
                f"    log10_x = {cls._r_bool(inputs.get('log10_x'), True)}",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/rankabundance.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_number(cls, inputs: dict[str, Any], name: str, minimum: int | float) -> bool | str:
        raw = inputs.get(name)
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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        if not str(inputs.get("metadata_list", "")).strip():
            return "metadata_list is required"
        if not str(inputs.get("group_by", "")).strip():
            return "group_by is required"
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name in ("plot_width", "plot_height"):
            validation = cls._validate_number(inputs, name, 1)
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
                "group_by": ("STRING", {"description": "Discrete metadata variable used to group samples"}),
            },
            "optional": {
                "showSD": ("BOOLEAN", {"default": True, "description": "Show standard deviation from mean intervals"}),
                "log10_x": (
                    "BOOLEAN",
                    {"default": True, "description": "Log10-transform the x axis to emphasize abundant OTUs"},
                ),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2RarecurveNode(CommandNode):
    """Generate ampvis2 rarefaction curves for observed OTUs per sample."""

    NODE_ID = "ampvis2_rarecurve"
    DISPLAY_NAME = "ampvis2 rarefaction curve"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate rarefaction curves showing reads versus observed OTUs for ampvis2 samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 rarefaction curve",
        "amp_rarecurve",
        "amp_rarefaction_curve",
        "rarefaction curve",
        "observed OTUs",
        "reads versus observed OTUs",
        "microbiome rarefaction",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_rarecurve.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    FACET_SCALE_OPTIONS = ["fixed", "free", "free_x", "free_y"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    {option} = {value}")
        args = [
            "    data",
            f"    stepsize = {inputs.get('stepsize', 1000) if inputs.get('stepsize') not in (None, '') else 1000}",
        ]
        if str(inputs.get("color_by", "") or "").strip():
            args.append(f'    color_by = "{inputs.get("color_by")}"')
        if str(inputs.get("facet_by", "") or "").strip():
            args.append(f'    facet_by = "{inputs.get("facet_by")}"')
            if str(inputs.get("facet_scales", "") or "").strip():
                args.append(f'    facet_scales = "{inputs.get("facet_scales")}"')
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_rarecurve(",
            ",\n".join(args),
        ]
        lines.extend(
            [
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/rarecurve.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

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
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name, options, default in (
            ("facet_scales", cls.FACET_SCALE_OPTIONS, "fixed"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        for name, minimum, default in (
            ("stepsize", 1, 1000),
            ("plot_width", 1, None),
            ("plot_height", 1, None),
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "stepsize": ("INT", {"default": 1000, "min": 1, "description": "Read-count increment between rarefaction points"}),
                "color_by": ("STRING", {"default": "", "description": "Metadata variable used to color sample curves"}),
                "facet_by": ("STRING", {"default": "", "description": "Metadata variable used to split curves into panels"}),
                "facet_scales": (
                    "STRING",
                    {
                        "default": "fixed",
                        "options": cls.FACET_SCALE_OPTIONS,
                        "description": "Axis scaling mode for faceted panels",
                    },
                ),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2SetMetadataNode(CommandNode):
    """Set ampvis2 metadata column classes and regenerate metadata selectors."""

    NODE_ID = "ampvis2_setmetadata"
    DISPLAY_NAME = "ampvis2 set metadata"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq", "r-lubridate"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Manually set ampvis2 sample metadata column types and regenerate the metadata list."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 set metadata",
        "metadata type conversion",
        "metadata classes",
        "as.numeric metadata",
        "as.integer metadata",
        "lubridate as_date",
        "sample metadata list",
    ]
    RETURN_TYPES = ("FILE", "TSV")
    RETURN_NAMES = ("ampvis", "metadata_list_out")
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://github.com/galaxyproject/tools-iuc/blob/main/tools/ampvis2/setmetadata.xml"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TYPE_INPUTS = ("character", "numbers", "integers", "dates")

    @classmethod
    def _column_names(cls, inputs: dict[str, Any], name: str) -> list[str]:
        return [str(value).strip() for value in _as_list(inputs.get(name)) if str(value).strip()]

    @classmethod
    def _raw_column_names(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, (list, tuple)):
            return [str(item).strip() for item in value]
        return [str(value).strip()]

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        lines = [
            "library(lubridate, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
        ]
        for column in cls._column_names(inputs, "character"):
            lines.append(f"data$metadata${column} <- as.character(data$metadata${column})")
        for column in cls._column_names(inputs, "numbers"):
            lines.append(f"data$metadata${column} <- as.numeric(data$metadata${column})")
        for column in cls._column_names(inputs, "integers"):
            lines.append(f"data$metadata${column} <- as.integer(data$metadata${column})")
        for column in cls._column_names(inputs, "dates"):
            lines.append(f"data$metadata${column} <- as_date(data$metadata${column})")
        lines.extend(
            [
                f'saveRDS(data, "{out}/ampvis.rds")',
                *Ampvis2LoadNode._metadata_list_lines(out),
                "data",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/setmetadata.R"
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
        raw_values = [column for name in cls.TYPE_INPUTS for column in cls._raw_column_names(inputs.get(name))]
        if any(not column for column in raw_values):
            return "metadata column names must be non-empty"
        seen: set[str] = set()
        duplicates: list[str] = []
        for column in raw_values:
            if column in seen and column not in duplicates:
                duplicates.append(column)
            seen.add(column)
        if duplicates:
            return f"metadata columns can only be assigned to one type: {', '.join(duplicates)}"
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
            },
            "optional": {
                "character": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Metadata variables to keep or cast as character values",
                    },
                ),
                "numbers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Metadata variables to cast with as.numeric",
                    },
                ),
                "integers": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Discrete numerical metadata variables to cast with as.integer",
                    },
                ),
                "dates": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Date metadata variables to cast with lubridate::as_date",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2SubsetSamplesNode(CommandNode):
    """Subset ampvis2 samples by metadata variable values."""

    NODE_ID = "ampvis2_subset_samples"
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

    NODE_ID = "ampvis2_subset_taxa"
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

class Ampvis2TimeseriesNode(CommandNode):
    """Generate ampvis2 time-series abundance plots."""

    NODE_ID = "ampvis2_timeseries"
    DISPLAY_NAME = "ampvis2 timeseries plot"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate ampvis2 time-series plots of relative read abundance over time."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 timeseries plot",
        "amp_timeseries",
        "time-series abundance",
        "relative read abundance over time",
        "date metadata",
        "taxon facets",
        "microbiome time series",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_timeseries.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    TAX_LEVELS = ["OTU", "Species", "Genus", "Family", "Order", "Class", "Phylum", "Kingdom"]
    TAX_EMPTY_OPTIONS = ["remove", "best", "OTU"]
    TAX_SHOW_MODES = ["number", "explicit"]
    SCALE_OPTIONS = ["fixed", "free", "free_x", "free_y"]
    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _r_vector(cls, values: list[str]) -> str:
        return "c(" + ", ".join(f'"{value}"' for value in values) + ")"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _tax_show(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            return cls._r_vector(_as_list(inputs.get("tax_show")))
        return str(inputs.get("tax_show", 6) or 6)

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        tax_add = _as_list(inputs.get("tax_add"))
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_timeseries(",
            "    data,",
            f'    time_variable = "{inputs.get("time_variable", "")}",',
        ]
        if str(inputs.get("group_by", "") or "").strip():
            lines.append(f'    group_by = "{inputs.get("group_by")}",')
        lines.extend(
            [
                f'    tax_aggregate = "{inputs.get("tax_aggregate", "OTU") or "OTU"}",',
                f"    tax_add = {cls._r_vector(tax_add) if tax_add else 'NULL'},",
                f"    tax_show = {cls._tax_show(inputs)},",
                "    tax_class = NULL,",
                f'    tax_empty = "{inputs.get("tax_empty", "best") or "best"}",',
                f"    split = {cls._r_bool(inputs.get('split'), False)},",
                f'    scales = "{inputs.get("scales", "free_y") or "free_y"}",',
                f"    normalise = {cls._r_bool(inputs.get('normalise'), True)},",
                "    plotly = FALSE,",
                '    format = "%Y-%m-%d"',
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/timeseries.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_choice(cls, inputs: dict[str, Any], name: str, options: list[str], default: str) -> bool | str:
        value = str(inputs.get(name, default) or default)
        if value not in options:
            return f"{name} must be one of: {', '.join(options)}"
        return True

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
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        if not str(inputs.get("time_variable", "")).strip():
            return "time_variable is required"
        for name, options, default in (
            ("tax_aggregate", cls.TAX_LEVELS, "OTU"),
            ("tax_show_mode", cls.TAX_SHOW_MODES, "number"),
            ("tax_empty", cls.TAX_EMPTY_OPTIONS, "best"),
            ("scales", cls.SCALE_OPTIONS, "free_y"),
            ("out_format", cls.OUT_FORMATS, "pdf"),
        ):
            validation = cls._validate_choice(inputs, name, options, default)
            if validation is not True:
                return validation
        unsupported_tax_add = [level for level in _as_list(inputs.get("tax_add")) if level not in cls.TAX_LEVELS]
        if unsupported_tax_add:
            return f"tax_add contains unsupported values: {', '.join(unsupported_tax_add)}"
        if str(inputs.get("tax_show_mode", "number") or "number") == "explicit":
            if not _as_list(inputs.get("tax_show")):
                return "tax_show must include at least one taxon when tax_show_mode is explicit"
        else:
            validation = cls._validate_number(inputs, "tax_show", 1, 6)
            if validation is not True:
                return validation
        for name in ("plot_width", "plot_height"):
            validation = cls._validate_number(inputs, name, 1, None)
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
                "time_variable": ("STRING", {"description": "Date-compatible metadata variable used for the x axis"}),
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "group_by": ("STRING", {"default": "", "description": "Discrete metadata variable used to group samples"}),
                "tax_aggregate": (
                    "STRING",
                    {"default": "OTU", "options": cls.TAX_LEVELS, "description": "Taxonomic level used to aggregate OTUs"},
                ),
                "tax_add": (
                    "STRING_LIST",
                    {"default": [], "multiple": True, "options": cls.TAX_LEVELS, "description": "Additional taxonomic levels to display"},
                ),
                "tax_show_mode": (
                    "STRING",
                    {"default": "number", "options": cls.TAX_SHOW_MODES, "description": "Limit displayed taxa by count or explicit list"},
                ),
                "taxonomy_list": ("TSV", {"default": "", "description": "Taxonomy list generated by ampvis2: load for explicit taxon selection"}),
                "tax_show": ("STRING", {"default": 6, "description": "Number of taxa or explicit taxa to display"}),
                "tax_empty": (
                    "STRING",
                    {"default": "best", "options": cls.TAX_EMPTY_OPTIONS, "description": "How to show OTUs without taxonomy"},
                ),
                "split": ("BOOLEAN", {"default": False, "description": "Create a facet for each taxon"}),
                "scales": ("STRING", {"default": "free_y", "options": cls.SCALE_OPTIONS, "description": "Axis scaling mode for facets"}),
                "normalise": ("BOOLEAN", {"default": True, "description": "Transform OTU read counts to percent per sample"}),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class Ampvis2VennNode(CommandNode):
    """Generate ampvis2 Venn diagrams of shared core OTUs."""

    NODE_ID = "ampvis2_venn"
    DISPLAY_NAME = "ampvis2 venn diagram"
    REQUIRED_CONDA_PACKAGES = ["r-ampvis2", "r-readr", "bioconductor-phyloseq"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Generate ampvis2 Venn diagrams of core OTUs shared across sample groups."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ampvis2",
        "ampvis2 venn diagram",
        "amp_venn",
        "Venn diagram",
        "core OTUs",
        "shared OTUs",
        "sample group overlap",
        "microbiome core community",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("plot",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://kasperskytte.github.io/ampvis2/reference/amp_venn.html"
    CITATION_DOIS = [AMPVIS2_CITATION_DOIS[0]]
    CITATION_URLS = [f"{DOI_URL}{AMPVIS2_CITATION_DOIS[0]}"]
    CITATION_TEXT = AMPVIS2_CITATION_TEXT
    VERSION = "2.8.11+galaxy2"
    SHELL = True

    OUT_FORMATS = ["pdf", "png", "svg"]

    @classmethod
    def _r_bool(cls, value: Any, default: bool = False) -> str:
        if value in (None, ""):
            value = default
        if isinstance(value, str):
            return "FALSE" if value.lower() in {"false", "0", "no"} else "TRUE"
        return "TRUE" if bool(value) else "FALSE"

    @classmethod
    def _out_format(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        return out_format if out_format in cls.OUT_FORMATS else "pdf"

    @classmethod
    def _number_value(cls, inputs: dict[str, Any], name: str, default: int | float) -> Any:
        value = inputs.get(name, default)
        return default if value in (None, "") else value

    @classmethod
    def _script_body(cls, inputs: dict[str, Any], out: str) -> str:
        out_format = cls._out_format(inputs)
        ggsave_options = [
            f'    device = "{out_format}"',
        ]
        for name, option in (("plot_width", "width"), ("plot_height", "height")):
            value = inputs.get(name)
            if value not in (None, ""):
                ggsave_options.append(f"    {option} = {value}")
        lines = [
            "library(ampvis2, quietly = TRUE)",
            f'data <- readRDS("{inputs.get("data", "")}")',
            "plot <- amp_venn(",
            "    data,",
        ]
        if str(inputs.get("group_by", "") or "").strip():
            lines.append(f'    group_by = "{inputs.get("group_by")}",')
        lines.extend(
            [
                f"    cut_a = {cls._number_value(inputs, 'cut_a', 0.1)},",
                f"    cut_f = {cls._number_value(inputs, 'cut_f', 80)},",
                f"    text_size = {cls._number_value(inputs, 'text_size', 5)},",
                f"    normalise = {cls._r_bool(inputs.get('normalise'), False)}",
                ")",
                f'ggsave("{out}/plot.{out_format}",',
                "    print(plot),",
                ",\n".join(ggsave_options),
                ")",
            ]
        )
        return "\n".join(lines)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        script_path = f"{out}/venn.R"
        return f"cat > {shlex.quote(script_path)} <<'RSCRIPT'\n{cls._script_body(inputs, out)}\nRSCRIPT && {_shell_join(['Rscript', script_path])}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"plot.{cls._out_format(inputs)}"]

    @classmethod
    def _validate_number(
        cls,
        inputs: dict[str, Any],
        name: str,
        minimum: int | float | None = None,
        maximum: int | float | None = None,
        default: Any = None,
    ) -> bool | str:
        raw = inputs.get(name, default)
        if raw in (None, ""):
            return True
        try:
            value = float(raw)
        except (TypeError, ValueError):
            return f"{name} must be a number"
        if minimum is not None and value < minimum:
            return f"{name} must be >= {minimum}"
        if maximum is not None and value > maximum:
            return f"{name} must be <= {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("data", "")).strip():
            return "data is required"
        for name in ("cut_a", "cut_f"):
            validation = cls._validate_number(inputs, name, 0, 100)
            if validation is not True:
                return validation
        validation = cls._validate_number(inputs, "text_size", 1, None)
        if validation is not True:
            return validation
        group_by = str(inputs.get("group_by", "") or "").strip()
        if group_by:
            groups = [value.strip() for value in group_by.split(",") if value.strip()]
            if len(groups) > 3:
                return "group_by supports at most 3 groups"
        out_format = str(inputs.get("out_format", "pdf") or "pdf")
        if out_format not in cls.OUT_FORMATS:
            return f"out_format must be one of: {', '.join(cls.OUT_FORMATS)}"
        for name in ("plot_width", "plot_height"):
            validation = cls._validate_number(inputs, name, 1, None)
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
            },
            "optional": {
                "metadata_list": ("TSV", {"default": "", "description": "Metadata list generated by ampvis2: load"}),
                "group_by": (
                    "STRING",
                    {"default": "", "description": "Discrete metadata variable used to group samples, with at most 3 groups"},
                ),
                "cut_a": (
                    "FLOAT",
                    {
                        "default": 0.1,
                        "min": 0,
                        "max": 100,
                        "description": "Exclude OTUs below this abundance percentage",
                    },
                ),
                "cut_f": (
                    "FLOAT",
                    {
                        "default": 80,
                        "min": 0,
                        "max": 100,
                        "description": "Frequency percentage threshold for core OTUs",
                    },
                ),
                "text_size": ("INT", {"default": 5, "min": 1, "description": "Size of plotted text labels"}),
                "normalise": ("BOOLEAN", {"default": False, "description": "Transform OTU read counts to percent per sample"}),
                "out_format": ("STRING", {"default": "pdf", "options": cls.OUT_FORMATS, "description": "Plot output format"}),
                "plot_width": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot width in cm"}),
                "plot_height": ("FLOAT", {"default": "", "min": 1, "description": "Optional plot height in cm"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ALDEx2Node(CommandNode):
    """Run ALDEx2 differential abundance analyses."""

    NODE_ID = "aldex2"
    DISPLAY_NAME = "ALDEx2"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-aldex2", "r-data.table", "r-optparse", "r-qgraph"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Differential abundance analysis with ALDEx2 compositional data methods."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ALDEx2",
        "aldex2",
        "ALDEx2 differential abundance",
        "compositional data analysis",
        "microbiome differential abundance",
        "RNA-seq differential abundance",
        "Dirichlet Monte Carlo",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "IMAGE", "TSV", "IMAGE", "IMAGE", "TSV", "PDF")
    RETURN_NAMES = (
        "aldex",
        "aldex_corr",
        "aldex_effect",
        "aldex_expected_distance",
        "aldex_kw",
        "aldex_plot",
        "aldex_plot_feature",
        "aldex_ttest",
        "aldex_ttest_plot",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/ALDEx2"
    CITATION_DOIS = ALDEX2_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ALDEX2_CITATION_DOIS]
    CITATION_TEXT = ALDEX2_CITATION_TEXT
    VERSION = "1.26.0+galaxy0"
    SHELL = True

    ANALYSIS_TYPES = [
        "aldex",
        "aldex_corr",
        "aldex_effect",
        "aldex_expected_distance",
        "aldex_kw",
        "aldex_plot",
        "aldex_plot_feature",
        "aldex_ttest",
    ]
    DENOM_OPTIONS = ["all", "median", "iqlr", "zero", "lvha"]
    ALDEX_TEST_OPTIONS = ["t", "kw", "corr"]
    PLOT_TYPES = ["MA", "MW"]
    PLOT_TESTS = ["welch", "wilcox", "kruskal"]
    OUTPUT_FILES = {
        "aldex": "output_aldex.tsv",
        "aldex_corr": "output_aldex_corr.tsv",
        "aldex_effect": "output_aldex_effect.tsv",
        "aldex_expected_distance": "output_aldex_expected_distance.png",
        "aldex_kw": "output_aldex_kw.tsv",
        "aldex_plot": "output_aldex_plot.png",
        "aldex_plot_feature": "output_aldex_plot_feature.png",
        "aldex_ttest": "output_aldex_ttest.tsv",
    }

    @classmethod
    def _analysis_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("analysis_type", "aldex") or "aldex")

    @classmethod
    def _csv(cls, value: Any) -> str:
        return ",".join(_as_list(value))

    @classmethod
    def _bool_arg(cls, inputs: dict[str, Any], name: str, default: bool) -> str:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return "false" if value.lower() in {"false", "0", "no"} else "true"
        return "true" if bool(value) else "false"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        analysis_type = cls._analysis_type(inputs)
        cmd = [
            "Rscript",
            str(inputs.get("script_path", "aldex2.R")),
            "--reads",
            str(inputs.get("reads", "")),
            "--group_names",
            cls._csv(inputs.get("group_names")),
            "--num_cols",
            cls._csv(inputs.get("num_cols")),
            "--num_mc_samples",
            str(inputs.get("num_mc_samples", 128)),
            "--denom",
            str(inputs.get("denom", "all")),
            "--analysis_type",
            analysis_type,
        ]
        if analysis_type == "aldex":
            cmd.extend(
                [
                    "--aldex_test",
                    str(inputs.get("aldex_test", "t")),
                    "--effect",
                    cls._bool_arg(inputs, "effect", True),
                    "--include_sample_summary",
                    cls._bool_arg(inputs, "include_sample_summary", False),
                    "--iterate",
                    cls._bool_arg(inputs, "iterate", False),
                ]
            )
        elif analysis_type == "aldex_corr":
            cmd.extend(
                [
                    "--group_nums",
                    cls._csv(inputs.get("group_nums")),
                    "--num_cols_in_groups",
                    cls._csv(inputs.get("num_cols_in_groups")),
                ]
            )
        elif analysis_type == "aldex_effect":
            cmd.extend(["--include_sample_summary", cls._bool_arg(inputs, "include_sample_summary", False)])
        elif analysis_type == "aldex_plot":
            cmd.extend(
                [
                    "--aldex_test",
                    str(inputs.get("aldex_test", "t")),
                    "--effect",
                    cls._bool_arg(inputs, "effect", True),
                    "--include_sample_summary",
                    cls._bool_arg(inputs, "include_sample_summary", False),
                    "--iterate",
                    cls._bool_arg(inputs, "iterate", False),
                    "--plot_type",
                    str(inputs.get("plot_type", "MA")),
                    "--plot_test",
                    str(inputs.get("plot_test", "welch")),
                    "--cutoff_pval",
                    str(inputs.get("cutoff_pval", 0.1)),
                    "--cutoff_effect",
                    str(inputs.get("cutoff_effect", 1)),
                ]
            )
            _add_if_value(cmd, "--xlab", inputs.get("xlab"))
            _add_if_value(cmd, "--ylab", inputs.get("ylab"))
        elif analysis_type == "aldex_plot_feature":
            cmd.extend(["--feature_name", str(inputs.get("feature_name", ""))])
        elif analysis_type == "aldex_ttest":
            cmd.extend(
                [
                    "--paired_test",
                    cls._bool_arg(inputs, "paired_test", False),
                    "--hist_plot",
                    cls._bool_arg(inputs, "hist_plot", False),
                ]
            )
        cmd.extend(["--output", f"{out}/{cls.OUTPUT_FILES.get(analysis_type, cls.OUTPUT_FILES['aldex'])}"])
        command = _shell_join(cmd)
        if analysis_type == "aldex_ttest" and cls._bool_arg(inputs, "hist_plot", False) == "true":
            command = f"{command} && mv Rplots.pdf {shlex.quote(f'{out}/output_aldex_ttest_plot.pdf')}"
        return command

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        analysis_type = cls._analysis_type(inputs)
        outputs = [out / cls.OUTPUT_FILES.get(analysis_type, cls.OUTPUT_FILES["aldex"])]
        if analysis_type == "aldex_ttest" and cls._bool_arg(inputs, "hist_plot", False) == "true":
            outputs.append(out / "output_aldex_ttest_plot.pdf")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("reads", "")).strip():
            return "reads is required"
        group_names = _as_list(inputs.get("group_names"))
        num_cols = _as_list(inputs.get("num_cols"))
        if not group_names:
            return "at least one comparison group is required"
        if len(group_names) != len(num_cols):
            return "group_names and num_cols must have the same length"
        for value in num_cols:
            try:
                if int(value) < 1:
                    return "num_cols values must be >= 1"
            except (TypeError, ValueError):
                return "num_cols values must be integers"
        denom = str(inputs.get("denom", "all") or "all")
        if denom not in cls.DENOM_OPTIONS:
            return f"denom must be one of: {', '.join(cls.DENOM_OPTIONS)}"
        analysis_type = cls._analysis_type(inputs)
        if analysis_type not in cls.ANALYSIS_TYPES:
            return f"analysis_type must be one of: {', '.join(cls.ANALYSIS_TYPES)}"
        try:
            if int(inputs.get("num_mc_samples", 128)) < 1:
                return "num_mc_samples must be >= 1"
        except (TypeError, ValueError):
            return "num_mc_samples must be an integer"
        if analysis_type == "aldex_corr":
            group_nums = _as_list(inputs.get("group_nums"))
            num_cols_in_groups = _as_list(inputs.get("num_cols_in_groups"))
            if not group_nums or not num_cols_in_groups:
                return "aldex_corr requires group_nums and num_cols_in_groups"
            if len(group_nums) != len(num_cols_in_groups):
                return "group_nums and num_cols_in_groups must have the same length"
        if analysis_type == "aldex_plot_feature" and not str(inputs.get("feature_name", "")).strip():
            return "feature_name is required for aldex_plot_feature"
        if str(inputs.get("aldex_test", "t") or "t") not in cls.ALDEX_TEST_OPTIONS:
            return f"aldex_test must be one of: {', '.join(cls.ALDEX_TEST_OPTIONS)}"
        if str(inputs.get("plot_type", "MA") or "MA") not in cls.PLOT_TYPES:
            return f"plot_type must be one of: {', '.join(cls.PLOT_TYPES)}"
        if str(inputs.get("plot_test", "welch") or "welch") not in cls.PLOT_TESTS:
            return f"plot_test must be one of: {', '.join(cls.PLOT_TESTS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("TSV", {"description": "Reads table with genes/features in rows and sample count columns"}),
                "group_names": (
                    "STRING",
                    {"multiple": True, "default": ["Grp1"], "description": "Comparison group labels"},
                ),
                "num_cols": (
                    "INT",
                    {"multiple": True, "default": [1], "min": 1, "description": "Number of read-count columns per group"},
                ),
            },
            "optional": {
                "num_mc_samples": (
                    "INT",
                    {"default": 128, "min": 1, "description": "Monte Carlo samples for Dirichlet distribution estimates"},
                ),
                "denom": (
                    "STRING",
                    {"default": "all", "options": cls.DENOM_OPTIONS, "description": "Denominator features for geometric means"},
                ),
                "analysis_type": (
                    "STRING",
                    {"default": "aldex", "options": cls.ANALYSIS_TYPES, "description": "ALDEx2 analysis function to run"},
                ),
                "aldex_test": (
                    "STRING",
                    {"default": "t", "options": cls.ALDEX_TEST_OPTIONS, "description": "Statistical tests for aldex/aldex.plot"},
                ),
                "effect": ("BOOLEAN", {"default": True, "description": "Calculate abundances and effect sizes"}),
                "include_sample_summary": (
                    "BOOLEAN",
                    {"default": False, "description": "Include median clr values for each sample"},
                ),
                "iterate": ("BOOLEAN", {"default": False, "description": "Perform tests iteratively"}),
                "group_nums": (
                    "INT",
                    {"default": [], "multiple": True, "min": 1, "description": "Continuous variable group numbers for aldex.corr"},
                ),
                "num_cols_in_groups": (
                    "INT",
                    {"default": [], "multiple": True, "min": 1, "description": "Column counts per continuous variable group"},
                ),
                "plot_type": ("STRING", {"default": "MA", "options": cls.PLOT_TYPES, "description": "ALDEx plot type"}),
                "plot_test": (
                    "STRING",
                    {"default": "welch", "options": cls.PLOT_TESTS, "description": "Significance test for aldex.plot"},
                ),
                "cutoff_pval": ("FLOAT", {"default": 0.1, "min": 0, "description": "Benjamini-Hochberg FDR cutoff"}),
                "cutoff_effect": ("INT", {"default": 1, "min": 0, "description": "Effect-size cutoff for plotting"}),
                "xlab": ("STRING", {"default": "", "description": "Optional x-axis label for aldex.plot"}),
                "ylab": ("STRING", {"default": "", "description": "Optional y-axis label for aldex.plot"}),
                "feature_name": ("STRING", {"default": "", "description": "Feature name for aldex.plotFeature"}),
                "paired_test": ("BOOLEAN", {"default": False, "description": "Use paired tests for aldex.ttest"}),
                "hist_plot": ("BOOLEAN", {"default": False, "description": "Generate a p-value histogram PDF for aldex.ttest"}),
                "script_path": (
                    "FILE",
                    {"default": "aldex2.R", "advanced": True, "description": "Path to the Galaxy ALDEx2 R wrapper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ANCOMBCNode(CommandNode):
    """Run ANCOM-BC differential abundance analysis for microbiome data."""

    NODE_ID = "ancombc"
    DISPLAY_NAME = "ANCOM-BC"
    REQUIRED_CONDA_PACKAGES = ["bioconductor-ancombc", "r-data.table", "r-optparse"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Differential abundance analysis for microbiome compositions with bias correction."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ANCOM-BC",
        "ANCOMBC",
        "ancombc",
        "ANCOM-BC differential abundance",
        "microbiome composition",
        "bias correction",
        "phyloseq",
        "structural zeros",
        "global test",
    ]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("output_collection",)
    REQUIRED_EXECUTABLES = ["Rscript"]
    DOCUMENTATION_URL = "https://bioconductor.org/packages/ANCOMBC"
    CITATION_DOIS = ANCOMBC_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ANCOMBC_CITATION_DOIS]
    CITATION_TEXT = ANCOMBC_CITATION_TEXT
    VERSION = "1.4.0+galaxy0"
    SHELL = True

    P_ADJ_METHODS = ["holm", "hochberg", "hommel", "bonferroni", "BH", "BY", "fdr", "none"]
    OUTPUT_FILES = [
        "feature_table.tabular",
        "zero_ind.tabular",
        "samp_frac.tabular",
        "resid.tabular",
        "delta_em.tabular",
        "delta_wls.tabular",
        "res_beta.tabular",
        "res_se.tabular",
        "res_W.tabular",
        "res_p_val.tabular",
        "res_q_val.tabular",
        "res_diff_abn.tabular",
        "res_global.tabular",
    ]

    @classmethod
    def _bool_arg(cls, inputs: dict[str, Any], name: str, default: bool) -> str:
        value = inputs.get(name, default)
        if isinstance(value, str):
            return "false" if value.lower() in {"false", "0", "no"} else "true"
        return "true" if bool(value) else "false"

    @classmethod
    def _output_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_collection"

    @classmethod
    def expected_output_files(cls) -> list[str]:
        return list(cls.OUTPUT_FILES)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_dir = cls._output_dir(inputs)
        cmd = [
            "Rscript",
            str(inputs.get("script_path", "ancombc.R")),
            "--phyloseq",
            str(inputs.get("phyloseq", "")),
            "--formula",
            str(inputs.get("formula", "")),
            "--p_adj_method",
            str(inputs.get("p_adj_method", "holm")),
            "--zero_cut",
            str(inputs.get("zero_cut", 0.1)),
            "--lib_cut",
            str(inputs.get("lib_cut", 0)),
            "--group",
            str(inputs.get("group", "")),
            "--struc_zero",
            cls._bool_arg(inputs, "struc_zero", False),
            "--neg_lb",
            cls._bool_arg(inputs, "neg_lb", False),
            "--tol",
            str(inputs.get("tol", 0.00001)),
            "--max_iter",
            str(inputs.get("max_iter", 100)),
            "--conserve",
            cls._bool_arg(inputs, "conserve", False),
            "--alpha",
            str(inputs.get("alpha", 0.05)),
            "--global",
            cls._bool_arg(inputs, "global_test", False),
            "--output_dir",
            output_dir,
        ]
        return f"mkdir -p {shlex.quote(output_dir)} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output_collection"
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def _validate_range(
        cls,
        inputs: dict[str, Any],
        name: str,
        default: int | float,
        minimum: int | float,
        maximum: int | float | None = None,
    ) -> bool | str:
        value = inputs.get(name, default)
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return f"{name} must be numeric"
        if numeric < minimum:
            return f"{name} must be >= {minimum:g}"
        if maximum is not None and numeric > maximum:
            return f"{name} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("phyloseq", "")).strip():
            return "phyloseq is required"
        if not str(inputs.get("formula", "")).strip():
            return "formula is required"
        p_adj_method = str(inputs.get("p_adj_method", "holm") or "holm")
        if p_adj_method not in cls.P_ADJ_METHODS:
            return f"p_adj_method must be one of: {', '.join(cls.P_ADJ_METHODS)}"
        for name, default, minimum, maximum in [
            ("zero_cut", 0.1, 0, 1),
            ("lib_cut", 0, 0, None),
            ("tol", 0.00001, 0, None),
            ("alpha", 0.05, 0, None),
        ]:
            result = cls._validate_range(inputs, name, default, minimum, maximum)
            if result is not True:
                return result
        try:
            if int(inputs.get("max_iter", 100)) < 1:
                return "max_iter must be >= 1"
        except (TypeError, ValueError):
            return "max_iter must be an integer"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "phyloseq": ("FILE", {"description": "RDS file containing a phyloseq object"}),
                "formula": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Model formula describing metadata variables that explain microbial abundances",
                    },
                ),
            },
            "optional": {
                "p_adj_method": (
                    "STRING",
                    {"default": "holm", "options": cls.P_ADJ_METHODS, "description": "Method used to adjust p-values"},
                ),
                "zero_cut": (
                    "FLOAT",
                    {"default": 0.1, "min": 0, "max": 1, "description": "Minimum taxa prevalence retained"},
                ),
                "lib_cut": (
                    "INT",
                    {"default": 0, "min": 0, "description": "Minimum sample library size retained"},
                ),
                "group": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Discrete metadata variable for structural-zero detection and global testing",
                    },
                ),
                "struc_zero": (
                    "BOOLEAN",
                    {"default": False, "description": "Detect structural zeros using the group variable"},
                ),
                "neg_lb": (
                    "BOOLEAN",
                    {"default": False, "description": "Use asymptotic lower bounds when classifying structural zeros"},
                ),
                "tol": (
                    "FLOAT",
                    {"default": 0.00001, "min": 0, "description": "E-M algorithm convergence tolerance"},
                ),
                "max_iter": (
                    "INT",
                    {"default": 100, "min": 1, "description": "Maximum E-M algorithm iterations"},
                ),
                "conserve": (
                    "BOOLEAN",
                    {"default": False, "description": "Use a conservative variance estimator for test statistics"},
                ),
                "alpha": ("FLOAT", {"default": 0.05, "min": 0, "description": "Significance level"}),
                "global_test": (
                    "BOOLEAN",
                    {"default": False, "description": "Perform the ANCOM-BC global test for the group variable"},
                ),
                "script_path": (
                    "FILE",
                    {"default": "ancombc.R", "advanced": True, "description": "Path to the Galaxy ANCOM-BC R wrapper script"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ANGSDNode(CommandNode):
    """Generate ANGSD internal counts for X-contamination analysis."""

    NODE_ID = "angsd"
    DISPLAY_NAME = "ANGSD"
    REQUIRED_CONDA_PACKAGES = ["angsd", "samtools"]
    CATEGORY = "population_genetics"
    DESCRIPTION = "Extract internal counts for ANGSD X-contamination analysis."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ANGSD",
        "angsd",
        "ANGSD internal counts",
        "X-contamination",
        "low coverage sequencing",
        "population genetics",
        "BAM internal counts",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("internal_counts",)
    REQUIRED_EXECUTABLES = ["angsd", "samtools"]
    DOCUMENTATION_URL = "http://www.popgen.dk/angsd/index.php/ANGSD"
    CITATION_DOIS = ANGSD_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ANGSD_CITATION_DOIS]
    CITATION_TEXT = ANGSD_CITATION_TEXT
    VERSION = "0.940+galaxy0"
    SHELL = True

    @classmethod
    def _bam_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("input_bams"))

    @classmethod
    def _bam_indices(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("bam_indices"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        bam_filelist = f"{out}/bam.filelist"
        commands = [_shell_join(["mkdir", "-p", out]), f"touch {shlex.quote(bam_filelist)}"]
        bam_indices = cls._bam_indices(inputs)
        for index, bam in enumerate(cls._bam_files(inputs)):
            staged_bam = f"{out}/sample_{index}.bam"
            commands.append(_shell_join(["ln", "-s", bam, staged_bam]))
            if bam_indices:
                commands.append(_shell_join(["ln", "-s", bam_indices[index], f"{staged_bam}.bai"]))
            else:
                commands.append(_shell_join(["samtools", "index", staged_bam]))
            commands.append(f"echo {shlex.quote(staged_bam)} >> {shlex.quote(bam_filelist)}")
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = [
            "angsd",
            "-bam",
            bam_filelist,
            "-out",
            f"{out}/output",
            "-nThreads",
            slots,
            "-doCounts",
            "1",
            "-iCounts",
            "1",
            "-minMapQ",
            str(inputs.get("min_mapq", 20)),
            "-minQ",
            str(inputs.get("min_q", 20)),
            "-r",
            str(inputs.get("region", "")),
        ]
        commands.append(_shell_join(cmd).replace(shlex.quote(slots), slots))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "output.icnts.gz"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_bams = cls._bam_files(inputs)
        if not input_bams:
            return "at least one input BAM is required"
        region = str(inputs.get("region", "")).strip()
        if not region:
            return "region is required"
        if not re.fullmatch(r"[\w\d\._:-]+", region):
            return "region format must be like 'chr' or 'chr:start-end'"
        bam_indices = cls._bam_indices(inputs)
        if bam_indices and len(bam_indices) != len(input_bams):
            return "bam_indices must be empty or match input_bams length"
        for name, default, minimum in (
            ("min_mapq", 20, 0),
            ("min_q", 20, 0),
            ("threads", 1, 1),
        ):
            try:
                value = int(inputs.get(name, default))
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_bams": ("BAM", {"multiple": True, "description": "Coordinate-sorted BAM files"}),
                "region": (
                    "STRING",
                    {
                        "description": "Target region in ANGSD format, such as chr or chr:start-end",
                        "regex": r"^[\w\d\._:-]+$",
                    },
                ),
            },
            "optional": {
                "bam_indices": (
                    "FILE",
                    {
                        "default": [],
                        "multiple": True,
                        "advanced": True,
                        "description": "Optional BAM index files aligned with input_bams",
                    },
                ),
                "min_mapq": (
                    "INT",
                    {"default": 20, "min": 0, "description": "Discard reads below this mapping quality"},
                ),
                "min_q": (
                    "INT",
                    {"default": 20, "min": 0, "description": "Discard bases below this quality"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "description": "ANGSD thread count"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ANGSDContaminationNode(CommandNode):
    """Estimate X-chromosome nuclear contamination from ANGSD internal counts."""

    NODE_ID = "angsd_contamination"
    DISPLAY_NAME = "ANGSD X-Contamination"
    REQUIRED_CONDA_PACKAGES = ["angsd", "samtools", "python"]
    CATEGORY = "population_genetics"
    DESCRIPTION = "Estimate nuclear contamination on the X chromosome for biologically male samples."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ANGSD X-Contamination",
        "angsd_contamination",
        "X chromosome contamination",
        "nuclear contamination",
        "ancient DNA contamination",
        "HapMap ChrX",
        "EAGER contamination",
    ]
    RETURN_TYPES = ("TSV", "JSON")
    RETURN_NAMES = ("contamination_report", "multiqc_json")
    REQUIRED_EXECUTABLES = ["contamination", "python3"]
    DOCUMENTATION_URL = "https://nf-co.re/modules/angsd_contamination/"
    CITATION_DOIS = ANGSD_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in ANGSD_CITATION_DOIS]
    CITATION_TEXT = ANGSD_CITATION_TEXT
    VERSION = "0.940+galaxy0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [
            _shell_join(["mkdir", "-p", out]),
            _shell_join(["ln", "-s", str(inputs.get("icnts_file", "")), f"{out}/counts.icnts.gz"]),
            _shell_join(["ln", "-s", str(inputs.get("hapmap_file", "")), f"{out}/hapmap.gz"]),
            f"cd {shlex.quote(out)}",
            "contamination -a counts.icnts.gz -h hapmap.gz 2> contamination_report.out",
            "python3 print_x_contamination.py contamination_report.out",
        ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "nuclear_contamination.txt"]
        if inputs.get("generate_json"):
            outputs.append(out / "nuclear_contamination_mqc.json")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        icnts_file = str(inputs.get("icnts_file", "")).strip()
        if not icnts_file:
            return "icnts_file is required"
        hapmap_file = str(inputs.get("hapmap_file", "")).strip()
        if not hapmap_file:
            return "hapmap_file is required"
        if not icnts_file.endswith(".gz"):
            return "icnts_file must be a .gz file"
        if not hapmap_file.endswith(".gz"):
            return "hapmap_file must be a .gz file"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "icnts_file": ("FILE", {"description": "ANGSD internal counts output (.icnts.gz)"}),
                "hapmap_file": ("FILE", {"description": "HapMap ChrX reference file (.gz)"}),
            },
            "optional": {
                "generate_json": (
                    "BOOLEAN",
                    {"default": False, "description": "Also expose the MultiQC JSON report generated by the parser"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MiniasmNode(CommandNode):
    """Assemble noisy long reads into an assembly graph with Miniasm."""

    NODE_ID = "miniasm"
    DISPLAY_NAME = "Miniasm"
    REQUIRED_CONDA_PACKAGES = ["miniasm"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assemble noisy long reads into a GFA assembly graph using Miniasm and all-vs-all PAF overlaps."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Miniasm",
        "miniasm",
        "noisy long reads",
        "long-read assembler",
        "PAF overlaps",
        "GFA assembly graph",
        "OLC assembler",
    ]
    RETURN_TYPES = ("GFA",)
    RETURN_NAMES = ("assembly_graph",)
    REQUIRED_EXECUTABLES = ["miniasm"]
    DOCUMENTATION_URL = "https://github.com/lh3/miniasm"
    CITATION_DOIS = [MINIASM_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{MINIASM_CITATION_DOI}"]
    CITATION_TEXT = MINIASM_CITATION_TEXT
    VERSION = "0.3_r179"
    SHELL = True

    DEFAULTS = {
        "min_match": 100,
        "min_iden": 0.05,
        "min_span": 1000,
        "min_cov": 3,
        "min_ovlp": 1000,
        "max_hang": 1000,
        "int_thres": 0.08,
        "max_gap_diff": 1000,
        "max_bub_dist": 50000,
        "min_utg_size": 4,
        "n_rounds": 3,
        "final_drop_ratio": 0.8,
    }

    INTEGER_OPTIONS = {
        "min_match": "min_match",
        "min_span": "min_span",
        "min_cov": "min_cov",
        "min_ovlp": "min_ovlp",
        "max_hang": "max_hang",
        "max_gap_diff": "max_gap_diff",
        "max_bub_dist": "max_bub_dist",
        "min_utg_size": "min_utg_size",
        "n_rounds": "n_rounds",
    }
    FLOAT_OPTIONS = {
        "min_iden": "min_iden",
        "int_thres": "int_thres",
        "final_drop_ratio": "final_drop_ratio",
    }

    @classmethod
    def _option(cls, inputs: dict[str, Any], key: str) -> Any:
        return inputs.get(key, cls.DEFAULTS[key])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output = f"{_out(inputs)}/assembly_graph.gfa"
        cmd = [
            "miniasm",
            "-f",
            str(inputs.get("read_file", "")),
            "-m",
            str(cls._option(inputs, "min_match")),
            "-i",
            str(cls._option(inputs, "min_iden")),
            "-s",
            str(cls._option(inputs, "min_span")),
            "-c",
            str(cls._option(inputs, "min_cov")),
            "-o",
            str(cls._option(inputs, "min_ovlp")),
            "-h",
            str(cls._option(inputs, "max_hang")),
            "-I",
            str(cls._option(inputs, "int_thres")),
            "-g",
            str(cls._option(inputs, "max_gap_diff")),
            "-d",
            str(cls._option(inputs, "max_bub_dist")),
            "-e",
            str(cls._option(inputs, "min_utg_size")),
            "-n",
            str(cls._option(inputs, "n_rounds")),
            "-F",
            str(cls._option(inputs, "final_drop_ratio")),
            str(inputs.get("paf", "")),
        ]
        return f"{_shell_join(cmd)} > {shlex.quote(output)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "assembly_graph.gfa"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("read_file"):
            return "sequence reads are required"
        if not inputs.get("paf"):
            return "PAF overlaps are required"
        for key in cls.INTEGER_OPTIONS:
            try:
                value = int(cls._option(inputs, key))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 0:
                return f"{key} must be >= 0"
        for key in cls.FLOAT_OPTIONS:
            try:
                value = float(cls._option(inputs, key))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "read_file": ("FASTQ", {"description": "Long reads in FASTQ, FASTA, or compressed FASTQ/FASTA format"}),
                "paf": ("PAF", {"description": "All-vs-all read overlaps in Pairwise mApping Format"}),
            },
            "optional": {
                "min_match": (
                    "INT",
                    {"default": 100, "min": 0, "description": "Drop mappings with fewer matching bases"},
                ),
                "min_iden": (
                    "FLOAT",
                    {"default": 0.05, "min": 0, "description": "Ignore mappings below this col10/col11 ratio"},
                ),
                "min_span": ("INT", {"default": 1000, "min": 0, "description": "Drop mappings shorter than this many bp"}),
                "min_cov": ("INT", {"default": 3, "min": 0, "description": "Minimum coverage by other reads"}),
                "min_ovlp": ("INT", {"default": 1000, "min": 0, "description": "Minimum overlap length"}),
                "max_hang": ("INT", {"default": 1000, "min": 0, "description": "Maximum overhang length"}),
                "int_thres": (
                    "FLOAT",
                    {"default": 0.08, "min": 0, "description": "Containment or overlap internal mapping threshold"},
                ),
                "max_gap_diff": (
                    "INT",
                    {"default": 1000, "min": 0, "description": "Maximum gap difference for transitive reduction"},
                ),
                "max_bub_dist": (
                    "INT",
                    {"default": 50000, "min": 0, "description": "Maximum probing distance for bubble popping"},
                ),
                "min_utg_size": ("INT", {"default": 4, "min": 0, "description": "Small unitig read-count threshold"}),
                "n_rounds": ("INT", {"default": 3, "min": 0, "description": "Rounds of short-overlap removal"}),
                "final_drop_ratio": (
                    "FLOAT",
                    {"default": 0.8, "min": 0, "description": "Overlap drop ratio threshold after short unitig removal"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class MegahitContig2FastgNode(CommandNode):
    """Convert MEGAHIT contigs into FASTG assembly graph format."""

    NODE_ID = "megahit_contig2fastg"
    DISPLAY_NAME = "megahit contig2fastg"
    REQUIRED_CONDA_PACKAGES = ["megahit"]
    CATEGORY = "assembly"
    DESCRIPTION = "Convert MEGAHIT contigs into FASTG assembly graph format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "MEGAHIT",
        "megahit_contig2fastg",
        "megahit_toolkit",
        "contig2fastg",
        "FASTG",
        "assembly graph",
        "metagenomics assembly",
    ]
    RETURN_TYPES = ("GFA",)
    RETURN_NAMES = ("fastg",)
    REQUIRED_EXECUTABLES = ["megahit_toolkit"]
    DOCUMENTATION_URL = "https://github.com/voutcn/megahit"
    CITATION_DOIS = [MEGAHIT_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{MEGAHIT_CITATION_DOI}"]
    CITATION_TEXT = MEGAHIT_CITATION_TEXT
    VERSION = "1.1.3+galaxy1"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/contigs.fastg"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "megahit_toolkit",
            "contig2fastg",
            str(inputs.get("kmer", 99)),
            str(inputs.get("contigs", "")),
        ]
        return f"{_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "contigs.fastg"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("contigs", "")).strip():
            return "contigs is required"
        try:
            kmer = int(inputs.get("kmer", 99))
        except (TypeError, ValueError):
            return "kmer must be an integer"
        if kmer <= 0:
            return "kmer must be greater than 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "contigs": ("FASTA", {"description": "MEGAHIT contig FASTA file, such as k99.contigs.fa"}),
            },
            "optional": {
                "kmer": (
                    "INT",
                    {
                        "default": 99,
                        "min": 1,
                        "description": "K-mer length used by MEGAHIT for the input contigs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PrinseqNode(CommandNode):
    """Filter and trim FASTQ reads with PRINSEQ."""

    NODE_ID = "prinseq"
    DISPLAY_NAME = "PRINSEQ"
    REQUIRED_CONDA_PACKAGES = ["prinseq"]
    CATEGORY = "trimming"
    DESCRIPTION = "Filter and trim single-end or paired-end FASTQ reads with PRINSEQ."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PRINSEQ",
        "prinseq-lite",
        "quality control",
        "quality filter",
        "metagenomic preprocessing",
        "read trimming",
        "N filtering",
    ]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ")
    RETURN_NAMES = (
        "good_sequences",
        "rejected_sequences",
        "good_sequences_1",
        "good_sequences_1_singletons",
        "good_sequences_2",
        "rejected_sequences_2",
    )
    REQUIRED_EXECUTABLES = ["prinseq-lite.pl"]
    DOCUMENTATION_URL = "http://prinseq.sourceforge.net/manual.html"
    CITATION_DOIS = [PRINSEQ_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PRINSEQ_CITATION_DOI}"]
    CITATION_TEXT = PRINSEQ_CITATION_TEXT
    VERSION = "0.20.4"
    SHELL = True

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return bool(inputs.get("paired", False))

    @classmethod
    def _compress_output(cls, inputs: dict[str, Any]) -> bool:
        if "compress_output" in inputs:
            return bool(inputs.get("compress_output"))
        if not any(key in inputs for key in ("input_singles", "input_mate1", "input_mate2")):
            return True
        reads = [str(inputs.get("input_singles", "")), str(inputs.get("input_mate1", "")), str(inputs.get("input_mate2", ""))]
        return any(path.endswith(".gz") for path in reads if path)

    @classmethod
    def _planned_names(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._is_paired(inputs):
            names = [
                "good_sequences_1.fastq",
                "good_sequences_1_singletons.fastq",
                "rejected_sequences_1.fastq",
                "good_sequences_2.fastq",
                "good_sequences_2_singletons.fastq",
                "rejected_sequences_2.fastq",
            ]
        else:
            names = ["good_sequences.fastq", "rejected_sequences.fastq"]
        if cls._compress_output(inputs):
            names = [f"{name}.gz" for name in names]
        return names

    @classmethod
    def _stage_fastq(cls, source: str, target: str) -> str:
        if source.endswith(".gz"):
            return f"gunzip -c {shlex.quote(source)} > {target}"
        return f"ln -sf {shlex.quote(source)} {target}"

    @classmethod
    def _add_value_flag(cls, cmd: list[str], inputs: dict[str, Any], key: str, flag: str) -> None:
        value = inputs.get(key)
        if value is not None and str(value) != "":
            cmd.extend([flag, str(value)])

    @classmethod
    def _prinseq_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "prinseq-lite.pl",
            "-fastq",
            "fwd.fastq",
        ]
        if cls._is_paired(inputs):
            cmd.extend(["-fastq2", "rev.fastq"])
        if inputs.get("phred64"):
            cmd.append("-phred64")
        cmd.extend(["-out_good", f"{_out(inputs)}/tmp/good_sequences", "-out_bad", f"{_out(inputs)}/tmp/rejected_sequences"])
        for key, flag in (
            ("min_len", "-min_len"),
            ("max_len", "-max_len"),
            ("min_qual_score", "-min_qual_score"),
            ("max_qual_score", "-max_qual_score"),
            ("min_qual_mean", "-min_qual_mean"),
            ("max_qual_mean", "-max_qual_mean"),
            ("min_gc", "-min_gc"),
            ("max_gc", "-max_gc"),
            ("ns_max_n", "-ns_max_n"),
            ("ns_max_p", "-ns_max_p"),
            ("trim_to_len", "-trim_to_len"),
            ("trim_left", "-trim_left"),
            ("trim_right", "-trim_right"),
            ("trim_left_p", "-trim_left_p"),
            ("trim_right_p", "-trim_right_p"),
            ("trim_tail_left", "-trim_tail_left"),
            ("trim_tail_right", "-trim_tail_right"),
            ("trim_ns_left", "-trim_ns_left"),
            ("trim_ns_right", "-trim_ns_right"),
            ("trim_qual_left", "-trim_qual_left"),
            ("trim_qual_right", "-trim_qual_right"),
            ("trim_qual_type", "-trim_qual_type"),
            ("trim_qual_rule", "-trim_qual_rule"),
            ("trim_qual_window", "-trim_qual_window"),
            ("trim_qual_step", "-trim_qual_step"),
            ("lc_method", "-lc_method"),
            ("lc_threshold", "-lc_threshold"),
        ):
            cls._add_value_flag(cmd, inputs, key, flag)
        return " ".join(shlex.quote(part) for part in cmd)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        tmp = f"{out}/tmp"
        parts = ["set -eu", f"mkdir -p {shlex.quote(tmp)}"]
        if cls._is_paired(inputs):
            parts.extend(
                [
                    cls._stage_fastq(str(inputs.get("input_mate1", "")), "fwd.fastq"),
                    cls._stage_fastq(str(inputs.get("input_mate2", "")), "rev.fastq"),
                    (
                        f"touch {shlex.quote(tmp)}/good_sequences_1.fastq {shlex.quote(tmp)}/good_sequences_1_singletons.fastq "
                        f"{shlex.quote(tmp)}/rejected_sequences_1.fastq {shlex.quote(tmp)}/good_sequences_2.fastq "
                        f"{shlex.quote(tmp)}/good_sequences_2_singletons.fastq {shlex.quote(tmp)}/rejected_sequences_2.fastq"
                    ),
                ]
            )
        else:
            parts.extend(
                [
                    cls._stage_fastq(str(inputs.get("input_singles", "")), "fwd.fastq"),
                    f"touch {shlex.quote(tmp)}/good_sequences.fastq {shlex.quote(tmp)}/rejected_sequences.fastq",
                ]
            )
        parts.append(cls._prinseq_command(inputs))

        names = cls._planned_names(inputs)
        for name in names:
            source = name.removesuffix(".gz")
            source_path = f"{tmp}/{source}"
            target_path = f"{out}/{name}"
            if name.endswith(".gz"):
                parts.append(f"gzip -c {shlex.quote(source_path)} > {shlex.quote(target_path)}")
            else:
                parts.append(f"cp {shlex.quote(source_path)} {shlex.quote(target_path)}")
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / name for name in cls._planned_names(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "paired": ("BOOLEAN", {"default": False, "description": "Run paired-end PRINSEQ processing"}),
                "input_singles": ("FASTQ", {"default": "", "description": "Single-end FASTQ input"}),
                "input_mate1": ("FASTQ", {"default": "", "description": "Paired-end mate 1 FASTQ"}),
                "input_mate2": ("FASTQ", {"default": "", "description": "Paired-end mate 2 FASTQ"}),
            },
            "optional": {
                "compress_output": ("BOOLEAN", {"default": True, "description": "Write gzip-compressed FASTQ outputs"}),
                "phred64": ("BOOLEAN", {"default": False, "description": "Treat input qualities as Illumina/Phred+64"}),
                "min_len": ("INT", {"default": 60, "min": 0, "description": "Minimum sequence length to keep"}),
                "max_len": ("INT", {"default": "", "min": 0, "advanced": True, "description": "Maximum sequence length to keep"}),
                "min_qual_score": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "max_qual_score": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "min_qual_mean": ("INT", {"default": 15, "min": 0, "max": 40, "description": "Minimum mean quality to keep"}),
                "max_qual_mean": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "min_gc": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "max_gc": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "ns_max_n": ("INT", {"default": "", "min": 0, "advanced": True, "description": "Maximum number of N bases"}),
                "ns_max_p": ("INT", {"default": 2, "min": 0, "max": 100, "description": "Maximum percentage of N bases"}),
                "trim_to_len": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_left": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_right": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_left_p": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "trim_right_p": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "trim_tail_left": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_tail_right": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_ns_left": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_ns_right": ("INT", {"default": "", "min": 0, "advanced": True}),
                "trim_qual_left": ("INT", {"default": "", "min": 0, "max": 40, "advanced": True}),
                "trim_qual_right": ("INT", {"default": 20, "min": 0, "max": 40, "description": "Right-end quality trimming threshold"}),
                "trim_qual_type": ("STRING", {"default": "min", "options": ["min", "mean", "max", "sum"], "advanced": True}),
                "trim_qual_rule": ("STRING", {"default": "lt", "options": ["lt", "gt", "et"], "advanced": True}),
                "trim_qual_window": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "trim_qual_step": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "lc_method": ("STRING", {"default": "", "options": ["", "dust", "entropy"], "advanced": True}),
                "lc_threshold": ("INT", {"default": "", "min": 0, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AdapterRemovalNode(CommandNode):
    """Remove adapter sequences and trim FASTQ reads with AdapterRemoval."""

    NODE_ID = "adapter_removal"
    DISPLAY_NAME = "AdapterRemoval"
    REQUIRED_CONDA_PACKAGES = ["adapterremoval"]
    CATEGORY = "trimming"
    DESCRIPTION = "Remove adapter sequences from high-throughput sequencing FASTQ reads, trim low-quality bases, and optionally merge overlapping pairs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AdapterRemoval",
        "adapter_removal",
        "adapterremoval",
        "adapter trimming",
        "FASTQ trimming",
        "read merging",
        "ancient DNA",
    ]
    RETURN_TYPES = ("TEXT", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ", "FASTQ")
    RETURN_NAMES = (
        "output_settings",
        "output_truncated",
        "output_forward_truncated",
        "output_reverse_truncated",
        "output_interleaved_truncated",
        "output_singleton_truncated",
        "output_collapsed",
        "output_collapsed_truncated",
        "output_discarded",
    )
    REQUIRED_EXECUTABLES = ["AdapterRemoval"]
    DOCUMENTATION_URL = "https://adapterremoval.readthedocs.io/"
    CITATION_DOIS = [ADAPTER_REMOVAL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ADAPTER_REMOVAL_CITATION_DOI}"]
    CITATION_TEXT = ADAPTER_REMOVAL_CITATION_TEXT
    VERSION = "2.3.4"
    SHELL = True

    @classmethod
    def _output_path(cls, inputs: dict[str, Any], name: str) -> str:
        suffix = ".txt" if name == "output_settings" else ".fastq"
        return f"{_out(inputs)}/{name}{suffix}"

    @classmethod
    def _output_select(cls, inputs: dict[str, Any]) -> set[str]:
        selected: set[str] = set()
        for value in _as_list(inputs.get("output_select")):
            selected.update(part.strip() for part in value.split(",") if part.strip() and part.strip() != "none")
        return selected

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        input_type = str(inputs.get("input_type", "single") or "single")
        return input_type if input_type in {"single", "pair", "paired", "interleaved"} else "single"

    @classmethod
    def _interleaved_output_enabled(cls, inputs: dict[str, Any]) -> bool:
        value = inputs.get("interleaved_output", "no")
        if isinstance(value, bool):
            return value
        return str(value) == "yes"

    @classmethod
    def _read_pair(cls, inputs: dict[str, Any]) -> tuple[str, str]:
        if cls._input_type(inputs) == "paired":
            collection = inputs.get("reads_collection")
            if isinstance(collection, dict):
                return str(collection.get("forward", "")), str(collection.get("reverse", ""))
            reads = _as_list(collection or inputs.get("reads"))
            return (reads[0] if reads else "", reads[1] if len(reads) > 1 else "")
        return str(inputs.get("read1", "")), str(inputs.get("read2", ""))

    @classmethod
    def _read_ext(cls, inputs: dict[str, Any], key: str, path: str) -> str:
        explicit = inputs.get(f"{key}_ext")
        if explicit:
            return str(explicit)
        suffixes = "".join(Path(path).suffixes).lower()
        return "fastqsanger.gz" if suffixes.endswith(".gz") else "fastqsanger"

    @classmethod
    def _read_identifier(cls, inputs: dict[str, Any], key: str, path: str) -> str:
        index = "1" if key == "read1" else "2"
        return f"read{index}{cls._read_ext(inputs, key, path)}"

    @classmethod
    def _append_flag_value(cls, parts: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != "":
            parts.extend([flag, str(value)])

    @classmethod
    def _default_int(cls, inputs: dict[str, Any], name: str, default: int) -> Any:
        value = inputs.get(name)
        return default if value is None or str(value) == "" else value

    @classmethod
    def _default_float(cls, inputs: dict[str, Any], name: str, default: float) -> Any:
        value = inputs.get(name)
        return default if value is None or str(value) == "" else value

    @classmethod
    def _add_fastq_options(cls, parts: list[str], inputs: dict[str, Any]) -> None:
        parts.extend(
            [
                "--qualitybase",
                "33",
                "--qualitybase-output",
                "33",
                "--qualitymax",
                str(cls._default_int(inputs, "qualitymax", 41)),
            ]
        )
        if inputs.get("convert_uracils"):
            parts.append("--convert-uracils")
        if inputs.get("mask_degenerate_bases"):
            parts.append("--mask-degenerate-bases")

    @classmethod
    def _add_trimming_options(cls, parts: list[str], inputs: dict[str, Any]) -> None:
        parts.extend(
            [
                "--adapter1",
                str(inputs.get("adapter1") or ADAPTER_REMOVAL_ADAPTER1),
                "--adapter2",
                str(inputs.get("adapter2") or ADAPTER_REMOVAL_ADAPTER2),
            ]
        )
        cls._append_flag_value(parts, "--adapter-list", inputs.get("adapter_list"))
        parts.extend(
            [
                "--minadapteroverlap",
                str(cls._default_int(inputs, "minadapteroverlap", 0)),
                "--mm",
                str(cls._default_float(inputs, "mm", 3.0)),
                "--shift",
                str(cls._default_int(inputs, "shift", 2)),
            ]
        )
        if inputs.get("trim5p"):
            parts.extend(
                [
                    "--trim5p",
                    str(cls._default_int(inputs, "trim5p_mate1", 0)),
                    str(cls._default_int(inputs, "trim5p_mate2", 0)),
                ]
            )
        if inputs.get("trim3p"):
            parts.extend(
                [
                    "--trim3p",
                    str(cls._default_int(inputs, "trim3p_mate1", 0)),
                    str(cls._default_int(inputs, "trim3p_mate2", 0)),
                ]
            )
        if inputs.get("trimns"):
            parts.append("--trimns")
        parts.extend(["--maxns", str(cls._default_int(inputs, "maxns", 1000))])
        if inputs.get("trimqualities"):
            parts.append("--trimqualities")
        if inputs.get("sliding_window"):
            parts.extend(["--trimwindows", str(cls._default_int(inputs, "window_size", 0))])
        parts.extend(["--minquality", str(cls._default_int(inputs, "minquality", 2))])
        if inputs.get("preserve5p"):
            parts.append("--preserve5p")
        parts.extend(
            [
                "--minlength",
                str(cls._default_int(inputs, "minlength", 15)),
                "--maxlength",
                str(cls._default_int(inputs, "maxlength", 4294967295)),
            ]
        )

    @classmethod
    def _add_merging_options(cls, parts: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get("collapse"):
            parts.append("--collapse")
        parts.extend(["--minalignmentlength", str(cls._default_int(inputs, "minalignmentlength", 11))])
        if inputs.get("collapse_deterministic"):
            parts.append("--collapse-deterministic")
        if inputs.get("collapse_conservatively"):
            parts.append("--collapse-conservatively")

    @classmethod
    def _primary_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        input_type = cls._input_type(inputs)
        if input_type == "single":
            return ["output_settings", "output_truncated"]
        if input_type in {"pair", "paired"}:
            if cls._interleaved_output_enabled(inputs):
                return ["output_settings", "output_interleaved_truncated"]
            return ["output_settings", "output_forward_truncated", "output_reverse_truncated"]
        return ["output_settings"]

    @classmethod
    def _planned_output_names(cls, inputs: dict[str, Any]) -> list[str]:
        names = cls._primary_output_names(inputs)
        selected = cls._output_select(inputs)
        optional_map = {
            "output_singleton": "output_singleton_truncated",
            "output_collapsed": "output_collapsed",
            "output_collapsed_truncated": "output_collapsed_truncated",
            "output_discarded": "output_discarded",
        }
        names.extend(output for option, output in optional_map.items() if option in selected)
        return names

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_type = cls._input_type(inputs)
        read1, read2 = cls._read_pair(inputs)
        read1_identifier = cls._read_identifier(inputs, "read1", read1)
        read2_identifier = cls._read_identifier(inputs, "read2", read2)
        setup = [f"ln -sf {shlex.quote(read1)} {shlex.quote(read1_identifier)}"]
        if input_type in {"pair", "paired"}:
            setup.append(f"ln -sf {shlex.quote(read2)} {shlex.quote(read2_identifier)}")

        parts = ["AdapterRemoval", "--file1", read1_identifier]
        if input_type == "interleaved":
            parts.extend(["--interleaved", "--interleaved-input"])
            if cls._interleaved_output_enabled(inputs):
                parts.extend(["--interleaved-output", cls._output_path(inputs, "output_interleaved_truncated")])
            if inputs.get("combined_output"):
                parts.append("--combined-output")
        elif input_type in {"pair", "paired"}:
            parts.extend(["--file2", read2_identifier])
            if inputs.get("identify_adapters"):
                parts.append("--identify-adapters")
            if cls._interleaved_output_enabled(inputs):
                parts.append("--interleaved-output")
            if inputs.get("combined_output"):
                parts.append("--combined-output")

        parts.extend(["--threads", "${GALAXY_SLOTS:-8}"])
        cls._add_fastq_options(parts, inputs)
        cls._add_trimming_options(parts, inputs)
        cls._add_merging_options(parts, inputs)
        parts.extend(["--settings", cls._output_path(inputs, "output_settings")])

        if input_type == "single":
            parts.extend(["--output1", cls._output_path(inputs, "output_truncated")])
        elif input_type in {"pair", "paired"}:
            if cls._interleaved_output_enabled(inputs):
                parts.extend(["--output1", cls._output_path(inputs, "output_interleaved_truncated")])
            else:
                parts.extend(
                    [
                        "--output1",
                        cls._output_path(inputs, "output_forward_truncated"),
                        "--output2",
                        cls._output_path(inputs, "output_reverse_truncated"),
                    ]
                )

        selected = cls._output_select(inputs)
        optional_flags = [
            ("output_singleton", "--singleton", "output_singleton_truncated"),
            ("output_collapsed", "--outputcollapsed", "output_collapsed"),
            ("output_collapsed_truncated", "--outputcollapsedtruncated", "output_collapsed_truncated"),
            ("output_discarded", "--discarded", "output_discarded"),
        ]
        for option, flag, output_name in optional_flags:
            if option in selected:
                parts.extend([flag, cls._output_path(inputs, output_name)])

        command = " && ".join(setup + [" ".join(shlex.quote(part) for part in parts)])
        return command.replace("'${GALAXY_SLOTS:-8}'", "${GALAXY_SLOTS:-8}")

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / (f"{name}.txt" if name == "output_settings" else f"{name}.fastq")
            for name in cls._planned_output_names(inputs)
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "pair", "paired", "interleaved"],
                        "description": "Galaxy input mode: single, separate pair, paired collection, or interleaved reads",
                    },
                ),
                "read1": ("FASTQ", {"description": "Single, forward, or interleaved FASTQ reads"}),
            },
            "optional": {
                "read2": ("FASTQ", {"default": "", "description": "Reverse FASTQ reads for pair mode"}),
                "reads_collection": ("FASTQ_LIST", {"default": "", "description": "Paired collection as [forward, reverse] or a mapping with forward/reverse keys"}),
                "read1_ext": ("STRING", {"default": "", "description": "Galaxy datatype extension for read1 symlink naming", "advanced": True}),
                "read2_ext": ("STRING", {"default": "", "description": "Galaxy datatype extension for read2 symlink naming", "advanced": True}),
                "interleaved_output": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Write paired-end reads to one interleaved output"}),
                "identify_adapters": ("BOOLEAN", {"default": False, "description": "Attempt consensus adapter identification from overlapping pairs"}),
                "combined_output": ("BOOLEAN", {"default": False, "description": "Replace discarded or merged reads with a single N in paired output"}),
                "qualitymax": ("INT", {"default": 41, "min": 0, "max": 93, "description": "Maximum Phred score expected in input and output files"}),
                "convert_uracils": ("BOOLEAN", {"default": False, "description": "Convert uracils to thymine"}),
                "mask_degenerate_bases": ("BOOLEAN", {"default": False, "description": "Mask ambiguous IUPAC bases"}),
                "adapter1": ("STRING", {"default": ADAPTER_REMOVAL_ADAPTER1, "description": "Adapter sequence expected in mate 1 reads"}),
                "adapter2": ("STRING", {"default": ADAPTER_REMOVAL_ADAPTER2, "description": "Adapter sequence expected in mate 2 reads"}),
                "adapter_list": ("TSV", {"default": "", "description": "Optional tabular adapter sequence list"}),
                "minadapteroverlap": ("INT", {"default": 0, "min": 0, "description": "Minimum adapter overlap for single-end trimming"}),
                "mm": ("FLOAT", {"default": 3.0, "description": "Mismatch fraction or reciprocal mismatch rate"}),
                "shift": ("INT", {"default": 2, "min": 0, "max": 93, "description": "Allow alignment slip at the 5' end"}),
                "trim5p": ("BOOLEAN", {"default": False, "description": "Trim fixed bases from 5' ends"}),
                "trim5p_mate1": ("INT", {"default": 0, "min": 0, "description": "5' trim length for mate 1"}),
                "trim5p_mate2": ("INT", {"default": 0, "min": 0, "description": "5' trim length for mate 2"}),
                "trim3p": ("BOOLEAN", {"default": False, "description": "Trim fixed bases from 3' ends"}),
                "trim3p_mate1": ("INT", {"default": 0, "min": 0, "description": "3' trim length for mate 1"}),
                "trim3p_mate2": ("INT", {"default": 0, "min": 0, "description": "3' trim length for mate 2"}),
                "trimns": ("BOOLEAN", {"default": False, "description": "Trim consecutive terminal Ns"}),
                "maxns": ("INT", {"default": 1000, "min": 0, "description": "Discard reads with more Ns than this after trimming"}),
                "trimqualities": ("BOOLEAN", {"default": False, "description": "Trim terminal low-quality stretches"}),
                "sliding_window": ("BOOLEAN", {"default": False, "description": "Use sliding-window quality trimming"}),
                "window_size": ("INT", {"default": 0, "min": 0, "description": "Sliding-window size"}),
                "minquality": ("INT", {"default": 2, "min": 0, "description": "Low-quality trimming threshold"}),
                "preserve5p": ("BOOLEAN", {"default": False, "description": "Preserve 5' bases during quality trimming"}),
                "minlength": ("INT", {"default": 15, "min": 0, "description": "Discard reads shorter than this"}),
                "maxlength": ("INT", {"default": 4294967295, "min": 0, "description": "Discard reads longer than this"}),
                "collapse": ("BOOLEAN", {"default": False, "description": "Merge overlapping reads into consensus sequences"}),
                "minalignmentlength": ("INT", {"default": 11, "min": 0, "description": "Minimum mate overlap for collapsing"}),
                "collapse_deterministic": ("BOOLEAN", {"default": False, "description": "Use deterministic consensus bases when collapsing"}),
                "collapse_conservatively": ("BOOLEAN", {"default": False, "description": "Use conservative FASTQ-join inspired collapsing"}),
                "output_select": (
                    "STRING",
                    {
                        "default": "none",
                        "list": True,
                        "options": [
                            "none",
                            "output_singleton",
                            "output_collapsed",
                            "output_collapsed_truncated",
                            "output_discarded",
                        ],
                        "description": "Optional Galaxy outputs to request",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class TrimNNode(CommandNode):
    """Trim N stretches and fake cut sites from scaffold FASTA assemblies."""

    NODE_ID = "trimn"
    DISPLAY_NAME = "TrimN"
    REQUIRED_CONDA_PACKAGES = ["trimns_vgp"]
    CATEGORY = "trimming"
    DESCRIPTION = "Trim N stretches and remove fake cut sites from bionano hybrid scaffold FASTA assemblies."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "TrimN",
        "trimns",
        "trimns_vgp",
        "trim_Ns_DNAnexus.py",
        "remove fake cut sites",
        "bionano scaffolds",
        "VGP",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("trimmed_fasta",)
    REQUIRED_EXECUTABLES = [
        "remove_fake_cut_sites_DNAnexus.py",
        "trim_Ns_DNAnexus.py",
        "clip_regions_DNAnexus.py",
    ]
    DOCUMENTATION_URL = "https://github.com/VGP/vgp-assembly/tree/master/pipeline/trim"
    CITATION_DOIS = TRIMN_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in TRIMN_CITATION_DOIS]
    CITATION_TEXT = TRIMN_CITATION_TEXT
    VERSION = "1.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        fasta_in = shlex.quote(str(inputs.get("fasta_in", "")))
        return (
            f"remove_fake_cut_sites_DNAnexus.py {fasta_in} "
            f"{shlex.quote(f'{out}/step1_out.fasta')} {shlex.quote(f'{out}/step1.log')} && "
            f"trim_Ns_DNAnexus.py {fasta_in} {shlex.quote(f'{out}/step2_out.list')} && "
            f"clip_regions_DNAnexus.py {shlex.quote(f'{out}/step1_out.fasta')} "
            f"{shlex.quote(f'{out}/step2_out.list')} {shlex.quote(f'{out}/final_out.fasta')}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "final_out.fasta"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if not inputs.get("fasta_in"):
            return "fasta_in is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fasta_in": (
                    "FASTA",
                    {
                        "description": (
                            "FASTA assembly to trim and from which to remove N stretches and fake cut sites"
                        ),
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class TrimNGalaxyNode(TrimNNode):
    """Galaxy wrapper-ID compatible alias for TrimN."""

    NODE_ID = "trimns"
    DISPLAY_NAME = "TrimN (Galaxy)"
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "trimns",
        "TrimN",
        "trimns_vgp",
        "trim_Ns_DNAnexus.py",
        "remove fake cut sites",
        "bionano scaffolds",
        "VGP",
    ]

class VSearchSearchNode(CommandNode):
    """Search query sequences against a FASTA database with VSEARCH."""

    NODE_ID = "vsearch_search"
    DISPLAY_NAME = "VSEARCH Search"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Search amplicon or nucleotide sequences against a reference database with VSEARCH."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "vsearch", "usearch_global", "search", "amplicon", "otu"]
    RETURN_TYPES = ("TSV", "STATS_FILE", "FASTA")
    RETURN_NAMES = ("matches", "alignments", "unmatched")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            f"--{inputs.get('search_mode', 'usearch_global')}",
            str(inputs.get("query", "")),
            "--db",
            str(inputs.get("database", "")),
            "--id",
            str(inputs.get("identity", 0.97)),
            "--strand",
            str(inputs.get("strand", "both")),
            "--maxaccepts",
            str(inputs.get("maxaccepts", 1)),
            "--maxrejects",
            str(inputs.get("maxrejects", 32)),
            "--threads",
            str(inputs.get("threads", 1)),
            "--blast6out",
            f"{_out(inputs)}/matches.tsv",
            "--alnout",
            f"{_out(inputs)}/alignments.txt",
            "--notmatched",
            f"{_out(inputs)}/unmatched.fasta",
        ]
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "matches.tsv", out / "alignments.txt", out / "unmatched.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"description": "Query sequences"}),
                "database": ("FASTA", {"description": "Reference database FASTA"}),
            },
            "optional": {
                "search_mode": ("STRING", {"default": "usearch_global", "options": ["usearch_global", "search_exact"]}),
                "identity": ("FLOAT", {"default": 0.97, "min": 0, "max": 1}),
                "strand": ("STRING", {"default": "both", "options": ["plus", "both"]}),
                "maxaccepts": ("INT", {"default": 1, "min": 0, "advanced": True}),
                "maxrejects": ("INT", {"default": 32, "min": 0, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchClusterNode(CommandNode):
    """Cluster sequences into centroids and UC cluster assignments with VSEARCH."""

    NODE_ID = "vsearch_cluster"
    DISPLAY_NAME = "VSEARCH Cluster"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Cluster amplicon sequences with VSEARCH cluster_fast or cluster_size modes."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "vsearch", "cluster_fast", "cluster_size", "otu clustering", "centroids"]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("centroids", "clusters_uc")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            f"--{inputs.get('cluster_mode', 'cluster_fast')}",
            str(inputs.get("sequences", "")),
            "--id",
            str(inputs.get("identity", 0.97)),
            "--strand",
            str(inputs.get("strand", "plus")),
        ]
        if inputs.get("sizein"):
            cmd.append("--sizein")
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        cmd.extend([
            "--threads",
            str(inputs.get("threads", 1)),
            "--centroids",
            f"{_out(inputs)}/centroids.fasta",
            "--uc",
            f"{_out(inputs)}/clusters.uc",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "centroids.fasta", out / "clusters.uc"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"sequences": ("FASTA", {"description": "Sequences to cluster"})},
            "optional": {
                "cluster_mode": ("STRING", {"default": "cluster_fast", "options": ["cluster_fast", "cluster_size", "cluster_smallmem"]}),
                "identity": ("FLOAT", {"default": 0.97, "min": 0, "max": 1}),
                "strand": ("STRING", {"default": "plus", "options": ["plus", "both"]}),
                "sizein": ("BOOLEAN", {"default": False, "advanced": True}),
                "sizeout": ("BOOLEAN", {"default": False, "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchDereplicationNode(CommandNode):
    """Dereplicate identical FASTA sequences with VSEARCH."""

    NODE_ID = "vsearch_dereplication"
    DISPLAY_NAME = "VSEARCH Dereplication"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Dereplicate identical FASTA sequences with VSEARCH derep_fulllength and optional abundance filters."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "dereplication",
        "derep_fulllength",
        "amplicon dereplication",
        "unique sequences",
        "abundance",
    ]
    RETURN_TYPES = ("FASTA", "TSV")
    RETURN_NAMES = ("dereplicated_sequences", "uclust_output")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
            "--derep_fulllength",
            str(inputs.get("infile", inputs.get("sequences", ""))),
        ]
        _add_if_value(cmd, "--maxuniquesize", inputs.get("maxuniquesize"))
        _add_if_value(cmd, "--minuniquesize", inputs.get("minuniquesize"))
        cmd.extend(["--output", f"{_out(inputs)}/dereplicated.fasta"])
        if inputs.get("sizein"):
            cmd.append("--sizein")
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        cmd.extend(["--strand", str(inputs.get("strand", "plus"))])
        _add_if_value(cmd, "--topn", inputs.get("topn"))
        if inputs.get("uc"):
            cmd.extend(["--uc", f"{_out(inputs)}/dereplication.uc"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "dereplicated.fasta"]
        if inputs.get("uc"):
            outputs.append(out / "dereplication.uc")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"infile": ("FASTA", {"description": "FASTA sequences to dereplicate"})},
            "optional": {
                "topn": ("INT", {"default": "", "min": 1, "description": "Output only the n most abundant sequences"}),
                "sizein": ("BOOLEAN", {"default": False, "description": "Read abundance annotations from input"}),
                "sizeout": ("BOOLEAN", {"default": False, "description": "Write abundance annotations to output"}),
                "strand": ("STRING", {"default": "plus", "options": ["plus", "both"]}),
                "uc": ("BOOLEAN", {"default": False, "description": "Write UCLUST-like dereplication assignments"}),
                "minuniquesize": ("INT", {"default": "", "min": 1, "description": "Minimum abundance to output"}),
                "maxuniquesize": ("INT", {"default": "", "min": 1, "description": "Maximum abundance to output"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchMaskingNode(CommandNode):
    """Mask FASTA sequences with VSEARCH."""

    NODE_ID = "vsearch_masking"
    DISPLAY_NAME = "VSEARCH Masking"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Mask FASTA sequences with VSEARCH maskfasta using dust, soft, or no qmask modes and optional hard masking."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "masking",
        "maskfasta",
        "qmask",
        "hardmask",
        "soft masking",
        "dust masking",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("masked_sequences",)
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
        ]
        qmask = str(inputs.get("qmask", "dust"))
        if qmask != "none":
            cmd.extend(["--qmask", qmask])
        if inputs.get("hardmask"):
            cmd.append("--hardmask")
        cmd.extend([
            "--maskfasta",
            str(inputs.get("infile", inputs.get("sequences", ""))),
            "--output",
            f"{_out(inputs)}/masked.fasta",
        ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "masked.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"infile": ("FASTA", {"description": "FASTA sequences to mask"})},
            "optional": {
                "qmask": ("STRING", {"default": "dust", "options": ["none", "dust", "soft"], "description": "Masking mode"}),
                "hardmask": ("BOOLEAN", {"default": False, "description": "Replace masked bases with N instead of lowercase"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchShufflingNode(CommandNode):
    """Shuffle FASTA sequence order with VSEARCH."""

    NODE_ID = "vsearch_shuffling"
    DISPLAY_NAME = "VSEARCH Shuffling"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Shuffle FASTA sequence order pseudo-randomly with VSEARCH, using an explicit random seed and optional top-N limit."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "shuffling",
        "shuffle",
        "random sequence order",
        "randseed",
        "topn",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("shuffled_sequences",)
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
            "--output",
            f"{_out(inputs)}/shuffled.fasta",
            "--randseed",
            str(inputs.get("randseed", 0)),
            "--shuffle",
            str(inputs.get("infile", inputs.get("sequences", ""))),
        ]
        _add_if_value(cmd, "--topn", inputs.get("topn"))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "shuffled.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"infile": ("FASTA", {"description": "FASTA sequences to shuffle"})},
            "optional": {
                "randseed": ("INT", {"default": 0, "min": 0, "description": "Random seed; zero uses a random data source"}),
                "topn": ("INT", {"default": "", "min": 1, "description": "Output only the first n sequences after shuffling"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchSortingNode(CommandNode):
    """Sort FASTA sequences by length or abundance with VSEARCH."""

    NODE_ID = "vsearch_sorting"
    DISPLAY_NAME = "VSEARCH Sorting"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Sort FASTA sequences by length or abundance with VSEARCH, with optional abundance filters, relabeling, size annotations, and top-N output."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "sorting",
        "sortbylength",
        "sortbysize",
        "sort by abundance",
        "sizeout",
        "relabel",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("sorted_sequences",)
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
        ]
        sorting_mode = str(inputs.get("sorting_mode", inputs.get("sorting_mode_select", "sortbylength")))
        if sorting_mode == "sortbylength":
            cmd.extend(["--sortbylength", str(inputs.get("infile", inputs.get("sequences", "")))])
        else:
            cmd.extend(["--sortbysize", str(inputs.get("infile", inputs.get("sequences", "")))])
            _add_if_value(cmd, "--minsize", inputs.get("minsize"))
            _add_if_value(cmd, "--maxsize", inputs.get("maxsize"))
        cmd.extend(["--output", f"{_out(inputs)}/sorted.fasta"])
        _add_if_value(cmd, "--relabel", inputs.get("relabel"))
        if inputs.get("sizeout"):
            cmd.append("--sizeout")
        _add_if_value(cmd, "--topn", inputs.get("topn"))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "sorted.fasta"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "FASTA sequences to sort"}),
            },
            "optional": {
                "sorting_mode": ("STRING", {"default": "sortbylength", "options": ["sortbylength", "sortbyabundance"]}),
                "minsize": ("INT", {"default": "", "min": 1, "description": "Minimum abundance for sort-by-size mode"}),
                "maxsize": ("INT", {"default": "", "min": 1, "description": "Maximum abundance for sort-by-size mode"}),
                "relabel": ("STRING", {"default": "", "description": "Prefix used to relabel sequences after sorting"}),
                "sizeout": ("BOOLEAN", {"default": False, "description": "Add abundance annotations to output"}),
                "topn": ("INT", {"default": "", "min": 1, "description": "Output only the top n sorted sequences"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchAlignmentNode(CommandNode):
    """Compute all-pairs global alignments with VSEARCH."""

    NODE_ID = "vsearch_alignment"
    DISPLAY_NAME = "VSEARCH Alignment"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Compute all-pairs global alignments for FASTA sequences with VSEARCH and optional tabular user fields."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "alignment",
        "allpairs_global",
        "pairwise alignment",
        "alnout",
        "userfields",
    ]
    RETURN_TYPES = ("STATS_FILE", "TSV")
    RETURN_NAMES = ("alignments", "userfields")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
        ]
        if inputs.get("acceptall"):
            cmd.append("--acceptall")
        cmd.extend([
            "--id",
            str(inputs.get("id", inputs.get("identity", 0.97))),
            "--iddef",
            str(inputs.get("iddef", 2)),
            "--allpairs_global",
            str(inputs.get("infile", inputs.get("sequences", ""))),
            "--alnout",
            f"{_out(inputs)}/alignments.txt",
        ])
        _add_if_value(cmd, "--query_cov", inputs.get("query_cov"))

        if inputs.get("userfields_output_select") == "yes":
            userfields = _as_list(inputs.get("userfields"))
            if not userfields:
                userfields = ["query", "target"]
            cmd.extend([
                "--userfields",
                "+".join(userfields),
                "--userout",
                f"{_out(inputs)}/userfields.tsv",
            ])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "alignments.txt"]
        if inputs.get("userfields_output_select") == "yes":
            outputs.append(out / "userfields.tsv")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "infile": ("FASTA", {"description": "FASTA sequences for all-pairs global alignment"}),
            },
            "optional": {
                "id": ("FLOAT", {"default": 0.97, "min": 0, "max": 1, "description": "Minimum pairwise identity"}),
                "iddef": ("STRING", {"default": "2", "options": ["0", "1", "2", "3", "4"], "description": "VSEARCH identity definition"}),
                "acceptall": ("BOOLEAN", {"default": False, "description": "Output all pairwise alignments"}),
                "query_cov": ("FLOAT", {"default": "", "min": 0, "max": 1, "description": "Minimum aligned query fraction"}),
                "userfields_output_select": ("STRING", {"default": "no", "options": ["no", "yes"], "description": "Write tabular user fields"}),
                "userfields": (
                    "STRING",
                    {
                        "default": ["query", "target"],
                        "list": True,
                        "options": [
                            "aln",
                            "alnlen",
                            "bits",
                            "caln",
                            "evalue",
                            "exts",
                            "gaps",
                            "id",
                            "id0",
                            "id1",
                            "id2",
                            "id3",
                            "id4",
                            "ids",
                            "mism",
                            "opens",
                            "pairs",
                            "pctgaps",
                            "pctpv",
                            "pv",
                            "qcov",
                            "qframe",
                            "qhi",
                            "qihi",
                            "qilo",
                            "ql",
                            "qlo",
                            "qrow",
                            "qs",
                            "qstrand",
                            "query",
                            "raw",
                            "target",
                            "tcov",
                            "tframe",
                            "thi",
                            "tihi",
                            "tilo",
                            "tl",
                            "tlo",
                            "trow",
                            "ts",
                            "tstrand",
                        ],
                        "description": "Fields for optional tabular VSEARCH output",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class VSearchChimeraDetectionNode(CommandNode):
    """Detect chimeric FASTA sequences with VSEARCH UCHIME modes."""

    NODE_ID = "vsearch_chimera_detection"
    DISPLAY_NAME = "VSEARCH Chimera Detection"
    REQUIRED_CONDA_PACKAGES = ["vsearch"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Detect chimeric FASTA sequences with VSEARCH uchime_denovo or uchime_ref and optional UCHIME reports."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "vsearch",
        "chimera",
        "chimera detection",
        "uchime_denovo",
        "uchime_ref",
        "uchimeout",
        "nonchimeras",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "STATS_FILE", "TSV")
    RETURN_NAMES = ("chimeras", "nonchimeras", "uchime_alignments", "uchimeout")
    REQUIRED_EXECUTABLES = ["vsearch"]
    DOCUMENTATION_URL = "https://github.com/torognes/vsearch"
    CITATION_DOIS = ["10.7717/peerj.2584"]
    CITATION_URLS = ["https://doi.org/10.7717/peerj.2584"]
    CITATION_TEXT = "VSEARCH: a versatile open source tool for metagenomics."
    VERSION = "2.8.3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "vsearch",
            "--threads",
            str(inputs.get("threads", 4)),
            "--notrunclabels",
            "--abskew",
            str(inputs.get("abskew", 2.0)),
            "--chimeras",
            f"{_out(inputs)}/chimeras.fasta",
            "--dn",
            str(inputs.get("dn", 1.4)),
            "--mindiffs",
            str(inputs.get("mindiffs", 3)),
            "--mindiv",
            str(inputs.get("mindiv", 0.8)),
            "--minh",
            str(inputs.get("minh", 0.28)),
            "--xn",
            str(inputs.get("xn", 8.0)),
        ]
        if inputs.get("self_param"):
            cmd.append("--self")
        if inputs.get("selfid_param"):
            cmd.append("--selfid")

        detection_mode = str(inputs.get("detection_mode", inputs.get("detection_mode_select", "denovo")))
        if detection_mode == "reference":
            cmd.extend([
                "--uchime_ref",
                str(inputs.get("infile_reference", inputs.get("infile", ""))),
                "--db",
                str(inputs.get("db", "")),
            ])
        else:
            cmd.extend(["--uchime_denovo", str(inputs.get("infile_denovo", inputs.get("infile", "")))])

        outputs = set(_as_list(inputs.get("outputs")))
        if "nonchimeras" in outputs:
            cmd.extend(["--nonchimeras", f"{_out(inputs)}/nonchimeras.fasta"])
        if "uchimealns" in outputs:
            cmd.extend(["--uchimealns", f"{_out(inputs)}/uchime_alignments.txt"])
        if "uchimeout" in outputs:
            cmd.extend(["--uchimeout", f"{_out(inputs)}/uchimeout.tsv"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "chimeras.fasta"]
        requested = set(_as_list(inputs.get("outputs")))
        if "nonchimeras" in requested:
            outputs.append(out / "nonchimeras.fasta")
        if "uchimealns" in requested:
            outputs.append(out / "uchime_alignments.txt")
        if "uchimeout" in requested:
            outputs.append(out / "uchimeout.tsv")
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "detection_mode": ("STRING", {"default": "denovo", "options": ["denovo", "reference"], "description": "Galaxy chimera detection mode"}),
                "infile_denovo": ("FASTA", {"description": "Input FASTA for de novo chimera detection"}),
                "infile_reference": ("FASTA", {"description": "Input FASTA for reference-based chimera detection"}),
                "db": ("FASTA", {"description": "Reference database FASTA for uchime_ref mode"}),
            },
            "optional": {
                "abskew": ("FLOAT", {"default": 2.0, "min": 0, "description": "Minimum abundance ratio of parent versus chimera"}),
                "dn": ("FLOAT", {"default": 1.4, "min": 0, "description": "UCHIME no-vote pseudo-count"}),
                "xn": ("FLOAT", {"default": 8.0, "min": 0, "description": "UCHIME no-vote weight"}),
                "mindiffs": ("INT", {"default": 3, "min": 0, "description": "Minimum differences in segment"}),
                "mindiv": ("FLOAT", {"default": 0.8, "min": 0, "description": "Minimum divergence from closest parent"}),
                "minh": ("FLOAT", {"default": 0.28, "min": 0, "description": "Minimum chimera score"}),
                "self_param": ("BOOLEAN", {"default": False, "description": "Exclude identical labels for uchime_ref"}),
                "selfid_param": ("BOOLEAN", {"default": False, "description": "Exclude identical sequences for uchime_ref"}),
                "outputs": (
                    "STRING",
                    {
                        "default": [],
                        "list": True,
                        "options": ["nonchimeras", "uchimealns", "uchimeout"],
                        "description": "Optional Galaxy outputs to request",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }
