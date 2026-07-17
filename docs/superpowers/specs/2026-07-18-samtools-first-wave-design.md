# Samtools First-Wave Rebuild Design

**Status:** Approved by the user's direction to simplify and continue.

## Goal

Replace the seven Samtools nodes used by the variant templates with small,
documentation-backed runtime modules that behave identically in the local app
and the cloud worker.

The first wave is:

1. `samtools_view`
2. `samtools_collate`
3. `samtools_fixmate`
4. `samtools_sort`
5. `samtools_markdup`
6. `samtools_index`
7. `samtools_flagstat`

All seven remain quarantined until command, output, template, lightweight local,
and cloud canary gates pass.

## Why The Previous Direction Is Superseded

The foundation branch added a large contract and environment-verification layer
without producing a runtime `NodeSpec`. It does not fix the demonstrated
failures: wrong ports, incorrect flags, undeclared sidecars, conditional outputs,
or template races.

This wave therefore does not add a generic Git source verifier, another Pixi
parser, a new workflow executor, or a Galaxy runtime. The reviewed 943-ID queue
is retained as inventory. The existing Pixi manifest flow and the existing
`CommandNode` executor remain the local and cloud runtime.

The old source-lock implementation plan is superseded by this design. Pinned
upstream identity is recorded directly on the family adapter and checked in
focused tests.

The Pixi package constraint for Samtools is exact `1.23.1`. A minimum-version
range is not sufficient for a source-backed argv contract because local and
cloud solvers could otherwise select different Samtools releases.

## Chosen Architecture

Use one shared `SamtoolsCommandNode` adapter and one small module per operation.
Each operation module owns only its ports, parameters, fixed outputs, and argv
renderer. The adapter owns shared Samtools metadata, output planning, source
identity, and common validation.

The existing `bionodulo/nodes/builtin/samtools.py` remains a temporary legacy
module for the other 20 quarantined Samtools operations. The seven rebuilt
classes are removed from it so the registry has one owner per stable ID. The
legacy module shrinks as later waves migrate.

Two small runtime capabilities are added to `CommandNode`:

- a pre-execution hook for deterministic artifact preparation;
- a declared stdout output index so tools such as `samtools flagstat` can write
  an artifact without shell redirection.

These hooks directly support output collection and are covered by runtime tests.
They are not a new execution framework.

## Indexed BAM Semantics

`samtools_index` produces two declared outputs in its own node directory:

- `indexed_bam`: `BAM`, a hard-linked BAM copy when possible;
- `bai`: `BAI`, named `indexed_bam.bam.bai` beside the BAM.

The index command is fixed to BAI in this wave. CSI remains quarantined because
it changes the output type and compatibility contract.

Each indexed consumer has two explicit inputs: the BAM and its BAI. Templates
route the BAM from `samtools_index.indexed_bam` and the index from
`samtools_index.bai`, rather than routing the BAM directly from markdup or sort.
This makes the index node an actual DAG dependency, removes the cloud race, and
keeps the sidecar visible to workflow serialization and future artifact staging.

The existing backend already supports scalar `BAM` and `BAI` ports. A nominal
`BAM_INDEXED` path or dictionary bundle is deliberately not introduced in this
wave because current cache, API, output, and catalog code still model one path
per port.

The cloud worker runs the complete workflow in one workspace, so the BAM and
BAI remain colocated for GATK, FreeBayes, Manta, Delly, and deepTools. Local
execution uses the same executor and paths. The in-process coverage plot passes
its explicit index path to pysam rather than relying on discovery.

The affected official templates are `variant_calling_pipeline.json`,
`wgs_variant_pipeline.json`, and `chip_seq_pipeline.json`. RNA-seq uses only
sequential readers in its current graph and does not need an index edge.

## First-Wave Contracts

### View

- Input: `alignment` file, limited to SAM or BAM in this release.
- Parameters: `threads=4`, optional `require_all_flags`, optional
  `exclude_any_flags`.
- Output: BAM.
- Semantics: `-f` requires all specified bits; `-F` excludes reads with any
  specified bit.

### Collate

- Input: BAM.
- Parameters: `threads=4`.
- Output: name-collated BAM.
- Temporary prefix is internal to the node output directory.

### Fixmate

- Input: name-collated BAM.
- Parameters: `threads=4`, `add_markdup_tags=false`,
  `remove_secondary_unmapped=false`.
- Output: BAM.
- Templates set `add_markdup_tags=true` explicitly because markdup needs `ms`
  tags; the node default matches upstream.

### Sort

- Input: SAM or BAM file.
- Parameters: `threads=4`, `memory_per_thread="768M"`.
- Output: coordinate-sorted BAM.
- Name/minimiser/tag sort modes are not exposed in this wave.

### Markdup

- Input: coordinate-sorted BAM prepared by fixmate with `-m`.
- Parameters: `threads=4`, `remove_duplicates=false`,
  `mark_supplementary=false`, `optical_distance=0`, optional
  `read_coords`, and `clear_existing=false`.
- Outputs: marked BAM and plain-text duplicate statistics.
- `read_coords` is accepted only when `optical_distance` is positive.

### Index

- Input: coordinate-sorted BAM.
- Parameters: `threads=2`.
- Outputs: indexed BAM bundle primary plus BAI sidecar.
- Fixed BAI mode; CSI is a later separate contract.

### Flagstat

- Input: BAM.
- Parameters: `threads=2`.
- Output: plain-text report captured from stdout.
- JSON and TSV become separate contracts later rather than changing one port's
  type at runtime.

## Evidence

Final authority is Samtools 1.23.1 at Git commit
`6efb9b6da35224cf804921dedecf9fb8f411365d`, annotated tag object
`4ac78a7e9938dbef3c6f97d549758feceb0252db`.

Command ownership is confirmed in `bamtk.c`; implementation files are
`sam_view.c`, `bamshuf.c`, `bam_mate.c`, `bam_sort.c`, `bam_markdup.c`,
`bam_index.c`, and `bam_stat.c`. The corresponding 1.23.1 manpages are the
parameter and output authority. Tools-IUC commit
`8eb66da1f6f16fde92688ee6c500d2bcdc924a47` is secondary evidence only because
its shared macro currently pins Samtools 1.22.

## Verification

Local verification is intentionally light:

- exact argv tests for defaults and supported options;
- port/default/output-path tests;
- fake-context execution tests for stdout collection and indexed-BAM staging;
- registry and generated metadata freshness;
- template DAG tests proving indexed consumers depend on the index node;
- workflow validation and targeted executor tests.

No large bioinformatics installation or dataset runs on this host. After local
tests pass, a tiny synthetic SAM/BAM canary runs once on the disposable North
American cloud worker. Release requires matching local and cloud output hashes.
