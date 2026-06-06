"""Bioinformatics-specific R nodes for BioNodulo.

Wraps common Bioconductor and CRAN packages into workflow nodes for
statistical analysis and visualization of omics data.
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode


class DESeq2Node(BaseNode):
    """Differential expression analysis with DESeq2."""

    NODE_ID = "deseq2_analysis"
    DISPLAY_NAME = "DESeq2 Analysis"
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-deseq2', 'r-ggplot2', 'r-readr', 'r-ashr']
    CATEGORY = "rna_seq"
    DESCRIPTION = "Differential expression analysis using DESeq2 (requires count matrix + sample metadata)"
    RETURN_TYPES = ("FILE", "FILE", "FILE", "FILE")
    RETURN_NAMES = ("results_csv", "ma_plot", "normalized_counts_csv", "pca_scores_csv")
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_R_PACKAGES = ["DESeq2", "ggplot2", "readr", "ashr"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "count_matrix": ("FILE", {"label": "Count Matrix CSV"}),
                "sample_info": ("FILE", {"label": "Sample Info CSV"}),
                "design_formula": ("STRING", {"default": "~ condition", "label": "Design Formula"}),
                "contrast": ("STRING", {"default": "condition,treated,control", "label": "Contrast (variable,numerator,denominator)"}),
            },
            "optional": {
                "min_counts": ("INT", {"default": 10, "min": 0, "max": 1000, "step": 1, "label": "Minimum count filter", "advanced": True}),
                "lfc_threshold": ("FLOAT", {"default": 0.0, "min": 0.0, "max": 5.0, "step": 0.1, "label": "Log2 FC threshold", "advanced": True}),
                "padj_threshold": ("FLOAT", {"default": 0.05, "min": 0.0, "max": 1.0, "step": 0.01, "label": "Adjusted p-value threshold", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        count_matrix = kwargs["count_matrix"]
        sample_info = kwargs["sample_info"]
        design = kwargs.get("design_formula", "~ condition")
        contrast = kwargs.get("contrast", "condition,treated,control")
        min_counts = kwargs.get("min_counts", 10)
        lfc_threshold = kwargs.get("lfc_threshold", 0.0)
        padj_threshold = kwargs.get("padj_threshold", 0.05)

        results_csv = out_dir / "deseq2_results.csv"
        norm_counts_csv = out_dir / "normalized_counts.csv"
        pca_scores_csv = out_dir / "pca_scores.csv"
        ma_plot = out_dir / "MA_plot.png"

        script = textwrap.dedent(f"""\
            if (!requireNamespace("DESeq2", quietly = TRUE)) stop("Package 'DESeq2' is required but not installed. Install it with: BiocManager::install('DESeq2')")
            if (!requireNamespace("ggplot2", quietly = TRUE)) stop("Package 'ggplot2' is required but not installed. Install it with: install.packages('ggplot2')")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")
            library(DESeq2)
            library(ggplot2)
            library(readr)

            countData <- as.matrix(read.csv("{Path(count_matrix).as_posix()}", row.names = 1, check.names = FALSE))
            colData <- read.csv("{Path(sample_info).as_posix()}", row.names = 1)

            # Ensure columns match
            colData <- colData[colnames(countData), , drop = FALSE]

            dds <- DESeqDataSetFromMatrix(countData = countData, colData = colData, design = {design})
            keep <- rowSums(counts(dds)) >= {min_counts}
            dds <- dds[keep,]
            dds <- DESeq(dds)

            contrast_parts <- strsplit("{contrast}", ",")[[1]]
            res <- results(dds, contrast = contrast_parts, lfcThreshold = {lfc_threshold})
            res <- lfcShrink(dds, contrast = contrast_parts, res = res, type = "ashr")

            # Write results
            write.csv(as.data.frame(res), "{results_csv.as_posix()}")

            # Write normalized counts
            norm_counts <- counts(dds, normalized = TRUE)
            write.csv(as.data.frame(norm_counts), "{norm_counts_csv.as_posix()}")

            # PCA scores for sample clustering plots
            vst_counts <- varianceStabilizingTransformation(dds, blind = FALSE)
            pca <- prcomp(t(assay(vst_counts)))
            percent_var <- round(100 * (pca$sdev^2 / sum(pca$sdev^2)), 2)
            pca_scores <- as.data.frame(pca$x[, seq_len(min(2, ncol(pca$x))), drop = FALSE])
            if (!"PC2" %in% colnames(pca_scores)) pca_scores$PC2 <- 0
            pca_scores <- data.frame(sample = rownames(pca_scores), pca_scores[, c("PC1", "PC2"), drop = FALSE], check.names = FALSE)
            pca_scores <- cbind(pca_scores, as.data.frame(colData[pca_scores$sample, , drop = FALSE]))
            pca_scores$PC1_variance <- percent_var[1]
            pca_scores$PC2_variance <- ifelse(length(percent_var) >= 2, percent_var[2], 0)
            write.csv(pca_scores, "{pca_scores_csv.as_posix()}", row.names = FALSE)

            # MA plot
            res_df <- as.data.frame(res)
            res_df$significant <- ifelse(!is.na(res_df$padj) & res_df$padj < {padj_threshold} & abs(res_df$log2FoldChange) > {lfc_threshold}, "Significant", "Not significant")
            p <- ggplot(res_df, aes(x = baseMean, y = log2FoldChange, color = significant)) +
                geom_point(alpha = 0.5, size = 1) +
                scale_x_log10() +
                scale_color_manual(values = c("Significant" = "red", "Not significant" = "grey50")) +
                theme_minimal() +
                labs(title = "MA Plot", x = "Mean of normalized counts", y = "Log2 fold change") +
                theme(plot.title = element_text(hjust = 0.5))
            ggsave("{ma_plot.as_posix()}", plot = p, width = 8, height = 6, dpi = 100)
        """)

        script_path = out_dir / "deseq2.R"
        script_path.write_text(script, encoding="utf-8")

        cmd = ["Rscript", str(script_path)]
        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {"returncode": proc.returncode}

        if result.get("returncode", 0) != 0:
            raise RuntimeError(f"DESeq2 script failed: {result.get('stderr', '')}")

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(ma_plot, label="DESeq2 MA Plot")

        return (str(results_csv), str(ma_plot), str(norm_counts_csv), str(pca_scores_csv))


class DESeq2AliasNode(DESeq2Node):
    """Planner/workflow compatibility alias for DESeq2Node."""

    NODE_ID = "deseq2"
    DISPLAY_NAME = "DESeq2"
    DESCRIPTION = "Run DESeq2 differential expression analysis for RNA-seq count matrices."
    SEARCH_ALIASES = [
        "deseq2",
        "differential expression",
        "rna-seq",
        "counts",
        "bioconductor",
    ]


class PheatmapNode(BaseNode):
    """Generate clustered heatmaps with pheatmap."""

    NODE_ID = "r_pheatmap"
    DISPLAY_NAME = "R Heatmap (pheatmap)"
    REQUIRED_CONDA_PACKAGES = ['r-base', 'r-pheatmap', 'r-rcolorbrewer', 'r-readr']
    CATEGORY = "r"
    DESCRIPTION = "Generate publication-quality clustered heatmaps with pheatmap"
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("plot_png",)
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_R_PACKAGES = ["pheatmap", "RColorBrewer", "readr"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "data_csv": ("FILE", {"label": "Data Matrix CSV"}),
                "scale": ("STRING", {
                    "default": "row",
                    "options": ["none", "row", "column"],
                    "label": "Scale",
                }),
            },
            "optional": {
                "annotation_csv": ("FILE", {"label": "Annotation CSV (optional)", "advanced": True}),
                "cluster_rows": ("BOOLEAN", {"default": True, "label": "Cluster rows", "advanced": True}),
                "cluster_cols": ("BOOLEAN", {"default": True, "label": "Cluster columns", "advanced": True}),
                "show_rownames": ("BOOLEAN", {"default": True, "label": "Show row names", "advanced": True}),
                "show_colnames": ("BOOLEAN", {"default": True, "label": "Show column names", "advanced": True}),
                "fontsize": ("INT", {"default": 10, "min": 4, "max": 24, "step": 1, "label": "Font size", "advanced": True}),
                "width": ("INT", {"default": 800, "min": 200, "max": 4000, "step": 50, "display": "slider", "label": "Width (px)", "advanced": True}),
                "height": ("INT", {"default": 600, "min": 200, "max": 4000, "step": 50, "display": "slider", "label": "Height (px)", "advanced": True}),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        data_csv = kwargs["data_csv"]
        scale = kwargs.get("scale", "row")
        annotation_csv = kwargs.get("annotation_csv", "") or ""
        cluster_rows = kwargs.get("cluster_rows", True)
        cluster_cols = kwargs.get("cluster_cols", True)
        show_rownames = kwargs.get("show_rownames", True)
        show_colnames = kwargs.get("show_colnames", True)
        fontsize = kwargs.get("fontsize", 10)
        width = kwargs.get("width", 800)
        height = kwargs.get("height", 600)

        png_path = out_dir / "heatmap.png"
        script_path = out_dir / "heatmap.R"

        ann_arg = f'annotation_col = read.csv("{Path(annotation_csv).as_posix()}", row.names = 1),' if annotation_csv else ''

        script = textwrap.dedent(f"""\
            if (!requireNamespace("pheatmap", quietly = TRUE)) stop("Package 'pheatmap' is required but not installed. Install it with: install.packages('pheatmap')")
            if (!requireNamespace("RColorBrewer", quietly = TRUE)) stop("Package 'RColorBrewer' is required but not installed. Install it with: install.packages('RColorBrewer')")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")
            library(pheatmap)
            library(RColorBrewer)
            library(readr)

            data <- as.matrix(read.csv("{Path(data_csv).as_posix()}", row.names = 1, check.names = FALSE))
            {f'ann <- read.csv("{Path(annotation_csv).as_posix()}", row.names = 1)' if annotation_csv else ''}

            png("{png_path.as_posix()}", width = {width}, height = {height}, res = 100)
            pheatmap(data,
                scale = "{scale}",
                cluster_rows = {str(cluster_rows).upper()},
                cluster_cols = {str(cluster_cols).upper()},
                show_rownames = {str(show_rownames).upper()},
                show_colnames = {str(show_colnames).upper()},
                fontsize = {fontsize},
                color = colorRampPalette(rev(brewer.pal(n = 7, name = "RdYlBu")))(100),
                {ann_arg}
                main = "Heatmap"
            )
            dev.off()
        """)

        script_path.write_text(script, encoding="utf-8")

        cmd = ["Rscript", str(script_path)]
        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {"returncode": proc.returncode}

        if result.get("returncode", 0) != 0:
            raise RuntimeError(f"pheatmap script failed: {result.get('stderr', '')}")

        if context is not None and hasattr(context, "register_preview"):
            context.register_preview(png_path, label="pheatmap")

        return (str(png_path),)


class BiostringsStatsNode(BaseNode):
    """Advanced sequence analysis using Biostrings (ORFs, complements, translation)."""

    NODE_ID = "r_biostrings_stats"
    DISPLAY_NAME = "Biostrings Stats"
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-biostrings', 'r-readr']
    CATEGORY = "sequence"
    DESCRIPTION = "Advanced sequence stats with Biostrings: ORF finding, reverse complement, 6-frame translation"
    RETURN_TYPES = ("FILE", "FILE", "FILE")
    RETURN_NAMES = ("orf_table_csv", "revcomp_fasta", "six_frame_fasta")
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_R_PACKAGES = ["Biostrings", "readr"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FILE", {"label": "DNA FASTA"}),
            },
            "optional": {
                "min_orf_length": ("INT", {"default": 100, "min": 30, "max": 1000, "step": 10, "label": "Min ORF length (aa)", "advanced": True}),
                "genetic_code": ("STRING", {
                    "default": "Standard",
                    "options": ["Standard", "Bacterial", "Vertebrate Mitochondrial", "Yeast Mitochondrial"],
                    "label": "Genetic code",
                    "advanced": True,
                }),
            },
        }

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        output_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)

        input_fasta = kwargs["input_fasta"]
        min_orf = kwargs.get("min_orf_length", 100)
        genetic_code = kwargs.get("genetic_code", "Standard")

        code_map = {
            "Standard": "1",
            "Bacterial": "11",
            "Vertebrate Mitochondrial": "2",
            "Yeast Mitochondrial": "3",
        }
        code_num = code_map.get(genetic_code, "1")

        orf_csv = out_dir / "orf_table.csv"
        revcomp_fasta = out_dir / "reverse_complement.fasta"
        sixframe_fasta = out_dir / "six_frame_translation.fasta"

        script = textwrap.dedent(f"""\
            if (!requireNamespace("Biostrings", quietly = TRUE)) stop("Package 'Biostrings' is required but not installed. Install it with: BiocManager::install('Biostrings')")
            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")
            library(Biostrings)
            library(readr)

            dna <- readDNAStringSet("{Path(input_fasta).as_posix()}")

            # Reverse complement
            revcomp <- reverseComplement(dna)
            writeXStringSet(revcomp, "{revcomp_fasta.as_posix()}")

            # ORF finding per sequence
            orf_results <- data.frame(
                sequence_id = character(),
                frame = integer(),
                start = integer(),
                end = integer(),
                length_aa = integer(),
                stringsAsFactors = FALSE
            )

            for (i in seq_along(dna)) {{
                seq <- dna[[i]]
                seq_name <- names(dna)[i]
                for (frame in 0:2) {{
                    shifted <- subseq(seq, start = frame + 1)
                    aa <- translate(shifted, genetic.code = getGeneticCode("{code_num}"), if.fuzzy.codon = "X")
                    # Split on stop codons and find ORFs
                    aa_str <- as.character(aa)
                    peptides <- strsplit(aa_str, "\\\\*")[[1]]
                    pos <- 1
                    for (p in peptides) {{
                        if (nchar(p) >= {min_orf}) {{
                            orf_results <- rbind(orf_results, data.frame(
                                sequence_id = seq_name,
                                frame = frame + 1,
                                start = pos,
                                end = pos + nchar(p) - 1,
                                length_aa = nchar(p),
                                stringsAsFactors = FALSE
                            ))
                        }}
                        pos <- pos + nchar(p) + 1
                    }}
                }}
            }}

            write.csv(orf_results, "{orf_csv.as_posix()}", row.names = FALSE)

            # Six-frame translation
            six_frame <- AAStringSet()
            six_frame_names <- character()
            for (i in seq_along(dna)) {{
                seq <- dna[[i]]
                seq_name <- names(dna)[i]
                for (frame in 0:2) {{
                    shifted <- subseq(seq, start = frame + 1)
                    aa <- translate(shifted, genetic.code = getGeneticCode("{code_num}"), if.fuzzy.codon = "X")
                    six_frame <- c(six_frame, AAStringSet(aa))
                    six_frame_names <- c(six_frame_names, paste0(seq_name, "_frame", frame + 1))
                }}
                rev_seq <- reverseComplement(seq)
                for (frame in 0:2) {{
                    shifted <- subseq(rev_seq, start = frame + 1)
                    aa <- translate(shifted, genetic.code = getGeneticCode("{code_num}"), if.fuzzy.codon = "X")
                    six_frame <- c(six_frame, AAStringSet(aa))
                    six_frame_names <- c(six_frame_names, paste0(seq_name, "_rev_frame", frame + 1))
                }}
            }}
            names(six_frame) <- six_frame_names
            writeXStringSet(six_frame, "{sixframe_fasta.as_posix()}", format = "fasta")
        """)

        script_path = out_dir / "biostrings.R"
        script_path.write_text(script, encoding="utf-8")

        cmd = ["Rscript", str(script_path)]
        if context is not None and hasattr(context, "run_command"):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {"returncode": proc.returncode}

        if result.get("returncode", 0) != 0:
            raise RuntimeError(f"Biostrings script failed: {result.get('stderr', '')}")

        return (str(orf_csv), str(revcomp_fasta), str(sixframe_fasta))
