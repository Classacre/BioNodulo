# Workflow templates

BioNodulo includes 23 bundled workflow templates. Open one in the editor,
review its input files and runtime requirements, then run it in a configured
environment. Small smoke-test inputs do not establish scientific validation.

| Template | Workflow |
| --- | --- |
| [Genome Assembly](../templates/assembly_pipeline.json) | De novo assembly and quality assessment |
| [Biopython Analysis Pipeline](../templates/biopython_analysis_pipeline.json) | Sequence parsing, statistics, translation and local BLAST |
| [ChIP-Seq Pipeline](../templates/chip_seq_pipeline.json) | Chromatin immunoprecipitation sequencing analysis |
| [CRISPR Editing and Screen Analysis](../templates/crispr_editing_pipeline.json) | Guide design and candidate off-target analysis |
| [DESeq2 Differential Expression](../templates/deseq2_differential_expression.json) | Differential expression with DESeq2 |
| [Transcript Quantification](../templates/differential_expression.json) | Transcript quantification with Salmon and Kallisto |
| [FASTQ QC Pipeline](../templates/fastq_qc_pipeline.json) | Read quality control with FastQC |
| [ONT Long-Read Sequencing](../templates/long_read_ont_pipeline.json) | Oxford Nanopore basecalling and downstream analysis |
| [Metabolomics LC-MS Workflow](../templates/metabolomics_lcms_pipeline.json) | Multi-sample LC-MS analysis |
| [Metagenomics Profiling](../templates/metagenomics_pipeline.json) | Taxonomic and functional profiling |
| [Pangenomics Graph QC and Visualization](../templates/pangenomics_graph_pipeline.json) | Validate and visualize a pangenome graph |
| [Phylogenetics Pipeline](../templates/phylogenetics_pipeline.json) | Multiple sequence alignment and tree construction |
| [Protein Structure Database Workflow](../templates/protein_structure_database_workflow.json) | Search UniProt for reviewed protein structure records |
| [Proteomics Sage-Percolator Search](../templates/proteomics_sage_percolator_pipeline.json) | Database search and PIN validation |
| [R Visualization Pipeline](../templates/r_visualization_pipeline.json) | Plot workflow results with R and ggplot2 |
| [RNA-Seq Pipeline](../templates/rna_seq_pipeline.json) | RNA sequencing analysis from reads to counts |
| [ROBUST Designer](../templates/robust_designer.json) | Multi-target mRNA design campaign |
| [Single Cell RNA-Seq](../templates/single_cell_pipeline.json) | 10x single-cell analysis with Cell Ranger |
| [Spatial Transcriptomics QC and Clustering](../templates/spatial_transcriptomics_qc_clustering.json) | Quality control and clustering of spatial data |
| [Synthetic Biology Design and Simulation](../templates/synthetic_biology_design_simulation.json) | SBOL design import and COPASI simulation |
| [Variant Calling Pipeline](../templates/variant_calling_pipeline.json) | Germline variant calling with GATK |
| [WGBS Methylation Profiling](../templates/wgbs_methylation_pipeline.json) | Whole-genome bisulfite sequencing analysis |
| [WGS Variant Pipeline](../templates/wgs_variant_pipeline.json) | Whole-genome variant calling with BWA |

Definitions and PNG thumbnails live in `templates/`; fixture data lives in
`templates/data/`. The template tests check graph
structure and reference consistency. See the [node verification guide](testing/node-verification.md)
for real-tool checks and the [script index](../scripts/README.md) for maintenance.
