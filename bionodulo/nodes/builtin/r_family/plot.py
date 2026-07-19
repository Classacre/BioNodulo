"""ggplot2 4.0.3 CSV plotting contract."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import (
    R_VERSION,
    PreparedRScriptNode,
    path_value,
    r_string,
    validate_choice,
    validate_int,
)


GGPLOT2_VERSION = "4.0.3"
GGPLOT2_COMMIT = "cc1444c10edb87650fbe0cb31d56f0da1a255634"
PLOT_TYPES = ("scatter", "line", "bar", "histogram", "boxplot", "density", "heatmap", "custom")


class RPlotNode(PreparedRScriptNode):
    """Generate one PNG from a CSV using documented ggplot2 aesthetics."""

    NODE_ID = "r_plot"
    DISPLAY_NAME = "R Plot"
    DESCRIPTION = "Generate a source-pinned ggplot2 PNG from named CSV columns."
    SEARCH_ALIASES = ["BioNodulo builtin", "R", "ggplot2", "plot", "chart", "visualization"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("plot_png",)
    OUTPUT_NODE = True
    REQUIRED_R_PACKAGES = ["ggplot2"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "r-ggplot2"]
    CONDA_PACKAGE_CONSTRAINTS = {"r-base": R_VERSION, "r-ggplot2": GGPLOT2_VERSION}
    VERSION = GGPLOT2_VERSION
    GIT_URL = "https://github.com/tidyverse/ggplot2.git"
    GIT_COMMIT = GGPLOT2_COMMIT
    DOCUMENTATION_URL = "https://ggplot2.tidyverse.org/reference/"
    UPSTREAM_SOURCE = "R/aes.R; R/geoms.R; R/save.R; man/aes_.Rd; man/ggsave.Rd"
    CITATION_DOIS = ["10.1007/978-3-319-24277-4"]
    CITATION_URLS = ["https://doi.org/10.1007/978-3-319-24277-4"]
    CITATION_TEXT = "ggplot2 implements the grammar of graphics for declarative data visualization."
    REQUIRED_PATH_INPUTS = ("data_csv",)
    OUTPUT_FILENAMES = ("plot.png",)
    SCRIPT_FILENAME = "plot.R"
    PREVIEW_LABELS = ("R plot",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data_csv": ("FILE", {"description": "CSV with a header row"}),
                "plot_type": ("STRING", {"default": "scatter", "options": list(PLOT_TYPES)}),
                "x_axis": ("STRING", {"default": "x"}),
                "y_axis": ("STRING", {"default": "y"}),
            },
            "optional": {
                "color_column": ("STRING", {"default": "", "advanced": True}),
                "title": ("STRING", {"default": "", "advanced": True}),
                "x_label": ("STRING", {"default": "", "advanced": True}),
                "y_label": ("STRING", {"default": "", "advanced": True}),
                "width": ("INT", {"default": 800, "min": 200, "max": 4000, "advanced": True}),
                "height": ("INT", {"default": 600, "min": 200, "max": 4000, "advanced": True}),
                "custom_script": (
                    "STRING",
                    {
                        "default": "",
                        "multiline": True,
                        "advanced": True,
                        "description": "R code that must write BIONODULO_PLOT_PNG",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        plot_type = str(inputs.get("plot_type", "scatter"))
        validation = validate_choice(plot_type, "plot_type", PLOT_TYPES)
        if validation is not True:
            return validation
        custom_script = str(inputs.get("custom_script", "") or "")
        if plot_type == "custom" and not custom_script.strip():
            return "Input 'custom_script' is required when plot_type is 'custom'"
        if not custom_script.strip():
            if not str(inputs.get("x_axis", "")).strip():
                return "Input 'x_axis' must be non-empty"
            if plot_type not in {"histogram", "density"} and not str(inputs.get("y_axis", "")).strip():
                return f"Input 'y_axis' must be non-empty for plot_type '{plot_type}'"
        for key, default in (("width", 800), ("height", 600)):
            validation = validate_int(inputs.get(key, default), key, minimum=200, maximum=4000)
            if validation is not True:
                return validation
        return True

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        custom_script = str(inputs.get("custom_script", "") or "")
        if custom_script.strip():
            return textwrap.dedent(
                f"""\
                BIONODULO_DATA_CSV <- {r_string(path_value(inputs.get('data_csv')))}
                BIONODULO_PLOT_PNG <- {r_string(outputs[0])}
                {custom_script.rstrip()}
                """
            )
        return cls._build_ggplot_script(
            data_csv=path_value(inputs.get("data_csv")),
            plot_type=str(inputs.get("plot_type", "scatter")),
            x_axis=str(inputs.get("x_axis", "x")),
            y_axis=str(inputs.get("y_axis", "y")),
            color_column=str(inputs.get("color_column", "") or ""),
            title=str(inputs.get("title", "") or ""),
            x_label=str(inputs.get("x_label", "") or ""),
            y_label=str(inputs.get("y_label", "") or ""),
            width=int(inputs.get("width", 800)),
            height=int(inputs.get("height", 600)),
            png_path=outputs[0],
        )

    @staticmethod
    def _build_ggplot_script(
        *,
        data_csv: str,
        plot_type: str,
        x_axis: str,
        y_axis: str,
        color_column: str,
        title: str,
        x_label: str,
        y_label: str,
        width: int,
        height: int,
        png_path: Path,
    ) -> str:
        x_only = plot_type in {"histogram", "density"}
        base_aes = "ggplot2::aes(x = .data[[x_name]])"
        if not x_only:
            base_aes = "ggplot2::aes(x = .data[[x_name]], y = .data[[y_name]])"

        color_aes = ".data[[color_name]]"
        if plot_type == "scatter":
            layer = f"ggplot2::geom_point({f'ggplot2::aes(colour = {color_aes})' if color_column else ''})"
        elif plot_type == "line":
            mapping = f"ggplot2::aes(colour = {color_aes}, group = {color_aes})" if color_column else ""
            layer = f"ggplot2::geom_line({mapping}) + ggplot2::geom_point()"
        elif plot_type == "bar":
            mapping = f"ggplot2::aes(fill = {color_aes})" if color_column else ""
            layer = f"ggplot2::geom_col({mapping})"
        elif plot_type == "histogram":
            mapping = f"ggplot2::aes(fill = {color_aes})" if color_column else ""
            mapping_arg = f"{mapping}, " if mapping else ""
            layer = f"ggplot2::geom_histogram({mapping_arg}bins = 30)"
        elif plot_type == "boxplot":
            mapping = f"ggplot2::aes(fill = {color_aes})" if color_column else ""
            layer = f"ggplot2::geom_boxplot({mapping})"
        elif plot_type == "density":
            mapping = f"ggplot2::aes(colour = {color_aes})" if color_column else ""
            layer = f"ggplot2::geom_density({mapping})"
        elif plot_type == "heatmap":
            mapping = f"ggplot2::aes(fill = {color_aes})" if color_column else ""
            layer = f"ggplot2::geom_tile({mapping})"
        else:
            raise ValueError(f"Unsupported generated plot type: {plot_type}")

        required_columns = [x_axis]
        if not x_only:
            required_columns.append(y_axis)
        if color_column:
            required_columns.append(color_column)
        required_r = "c(" + ", ".join(r_string(column) for column in required_columns) + ")"
        default_y_label = "Count" if plot_type == "histogram" else "Density" if plot_type == "density" else y_axis
        return textwrap.dedent(
            f"""\
            if (!requireNamespace("ggplot2", quietly = TRUE)) stop("Missing required R package: ggplot2")
            plot_data <- read.csv(
                {r_string(data_csv)},
                check.names = FALSE,
                stringsAsFactors = FALSE
            )
            required_columns <- {required_r}
            missing_columns <- setdiff(required_columns, colnames(plot_data))
            if (length(missing_columns) > 0) {{
                stop("Plot CSV is missing column(s): ", paste(missing_columns, collapse = ", "))
            }}

            x_name <- {r_string(x_axis)}
            y_name <- {r_string(y_axis)}
            color_name <- {r_string(color_column)}
            plot_object <- ggplot2::ggplot(plot_data, {base_aes}) +
                {layer} +
                ggplot2::labs(
                    title = {r_string(title)},
                    x = {r_string(x_label or x_axis)},
                    y = {r_string(y_label or default_y_label)}
                ) +
                ggplot2::theme_minimal() +
                ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5))
            ggplot2::ggsave(
                filename = {r_string(png_path)},
                plot = plot_object,
                width = {width},
                height = {height},
                units = "px",
                dpi = 100
            )
            """
        )
