args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 10L) {
    stop("Expected 10 arguments: manifest, tx2gene, reference GTF, read length, mode, three matrices, RDS, metadata")
}

suppressPackageStartupMessages({
    library("tximport")
    library("jsonlite")
})

manifest_path <- args[[1L]]
tx2gene_path <- args[[2L]]
reference_gtf_path <- args[[3L]]
read_length <- suppressWarnings(as.numeric(args[[4L]]))
counts_from_abundance <- args[[5L]]
counts_path <- args[[6L]]
abundance_path <- args[[7L]]
length_path <- args[[8L]]
rds_path <- args[[9L]]
metadata_path <- args[[10L]]

if (!is.finite(read_length) || read_length <= 0) stop("readLength must be an explicit positive number")
if (!file.exists(reference_gtf_path)) stop("reference GTF does not exist")
allowed_modes <- c("no", "scaledTPM", "lengthScaledTPM")
if (!(counts_from_abundance %in% allowed_modes)) {
    stop("countsFromAbundance must be no, scaledTPM, or lengthScaledTPM")
}

manifest <- read.delim(manifest_path, header = TRUE, sep = "\t", quote = "", comment.char = "", check.names = FALSE, stringsAsFactors = FALSE)
if (!identical(names(manifest), c("sample_id", "ctab_file")) || nrow(manifest) < 1L) {
    stop("Sample manifest must contain sample_id and ctab_file columns and at least one row")
}
if (anyNA(manifest) || any(manifest$sample_id == "") || anyDuplicated(manifest$sample_id)) {
    stop("Sample identifiers must be non-empty and unique")
}
if (any(!file.exists(manifest$ctab_file))) stop("One or more StringTie tables do not exist")

tx2gene <- read.delim(tx2gene_path, header = TRUE, sep = "\t", quote = "", comment.char = "", check.names = FALSE, stringsAsFactors = FALSE)
if (!identical(names(tx2gene), c("transcript_id", "gene_id")) || nrow(tx2gene) < 1L || anyNA(tx2gene) || any(tx2gene == "") || anyDuplicated(tx2gene$transcript_id)) {
    stop("tx2gene must contain unique, non-empty transcript_id and gene_id columns")
}

extract_gtf_attribute <- function(attributes, key) {
    pattern <- paste0("(?:^|;[[:space:]]*)", key, "[[:space:]]+\"([^\"]+)\"")
    match <- regexec(pattern, attributes, perl = TRUE)
    values <- regmatches(attributes, match)[[1L]]
    if (length(values) == 0L) NA_character_ else values[[2L]]
}

gtf_lines <- readLines(reference_gtf_path, warn = FALSE, encoding = "UTF-8")
gtf_mapping <- character()
for (line_number in seq_along(gtf_lines)) {
    line <- gtf_lines[[line_number]]
    if (line == "" || startsWith(line, "#")) next
    fields <- strsplit(line, "\t", fixed = TRUE)[[1L]]
    if (length(fields) != 9L) {
        stop(paste("reference GTF must contain exactly 9 tab-separated fields at line", line_number))
    }
    transcript <- extract_gtf_attribute(fields[[9L]], "transcript_id")
    if (is.na(transcript)) next
    gene <- extract_gtf_attribute(fields[[9L]], "gene_id")
    if (is.na(gene) || transcript == "" || gene == "") {
        stop(paste("reference GTF transcript record lacks gene_id/transcript_id at line", line_number))
    }
    if (transcript %in% names(gtf_mapping) && unname(gtf_mapping[[transcript]]) != gene) {
        stop(paste("reference GTF maps transcript", transcript, "to multiple genes"))
    }
    gtf_mapping[[transcript]] <- gene
}
if (length(gtf_mapping) < 1L) stop("reference GTF contains no transcript_id to gene_id assignments")
unknown <- setdiff(tx2gene$transcript_id, names(gtf_mapping))
if (length(unknown) > 0L) {
    stop(paste("tx2gene contains transcript(s) absent from reference GTF:", paste(head(unknown, 5L), collapse = ", ")))
}
expected_genes <- unname(gtf_mapping[tx2gene$transcript_id])
contradictions <- which(expected_genes != tx2gene$gene_id)
if (length(contradictions) > 0L) {
    index <- contradictions[[1L]]
    stop(paste(
        "tx2gene contradicts reference GTF for transcript", tx2gene$transcript_id[[index]],
        ": expected gene", expected_genes[[index]], "received", tx2gene$gene_id[[index]]
    ))
}

