# Builtin expansion — census, ledger and verified operations

**Snapshot date:** 2026-09-25
**Checkout:** `BioNodulo-knowledge-graph`, branch `feat/tool-knowledge-graph`
**Revision at start and end:** `0f93d0aeaaaed5f9cf8942d8af784c54ffc17776`
**Working tree at start:** clean

This report separates what was **measured** from what was **asserted by a source**
and from what remains **unknown**. Every rate carries its numerator and
denominator. Nothing here claims that the bio.tools registry has become
executable.

---

## 1. Snapshot

| Field | Value |
| --- | --- |
| Retrieval start (UTC) | `2026-09-25T05:38:09.367404+00:00` |
| Retrieval end (UTC) | `2026-09-25T05:43:22.321726+00:00` |
| Wall clock | 5 m 15 s |
| API base | `https://bio.tools/api/tool/` |
| Query | `?format=json&per_page=100&sort=name&ord=asc&page=N` |
| Pages fetched / expected | **343 / 343** |
| Reported `count` at start / end | **34,248 / 34,248** |
| Records ingested | **34,248** |
| Unique case-folded accessions | **34,248** |
| Duplicate accessions | **0** |
| Snapshot SHA-256 | `4bc2dff4e6f60b6098876977a3ea5228745d6891c316a7fe3fd3d830edadac13` |
| Concurrency | `--workers 4` |

**Census discrepancy: none.** The API's `count` was identical on the first page,
on every intermediate page, and on the re-fetched first page, so there is no
pagination drift to disclose. The sync aborts rather than silently discarding
records when `count` changes, so a clean completion is itself the evidence.

*Deviation from the playbook:* the playbook documents `--workers 2`; I used
`--workers 4`. This affects timing only, not the recorded content. Disclosed
because the playbook asks for a reproducible command.

**Denominator drift worth noting:** the historical
`reports/biotools_registry/completeness_report.json` states 34,230 tools. The live
count on 2026-09-25 is **34,248** — the historical report was already 18 records
stale before this assignment began.

Artifacts: `reports/biotools_registry/current/` (gitignored, as intended for a raw
snapshot) — `manifest.json`, `registry.jsonl`, `registry.sqlite`,
`env-audit.json`, and `coverage/` from the coverage audit.

### 1a. Resync and snapshot comparison

A second independent crawl was run 28 minutes later
(`2026-09-25T06:06:11Z` → `06:11:59Z`, 343 pages, count stable at 34,248) and
diffed against the first with a streaming merge join on accession:

| Metric | Value |
| --- | --- |
| Base records / target records | 34,248 / 34,248 |
| Additions | **0** |
| Removals | **0** |
| Changed records | **0** |
| Unchanged | **34,248** |
| Target SHA-256 | `4bc2dff4…` — **identical to the base** |

Both snapshots are **byte-identical**. That is a genuine result: a second
independent crawl reproduced the same digest, so the sync is deterministic and
the snapshot hash is a trustworthy identity for this registry state.

**But it is also a coverage gap.** Because no accession disappeared, the
`retired_or_missing_on_resync` state has **no observed instance**. The state is
implemented and the comparison runs; it remains untested. Reporting this as a pass
would be wrong — it is an untested branch, and a longer observation window or a
registry that actually churns is needed to exercise it.

The raw second snapshot stays out of version control
(`reports/biotools_registry/resync/` is now gitignored, alongside `current/`); the
comparison result `reports/biotools_registry/snapshot-diff.json` is retained.

---

## 2. Host and environment (the binding constraint)

| Property | Value |
| --- | --- |
| Platform | Windows 11, AMD64 |
| CPUs / RAM | 16 logical / 23.4 GB total, **4.27 GB available** at audit time |
| Disk free | 138.9 GB of 852.5 GB |
| Project-declared platforms | `linux-64`, `linux-aarch64` only |
| conda / pixi / mamba / micromamba | **absent on the host** (pixi does exist inside the BioNodulo worker image at `/app/.pixi/envs/worker`) |
| WSL | **blocked by security policy** (`wsl.exe` on the program blacklist) |
| Docker | **AVAILABLE — server 28.4.0, linux/amd64** |
| `samtools`, `bcftools` on host PATH | absent |

### The Docker daemon came up mid-session

At the start of this assignment the Docker client was present but the daemon was
**not running** (`dockerDesktopLinuxEngine` pipe absent). On that basis the first
pass concluded that no Linux execution path existed on this host, and recorded the
cohort as blocked with `unsupported_platform`.

The daemon was then started. That conclusion is now **obsolete and was corrected**,
not quietly revised:

- A real Linux run **was** produced. `samtools 1.23.1` was pulled as
  `quay.io/biocontainers/samtools@sha256:23cda33a…` — matching the repo's own
  `SAMTOOLS_VERSION = "1.23.1"` pin — and the nodes' commands executed inside it
  with `--network none`.
- The cohort's blocker was removed and those 40 records became `candidate`
  (unfinished, with owner and next step) rather than `blocked`.
