"""Focused ampvis2 diversity and depth-analysis nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

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
    RETURN_TYPES = ("TSV", "IMAGE")
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE",)
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE",)
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE",)
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE",)
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


pin_contract(Ampvis2AlphaDiversityNode)
pin_contract(Ampvis2CoreNode)
pin_contract(Ampvis2OctaveNode)
pin_contract(Ampvis2RankAbundanceNode)
pin_contract(Ampvis2RarecurveNode)
