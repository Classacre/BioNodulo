"""DESeq2 1.50.2 differential-expression contract for Bioconductor 3.22."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import (
    R_VERSION,
    PreparedRScriptNode,
    path_value,
    r_string,
    validate_int,
    validate_number,
)


DESEQ2_VERSION = "1.50.2"
DESEQ2_COMMIT = "d90821a3153a27b2a6b727df7188ea7a5b8929fd"
GGPLOT2_VERSION = "4.0.3"
GGPLOT2_COMMIT = "cc1444c10edb87650fbe0cb31d56f0da1a255634"
ASHR_VERSION = "2.2_63"
ASHR_COMMIT = "cba7ded0d9ca0d7843dfe7ca3eecabde1202aa20"


class DESeq2Node(PreparedRScriptNode):
    """Fit a DESeq2 Wald model, shrink one contrast, and export tabular results."""

    LEGACY_NODE_ID = "deseq2_analysis"
    DISPLAY_NAME = "DESeq2 Analysis"
    CATEGORY = "rna_seq"
    DESCRIPTION = (
        "Run a source-pinned DESeq2 Wald analysis from integer counts and ordered "
        "sample metadata."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "DESeq2",
        "differential expression",
        "RNA-seq",
        "negative binomial",
        "Wald test",
    ]
    RETURN_TYPES = ("CSV", "IMAGE", "CSV", "CSV")
    RETURN_NAMES = ("results_csv", "ma_plot", "normalized_counts_csv", "pca_scores_csv")
    OUTPUT_NODE = True
    REQUIRED_R_PACKAGES = ["DESeq2", "ggplot2", "ashr"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-deseq2", "r-ggplot2", "r-ashr"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "r-base": R_VERSION,
        "bioconductor-deseq2": DESEQ2_VERSION,
        "r-ggplot2": GGPLOT2_VERSION,
        "r-ashr": ASHR_VERSION,
    }
    PACKAGE_CONSTRAINTS = tuple(
        f"{package}={version}" for package, version in CONDA_PACKAGE_CONSTRAINTS.items()
    )
    VERSION = DESEQ2_VERSION
    GIT_URL = "https://git.bioconductor.org/packages/DESeq2"
    GIT_COMMIT = DESEQ2_COMMIT
    DOCUMENTATION_URL = "https://bioconductor.org/packages/3.22/bioc/html/DESeq2.html"
    UPSTREAM_SOURCE = "R/AllClasses.R; R/core.R; R/results.R; R/lfcShrink.R; R/vst.R"
    SOURCE_AUTHORITIES = {
        "DESeq2": ("1.50.2", DESEQ2_COMMIT),
        "ggplot2": ("4.0.3", GGPLOT2_COMMIT),
        "ashr": ("2.2-63", ASHR_COMMIT),
    }
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = ["10.1186/s13059-014-0550-8", "10.18129/B9.bioc.DESeq2"]
    CITATION_URLS = [
        "https://doi.org/10.1186/s13059-014-0550-8",
        "https://doi.org/10.18129/B9.bioc.DESeq2",
    ]
    CITATION_TEXT = "DESeq2 models sequencing counts with negative-binomial generalized linear models."
    REQUIRED_PATH_INPUTS = ("count_matrix", "sample_info")
    OUTPUT_FILENAMES = (
        "deseq2_results.csv",
        "MA_plot.png",
        "normalized_counts.csv",
        "pca_scores.csv",
    )
    SCRIPT_FILENAME = "deseq2.R"
    PREVIEW_LABELS = (None, "DESeq2 MA Plot", None, None)
    EXIT_SEMANTICS = (
        "DESeq2, ashr, and ggplot2 errors propagate through Rscript; exit code 0 and "
        "all four native output files are required."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "count_matrix": (
                    "FILE",
                    {"description": "CSV with gene identifiers in column 1 and integer sample counts"},
                ),
                "sample_info": (
                    "FILE",
                    {"description": "CSV whose first column lists samples in count-matrix order"},
                ),
                "design_formula": ("STRING", {"default": "~ condition"}),
                "contrast": (
                    "STRING",
                    {"default": "condition,treated,control", "description": "variable,numerator,denominator"},
                ),
            },
            "optional": {
                "min_counts": ("INT", {"default": 10, "min": 0}),
                "lfc_threshold": ("FLOAT", {"default": 0.0, "min": 0.0}),
                "padj_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @staticmethod
    def _contrast_parts(value: Any) -> tuple[str, str, str] | None:
        parts = tuple(part.strip() for part in str(value).split(","))
        if len(parts) != 3 or any(not part for part in parts):
            return None
        return parts  # type: ignore[return-value]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        design = str(inputs.get("design_formula", "~ condition")).strip()
        if not design.startswith("~") or len(design) == 1:
            return "Input 'design_formula' must be a non-empty R formula beginning with '~'"
        if cls._contrast_parts(inputs.get("contrast", "condition,treated,control")) is None:
            return "Input 'contrast' must contain variable,numerator,denominator"
        validation = validate_int(inputs.get("min_counts", 10), "min_counts", minimum=0)
        if validation is not True:
            return validation
        validation = validate_number(inputs.get("lfc_threshold", 0.0), "lfc_threshold", minimum=0.0)
        if validation is not True:
            return validation
        validation = validate_number(
            inputs.get("padj_threshold", 0.05),
            "padj_threshold",
            minimum=0.0,
            maximum=1.0,
        )
        if validation is not True:
            return validation
        padj_threshold = float(inputs.get("padj_threshold", 0.05))
        if not 0.0 < padj_threshold < 1.0:
            return "Input 'padj_threshold' must be greater than 0 and less than 1"
        for key in cls.REQUIRED_PATH_INPUTS:
            path = Path(path_value(inputs.get(key)))
            if not path.is_file():
                return f"Input '{key}' is not a materialized file: {path}"
            try:
                if path.stat().st_size == 0:
                    return f"Input '{key}' file is empty: {path}"
            except OSError as exc:
                return f"Cannot inspect input '{key}' file {path}: {exc}"
        return True

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        contrast = cls._contrast_parts(inputs.get("contrast", "condition,treated,control"))
        if contrast is None:
            raise ValueError("Input 'contrast' must contain variable,numerator,denominator")
        contrast_r = "c(" + ", ".join(r_string(part) for part in contrast) + ")"
        return textwrap.dedent(
            f"""\
            required_packages <- c("DESeq2", "ggplot2", "ashr")
            missing_packages <- required_packages[!vapply(required_packages, requireNamespace, logical(1), quietly = TRUE)]
            if (length(missing_packages) > 0) {{
                stop("Missing required R package(s): ", paste(missing_packages, collapse = ", "))
            }}
            suppressPackageStartupMessages(library(DESeq2))

            count_frame <- read.csv(
                {r_string(path_value(inputs.get('count_matrix')))},
                row.names = 1,
                check.names = FALSE,
                stringsAsFactors = FALSE
            )
            count_data <- as.matrix(count_frame)
            suppressWarnings(storage.mode(count_data) <- "numeric")
            if (anyNA(count_data) || any(!is.finite(count_data))) {{
                stop("Count matrix must contain only finite numeric values after the identifier column.")
            }}
            if (any(count_data < 0) || any(count_data != floor(count_data))) {{
                stop("DESeq2 count data must contain non-negative integer values.")
            }}
            if (any(count_data > .Machine$integer.max)) {{
                stop("DESeq2 count values exceed R's integer range.")
            }}
            storage.mode(count_data) <- "integer"

            col_data <- read.csv(
                {r_string(path_value(inputs.get('sample_info')))},
                row.names = 1,
                check.names = FALSE,
                stringsAsFactors = FALSE
            )
            if (anyDuplicated(colnames(count_data)) || anyDuplicated(rownames(col_data))) {{
                stop("Sample identifiers must be unique in both input files.")
            }}
            if (!identical(colnames(count_data), rownames(col_data))) {{
                stop("Sample metadata row names must exactly match count-matrix columns in the same order.")
            }}
            if (ncol(count_data) < 2) stop("DESeq2 analysis requires at least two samples.")

            design_formula <- as.formula({r_string(str(inputs.get('design_formula', '~ condition')).strip())})
            missing_design <- setdiff(all.vars(design_formula), colnames(col_data))
            if (length(missing_design) > 0) {{
                stop("Design variable(s) missing from sample metadata: ", paste(missing_design, collapse = ", "))
            }}

            dds <- DESeqDataSetFromMatrix(countData = count_data, colData = col_data, design = design_formula)
            keep <- rowSums(counts(dds)) >= {int(inputs.get('min_counts', 10))}
            if (sum(keep) < 2) stop("Fewer than two genes remain after the minimum-count filter.")
            dds <- dds[keep, ]
            dds <- DESeq(dds, quiet = TRUE)

            contrast_parts <- {contrast_r}
            res <- results(
                dds,
                contrast = contrast_parts,
                lfcThreshold = {float(inputs.get('lfc_threshold', 0.0))!r},
                alpha = {float(inputs.get('padj_threshold', 0.05))!r}
            )
            res <- lfcShrink(
                dds,
                res = res,
                type = "ashr",
                lfcThreshold = {float(inputs.get('lfc_threshold', 0.0))!r},
                quiet = TRUE
            )

            res_frame <- data.frame(gene = rownames(res), as.data.frame(res), check.names = FALSE)
            write.csv(res_frame, {r_string(outputs[0])}, row.names = FALSE)

            normalized <- counts(dds, normalized = TRUE)
            normalized_frame <- data.frame(
                gene = rownames(normalized),
                as.data.frame(normalized),
                check.names = FALSE
            )
            write.csv(normalized_frame, {r_string(outputs[2])}, row.names = FALSE)

            transformed <- varianceStabilizingTransformation(dds, blind = FALSE)
            pca <- prcomp(t(assay(transformed)))
            percent_variance <- 100 * (pca$sdev^2 / sum(pca$sdev^2))
            pc1 <- pca$x[, 1]
            pc2 <- if (ncol(pca$x) >= 2) pca$x[, 2] else rep(0, nrow(pca$x))
            pca_frame <- data.frame(
                sample = rownames(pca$x),
                PC1 = pc1,
                PC2 = pc2,
                check.names = FALSE
            )
            pca_frame <- cbind(pca_frame, as.data.frame(colData(dds))[pca_frame$sample, , drop = FALSE])
            pca_frame$PC1_variance <- percent_variance[1]
            pca_frame$PC2_variance <- if (length(percent_variance) >= 2) percent_variance[2] else 0
            write.csv(pca_frame, {r_string(outputs[3])}, row.names = FALSE)

            res_frame$significant <- ifelse(
                !is.na(res_frame$padj) &
                    res_frame$padj <= {float(inputs.get('padj_threshold', 0.05))!r} &
                    abs(res_frame$log2FoldChange) >= {float(inputs.get('lfc_threshold', 0.0))!r},
                "Significant",
                "Not significant"
            )
            plot_frame <- res_frame[is.finite(res_frame$baseMean) & is.finite(res_frame$log2FoldChange), ]
            plot_frame$mean_for_plot <- plot_frame$baseMean + 1
            ma_plot <- ggplot2::ggplot(
                plot_frame,
                ggplot2::aes(x = mean_for_plot, y = log2FoldChange, colour = significant)
            ) +
                ggplot2::geom_point(alpha = 0.5, size = 1, na.rm = TRUE) +
                ggplot2::scale_x_log10() +
                ggplot2::scale_colour_manual(values = c("Significant" = "#b51f2e", "Not significant" = "grey55")) +
                ggplot2::theme_minimal() +
                ggplot2::labs(title = "MA Plot", x = "Mean normalized count + 1", y = "Shrunken log2 fold change") +
                ggplot2::theme(plot.title = ggplot2::element_text(hjust = 0.5))
            ggplot2::ggsave(
                filename = {r_string(outputs[1])},
                plot = ma_plot,
                width = 8,
                height = 6,
                units = "in",
                dpi = 100
            )
            """
        )


class DESeq2AliasNode(DESeq2Node):
    """Stable planner alias for the same DESeq2 1.50.2 operation."""

    LEGACY_NODE_ID = "deseq2"
    DISPLAY_NAME = "DESeq2"
    DESCRIPTION = "Run the source-pinned DESeq2 differential-expression contract."
