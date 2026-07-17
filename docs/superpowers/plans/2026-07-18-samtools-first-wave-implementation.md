# Samtools First-Wave Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the seven template-critical Samtools nodes with small source-backed modules and make indexed BAM dependencies explicit in local and cloud workflows.

**Architecture:** Keep the existing `CommandNode`, registry, executor, and Pixi workflow environment. Add two narrow command-output hooks, one shared Samtools adapter, and seven operation modules. `samtools_index` publishes a colocated BAM/BAI pair through separate existing port types; three affected templates wire both artifacts to indexed consumers. Advanced modes and all nodes remain quarantined.

**Tech Stack:** Python 3.11+, pytest, existing BioNodulo executor and registry, Samtools 1.23.1 documentation/source

---

## File Structure

```text
bionodulo/nodes/builtin/samtools_family/
  __init__.py
  adapter.py
  view.py
  collate.py
  fixmate.py
  sort.py
  markdup.py
  index.py
  flagstat.py

tests/nodes/samtools/
  test_adapter.py
  test_first_wave.py

tests/
  test_command_node_outputs.py
```

The legacy `bionodulo/nodes/builtin/samtools.py` keeps only the other 20
operations. Generated node index and metadata files are refreshed after the
split.

### Task 1: Add Command Output Hooks

**Files:**
- Modify: `bionodulo/nodes/command_node.py`
- Modify: `bionodulo/execution/executor.py`
- Create: `tests/test_command_node_outputs.py`

- [ ] **Step 1: Write RED tests**

Add a fake command node whose `PREPARE_EXECUTION(inputs, outputs)` records the
planned output and whose `STDOUT_OUTPUT_INDEX = 0`. Use a fake execution context
that records the requested stdout path and writes the output file. Assert that
preparation runs before command rendering and that stdout is written directly to
the planned artifact rather than `stdout.log`.

- [ ] **Step 2: Confirm RED**

Run:

```bash
../../.venv/bin/python -m pytest -q tests/test_command_node_outputs.py
```

Expected: failure because `PREPARE_EXECUTION`, `STDOUT_OUTPUT_INDEX`, and the
context stdout-path override do not exist.

- [ ] **Step 3: Implement the minimum hooks**

Add these class attributes/methods to `CommandNode`:

```python
STDOUT_OUTPUT_INDEX: ClassVar[int | None] = None

@classmethod
def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
    return None
```

Plan outputs before rendering, call `PREPARE_EXECUTION`, then render. Extend
`ExecutionContext.run_command` with optional `stdout_path` and `stderr_path`
arguments that default to the existing log paths. When a stdout output index is
declared, pass that planned path to both the context and direct-subprocess paths.

- [ ] **Step 4: Confirm GREEN and regressions**

Run:

```bash
../../.venv/bin/python -m pytest -q tests/test_command_node_outputs.py tests/test_execution_runtime.py
```

Expected: all tests pass.

### Task 2: Build The Shared Adapter And Seven Modules

**Files:**
- Create: `bionodulo/nodes/builtin/samtools_family/__init__.py`
- Create: `bionodulo/nodes/builtin/samtools_family/adapter.py`
- Create: seven operation modules listed above
- Modify: `bionodulo/nodes/builtin/samtools.py`
- Create: `tests/nodes/samtools/test_adapter.py`
- Create: `tests/nodes/samtools/test_first_wave.py`

- [ ] **Step 1: Write RED registry and contract tests**

Assert that each stable ID resolves to its own module, inherits the shared
adapter, declares Samtools `1.23.1`, the pinned Git commit, one manpage, and one
implementation source file. Assert exact input sections, defaults, return types,
return names, and fixed output paths.

- [ ] **Step 2: Write RED argv tests**

Assert the exact token arrays:

```python
["samtools", "view", "-b", "-@", "4", "-o", OUT, INPUT]
["samtools", "collate", "-@", "4", "-T", TMP, "-o", OUT, INPUT]
["samtools", "fixmate", "-@", "4", INPUT, OUT]
["samtools", "sort", "-@", "4", "-m", "768M", "-T", TMP, "-o", OUT, INPUT]
["samtools", "markdup", "-@", "4", "-f", STATS, INPUT, OUT]
["samtools", "index", "-@", "2", "-b", "-o", BAI, INDEXED_BAM]
["samtools", "flagstat", "-@", "2", INPUT]
```

Add option tests for view masks, fixmate `-m/-r`, and markdup
`-r/-S/-d/--read-coords/-c`. Assert invalid thread counts, invalid sort memory,
negative optical distance, and `read_coords` without optical detection are
rejected.

- [ ] **Step 3: Confirm RED**

Run:

```bash
../../.venv/bin/python -m pytest -q tests/nodes/samtools
```

Expected: import/ownership failures because the new package does not exist and
the legacy module still owns the seven IDs.

- [ ] **Step 4: Implement the adapter and modules**

The adapter supplies shared category, package, executable, citations, version,
Git URL/commit, thread validation, declarative output planning, and source
metadata. Each operation module contains one concrete class and its argv logic.
Remove only the seven migrated classes and now-unused stem helpers from the
legacy monolith.

- [ ] **Step 5: Confirm GREEN**

Run the Samtools tests above. Expected: all first-wave tests pass without
executing Samtools.

### Task 3: Implement Explicit BAM/BAI Semantics

**Files:**
- Modify: `bionodulo/nodes/builtin/samtools_family/index.py`
- Modify: `bionodulo/nodes/builtin/variant.py`
- Modify: `bionodulo/nodes/builtin/visualization.py`
- Modify: the module that owns `deeptools_bamcoverage`
- Modify: `tests/nodes/samtools/test_first_wave.py`
- Create: `tests/nodes/test_indexed_bam_consumers.py`

- [ ] **Step 1: Write RED staging and consumer-contract tests**

Use a small fake BAM text file and a fake context. The index preparation hook
must create `indexed_bam.bam` in the index node directory, prefer a hard link,
render `indexed_bam.bam.bai` beside it, and return both declared outputs after
the fake context creates the BAI.

Assert that GATK HaplotypeCaller, FreeBayes, Manta, Delly, and deepTools
bamCoverage declare a `bam_index: BAI` input. Assert that coverage plotting
declares `alignment_index: BAI` and passes it to pysam for BAM region access.
Consumers whose underlying CLI discovers a sibling index validate that the BAM
and BAI are a matching colocated pair before execution.

- [ ] **Step 2: Confirm RED**

Run the focused tests. Expected: missing second index output and missing
consumer index ports.

- [ ] **Step 3: Implement minimum semantics**

In the index node preparation hook, hard-link the source BAM to the planned BAM;
fall back to `shutil.copy2` only for cross-device or unsupported-link errors.
Set the command input to the staged BAM and its explicit BAI output. Add the
small consumer port and validation changes described above; do not add a
composite artifact serializer.

- [ ] **Step 4: Confirm GREEN**

Run the focused consumer and Samtools tests. Expected: all pass.

### Task 4: Rewire Indexed Consumers Through The Index Node

**Files:**
- Modify: `templates/variant_calling_pipeline.json`
- Modify: `templates/wgs_variant_pipeline.json`
- Modify: `templates/chip_seq_pipeline.json`
- Modify: `tests/test_workflow_templates.py`
- Modify: `tests/test_variant_template_robustness.py`
- Modify: `tests/test_variant_template_sv_calling.py`
- Modify: `tests/test_wgs_variant_template_sv_calling.py`
- Modify: `tests/test_chip_seq_template_coverage_plot.py`

- [ ] **Step 1: Write RED DAG assertions**