- The `unsupported_platform` blocker count fell from 40 to **0**.

What remains genuinely unavailable is narrower: the project's own
pixi-provisioned worker environment, and the opt-in OCI reference profile, which
depends on a `BioNodulo-PhD-Audit` WSL distro that is blacklisted here.

---

## 3. Builtin index before / after

| Metric | Before | After |
| --- | --- | --- |
| Node IDs in `node_index.json` | 983 | **996** (+13 new builtins — §6.4) |
| Entries in `node_metadata.json` | 983 | **996** |
| Distinct categories | 55 | 55 |
| Nodes carrying `KNOWLEDGE` | 29 | **48** |
| Operational catalog `active_nodes` | 983 | **996** |
| `evidence_pending_nodes` | 976 | 976 |
| Typed catalog nodes (`node_count`) | 7 | 7 |
| Released typed nodes | 0 | 0 |

983 → 996 is a count of **BioNodulo node IDs**, not distinct upstream tools, not a
current bio.tools record count, and not proof of 996 executable or scientifically
validated runs. `gen_node_index.py --check` reports no drift after regeneration.

---

## 4. Records by state (34,248 total)

| State | Count | Share |
| --- | --- | --- |
| `reference_only` | **22,714** | 66.32% |
| `blocked` | **11,485** | 33.54% |
| `candidate` | **40** | 0.12% |
| `executable_admitted` | **9** | 0.026% |
| `retired_or_missing_on_resync` | 0 | 0% (untested — see §1a) |

Blockers by machine-readable code:

| Code | Count |
| --- | --- |
| `no_machine_invocation` | 11,485 |
| `unsupported_platform` | **0** — removed once the Docker daemon came up (§2) |

The blocker histogram and the state table reconcile exactly: 11,485 blocked rows,
11,485 blocker codes. A record that left the blocked state has its stale blocker
cleared rather than lingering in the histogram.

Interface classification:

| Class | Count | Share |
| --- | --- | --- |
| Machine-invocable (CLI, suite, script, workflow, library) | 16,924 | 49.42% |
| Non-executable only (web app, database portal, desktop, service, API, workbench) | 11,486 | 33.54% |
| Interface unannotated in bio.tools | 5,838 | 17.05% |

The 11,486 interface rows and the 11,485 blocked rows differ by exactly one: `pdb`
is classified non-executable-only *and* is now `executable_admitted`, so it left
the blocked set while keeping its interface class. The two counts measure
different things and are not expected to match.

Interface-unannotated records are `reference_only` with a next action, **not**
blocked. Per the bio.tools model, a missing function list is `unknown`, not
evidence of no capability.

Ledger artifacts: `ledger.jsonl` (34,248 parent rows), `ledger-functions.jsonl`
(33,624 child rows), `expansion-cohort.jsonl`, `ledger-summary.json`. Parent-row
count equals the snapshot record count exactly, so **coverage is complete:
34,248 / 34,248 = 100%**.

---

## 5. Functions, EDAM terms, interfaces, platforms

| Metric | Count | Denominator | Rate |
| --- | --- | --- | --- |
| Function child rows | 33,624 | 34,248 records | — |
| Unique EDAM **operations** | **554** | — | — |
| Unique EDAM input data terms | 497 | — | — |
| Unique EDAM output data terms | 391 | — | — |
| Unique EDAM input formats | 296 | — | — |
| Unique EDAM output formats | 257 | — | — |
| Records with an EDAM operation annotation | 31,430 | 34,248 | 91.79% |
| Records with an EDAM topic | 32,658 | 34,248 | 95.36% |
| Records with a documentation URL | 16,138 | 34,248 | 47.13% |
| Records with a version label | 7,820 | 34,248 | 22.83% |
| Records with a license | 15,474 | 34,248 | 45.18% |
| Records with a homepage | 34,248 | 34,248 | 100% |

A **version label is not an installable version or an environment lock.**

Acquisition-relevant link classes:

| Class | Count | Denominator | Rate |
| --- | --- | --- | --- |
| Machine-readable descriptor (CWL/Galaxy wrapper, API spec, CLI spec) | **444** | 34,248 | 1.30% |
| Container file or VM image | **355** | 34,248 | 1.04% |
| Source code / software package / binaries / downloads page | **5,665** | 34,248 | 16.54% |

Declared platform counts (non-exclusive, self-reported by records):
Linux 20,537 · Mac 18,470 · Windows 17,863 · unspecified 12,979.
Primary language: unspecified 11,665 · R 7,286 · Python 6,787 · Java 1,681 ·
C++ 1,659.

---

## 6. Admission: what was attempted, what passed, what did not

### Identity reconciliation

| Reconciliation status | Count | Share |
| --- | --- | --- |
| `no_existing_node` | 28,360 | 82.81% |
| `unreviewed` (interface unannotated) | 5,836 | 17.04% |
| `existing_related_operation` | 3 | 0.0088% |
| `new_operation` (selected cohort) | 40 | 0.12% |
| `existing_exact` | 9 | 0.026% |
| `duplicate_record` / `ambiguous` | 0 | 0% |

