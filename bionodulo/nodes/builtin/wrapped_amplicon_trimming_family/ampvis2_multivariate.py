"""Focused ampvis2 multivariate and longitudinal nodes."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

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
    RETURN_TYPES = ("IMAGE", "IMAGE")
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
                ggsave_options.append(f"    {option} = {value}")
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
    RETURN_TYPES = ("IMAGE",)
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
    RETURN_TYPES = ("IMAGE",)
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


pin_contract(Ampvis2OrdinateNode)
pin_contract(Ampvis2TimeseriesNode)
pin_contract(Ampvis2VennNode)