For both variant templates, assert `markdup.marked_bam -> index.bam`. Assert
indexed consumers receive both `index.indexed_bam` and `index.bai`, including
GATK retry/HaplotypeCaller or FreeBayes, coverage plotting, Manta, and Delly.
Assert no indexed consumer receives `markdup.marked_bam` directly. Keep flagstat
free to consume marked BAM because it does not require random-access indexing.

For ChIP-seq, add a Samtools index node after the treatment sort. Route
deepTools bamCoverage from its `indexed_bam` and `bai` outputs; MACS2 retains
the direct sorted-BAM edge because it does not require BAI.

- [ ] **Step 2: Confirm RED**

Run:

```bash
../../.venv/bin/python -m pytest -q \
  tests/test_workflow_templates.py \
  tests/test_variant_template_robustness.py \
  tests/test_variant_template_sv_calling.py \
  tests/test_wgs_variant_template_sv_calling.py \
  tests/test_chip_seq_template_coverage_plot.py
```

Expected: failures showing the existing dead or absent index branches.

- [ ] **Step 3: Rewire only the affected edges**

Replace indexed consumers' BAM sources with the corresponding index node and
`indexed_bam` port, and add a BAI edge to the consumer's explicit index input.
Do not change unrelated parameters, outputs, or reporting edges.

- [ ] **Step 4: Confirm GREEN and workflow validity**

Run the tests above plus `tests/test_workflow_validation.py`. Expected: all pass.

### Task 5: Refresh Discovery Artifacts And Verify The Slice

**Files:**
- Regenerate: `bionodulo/nodes/node_index.json`
- Regenerate: `bionodulo/nodes/node_metadata.json`
- Modify only if required: focused existing Samtools tests whose assertions
  describe the superseded contracts

- [ ] **Step 1: Regenerate discovery files**

Run:

```bash
../../.venv/bin/python scripts/gen_node_index.py
```

Expected: exactly 943 stable node IDs and no duplicate ownership.

- [ ] **Step 2: Run targeted verification**

Run:

```bash
../../.venv/bin/python -m pytest -q \
  tests/test_command_node_outputs.py \
  tests/nodes/samtools \
  tests/nodes/test_indexed_bam_consumers.py \
  tests/test_samtools_nodes.py \
  tests/test_node_index.py \
  tests/test_workflow_templates.py \
  tests/test_variant_template_robustness.py \
  tests/test_variant_template_sv_calling.py \
  tests/test_wgs_variant_template_sv_calling.py \
  tests/test_chip_seq_template_coverage_plot.py \
  tests/test_workflow_validation.py
```

Expected: all pass without installing or running heavy bioinformatics tools.

- [ ] **Step 3: Run static checks on changed Python files**

Run Ruff on the adapter, seven modules, runtime hooks, indexed consumers, and
focused tests. Expected: no findings.

- [ ] **Step 4: Independent review**

Review exact argv against the pinned 1.23.1 manpages and implementation files,
then review code quality. Fix every material finding and rerun targeted tests.

### Task 6: Prepare The Cloud Canary

**Files:**
- Create: `tests/fixtures/samtools_first_wave/tiny.sam`
- Create: `tests/fixtures/samtools_first_wave/workflow.json`
- Create: `docs/testing/samtools-first-wave-canary.md`

- [ ] **Step 1: Add a tiny synthetic workflow fixture**

The workflow performs view, collate, fixmate with `-m`, sort, markdup, index,
and flagstat on a few paired alignments. It returns both the BAM and BAI from
the index node, is small enough for a disposable worker, and contains no
private data.

- [ ] **Step 2: Validate locally without tool execution**

Run workflow validation and dry-run command planning. Expected: seven nodes in
order, explicit BAM and BAI outputs, and no shell command strings.

- [ ] **Step 3: Document the remote gate**

The canary runs on one disposable NA worker after the worker image contains this
commit. Record command, worker image digest, region/provider, Samtools version,
output SHA-256 values, duration, and cost. Do not release the nodes until local
and cloud output hashes match.
