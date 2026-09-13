# Round-trip fidelity report

Generated: 2026-09-13T06:20:44.270259+00:00  
Templates: 23  
Metric: f_target is the geometric mean of node, edge, parameter,
label, and annotation preservation per target (dossier section 5.3).

| Template | snakemake | nextflow | galaxy | cwl |
| --- | --- | --- | --- | --- |
| assembly_pipeline (19n) | 0.0 | 0.0 | 0.0 | 0.0 |
| biopython_analysis_pipeline (15n) | 1.0 | 1.0 | 1.0 | 1.0 |
| chip_seq_pipeline (27n) | 0.0 | 0.0 | 0.0 | 0.0 |
| crispr_editing_pipeline (17n) | 1.0 | 1.0 | 1.0 | 1.0 |
| deseq2_differential_expression (20n) | 1.0 | 1.0 | 1.0 | 0.0 |
| differential_expression (14n) | 0.0 | 0.0 | 0.0 | 0.0 |
| fastq_qc_pipeline (10n) | 0.0 | 0.0 | 0.0 | 0.0 |
| long_read_ont_pipeline (16n) | 1.0 | 1.0 | 1.0 | 1.0 |
| metabolomics_lcms_pipeline (6n) | 1.0 | 1.0 | 1.0 | 1.0 |
| metagenomics_pipeline (31n) | 0.0 | 0.0 | 0.0 | 0.0 |
| pangenomics_graph_pipeline (7n) | 1.0 | 1.0 | 1.0 | 1.0 |
| phylogenetics_pipeline (9n) | 0.0 | 0.0 | 0.0 | 0.0 |
| protein_structure_database_workflow (9n) | 1.0 | 1.0 | 1.0 | 1.0 |
| proteomics_sage_percolator_pipeline (8n) | 1.0 | 1.0 | 1.0 | 1.0 |
| r_visualization_pipeline (11n) | 1.0 | 1.0 | 1.0 | 1.0 |
| rna_seq_pipeline (22n) | 0.0 | 0.0 | 0.0 | 0.0 |
| robust_designer (43n) | 1.0 | 1.0 | 1.0 | 1.0 |
| single_cell_pipeline (12n) | 1.0 | 1.0 | 1.0 | 1.0 |
| spatial_transcriptomics_qc_clustering (6n) | 1.0 | 1.0 | 1.0 | 1.0 |
| synthetic_biology_design_simulation (5n) | 1.0 | 1.0 | 1.0 | 1.0 |
| variant_calling_pipeline (29n) | 0.0 | 0.0 | 0.0 | 0.0 |
| wgbs_methylation_pipeline (15n) | 0.0 | 0.0 | 0.0 | 0.0 |
| wgs_variant_pipeline (29n) | 0.0 | 0.0 | 0.0 | 0.0 |

## Per-target averages

| Target | mean f_target | idempotent |
| --- | --- | --- |
| snakemake | 0.5652 | 13/23 |
| nextflow | 0.5652 | 20/23 |
| galaxy | 0.5652 | 23/23 |
| cwl | 0.5217 | 23/23 |