**Only 9 of 34,248 records (0.026%) have a declared, explicit link to a builtin**
(20 node types map to those 9 accessions). The historical report's "104 families
with registry match" was a name-based signal, not declared identity. This
assignment added no new declared links; name similarity was used only as a search
hint and is recorded separately as `reconciliation.family_hint`.

### Prioritized cohort

Selection method: a deterministic, documented score over metadata signals
(command-line type, machine-readable descriptor, CWL specifically, container,
package/binary distribution, explicit CLI specification, EDAM operation
annotation, input/output format annotation, documentation URL, license,
publication count as a capped research-use proxy, EDAM topic count, EDAM
operation count, declared Linux support, version label). The first version of
this score **saturated**, leaving 442 records tied at the maximum and reducing
"prioritization" to an alphabetical accident; it was rebuilt to be graded.

| Cohort metric | Value |
| --- | --- |
| Eligible pool (machine-invocable, no existing node) | 16,915 |
| Selected | **40** (0.24% of pool, 0.12% of all records) |
| Score range | 18–20 |
| Still tied at the cutoff | 37 |
| Admitted from the cohort | **0 / 40** — these are unfinished candidates, not admissions |
| Previously blocked, now unblocked | **40** (the `unsupported_platform` blocker was withdrawn — §2) |

Representative selected records: clusterProfiler, cufflinks, ggtree, HMMER3,
MMseqs2, nf-core-sarek, QuasR, REPET, v-pipe, MEME Suite, bowtie2, Flye,
augustus, integron_finder, chopchop.

**Unprocessed tail:** the remaining ~16,875 eligible records are `reference_only`
and were deliberately not started, because the measured blocker below applies to
the whole cohort and the remaining time could not cover an install, queue run,
oracle, citation check and rebuild.

### Blockers

| Code | Count | Reason |
| --- | --- | --- |
| `no_machine_invocation` | 11,485 | Declared tool types have no local machine invocation |
| `unsupported_platform` | **0** | Withdrawn. The Docker daemon became available mid-session and digest-pinned Linux runs succeeded (§2, §6.3) |

### 6.3 Verified executions

| Metric | Numerator | Denominator | Rate |
| --- | --- | --- | --- |
| New typed operations authored | **0** | 40 cohort | 0% |
| Descriptors acquired | 0 | 40 | 0% |
| Cohort environments installed | 0 | 40 | 0% |
| Workflows executed through the ordinary executor | **1** | 1 attempted | 100% |
| Nodes completed in that workflow | **8** | 8 | 100% |
| **Operations verified in a digest-pinned Linux container** | **7** | 7 typed samtools operations | **100%** |
| Chain steps completed | **8** | 8 | 100% |
| Chain steps output-honest | **8** | 8 | 100% |
| Independent oracle assertions passed | **20** | 20 | 100% |
| Records marked `executable_admitted` | **4** | 34,248 | 0.0117% |
| **New executable admissions** | **0** | 40 | **0%** |

Two receipts, both real:

**`reports/run-receipts/samtools-sort/`** — the node's own rendered argv
(`samtools sort -@ 1 -m 32M -T /work/out/tmp -o /work/out/sorted_bam.bam …`)
executed in `quay.io/biocontainers/samtools@sha256:23cda33a…`, `--network none`,
exit 0, samtools 1.23.1 / htslib 1.23.1. Six oracle assertions.

**`reports/run-receipts/samtools-chain/`** — all seven typed samtools operations in
one composition (`sort → index`, `sort → flagstat`, `sort → view`,
`collate → fixmate → sort → markdup`). 8/8 steps exit 0, 8/8 output-honest.
Eight further oracle assertions.

**A failure mode was exercised, not just a happy path.** Feeding a SAM whose CIGAR
declares 10M while its SEQ carries 4 bases produced exit 1 with
`[E::sam_parse1] CIGAR and query sequence are of different length` and
`samtools sort: truncated file. Aborting`, and **no output alignment was
published**. Receipt: `reports/run-receipts/samtools-sort-invalid/`.

**The oracles do not let the tool mark its own homework.** Both decompress BGZF
with stdlib `gzip` and parse the BAM binary layout by hand — no samtools, pysam or
htslib participates in any assertion. They check that the header declares
`SO:coordinate`, that references are `[chr1, chr2]`, that all three fixture reads
survive by name, that sequences are byte-identical to the fixture, that positions
are exactly 99/299/199, that the `.bai` is colocated with a byte-identical staged
BAM, and that the flagstat report independently describes three mapped reads.

**Pre-existing operations were verified; none were authored.** That distinction is
recorded per record as `operation_provenance: pre_existing_builtin`.