files <- manifest$ctab_file
names(files) <- manifest$sample_id
txi <- tximport::tximport(
    files = files,
    type = "stringtie",
    tx2gene = tx2gene,
    countsFromAbundance = counts_from_abundance,
    readLength = read_length,
    txOut = FALSE,
    dropInfReps = TRUE
)

matrices <- list(counts = txi$counts, abundance = txi$abundance, length = txi$length)
expected_rows <- rownames(txi$counts)
for (matrix_name in names(matrices)) {
    matrix_value <- matrices[[matrix_name]]
    if (!is.matrix(matrix_value) || !identical(colnames(matrix_value), manifest$sample_id)) stop(paste("Invalid sample columns for", matrix_name))
    if (!identical(rownames(matrix_value), expected_rows) || length(expected_rows) < 1L) stop(paste("Invalid gene rows for", matrix_name))
    if (any(!is.finite(matrix_value)) || any(matrix_value < 0)) stop(paste("Invalid numeric values for", matrix_name))
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
        "Estimated count-scale values reconstructed from StringTie coverage as coverage *",
        "transcript length / explicit read length, then summarized to genes; these are not raw counts.",
        "Use the saved tximport object with a tximport-aware DGE constructor."
    ),
    scaledTPM = "Count-scale values derived from StringTie FPKM abundance and scaled to library size; these are not raw counts. Do not use a length offset.",
    lengthScaledTPM = "Count-scale values derived from StringTie FPKM abundance, average transcript length, and library size; these are not raw counts. Do not use a length offset."
)

metadata <- list(
    tool = "tximport",
    tximport_version = as.character(utils::packageVersion("tximport")),
    r_version = R.version.string,
    quantifier = "stringtie",
    aggregation_level = "gene",
    abundance_units = "FPKM",
    read_length = read_length,
    coverage_to_count_formula = "coverage * transcript_length / read_length",
    counts_from_abundance = counts_from_abundance,
    counts_semantics = semantics,
    raw_counts = FALSE,
    downstream_offset = if (counts_from_abundance == "no") "required_by_tximport_aware_DGE" else "must_not_be_used",
    sample_ids = I(manifest$sample_id),
    sample_manifest = normalizePath(manifest_path, winslash = "/", mustWork = TRUE),
    sample_manifest_md5 = unname(as.character(tools::md5sum(manifest_path))),
    ctab_files = I(normalizePath(manifest$ctab_file, winslash = "/", mustWork = TRUE)),
    ctab_md5 = I(unname(as.character(tools::md5sum(manifest$ctab_file)))),
    tx2gene = normalizePath(tx2gene_path, winslash = "/", mustWork = TRUE),
    tx2gene_md5 = unname(as.character(tools::md5sum(tx2gene_path))),
    reference_gtf = normalizePath(reference_gtf_path, winslash = "/", mustWork = TRUE),
    reference_gtf_md5 = unname(as.character(tools::md5sum(reference_gtf_path))),
    reference_gtf_sha256 = unname(as.character(tools::sha256sum(reference_gtf_path))),
    gene_count = nrow(txi$counts),
    transcript_mapping_count = nrow(tx2gene),
    inferential_replicates = "not_available_for_stringtie_ctab"
)
jsonlite::write_json(metadata, metadata_path, auto_unbox = TRUE, pretty = TRUE)
