"""pheatmap 1.0.13 clustered-matrix visualization contract."""

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


PHEATMAP_VERSION = "1.0.13"
PHEATMAP_COMMIT = "ffd0f8c4b5a3dc2628a3dfd9b5fd4321c2aa1569"

# Native pheatmap emits a heading followed by its rectangle/text legend block.
# Measure those grobs on the output device; font-code predicates and a fixed
# offset are unreliable across devices. Preserve every non-position property.
_ANNOTATION_LEGEND_PADDING_R = """\
pad_annotation_legend <- function(legend, annotation_names, fontsize) {
    indices <- seq_along(legend$children)
    headings <- vapply(indices, function(index) {
        child <- legend$children[[index]]
        inherits(child, "text") && length(child$label) == 1L &&
            child$label %in% annotation_names && index < length(legend$children) &&
            inherits(legend$children[[index + 1L]], "rect")
    }, logical(1))
    offset <- grid::unit(0, "bigpts")
    gap <- fontsize * 0.25
    for (index in indices) {
        child <- legend$children[[index]]
        child$y <- child$y - offset
        legend$children[[index]] <- child
        if (headings[index]) {
            following <- indices[headings & indices > index]
            last <- if (length(following)) following[1] - 1L else length(indices)
            body_top <- max(vapply(seq.int(index + 1L, last), function(body_index) {
                body <- legend$children[[body_index]]
                body$y <- body$y - offset
                grid::convertY(grid::grobY(body, 90), "bigpts", valueOnly = TRUE)
            }, numeric(1)))
            heading_bottom <- grid::convertY(grid::grobY(child, 270), "bigpts", valueOnly = TRUE)
            offset <- offset + grid::unit(max(0, body_top + gap - heading_bottom), "bigpts")
        }
    }
    legend
}
"""


