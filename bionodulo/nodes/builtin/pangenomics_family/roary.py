"""Focused owner for ``roary``."""

from bionodulo.nodes.builtin._annotation_sequence_adapter import _RoaryContract


class RoaryNode(_RoaryContract):
    NODE_ID = "roary"
    OUTPUT_NAME_BY_BASENAME = {
        "summary_statistics.txt": "summary_statistics",
        "core_gene_alignment.aln": "core_gene_alignment",
        "gene_presence_absence.csv": "gene_presence_absence",
        "accessory_binary_genes.fa": "accessory_binary_genes",
        "accessory_binary_genes.fa.newick": "accessory_binary_genes_newick",
        "accessory_graph.dot": "accessory_graph",
        "accessory.header.embl": "accessory_header_embl",
        "accessory.tab": "accessory_table",
        "blast_identity_frequency.Rtab": "blast_identity_frequency",
        "clustered_proteins": "clustered_proteins",
        "core_accessory_graph.dot": "core_accessory_graph",
        "core_accessory.header.embl": "core_accessory_embl",
        "core_accessory.tab": "core_accessory_table",
        "gene_presence_absence.Rtab": "gene_presence_absence_rtab",
        "number_of_conserved_genes.Rtab": "number_of_conserved_genes",
        "number_of_genes_in_pan_genome.Rtab": "number_of_genes_in_pan_genome",
        "number_of_new_genes.Rtab": "number_of_new_genes",
        "number_of_unique_genes.Rtab": "number_of_unique_genes",
        "pan_genome_reference.fa": "pan_genome_reference",
    }
