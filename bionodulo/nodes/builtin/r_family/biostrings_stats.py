"""Biostrings 2.78.0 reverse-complement and six-frame translation contract."""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from .adapter import R_VERSION, PreparedRScriptNode, path_value, r_string, validate_choice, validate_int


BIOSTRINGS_VERSION = "2.78.0"
BIOSTRINGS_COMMIT = "eda5d667ad05a73336d8c83a71f670198433232f"
GENETIC_CODES = {
    "Standard": "1",
    "Bacterial": "11",
    "Vertebrate Mitochondrial": "2",
    "Yeast Mitochondrial": "3",
}


class BiostringsStatsNode(PreparedRScriptNode):
    """Generate documented Biostrings sequence transformations and candidate segments."""

    NODE_ID = "r_biostrings_stats"
    DISPLAY_NAME = "Biostrings Stats"
    CATEGORY = "sequence"
    DESCRIPTION = (
        "Create reverse complements, six-frame translations, and stop-delimited "
        "candidate peptide segments with source-pinned Biostrings."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "R",
        "Biostrings",
        "reverse complement",
        "six-frame translation",
        "candidate ORF",
    ]
    RETURN_TYPES = ("CSV", "FASTA", "FASTA")
    RETURN_NAMES = ("orf_table_csv", "revcomp_fasta", "six_frame_fasta")
    REQUIRED_R_PACKAGES = ["Biostrings"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-biostrings"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "r-base": R_VERSION,
        "bioconductor-biostrings": BIOSTRINGS_VERSION,
    }
    VERSION = BIOSTRINGS_VERSION
    GIT_URL = "https://git.bioconductor.org/packages/Biostrings"
    GIT_COMMIT = BIOSTRINGS_COMMIT
    DOCUMENTATION_URL = "https://bioconductor.org/packages/3.22/bioc/html/Biostrings.html"
    UPSTREAM_SOURCE = (
        "R/GENETIC_CODE.R; R/reverseComplement.R; R/translate.R; "
        "man/GENETIC_CODE.Rd; man/translate.Rd; man/XStringSet-io.Rd"
    )
    CITATION_DOIS = ["10.18129/B9.bioc.Biostrings"]
    CITATION_URLS = ["https://doi.org/10.18129/B9.bioc.Biostrings"]
    CITATION_TEXT = "Biostrings provides memory-efficient biological string containers and operations."
    REQUIRED_PATH_INPUTS = ("input_fasta",)
    OUTPUT_FILENAMES = ("orf_table.csv", "reverse_complement.fasta", "six_frame_translation.fasta")
    SCRIPT_FILENAME = "biostrings.R"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FILE", {"description": "DNA FASTA readable by readDNAStringSet"}),
            },
            "optional": {
                "min_orf_length": (
                    "INT",
                    {
                        "default": 100,
                        "min": 30,
                        "max": 100000,
                        "description": "Minimum stop-delimited peptide length in amino acids",
                    },
                ),
                "genetic_code": (
                    "STRING",
                    {"default": "Standard", "options": list(GENETIC_CODES)},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_int(
            inputs.get("min_orf_length", 100),
            "min_orf_length",
            minimum=30,
            maximum=100000,
        )
        if validation is not True:
            return validation
        return validate_choice(
            inputs.get("genetic_code", "Standard"),
            "genetic_code",
            tuple(GENETIC_CODES),
        )

    @classmethod
    def build_script(cls, inputs: dict[str, Any], outputs: list[Path]) -> str:
        genetic_code = GENETIC_CODES[str(inputs.get("genetic_code", "Standard"))]
        return textwrap.dedent(
            f"""\
            if (!requireNamespace("Biostrings", quietly = TRUE)) stop("Missing required R package: Biostrings")
            suppressPackageStartupMessages(library(Biostrings))

            dna <- readDNAStringSet({r_string(path_value(inputs.get('input_fasta')))}, format = "fasta")
            if (length(dna) == 0) stop("Input FASTA contains no DNA sequences.")
            sequence_names <- names(dna)
            missing_names <- is.na(sequence_names) | sequence_names == ""
            sequence_names[missing_names] <- paste0("sequence_", which(missing_names))
            names(dna) <- sequence_names

            reverse_complements <- reverseComplement(dna)
            writeXStringSet(reverse_complements, {r_string(outputs[1])}, format = "fasta")

            genetic_code <- getGeneticCode({r_string(genetic_code)})
            translated_sequences <- character()
            translated_names <- character()
            candidate_rows <- list()
            candidate_index <- 1L

            for (sequence_index in seq_along(dna)) {{
                forward_sequence <- dna[[sequence_index]]
                sequence_id <- names(dna)[sequence_index]
                strand_sequences <- list("+" = forward_sequence, "-" = reverseComplement(forward_sequence))

                for (strand_name in names(strand_sequences)) {{
                    strand_sequence <- strand_sequences[[strand_name]]
                    for (frame_offset in 0:2) {{
                        usable_length <- width(strand_sequence) - frame_offset
                        usable_length <- usable_length - (usable_length %% 3L)
                        if (usable_length <= 0) next

                        shifted <- subseq(strand_sequence, start = frame_offset + 1L, width = usable_length)
                        amino_acids <- translate(
                            shifted,
                            genetic.code = genetic_code,
                            no.init.codon = TRUE,
                            if.fuzzy.codon = "X"
                        )
                        amino_text <- as.character(amino_acids)
                        frame_name <- paste0(
                            sequence_id,
                            if (strand_name == "+") "_frame" else "_rev_frame",
                            frame_offset + 1L
                        )
                        translated_sequences <- c(translated_sequences, amino_text)
                        translated_names <- c(translated_names, frame_name)

                        peptides <- strsplit(amino_text, "*", fixed = TRUE)[[1]]
                        peptide_start <- 1L
                        for (peptide in peptides) {{
                            peptide_length <- nchar(peptide)
                            if (peptide_length >= {int(inputs.get('min_orf_length', 100))}) {{
                                candidate_rows[[candidate_index]] <- data.frame(
                                    sequence_id = sequence_id,
                                    strand = strand_name,
                                    frame = frame_offset + 1L,
                                    start = peptide_start,
                                    end = peptide_start + peptide_length - 1L,
                                    length_aa = peptide_length,
                                    stringsAsFactors = FALSE
                                )
                                candidate_index <- candidate_index + 1L
                            }}
                            peptide_start <- peptide_start + peptide_length + 1L
                        }}
                    }}
                }}
            }}

            six_frame <- AAStringSet(translated_sequences)
            if (length(six_frame) == 0) stop("No complete codon frame could be translated from the input FASTA.")
            names(six_frame) <- translated_names
            writeXStringSet(six_frame, {r_string(outputs[2])}, format = "fasta")

            if (length(candidate_rows) == 0) {{
                candidate_table <- data.frame(
                    sequence_id = character(),
                    strand = character(),
                    frame = integer(),
                    start = integer(),
                    end = integer(),
                    length_aa = integer(),
                    stringsAsFactors = FALSE
                )
            }} else {{
                candidate_table <- do.call(rbind, candidate_rows)
            }}
            write.csv(candidate_table, {r_string(outputs[0])}, row.names = FALSE)
            """
        )