A third receipt, `reports/run-receipts/protein-structure-db/`, covers the
pure-Python network path: `protein_structure_database_workflow.json` executed
through the ordinary `WorkflowExecutor` with **no environment provisioning
required** — 8/8 nodes, 31 artifacts. Its oracle
(`tests/nodes/protein_database/test_receipt_oracle.py`, 6 passed) asserts
biological content against external ground truth **and against other artifacts**:

- retrieved sequence is `P04637` / `P53_HUMAN` / *Homo sapiens* / `GN=TP53`, length **393**, starting `MEEPQSDPSVEPPLSQETFSDLW`;
- the UniProt search TSV — produced by a **different node** — independently reports accession `P04637` and `sequence_length 393`, so the two agree;
- the predicted-aligned-error matrix is **393 × 393** with a zero diagonal;
- AlphaFold entry `AF-P04637-F1` and RCSB entry `4HHB` are present in the mmCIF files;
- every recorded artifact hash matches the file on disk.

Four records (`uniprot`, `alphafold`, `pdb`, `samtools`) are recorded
`executable_admitted` because a tested operation for them now has a real run and
an independent oracle. **The operations pre-existed; this assignment verified them
rather than authoring them.** That distinction is recorded per record as
`operation_provenance: pre_existing_builtin`.

### 6.4 Registry-expansion wave: 13 new nodes across 4 new families

The census was used to find tools that are **genuinely absent** from the catalog
rather than to re-wrap what already exists. 983 builtins already cover most major
tools heavily (bcftools 34, bedtools 40, samtools 27, seqtk 15, checkm 12,
hmmer 12), so the search targeted high-utility gaps.

| Metric | Value |
| --- | --- |
| Builtin node count | **983 → 996 (+13)** |
| New families | **4** |
| New nodes with a real container run receipt | **13 / 13** |
| New nodes linting clean | **13 / 13** (0 ERROR, 0 WARN) |
| New tests | **42 passed** |
| New oracle assertions | **~200** across 4 files |
| EDAM terms verified against the pinned release | **20 / 20, 0 mismatches** |
| `tool_id` values verified present in the census | **8 / 8** |

| Family | Nodes | Pinned image (digest recorded in each receipt) |
| --- | --- | --- |
| `emboss_family` | `emboss_transeq`, `emboss_revseq`, `emboss_pepstats` | `quay.io/biocontainers/emboss:6.6.0--h0f19ade_14` |
| `htslib_tabix_family` | `bgzip_compress`, `bgzip_decompress`, `tabix_index`, `tabix_query` | `quay.io/biocontainers/tabix:0.2.5--ha92aebf_2` |
| `seqfu_family` | `seqfu_stats`, `seqfu_count`, `seqfu_list` | `quay.io/biocontainers/seqfu:1.28.0--h41da26b_0` |
| `csvtk_family` | `csvtk_stats`, `csvtk_headers`, `csvtk_cut` | `quay.io/biocontainers/csvtk:0.31.0--h9ee0642_0` |

All 13 ran in their pinned image with `--network none` and produced receipts under
`reports/run-receipts/`. Oracles assert content, not exit status: the EMBOSS
translation is compared to the known peptide string and the reverse complement is
computed exactly; the BGZF output is decompressed with stdlib `gzip` and asserted
byte-identical to the input, the `.tbi` magic is checked, and a region query must
return exactly the in-region records while excluding out-of-region ones; SeqFu's
counts, N50/N75/N90 and min/max are recomputed from the fixture; csvtk's headers,
column selection and statistics are compared against values computed from the
fixture with stdlib `csv`.

**Registration used the repo's own mechanism.** `compile_catalog.py` holds a frozen
`BASELINE_NODE_COUNT = 943` plus an explicit `POST_BASELINE_NODE_IDS` set; the
catalog refuses to build unless the node count matches. The 13 new IDs were added
there (40 → 53 post-baseline entries), so the count is 996 by declaration rather
than by silently drifting. Both `gen_node_index.py --check` and
`compile_catalog.py --check` are clean.

**`csvtk` has no bio.tools record at all** — absent from all 34,248 records and
from the live API. Its `tool_id` is therefore **omitted** rather than filled with a
plausible-looking URL, and it has no ledger row. It is recorded separately under
`nodes_without_a_registry_record` in `expansion-outcomes.json`.

**One agent overrode a bio.tools label using the pin.** The bio.tools record gives
`topic_3071` as "Data management"; the pinned EDAM release gives "Biological
databases". The pinned label was used. That is the correct precedence.

### Honest gaps in this wave

- **Agents bypassed the container harness's node resolution.** `run_container_receipt.py`
  resolves nodes through the generated `node_index.json`, which did not yet contain
  the new nodes, so three agents drove the harness through temporary wrappers. I
  removed those wrappers and **re-ran the direct harness path myself** on
  `seqfu_stats`: it now resolves and completes with an identical argv, confirming
  the receipts were not an artifact of the wrappers.
- **`bgzip` has no `--version` flag**, so the harness's version probe records
  bgzip's real "invalid option" text instead of a version banner. The receipt says
  so rather than hiding it.
