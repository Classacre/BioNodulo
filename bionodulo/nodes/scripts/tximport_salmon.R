args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 8L) {
    stop("Expected 8 arguments: manifest, tx2gene, mode, three matrices, RDS, and metadata")
}

suppressPackageStartupMessages({
    library("tximport")
    library("jsonlite")
})

manifest_path <- args[[1L]]
tx2gene_path <- args[[2L]]
counts_from_abundance <- args[[3L]]
counts_path <- args[[4L]]
abundance_path <- args[[5L]]
length_path <- args[[6L]]
rds_path <- args[[7L]]
metadata_path <- args[[8L]]

allowed_modes <- c("no", "scaledTPM", "lengthScaledTPM")
if (!(counts_from_abundance %in% allowed_modes)) {
    stop("countsFromAbundance must be no, scaledTPM, or lengthScaledTPM")
}

manifest <- read.delim(
    manifest_path,
    header = TRUE,
    sep = "\t",
    quote = "",
    comment.char = "",
    check.names = FALSE,
    stringsAsFactors = FALSE
)
if (!identical(names(manifest), c("sample_id", "quant_file")) || nrow(manifest) < 1L) {
    stop("Sample manifest must contain sample_id and quant_file columns and at least one row")
}
if (anyNA(manifest) || any(manifest$sample_id == "") || anyDuplicated(manifest$sample_id)) {
    stop("Sample identifiers must be non-empty and unique")
}
if (any(!file.exists(manifest$quant_file))) {
    stop(paste("Missing quantification file(s):", paste(manifest$quant_file[!file.exists(manifest$quant_file)], collapse = ", ")))
}

tx2gene <- read.delim(
    tx2gene_path,
    header = TRUE,
    sep = "\t",
    quote = "",
    comment.char = "",
    check.names = FALSE,
    stringsAsFactors = FALSE
)
if (!identical(names(tx2gene), c("transcript_id", "gene_id")) || ncol(tx2gene) != 2L) {
    stop("tx2gene must have exactly transcript_id and gene_id columns")
}
if (nrow(tx2gene) < 1L || anyNA(tx2gene) || any(tx2gene == "") || anyDuplicated(tx2gene$transcript_id)) {
    stop("tx2gene transcript and gene identifiers must be non-empty; transcripts must be unique")
}

files <- manifest$quant_file
names(files) <- manifest$sample_id
txi <- tximport::tximport(
    files = files,
    type = "salmon",
    tx2gene = tx2gene,
    countsFromAbundance = counts_from_abundance,
    txOut = FALSE,
    dropInfReps = TRUE
)

matrices <- list(counts = txi$counts, abundance = txi$abundance, length = txi$length)
expected_columns <- manifest$sample_id
expected_rows <- rownames(txi$counts)
if (length(expected_rows) < 1L || anyDuplicated(expected_rows)) {
    stop("tximport returned no gene rows or duplicate gene identifiers")
}
for (matrix_name in names(matrices)) {
    matrix_value <- matrices[[matrix_name]]
    if (!is.matrix(matrix_value) || !identical(colnames(matrix_value), expected_columns)) {
        stop(paste("tximport returned invalid sample columns for", matrix_name))
    }
    if (!identical(rownames(matrix_value), expected_rows)) {
        stop(paste("tximport returned mismatched gene rows for", matrix_name))
    }
    if (any(!is.finite(matrix_value)) || any(matrix_value < 0)) {
        stop(paste("tximport returned non-finite or negative values for", matrix_name))
    }
}

write_matrix <- function(matrix_value, path) {
    output <- data.frame(gene_id = rownames(matrix_value), matrix_value, check.names = FALSE)
    write.table(output, path, sep = "\t", quote = FALSE, row.names = FALSE, col.names = TRUE)
}

write_matrix(txi$counts, counts_path)
write_matrix(txi$abundance, abundance_path)
write_matrix(txi$length, length_path)
saveRDS(txi, rds_path, version = 3)

semantics <- switch(
    counts_from_abundance,
    no = paste(
        "Estimated transcript fragment counts summed to genes; these are not raw counts.",
        "For DESeq2, use the saved tximport object with DESeqDataSetFromTximport so the",
        "sample-specific gene length offset is retained."
    ),
    scaledTPM = paste(
        "Count-scale values derived from TPM and scaled to library size; these are not raw counts.",
        "Do not provide the effective-length matrix as a downstream offset."
    ),
    lengthScaledTPM = paste(
        "Count-scale values derived from TPM, average transcript length, and library size;",
        "these are not raw counts. Do not provide the effective-length matrix as a downstream offset."
    )
)

metadata <- list(
    tool = "tximport",
    tximport_version = as.character(utils::packageVersion("tximport")),
    r_version = R.version.string,
    quantifier = "salmon",
    aggregation_level = "gene",
    counts_from_abundance = counts_from_abundance,
    counts_semantics = semantics,
    raw_counts = FALSE,
    downstream_offset = if (counts_from_abundance == "no") "required_by_tximport_aware_DGE" else "must_not_be_used",
    sample_ids = I(manifest$sample_id),
    sample_manifest = normalizePath(manifest_path, winslash = "/", mustWork = TRUE),
    sample_manifest_md5 = unname(as.character(tools::md5sum(manifest_path))),
    quant_files = I(normalizePath(manifest$quant_file, winslash = "/", mustWork = TRUE)),
    quant_md5 = I(unname(as.character(tools::md5sum(manifest$quant_file)))),
    tx2gene = normalizePath(tx2gene_path, winslash = "/", mustWork = TRUE),
    tx2gene_md5 = unname(as.character(tools::md5sum(tx2gene_path))),
    gene_count = nrow(txi$counts),
    transcript_mapping_count = nrow(tx2gene),
    inferential_replicates = "dropped"
)
jsonlite::write_json(metadata, metadata_path, auto_unbox = TRUE, pretty = TRUE)
