"""Focused ampvis2 abundance visualization nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

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
    RETURN_TYPES = ("IMAGE",)
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE",)
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE", "TSV")
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
                ggsave_options.append(f"    {option} = {value}")
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
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        path = planned_paths[0]
        return {"plot_raw" if path.name == "plot_raw.tsv" else "plot": path}

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
    RETURN_TYPES = ("IMAGE",)
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
                ggsave_options.append(f"    {option} = {value}")
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


pin_contract(Ampvis2BoxplotNode)
pin_contract(Ampvis2FrequencyNode)
pin_contract(Ampvis2HeatmapNode)
pin_contract(Ampvis2OtuNetworkNode)