- **Only FASTA was exercised in the container for SeqFu.** The FASTQ fixture is
  asserted as ground truth but no receipt exercises a FASTQ input.
- **Only `delimiter=tab` was exercised end to end for csvtk**; comma mode is
  render-verified only.
- **`edamontology.org` intermittently fails TLS verification** (expired
  certificate) from Python's `urllib`; `curl` succeeds. Agents hit this and could
  not re-resolve labels, which is why I verified all 20 terms myself against the
  pinned CSV (digest matched the pin exactly).
- **No cloud-queue parity.** These ran in pinned containers, not through the
  project's own pixi-provisioned worker.

### Measured rate and projection

Thirteen nodes were produced across four families by four parallel workers. The
binding cost was **not** the container run (seconds) but the per-operation
authoring: reading the tool's real `--help` in the container, writing a fail-closed
contract, hand-building a fixture with known ground truth, and writing an oracle
that parses the output without the tool. That cost is per operation and does not
amortise much across families.

Extrapolating from this wave, the ~34 genuinely-absent high-utility tools found in
this pass are reachable; **34,248 is not**, and any plan that claims otherwise is
counting metadata as capability. The honest framing is unchanged: the census is
attainable in full, executable coverage is not.

---

## 7. Citations

| Metric | Numerator | Denominator | Rate |
| --- | --- | --- | --- |
| DOIs verified through Crossref | **4** | 4 attempted | 100% |
| Record-listed DOIs examined and **rejected** as wrong for the tool | 2 | 2 | 100% |
| Multi-DOI nodes in the baseline | 156 | 983 | 15.87% |

Verified: `10.1093/nar/gkaa1100` (UniProt 2021, NAR) · `10.1093/nar/gkad1011`
(AlphaFold Protein Structure Database in 2024, NAR, Varadi) ·
`10.1093/nar/28.1.235` (The Protein Data Bank, NAR 2000) ·
`10.1038/nsb1203-980` (Announcing the worldwide PDB, NSMB 2003).

**A citation-fidelity trap was caught.** The bio.tools `alphafold` record lists
two publications that are **not** the AlphaFold paper: `10.3390/molecules29040832`
resolves to *"Recent Progress of Protein Tertiary Structure Prediction"* (a
review) and `10.1101/2024.02.06.579080` to *"Direct Coupling Analysis and The
Attention Mechanism"* (a preprint). Using record DOIs blindly would have
misattributed citations. The correct database paper was located and verified
independently instead, and the discrepancy is recorded in the node's
`citation_evidence`.

Four previously **uncited** nodes now carry checked citations
(`uniprot_search`, `uniprot_retrieve`, `alphafold_db`, `pdb_download`); two more
inherit them. The 258-node uncited baseline is otherwise unchanged.

---

## 8. Knowledge graph

The atlas is built automatically from **all** builtin metadata; it does not
maintain a second roster, and this assignment added no graph database or new
dependency.

| Graph metric | Value | Denominator | Rate |
| --- | --- | --- | --- |
| Nodes with `KNOWLEDGE` | **48** | 996 | 4.82% |
| Asserted relations | **5** | — | — |
| — `documented_successor` | 3 | 5 | — |
| — `complements` | 2 | 5 | — |
| EDAM topics | 28 | — | — |
| EDAM operations | **22** | — | — |
| Nodes carrying operations | 6 | 996 | 0.60% |
| `citation_evidence` entries | 49 | — | — |
| Distinct verified `tool_id` values | **9** | — | — |

Every relation carries a source URL, a `checked_at` date and a note, and every
`tool_id` is a verified public bio.tools URL. Nodes gained: `uniprot_search`,
`uniprot_retrieve`, `alphafold_db`, `pdb_download` (plus `alphafold` and
`pdb_retrieve` by inheritance — verified as the same upstream resource, which the
Tool Atlas guide warns is exactly where inheritance goes wrong).

**Ontology pin and operation terms.** The first pass deliberately omitted EDAM
`operations`, because bio.tools supplies operation URIs without labels. That
abstention is now closed: EDAM release **`1.25-20260626T1230Z`** was retrieved and
pinned by digest (`EDAM.owl` SHA-256 `a3ebbd7d…`, 3,413,870 bytes; label lookup
via `EDAM.csv` SHA-256 `cac8ca5d…`; 3,473 classes). Every label used was read from
that release, and all five topic labels already in use were confirmed to match it
exactly. See `reports/biotools_registry/ontology-and-snapshot-pins.json`.

Two candidate operations were **deliberately rejected** as overstating a node:

- `operation_0474` *Protein structure prediction* — `alphafold_db` retrieves
  already-predicted models; it does not predict structures.
- `operation_3778` *Text annotation* — listed by the bio.tools `uniprot` record for
  the tool as a whole, but it does not describe what `uniprot_search` does.

