# Adaptability note: alternative RNA-seq tool chains in the registry (Aim B)

Date: 2026-09-13. Branch: `phd/contract-typing`.
Companion tests: `tests/test_adaptability_chains.py`, `tests/test_semantic_all_nodes.py`.

## Alternative tool chains that exist today

The node registry (`bionodulo/nodes/node_index.json`, 979 entries) ships these
alternative RNA-seq quantification/alignment chains (categories from
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

Downstream of any aligner, the registry carries interchangeable SAM/BAM
converters with contracts (`samtools_view`, `sam_to_bam`, `samtools_sort`) and
the shared counting sink `featurecounts`.

## What the test covers

`tests/test_adaptability_chains.py` builds two structurally different chains
over the same contract dimensions (sort_order, strandedness,
normalization_state), wired with the real port names of the registered node
classes:

- **Chain A (HISAT2):** `unstranded_library_reads -> hisat2_align -> samtools_view -> samtools_sort -> featurecounts`
- **Chain B (STAR + Galaxy converter):** `unstranded_library_reads -> star_align -> sam_to_bam -> samtools_sort -> featurecounts`

Assertions:

1. Both chains pass `check_workflow_semantics` with zero violations when
   configured correctly (`strand_specificity=0` on an unstranded library), and
   the same dimensions are tracked to the same sink states
   (`coordinate` sort, `unstranded` strandedness, `raw_counts`).
2. The documented silent-halving misconfiguration [E8][E11] —
   `strand_specificity=2` (reverse) counting an unstranded library — produces
   one identical strandedness violation (observed `unstranded`, required
   `reverse`, blamed producer/consumer) in **both** chains, with no
   auto-repair suggestion (a known-wrong strandedness is never coerced [E57]).

Chain B's STAR head and the synthetic unstranded-library producer are not in
the bundled contract JSON yet, so the test composes them with extra
`NodeSemanticContract` entries (the library composition pattern from
`tests/test_semantic_contracts.py`); the STAR contract is cross-validated
against `STARAlignNode`'s real ports (reads/index in, alignment out).

## What a third chain would need

A **BWA/Bowtie2 chain** (`bwa_mem` or `bowtie2_align` -> `sam_to_bam` ->
`samtools_sort` -> `featurecounts`) needs only: one `NodeSemanticContract`
for the aligner (real ports: `reads` + `reference`/`index` in, `alignment`
out; guarantees `sort_order=unsorted`, strandedness `propagate`) composed
onto the library — the rest of the chain is already contracted. No checker
code changes. An **alignment-free chain** (`salmon_quant`/`kallisto_quant` ->
count-model consumers) would additionally need the `normalization_state`
dimension's values (tpm is already a member) attached to the quantifier
output ports; it replaces `featurecounts` rather than reusing it, since
transcript-level quantification emits abundances, not BAM counts.

## Conclusion for Aim B

The typed graph reconfigures across tool chains without new checker code:
swapping the HISAT2 head for a STAR head (plus a different SAM-to-BAM
converter) keeps the graph type-correct, propagates the same contract
dimensions to the same sink, and catches the same planted strandedness error
with identical blame. Adaptability holds as claimed: reconfiguration is a
graph edit plus (for not-yet-annotated heads) declarative contract entries —
never a change to the enforcement engine.
