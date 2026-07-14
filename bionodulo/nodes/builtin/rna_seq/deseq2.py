"""deseq2 — rna_seq node(s). One tool per file (extracted from r_bioinformatics.py)."""
from __future__ import annotations
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class DESeq2Node(BaseNode):
    """Differential expression analysis with DESeq2."""
    NODE_ID = 'deseq2_analysis'
    DISPLAY_NAME = 'DESeq2 Analysis'
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-deseq2', 'r-ggplot2', 'r-readr', 'r-ashr']
    CATEGORY = 'rna_seq'
    DESCRIPTION = 'Differential expression analysis using DESeq2 (requires count matrix + sample metadata)'
    RETURN_TYPES = ('FILE', 'FILE', 'FILE', 'FILE')
    RETURN_NAMES = ('results_csv', 'ma_plot', 'normalized_counts_csv', 'pca_scores_csv')
    OUTPUT_NODE = True
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_R_PACKAGES = ['DESeq2', 'ggplot2', 'readr', 'ashr']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'count_matrix': ('FILE', {'label': 'Count Matrix CSV'}), 'sample_info': ('FILE', {'label': 'Sample Info CSV'}), 'design_formula': ('STRING', {'default': '~ condition', 'label': 'Design Formula'}), 'contrast': ('STRING', {'default': 'condition,treated,control', 'label': 'Contrast (variable,numerator,denominator)'})}, 'optional': {'min_counts': ('INT', {'default': 10, 'min': 0, 'max': 1000, 'step': 1, 'label': 'Minimum count filter', 'advanced': True}), 'lfc_threshold': ('FLOAT', {'default': 0.0, 'min': 0.0, 'max': 5.0, 'step': 0.1, 'label': 'Log2 FC threshold', 'advanced': True}), 'padj_threshold': ('FLOAT', {'default': 0.05, 'min': 0.0, 'max': 1.0, 'step': 0.01, 'label': 'Adjusted p-value threshold', 'advanced': True})}}

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop('context', None)
        output_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        count_matrix = kwargs['count_matrix']
        sample_info = kwargs['sample_info']
        design = kwargs.get('design_formula', '~ condition')
        contrast = kwargs.get('contrast', 'condition,treated,control')
        min_counts = kwargs.get('min_counts', 10)
        lfc_threshold = kwargs.get('lfc_threshold', 0.0)
        padj_threshold = kwargs.get('padj_threshold', 0.05)
        results_csv = out_dir / 'deseq2_results.csv'
        norm_counts_csv = out_dir / 'normalized_counts.csv'
        pca_scores_csv = out_dir / 'pca_scores.csv'
        ma_plot = out_dir / 'MA_plot.png'
        script = textwrap.dedent(f'''            if (!requireNamespace("DESeq2", quietly = TRUE)) stop("Package 'DESeq2' is required but not installed. Install it with: BiocManager::install('DESeq2')")\n            if (!requireNamespace("ggplot2", quietly = TRUE)) stop("Package 'ggplot2' is required but not installed. Install it with: install.packages('ggplot2')")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")\n            library(DESeq2)\n            library(ggplot2)\n            library(readr)\n\n            countData <- as.matrix(read.csv("{Path(count_matrix).as_posix()}", row.names = 1, check.names = FALSE))\n            colData <- read.csv("{Path(sample_info).as_posix()}", row.names = 1)\n\n            # Ensure columns match\n            colData <- colData[colnames(countData), , drop = FALSE]\n\n            dds <- DESeqDataSetFromMatrix(countData = countData, colData = colData, design = {design})\n            keep <- rowSums(counts(dds)) >= {min_counts}\n            dds <- dds[keep,]\n            dds <- DESeq(dds)\n\n            contrast_parts <- strsplit("{contrast}", ",")[[1]]\n            res <- results(dds, contrast = contrast_parts, lfcThreshold = {lfc_threshold})\n            res <- lfcShrink(dds, contrast = contrast_parts, res = res, type = "ashr")\n\n            # Write results\n            res_df <- data.frame(gene = rownames(res), as.data.frame(res), check.names = FALSE)\n            write.csv(res_df, "{results_csv.as_posix()}", row.names = FALSE)\n\n            # Write normalized counts\n            norm_counts <- counts(dds, normalized = TRUE)\n            norm_counts <- data.frame(gene = rownames(norm_counts), as.data.frame(norm_counts), check.names = FALSE)\n            write.csv(norm_counts, "{norm_counts_csv.as_posix()}", row.names = FALSE)\n\n            # PCA scores for sample clustering plots\n            vst_counts <- varianceStabilizingTransformation(dds, blind = FALSE)\n            pca <- prcomp(t(assay(vst_counts)))\n            percent_var <- round(100 * (pca$sdev^2 / sum(pca$sdev^2)), 2)\n            pca_scores <- as.data.frame(pca$x[, seq_len(min(2, ncol(pca$x))), drop = FALSE])\n            if (!"PC2" %in% colnames(pca_scores)) pca_scores$PC2 <- 0\n            pca_scores <- data.frame(sample = rownames(pca_scores), pca_scores[, c("PC1", "PC2"), drop = FALSE], check.names = FALSE)\n            pca_scores <- cbind(pca_scores, as.data.frame(colData[pca_scores$sample, , drop = FALSE]))\n            pca_scores$PC1_variance <- percent_var[1]\n            pca_scores$PC2_variance <- ifelse(length(percent_var) >= 2, percent_var[2], 0)\n            write.csv(pca_scores, "{pca_scores_csv.as_posix()}", row.names = FALSE)\n\n            # MA plot\n            res_df$significant <- ifelse(!is.na(res_df$padj) & res_df$padj < {padj_threshold} & abs(res_df$log2FoldChange) > {lfc_threshold}, "Significant", "Not significant")\n            p <- ggplot(res_df, aes(x = baseMean, y = log2FoldChange, color = significant)) +\n                geom_point(alpha = 0.5, size = 1) +\n                scale_x_log10() +\n                scale_color_manual(values = c("Significant" = "red", "Not significant" = "grey50")) +\n                theme_minimal() +\n                labs(title = "MA Plot", x = "Mean of normalized counts", y = "Log2 fold change") +\n                theme(plot.title = element_text(hjust = 0.5))\n            ggsave("{ma_plot.as_posix()}", plot = p, width = 8, height = 6, dpi = 100)\n        ''')
        script_path = out_dir / 'deseq2.R'
        script_path.write_text(script, encoding='utf-8')
        cmd = ['Rscript', str(script_path)]
        if context is not None and hasattr(context, 'run_command'):
            result = await context.run_command(cmd, cwd=str(out_dir))
        else:
            import asyncio
            proc = await asyncio.create_subprocess_exec(*cmd)
            await proc.wait()
            result = {'returncode': proc.returncode}
        if result.get('returncode', 0) != 0:
            raise RuntimeError(f"DESeq2 script failed: {result.get('stderr', '')}")
        if context is not None and hasattr(context, 'register_preview'):
            context.register_preview(ma_plot, label='DESeq2 MA Plot')
        return (str(results_csv), str(ma_plot), str(norm_counts_csv), str(pca_scores_csv))