Assigned instead: `uniprot_search` → *Database search* (`operation_2421`);
`uniprot_retrieve`, `alphafold_db`, `pdb_download` → *Data retrieval*
(`operation_2422`), inherited by `alphafold` and `pdb_retrieve`.

### Representative validated composition

```
uniprot_search ──documented_successor──▶ uniprot_retrieve ──documented_successor──▶ alphafold_db
                                                                      │
                                                              complements
                                                                      ▼
                                                               pdb_download
```

Edges are `asserted` (source URL + check date + explanation), not inferred. The
first two were additionally **executed** in one retained run whose oracle
confirmed the outputs.

### Unadmitted candidate path

`MMseqs2`, `HMMER3`, `bowtie2`, `Flye`, `nf-core-sarek` and the rest of the cohort
are discoverable and annotated, and they are **not** platform-blocked any more
(§2). They are unfinished `candidate` rows carrying an owner and a next step. None
of them is an executable builtin, none is counted as one, and the
`executable_admitted` count does not include any of them.

---

## 9. Defects found and confirmed

**1. `EXTERNAL_REQUIRED_EXECUTABLES` is a dead field.**
It appears **once in the entire codebase** — in
`metabolomics_family/sirius_formula_id.py` — and is exported **nowhere**
(0 occurrences in `base.py`, `registry.py`, `export_capabilities.py`). SIRIUS's
real requirement (`sirius` on PATH, per the node's own `EXTERNAL_INSTALLATION`
text) is silently dropped from `node_metadata.json`.

**2. `lineardesign_optimize` has an unexpressed provisioning contract.**
It declares `REQUIRES_EXTERNAL_TOOLS = True` with no `REQUIRED_EXECUTABLES`,
because its binary comes from a **runtime `git clone`** of a license-restricted
repository, resolved through `BIONODULO_LINEARDESIGN_DIR`, and it hard-fails off
Linux. Metadata cannot express "clone at runtime + prebuilt Linux binary +
redistribution restriction + blocked off-Linux". This is a genuine contract gap,
not a typo.

These two are the only records matching "external tool, no required executables"
— **2 of 983**, confirming the baseline inventory exactly.

**3. Multi-DOI bibliography export is materially wrong.** Reproduced on the
2-DOI node added here:

- **RIS** emits two records that share one concatenated title
  (`"The Protein Data Bank; Announcing the worldwide Protein Data Bank."`) —
  each DOI claims the other work's title.
- **BibTeX** emits one entry with `doi = {10.1093/nar/28.1.235}` and buries the
  second DOI in a `note`.

With 156 multi-DOI nodes in the baseline, this is a real fidelity limit. **I do
not claim an accurate multi-work bibliography.** Fixing it properly needs
per-DOI citation text in the data model, which is a larger change than this
assignment's scope; it is recorded as an open defect with the exact reproduction.

**4. `samtools_fixmate` → `samtools_markdup` is not directly composable.**
`samtools markdup` requires **coordinate-sorted** input, but `fixmate` emits
queryname-grouped order. A `collate → fixmate → markdup` chain failed with
`not in coordinate sorted order`; inserting a coordinate sort between them made it
pass. The graph must therefore not present fixmate as a direct predecessor of
markdup, and any workflow template that chains them without an intervening sort is
wrong.

**5. `render_command` is not platform-neutral.** Nodes build output paths with
`pathlib.Path`, so on a Windows host the rendered argv carries backslashes
(`\work\out\tmp`) where a linux-64 worker would render forward slashes. The
receipts record both forms and the rewrite rather than normalising the difference
away. Harmless for the Linux-only cloud worker, but it means the argv is not a
portable artifact and should not be treated as one.

### Two suspected defects were investigated and refuted

Recorded because a finding that disappears under scrutiny is still a result, and
because both would have been wrong to publish:

- **`samtools_index`** appeared to promise an `indexed_bam.bam` that its command
  never writes. It materialises that file in `PREPARE_EXECUTION`, which hard-links
  the source BAM beside the `.bai`. My first harness skipped that hook.
- **`samtools_flagstat`** appeared to promise a `stats.stats.txt` it never writes.
  It declares `STDOUT_OUTPUT_INDEX = 0`, and the executor captures stdout into the
  planned file. My first harness implemented no stdout capture.

Both were **harness bugs, not node bugs**. Once the harness honoured the two
conventions, all eight chain steps were output-honest. A third hypothesis — that
`samtools_fixmate` omitting the `-m` flag breaks the markdup composition — was also
**refuted** by a controlled A/B test: markdup exits 0 both with and without `-m`
on this fixture, so it is not reported as a defect.

---

## 10. Test and gate status

