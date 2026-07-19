"""Stable owner for ``amrfinderplus``."""

from .legacy import _AMRFinderPlusContract


class AMRFinderPlusNode(_AMRFinderPlusContract):
    NODE_ID = "amrfinderplus"
    OUTPUT_NAME_BY_BASENAME = {
        "amrfinderplus_report.tsv": "amrfinderplus_report",
        "mutation_all_report.tsv": "mutation_all_report",
        "amrfinderplus_protein_output.fasta": "protein_output",
        "amrfinderplus_nucleotide_output.fasta": "nucleotide_output",
        "amrfinderplus_flanking_sequence_output.fasta": "nucleotide_flank5_output",
    }
