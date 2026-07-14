"""r — sequence node(s). One tool per file (extracted from r_bioinformatics.py)."""
from __future__ import annotations
import textwrap
from pathlib import Path
from typing import Any
from bionodulo.nodes.base import BaseNode


class BiostringsStatsNode(BaseNode):
    """Advanced sequence analysis using Biostrings (ORFs, complements, translation)."""
    NODE_ID = 'r_biostrings_stats'
    DISPLAY_NAME = 'Biostrings Stats'
    REQUIRED_CONDA_PACKAGES = ['r-base', 'bioconductor-biostrings', 'r-readr']
    CATEGORY = 'sequence'
    DESCRIPTION = 'Advanced sequence stats with Biostrings: ORF finding, reverse complement, 6-frame translation'
    RETURN_TYPES = ('FILE', 'FILE', 'FILE')
    RETURN_NAMES = ('orf_table_csv', 'revcomp_fasta', 'six_frame_fasta')
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ['Rscript']
    REQUIRED_R_PACKAGES = ['Biostrings', 'readr']

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {'required': {'input_fasta': ('FILE', {'label': 'DNA FASTA'})}, 'optional': {'min_orf_length': ('INT', {'default': 100, 'min': 30, 'max': 1000, 'step': 10, 'label': 'Min ORF length (aa)', 'advanced': True}), 'genetic_code': ('STRING', {'default': 'Standard', 'options': ['Standard', 'Bacterial', 'Vertebrate Mitochondrial', 'Yeast Mitochondrial'], 'label': 'Genetic code', 'advanced': True})}}

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop('context', None)
        output_dir = Path(getattr(context, 'node_dir', '.') if context else '.')
        out_dir = output_dir / self.NODE_ID
        out_dir.mkdir(parents=True, exist_ok=True)
        input_fasta = kwargs['input_fasta']
        min_orf = kwargs.get('min_orf_length', 100)
        genetic_code = kwargs.get('genetic_code', 'Standard')
        code_map = {'Standard': '1', 'Bacterial': '11', 'Vertebrate Mitochondrial': '2', 'Yeast Mitochondrial': '3'}
        code_num = code_map.get(genetic_code, '1')
        orf_csv = out_dir / 'orf_table.csv'
        revcomp_fasta = out_dir / 'reverse_complement.fasta'
        sixframe_fasta = out_dir / 'six_frame_translation.fasta'
        script = textwrap.dedent(f'''            if (!requireNamespace("Biostrings", quietly = TRUE)) stop("Package 'Biostrings' is required but not installed. Install it with: BiocManager::install('Biostrings')")\n            if (!requireNamespace("readr", quietly = TRUE)) stop("Package 'readr' is required but not installed. Install it with: install.packages('readr')")\n            library(Biostrings)\n            library(readr)\n\n            dna <- readDNAStringSet("{Path(input_fasta).as_posix()}")\n\n            # Reverse complement\n            revcomp <- reverseComplement(dna)\n            writeXStringSet(revcomp, "{revcomp_fasta.as_posix()}")\n\n            # ORF finding per sequence\n            orf_results <- data.frame(\n                sequence_id = character(),\n                frame = integer(),\n                start = integer(),\n                end = integer(),\n                length_aa = integer(),\n                stringsAsFactors = FALSE\n            )\n\n            for (i in seq_along(dna)) {{\n                seq <- dna[[i]]\n                seq_name <- names(dna)[i]\n                for (frame in 0:2) {{\n                    shifted <- subseq(seq, start = frame + 1)\n                    aa <- translate(shifted, genetic.code = getGeneticCode("{code_num}"), if.fuzzy.codon = "X")\n                    # Split on stop codons and find ORFs\n                    aa_str <- as.character(aa)\n                    peptides <- strsplit(aa_str, "\\\\*")[[1]]\n                    pos <- 1\n                    for (p in peptides) {{\n                        if (nchar(p) >= {min_orf}) {{\n                            orf_results <- rbind(orf_results, data.frame(\n                                sequence_id = seq_name,\n                                frame = frame + 1,\n                                start = pos,\n                                end = pos + nchar(p) - 1,\n                                length_aa = nchar(p),\n                                stringsAsFactors = FALSE\n                            ))\n                        }}\n                        pos <- pos + nchar(p) + 1\n                    }}\n                }}\n            }}\n\n            write.csv(orf_results, "{orf_csv.as_posix()}", row.names = FALSE)\n\n            # Six-frame translation\n            six_frame <- AAStringSet()\n            six_frame_names <- character()\n            for (i in seq_along(dna)) {{\n                seq <- dna[[i]]\n                seq_name <- names(dna)[i]\n                for (frame in 0:2) {{\n                    shifted <- subseq(seq, start = frame + 1)\n                    aa <- translate(shifted, genetic.code = getGeneticCode("{code_num}"), if.fuzzy.codon = "X")\n                    six_frame <- c(six_frame, AAStringSet(aa))\n                    six_frame_names <- c(six_frame_names, paste0(seq_name, "_frame", frame + 1))\n                }}\n                rev_seq <- reverseComplement(seq)\n                for (frame in 0:2) {{\n                    shifted <- subseq(rev_seq, start = frame + 1)\n                    aa <- translate(shifted, genetic.code = getGeneticCode("{code_num}"), if.fuzzy.codon = "X")\n                    six_frame <- c(six_frame, AAStringSet(aa))\n                    six_frame_names <- c(six_frame_names, paste0(seq_name, "_rev_frame", frame + 1))\n                }}\n            }}\n            names(six_frame) <- six_frame_names\n            writeXStringSet(six_frame, "{sixframe_fasta.as_posix()}", format = "fasta")\n        ''')
        script_path = out_dir / 'biostrings.R'
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
            raise RuntimeError(f"Biostrings script failed: {result.get('stderr', '')}")
        return (str(orf_csv), str(revcomp_fasta), str(sixframe_fasta))