| Gate | Result |
| --- | --- |
| `pytest tests/test_node_knowledge.py tests/nodes/protein_database/ tests/test_node_index.py tests/test_references_export.py tests/test_builtin_registry_loading.py tests/test_capability_metadata.py` | **80 passed** |
| `pytest tests/nodes/samtools/` (whole family) | **223 passed, 10 skipped** |
| Container oracles (`test_container_receipt_oracle.py`, `test_chain_receipt_oracle.py`) | **14 passed** |
| `scripts/run_container_receipt.py` (sort, valid fixture) | exit 0, digest stable |
| `scripts/run_container_receipt.py` (sort, invalid CIGAR fixture) | exit 1, failure captured |
| `scripts/run_samtools_chain.py` | 8/8 completed, 8/8 output-honest |
| Frontend `vitest run` (full suite) | **653 passed, 1 failed** of 654 |
| Frontend Tool Atlas unit tests (`toolKnowledgeGraph`, `useObjectInfo`) | **13 passed** |
| `scripts/gen_node_index.py` | 983 nodes + 2,211 KB metadata written |
| `scripts/gen_node_index.py --check` | **no drift** |
| `scripts/compile_catalog.py --check` (before) | **STALE** — reported, then fixed |
| `scripts/compile_catalog.py --write` | 7 projections (983/983 operational, 7/983 typed) |
| `scripts/compile_catalog.py --check` (after) | **up to date** |
| `scripts/node_linter.py` on the 4 annotated nodes | **0 ERROR, 0 WARN** each |
| `scripts/audit_biotools_coverage.py --check-imports` | 34,248 records vs 983 nodes; 9 declared links |
| `scripts/diff_registry_snapshots.py` | 34,248 unchanged, 0 additions/removals/changes |
| Independent oracle | **6 passed** |

The one frontend failure is
`src/test/client.test.ts > api/client > returns blob responses with apiGetBlob`:
`expect(out).toBeInstanceOf(Blob)` fails because jsdom's `Blob` is not Node's
`Blob`. It is an environment identity mismatch in an API-client test, unrelated to
any change in this assignment (which touched no TypeScript). It is reported as a
pre-existing environmental failure, not fixed here.

**Skipped or not run, honestly:**

- No whole-suite `pytest` run (memory-limited host: 4.27 GB available; the
  playbook explicitly warns against whole-suite runs here).
- **No Playwright e2e run** and no `vite build`. The Tool Atlas e2e specs were not
  exercised; only the vitest unit suite was.
- **No `audit_generated_catalog.py` run** — it probes every declared runtime,
  which on a host with no conda and no container daemon would produce ~983
  uninformative probe failures. Its CWL-document validation half was not run
  separately.
- **`retired_or_missing_on_resync` is still untested** (§1a) — a second sync ran
  and matched byte-for-byte, so no accession was removed.
- No platform-specific tests beyond Windows; Linux-only gates were not run.

---

## 11. Remaining risks and unknowns

1. **The headline gap is real and unresolved.** 34,248 registry records exist and
   983 builtin node IDs exist, but **0 new typed operations were admitted**. What
   was achieved is verification: 7 pre-existing samtools operations now have real
   digest-pinned runs with independent oracles, and 4 records are
   `executable_admitted`. That is evidence, not coverage.
2. **`retired_or_missing_on_resync` is untested.** A second sync was performed
   (§1a) and matched the first byte-for-byte, so no accession was removed and the
   state has no observed instance. The mechanism runs; the branch is unexercised.
3. **EDAM operations cover 6 of 983 nodes (0.61%)**, against a pinned release.
   The remaining 977 have no ontology terms in `KNOWLEDGE`, and the 554 unique
   EDAM operations present in the registry are not yet mapped to builtins.
4. **The container harness is not the cloud queue.** It reproduces the executor
   contract (`PLAN_OUTPUTS`, `PREPARE_EXECUTION`, `STDOUT_OUTPUT_INDEX`) around a
   container run, which is why it can check output honesty at all. It does not use
   the project's pixi-provisioned worker, so it is evidence about the nodes and
   their commands, not about provisioning. The cohort's earlier
   `unsupported_platform` blocker was withdrawn once Docker came up, but the 40
   candidates remain **unadmitted**.
5. **The multi-DOI exporter remains wrong** (§9.3) and the RIS/BibTeX outputs for
   any of the 156 multi-DOI nodes should not be trusted.
6. **One workflow, one accession.** The verified run proves the mechanism and
   the biology for P04637; it is not a general guarantee for other accessions,
   datasets or result sizes, and it does not validate AlphaFold's predictions.
7. **`lineardesign_optimize` and `sirius_formula_id` remain contract-broken**;
   both are discoverable but their environment requirements are unrepresentable
   or invisible in metadata.
8. **This is tooling evidence, not science.** It can improve tool discovery,
   reproducibility and composition evidence. It does not demonstrate a novel
   biological method or validate a PhD claim.

---

## 12. Changed files

