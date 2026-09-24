# Adaptability note: alternative RNA-seq tool chains in the registry (Aim B)

Date: 2026-09-13; source-contract correction: 2026-09-19.
Companion tests: `tests/test_adaptability_chains.py`, `tests/test_semantic_all_nodes.py`.

## Alternative tool chains that exist today

The node registry (`bionodulo/nodes/node_index.json`, 979 entries) contains these
RNA-seq quantification/alignment adapters (categories from
`bionodulo/nodes/node_metadata.json`):

| Family | Exact node type ids | Metadata category |
|---|---|---|
| HISAT2 (splice-aware aligner) | `hisat2_align`, `hisat2_build` | alignment |
| STAR (splice-aware aligner) | `star_align`, `star_index`, `starsolo_count` | alignment |
| Bowtie2 (end-to-end/local aligner) | `bowtie2`, `bowtie2_align`, `bowtie2_build`, `bowtie2_inspect` | alignment |
| BWA (MEM aligners) | `bwa`, `bwa_index`, `bwa_index_dir`, `bwa_mem`, `bwa_mem2`, `bwa_mem2_idx`, `bwameth` | alignment |
| Salmon (alignment-free quantifier) | `salmon_index`, `salmon_quant` | rna_seq |
| Kallisto (pseudoaligner) | `kallisto_index`, `kallisto_quant` | rna_seq |
| Counting | `featurecounts` | rna_seq |

No RSEM nodes exist in the registry (grep for `rsem` returns nothing).

The registry also contains SAM/BAM converters with contracts
(`samtools_view`, `sam_to_bam`, `samtools_sort`) and the counting sink
`featurecounts`. Converter selection depends on the actual producer format:
`star_align` already requests `--outSAMtype BAM SortedByCoordinate` and must
not be modeled as unsorted SAM.

## What the test covers

`tests/test_adaptability_chains.py` builds two structurally different chains
over the same contract dimensions (sort_order, strandedness,
normalization_state), wired with the real port names of the registered node
classes. This calls the semantic checker only: no reads are aligned, no
counts are generated, and no scientific ground-truth output is compared.
These two structural graphs do not validate the proposal's three execution
chains (STAR + featureCounts, HISAT2 + tximport, and Salmon):

- **Chain A (HISAT2):** `unstranded_library_reads -> hisat2_align -> samtools_view -> samtools_sort -> featurecounts`
- **Chain B (STAR sorted BAM):** `unstranded_library_reads -> star_align -> featurecounts`

Assertions:

1. Both chains pass `check_workflow_semantics` with zero violations when
   configured correctly (`strand_specificity=0` on an unstranded library), and
   the same dimensions are tracked to the same sink states
   (`coordinate` sort, `unstranded` strandedness, `raw_counts`).
2. The documented silent-halving misconfiguration [E8][E11] —
   `strand_specificity=2` (reverse) counting an unstranded library — produces
   one strandedness violation (observed `unstranded`, required
   `reverse`, blamed on each chain's actual producer and the counting consumer)
   in **both** chains, with no
   auto-repair suggestion (a known-wrong strandedness is never coerced [E57]).

Chain B's STAR head and the synthetic unstranded-library producer are not in
the bundled contract JSON yet, so the test composes them with extra
`NodeSemanticContract` entries (the library composition pattern from
`tests/test_semantic_contracts.py`); the STAR contract is cross-validated
against `STARAlignNode`'s real ports (reads/index in, alignment out), declared
BAM type, and rendered coordinate-sorted BAM flags. HISAT2's test contract
also replaces the bundled unknown strandedness with propagation from the
synthetic library producer; this is an explicit fixture assumption.

## What the proposal's additional chains would need

The **HISAT2 + tximport chain** is not the HISAT2 + featureCounts fixture
above. HISAT2 emits SAM, while tximport imports supported quantifier output.
It needs an explicit quantification stage, a tximport adapter, transcript-to-
gene mapping when aggregating genes, and contracts for abundance, estimated
counts, and effective lengths. The existing StringTie adapter does not
request the Ballgown output tables used by tximport's StringTie importer.

The **Salmon chain** has registered quantifier adapters, but this test never
executes them. It still needs a complete graph with matching reference and
annotation identifiers, explicit transcript/gene aggregation and length
correction semantics, and comparisons against independently verified outputs.
All three chains need actual pinned-binary execution on shared fixtures and
a recorded graph-edit versus script-edit measurement before the proposal's
adaptability evaluation can be claimed complete.

## Conclusion for Aim B

The two structural fixtures exercise the same semantic checker across
different graph shapes and catch the same planted strandedness mismatch.
They provide limited contract-propagation evidence. They do not demonstrate
installed tools, runnable end-to-end workflows, biological correctness,
FracFixR/STE migration, or the proposal's three-chain adaptability evaluation.