class PheatmapNode(PreparedRScriptNode):
    """Render a numeric CSV matrix with pheatmap's documented file output path."""

    NODE_ID = "r_pheatmap"
    DISPLAY_NAME = "R Heatmap (pheatmap)"
    DESCRIPTION = "Render a clustered numeric matrix with source-pinned pheatmap."
    SEARCH_ALIASES = ["BioNodulo builtin", "R", "pheatmap", "heatmap", "clustered matrix"]
    RETURN_TYPES = ("IMAGE",)
    RETURN_NAMES = ("plot_png",)
    OUTPUT_NODE = True
    REQUIRED_R_PACKAGES = ["pheatmap"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "r-pheatmap"]
    CONDA_PACKAGE_CONSTRAINTS = {"r-base": R_VERSION, "r-pheatmap": PHEATMAP_VERSION}
    VERSION = PHEATMAP_VERSION
    CACHE_VERSION = "1.0.13-render3"
    GIT_URL = "https://github.com/raivokolde/pheatmap.git"
    GIT_COMMIT = PHEATMAP_COMMIT
    DOCUMENTATION_URL = "https://cran.r-project.org/package=pheatmap"
    UPSTREAM_SOURCE = "R/pheatmap.r:pheatmap; man/pheatmap.Rd"
    CITATION_URLS = ["https://doi.org/10.32614/CRAN.package.pheatmap"]
    CITATION_TEXT = "pheatmap draws clustered heatmaps and writes images based on the filename extension."
    REQUIRED_PATH_INPUTS = ("data_csv",)
    OUTPUT_FILENAMES = ("heatmap.png",)
    SCRIPT_FILENAME = "pheatmap.R"
    PREVIEW_LABELS = ("pheatmap",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data_csv": ("FILE", {"description": "CSV with row identifiers in column 1"}),
                "scale": ("STRING", {"default": "row", "options": ["none", "row", "column"]}),
            },
            "optional": {
                "annotation_csv": (
                    "FILE",
                    {"description": "Optional column annotation CSV keyed by sample name", "advanced": True},
                ),
                "cluster_rows": ("BOOLEAN", {"default": True, "advanced": True}),
                "cluster_cols": ("BOOLEAN", {"default": True, "advanced": True}),
                "show_rownames": ("BOOLEAN", {"default": True, "advanced": True}),
                "show_colnames": ("BOOLEAN", {"default": True, "advanced": True}),
                "fontsize": ("INT", {"default": 10, "min": 4, "max": 24, "advanced": True}),
                "width": ("INT", {"default": 800, "min": 200, "max": 4000, "advanced": True}),
                "height": ("INT", {"default": 600, "min": 200, "max": 4000, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        annotation = inputs.get("annotation_csv")
        if annotation not in (None, "") and not path_value(annotation):
            return "Input 'annotation_csv' must be a non-empty path-like value when provided"
        validation = validate_choice(inputs.get("scale", "row"), "scale", ("none", "row", "column"))
        if validation is not True:
            return validation
        for key, default, minimum, maximum in (
            ("fontsize", 10, 4, 24),
            ("width", 800, 200, 4000),
            ("height", 600, 200, 4000),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if validation is not True:
                return validation
        return True

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        annotation = path_value(inputs.get("annotation_csv"))
        annotation_code = "annotation_data <- NA"
        if annotation:
            annotation_code = textwrap.dedent(
                f"""\
                annotation_data <- read.csv(
                    {r_string(annotation)},
                    row.names = 1,
                    check.names = FALSE,
                    stringsAsFactors = FALSE
                )
                missing_annotations <- setdiff(colnames(matrix_data), rownames(annotation_data))
                if (length(missing_annotations) > 0) {{
                    stop("Annotation CSV is missing matrix column(s): ", paste(missing_annotations, collapse = ", "))
                }}
                annotation_data <- annotation_data[colnames(matrix_data), , drop = FALSE]
                """
            ).strip()
        return textwrap.dedent(
            f"""\
            if (!requireNamespace("pheatmap", quietly = TRUE)) stop("Missing required R package: pheatmap")

            matrix_frame <- read.csv(
                {r_string(path_value(inputs.get('data_csv')))},
                row.names = 1,
                check.names = FALSE,
                stringsAsFactors = FALSE
            )
            matrix_data <- as.matrix(matrix_frame)
            suppressWarnings(storage.mode(matrix_data) <- "numeric")
            if (anyNA(matrix_data) || any(!is.finite(matrix_data))) {{
                stop("Heatmap matrix must contain only finite numeric values after the identifier column.")
            }}
            if ({str(bool(inputs.get('cluster_rows', True))).upper()} && nrow(matrix_data) < 2) {{
                stop("Row clustering requires at least two matrix rows.")
            }}
            if ({str(bool(inputs.get('cluster_cols', True))).upper()} && ncol(matrix_data) < 2) {{
                stop("Column clustering requires at least two matrix columns.")
            }}

            {annotation_code}

            heatmap <- pheatmap::pheatmap(
                matrix_data,
                scale = {r_string(inputs.get('scale', 'row'))},
                cluster_rows = {str(bool(inputs.get('cluster_rows', True))).upper()},
                cluster_cols = {str(bool(inputs.get('cluster_cols', True))).upper()},
                show_rownames = {str(bool(inputs.get('show_rownames', True))).upper()},
                show_colnames = {str(bool(inputs.get('show_colnames', True))).upper()},
                fontsize = {int(inputs.get('fontsize', 10))},
                annotation_col = annotation_data,
                main = "Heatmap",
                filename = {r_string(outputs[0])},
                width = {int(inputs.get('width', 800)) / 100!r},
                height = {int(inputs.get('height', 600)) / 100!r}
            )

            {_ANNOTATION_LEGEND_PADDING_R}
            legend_index <- which(heatmap$gtable$layout$name == "annotation_legend")
            if (length(legend_index) == 1L) {{
                # Reuse the computed gtable; do not cluster the matrix again.
                grDevices::png(
                    filename = {r_string(outputs[0])},
                    width = {int(inputs.get('width', 800)) / 100!r},
                    height = {int(inputs.get('height', 600)) / 100!r},
                    units = "in", res = 300
                )
                tryCatch({{
                    heatmap$gtable$grobs[[legend_index]] <- pad_annotation_legend(
                        heatmap$gtable$grobs[[legend_index]],
                        colnames(annotation_data),
                        {int(inputs.get('fontsize', 10))}
                    )
                    grid::grid.newpage()
                    grid::grid.draw(heatmap$gtable)
                }}, finally = grDevices::dev.off())
            }}
            """
        )