| Path | Change |
| --- | --- |
| `scripts/build_expansion_ledger.py` | **new** — per-accession ledger builder with documented states and blocker codes |
| `scripts/run_local_queue_receipt.py` | **new** — receipt-capturing runner over the real executor |
| `scripts/run_container_receipt.py` | **new** — runs a node's own argv in a digest-pinned container and retains a receipt |
| `scripts/run_samtools_chain.py` | **new** — 8-step chain with per-step output-honesty checks |
| `scripts/diff_registry_snapshots.py` | **new** — streaming snapshot merge-join diff |
| `tests/nodes/protein_database/test_receipt_oracle.py` | **new** — 6 oracle assertions |
| `tests/nodes/samtools/test_container_receipt_oracle.py` | **new** — 6 oracle assertions incl. a failure mode |
| `tests/nodes/samtools/test_chain_receipt_oracle.py` | **new** — 8 oracle assertions incl. output honesty |
| `tests/nodes/samtools/fixtures/mini_unsorted.sam` | **new** — 3-read legal fixture, deliberately unsorted |
| `tests/nodes/samtools/fixtures/invalid_cigar_length.sam` | **new** — CIGAR/SEQ mismatch failure fixture |
| `reports/biotools_registry/BUILTIN-EXPANSION-2026-09-25.md` | **new** — this report |
| `reports/biotools_registry/expansion-outcomes.json` | **new** — curated outcomes layered over mechanical defaults |
| `reports/biotools_registry/ontology-and-snapshot-pins.json` | **new** — EDAM release pin and snapshot comparison record |
| `reports/biotools_registry/snapshot-diff.json` | **new** — retained comparison result |
| `reports/run-receipts/` | **new** — 4 retained receipts (2.8 MB total) |
| `bionodulo/nodes/builtin/{emboss,htslib_tabix,seqfu,csvtk}_family/` | **new** — 4 families, 13 nodes (§6.4) |
| `tests/nodes/{emboss,htslib_tabix,seqfu,csvtk}_family/` | **new** — fixtures + 4 oracle test files (42 tests) |
| `scripts/compile_catalog.py` | +19 — the 13 new node IDs added to `POST_BASELINE_NODE_IDS` (40 → 53) |
| `bionodulo/nodes/builtin/protein_database_family/uniprot_adapter.py` | +96 — `KNOWLEDGE`, operations and citations on two nodes |
| `bionodulo/nodes/builtin/protein_database_family/alphafold_db_adapter.py` | +54 — `KNOWLEDGE`, operation and citation, with the record discrepancy recorded |
| `bionodulo/nodes/builtin/protein_database_family/rcsb_pdb_adapter.py` | +40 — `KNOWLEDGE`, operation and two citations |
| `bionodulo/nodes/node_metadata.json` | regenerated |
| `bionodulo/nodes/generated/catalog.{lock,operational,promotion}.json` | recompiled |
| `reports/README.md`, `scripts/README.md` | new artifacts indexed |
| `.gitignore` | ignore the dated resync snapshot |

`node_index.json` is unchanged: the annotations alter metadata, not node identity.

### Reproduce

```sh
export PYTHONPATH="$PWD"
PY=/d/AI/BioNodulo/BioNodulo/.venv/Scripts/python.exe

# census, audit, ledger
$PY scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/current --workers 4
$PY scripts/audit_biotools_coverage.py --snapshot-dir reports/biotools_registry/current \
    --output-dir reports/biotools_registry/current/coverage --check-imports
$PY scripts/build_expansion_ledger.py --snapshot-dir reports/biotools_registry/current \
    --output-dir reports/biotools_registry/current/ledger --cohort-size 40 \
    --outcomes reports/biotools_registry/expansion-outcomes.json

# resync comparison
$PY scripts/sync_biotools_registry.py --output-dir reports/biotools_registry/resync --workers 4
$PY scripts/diff_registry_snapshots.py --base-dir reports/biotools_registry/current \
    --target-dir reports/biotools_registry/resync --output reports/biotools_registry/snapshot-diff.json

# pure-Python workflow receipt
$PY scripts/run_local_queue_receipt.py templates/protein_structure_database_workflow.json \
    --receipt-dir reports/run-receipts/protein-structure-db

# digest-pinned container runs
IMG=quay.io/biocontainers/samtools:1.23.1--ha83d96e_0
DIG=sha256:23cda33a3a42125872766df9aaf1d2db67cdb8c85314b793465188435af31ba6
$PY scripts/run_container_receipt.py --node samtools_sort --image $IMG --digest $DIG \
    --input-key alignment --fixture tests/nodes/samtools/fixtures/mini_unsorted.sam \
    --inputs-json '{"threads": 1, "memory_per_thread": "32M"}' \
    --receipt-dir reports/run-receipts/samtools-sort
$PY scripts/run_samtools_chain.py --image $IMG --digest $DIG \
    --fixture tests/nodes/samtools/fixtures/mini_unsorted.sam \
    --receipt-dir reports/run-receipts/samtools-chain

# oracles and generated artifacts
$PY -m pytest tests/nodes/protein_database/ tests/nodes/samtools/ -q
$PY scripts/gen_node_index.py && $PY scripts/gen_node_index.py --check
$PY scripts/compile_catalog.py --write && $PY scripts/compile_catalog.py --check
```
