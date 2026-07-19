suppressPackageStartupMessages({
  if (!requireNamespace("DSS", quietly = TRUE)) {
    stop("Package 'DSS' is required but not installed.", call. = FALSE)
  }
  if (!requireNamespace("readr", quietly = TRUE)) {
    stop("Package 'readr' is required but not installed.", call. = FALSE)
  }
})

args <- commandArgs(trailingOnly = TRUE)

read_arg <- function(name, default = NULL) {
  index <- match(name, args)
  if (is.na(index)) {
    return(default)
  }
  if (index == length(args)) {
    stop(paste("Missing value for", name), call. = FALSE)
  }
  args[[index + 1]]
}

has_flag <- function(name) {
  name %in% args
}

methylation_files <- strsplit(read_arg("--methylation-files", ""), ",", fixed = TRUE)[[1]]
methylation_files <- methylation_files[nzchar(methylation_files)]
sample_info_path <- read_arg("--sample-info")
condition_column <- read_arg("--condition-column", "condition")
sample_column <- read_arg("--sample-column", "sample")
threads <- as.integer(read_arg("--threads", "1"))
output_bed <- read_arg("--output-bed")
output_stats <- read_arg("--output-stats")
delta <- as.numeric(read_arg("--delta", "0.1"))
pvalue <- as.numeric(read_arg("--pvalue", "0.001"))
minlen <- as.integer(read_arg("--minlen", "50"))
mincg <- as.integer(read_arg("--mincg", "3"))
smoothing <- has_flag("--smoothing")

if (length(methylation_files) < 2) {
  stop("At least two methylation files are required.", call. = FALSE)
}
if (is.null(sample_info_path) || is.null(output_bed) || is.null(output_stats)) {
  stop("Missing required DSS DMR output or sample metadata argument.", call. = FALSE)
}
if (is.na(threads) || threads < 1) {
  stop("--threads must be a positive integer.", call. = FALSE)
}

samples <- readr::read_tsv(sample_info_path, show_col_types = FALSE, progress = FALSE)
required_columns <- c(sample_column, condition_column)
missing_columns <- setdiff(required_columns, colnames(samples))
if (length(missing_columns) > 0) {
  stop(paste("sample_info is missing columns:", paste(missing_columns, collapse = ", ")), call. = FALSE)
}

if (nrow(samples) != length(methylation_files)) {
  stop("sample_info row count must match methylation_files count.", call. = FALSE)
}

groups <- as.character(samples[[condition_column]])
sample_ids <- as.character(samples[[sample_column]])
if (anyNA(groups) || any(!nzchar(groups))) {
  stop("Condition values must be non-empty.", call. = FALSE)
}
if (anyNA(sample_ids) || any(!nzchar(sample_ids)) || anyDuplicated(sample_ids)) {
  stop("Sample IDs must be non-empty and unique.", call. = FALSE)
}
if (length(unique(groups)) != 2L) {
  stop("DSS DMR currently requires exactly two condition groups.", call. = FALSE)
}

read_methylation <- function(path) {
  table <- readr::read_tsv(path, show_col_types = FALSE, progress = FALSE)
  required <- c("chr", "pos", "N", "X")
  missing <- setdiff(required, colnames(table))
  if (length(missing) > 0) {
    stop(paste("Methylation file", path, "is missing columns:", paste(missing, collapse = ", ")), call. = FALSE)
  }
  data.frame(
    chr = table$chr,
    pos = as.integer(table$pos),
    N = as.integer(table$N),
    X = as.integer(table$X),
    stringsAsFactors = FALSE
  )
}

methylation <- lapply(methylation_files, read_methylation)
bsseq <- DSS::makeBSseqData(methylation, sampleNames = sample_ids)
test <- DSS::DMLtest(
  bsseq,
  group1 = which(groups == unique(groups)[1]),
  group2 = which(groups == unique(groups)[2]),
  smoothing = smoothing,
  ncores = threads
)
dmrs <- DSS::callDMR(test, delta = delta, p.threshold = pvalue, minlen = minlen, minCG = mincg)

dir.create(dirname(output_bed), recursive = TRUE, showWarnings = FALSE)
dir.create(dirname(output_stats), recursive = TRUE, showWarnings = FALSE)

if (is.null(dmrs) || nrow(dmrs) == 0) {
  writeLines(character(), output_bed)
  readr::write_tsv(
    data.frame(
      chr = character(),
      start = integer(),
      end = integer(),
      length = integer(),
      nCG = integer(),
      meanMethy1 = numeric(),
      meanMethy2 = numeric(),
      diff.Methy = numeric(),
      areaStat = numeric()
    ),
    output_stats
  )
} else {
  stats <- as.data.frame(dmrs)
  readr::write_tsv(stats, output_stats)
  bed <- data.frame(
    chr = stats$chr,
    start = pmax(0L, as.integer(stats$start) - 1L),
    end = as.integer(stats$end),
    name = paste0("DMR_", seq_len(nrow(stats))),
    score = pmin(1000L, pmax(0L, as.integer(round(abs(stats$diff.Methy) * 1000)))),
    stringsAsFactors = FALSE
  )
  readr::write_tsv(bed, output_bed, col_names = FALSE)
}
