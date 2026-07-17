# Samtools 1.23.1 Source Lock Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable, read-only upstream Git source-lock verifier and bind all 27 stable Samtools node IDs to the exact Samtools 1.23.1 tag, commit, manpages, dispatcher entries, and implementation source files before any NodeSpec is authored.

**Architecture:** A strict build-time source-lock model lives in the catalog foundation and verifies immutable Git objects without checking out or executing the tool. The Samtools family contributes one canonical JSON lock under its exclusive package path. The lock records source-file SHA-256 identities and operation ownership only; evidence claims, parameters, outputs, environment locks, smoke results, and maturity remain separate and quarantined.

**Tech Stack:** Python 3.11+, Pydantic v2, Git object plumbing, pytest, Ruff, mypy

---

## File Structure

```text
bionodulo/nodes/catalog/source_lock.py
scripts/verify_tool_source_lock.py
tests/catalog/test_source_lock.py

bionodulo/nodes/catalog/tools/samtools/
  __init__.py
  source-lock.json

tests/catalog/tools/samtools/
  test_source_lock.py
```

`source_lock.py` owns parsing, canonical serialization, digesting, and read-only Git verification. The Samtools package contains data only in this phase. Package `__init__.py` stays empty.

### Task 1: Implement the Generic Source-Lock Contract

**Files:**
- Create: `bionodulo/nodes/catalog/source_lock.py`
- Create: `tests/catalog/test_source_lock.py`

- [ ] **Step 1: Write failing strict-model tests**

Define tests for this public API:

```python
from bionodulo.nodes.catalog.source_lock import ToolSourceLock, canonical_source_lock_bytes


def test_source_lock_requires_canonical_order_and_closed_fields() -> None:
    value = minimal_lock()
    value["operations"] = list(reversed(value["operations"]))
    with pytest.raises(ValueError, match="operations.*canonical"):
        ToolSourceLock.model_validate(value)

    value = minimal_lock()
    value["branch"] = "develop"
    with pytest.raises(ValueError, match="extra"):
        ToolSourceLock.model_validate(value)


def test_source_lock_bytes_are_deterministic() -> None:
    lock = ToolSourceLock.model_validate(minimal_lock())
    assert canonical_source_lock_bytes(lock).endswith(b"\n")
    assert canonical_source_lock_bytes(lock) == canonical_source_lock_bytes(lock)
    assert lock.lock_digest().startswith("sha256:")
```

`minimal_lock()` must use a two-file temporary fixture: one text manual and one C source file. It must include an annotated tag object and exact commit, one command, and one stable node ID.

- [ ] **Step 2: Run the tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
```

Expected: collection fails because `bionodulo.nodes.catalog.source_lock` does not exist.

- [ ] **Step 3: Implement strict immutable models**

Create frozen, `extra="forbid"` models with these exact fields:

```text
ToolSourceFile
  source_id
  kind: documentation | implementation | dispatcher
  repository_path
  content_format: text | source_code
  content_sha256

ToolCommandBinding
  command
  documentation_source_ids
  dispatcher_source_id
  implementation_source_id
  implementation_symbol

ToolOperationBinding
  node_id
  upstream_commands

ToolSourceLock
  schema_version: 1
  tool_id
  tool_version
  repository_url
  release_tag
  tag_kind: annotated | lightweight
  tag_object
  commit
  release_date
  source_files
  command_bindings
  operations
```

Validation requirements:

- Git object IDs are exactly 40 lowercase hex characters. An annotated tag must resolve to a Git `tag` object that peels to `commit`; a lightweight tag must resolve directly to the declared commit.
- Repository URL is canonical HTTPS with no credentials, query, fragment, escapes, or mutable branch field.
- Repository paths are ASCII, repository-relative POSIX paths with no empty, dot, traversal, or backslash components.
- SHA-256 values use `sha256:` plus 64 lowercase hex characters.
- Source IDs, commands, symbols, and node IDs are canonical bounded identifiers.
- Source files sort by `source_id`; commands sort by `command`; operations sort by `node_id`.
- All IDs are unique, every reference resolves, every source is used, every command is owned exactly once, and every operation references at least one command.
- Documentation bindings may reference only documentation sources; implementation bindings may reference only implementation sources; dispatcher bindings may reference only dispatcher sources.
- `canonical_source_lock_bytes()` uses ASCII canonical JSON with sorted keys, compact separators, no NaN, and one trailing newline. `lock_digest()` hashes those exact bytes.

- [ ] **Step 4: Add adversarial model tests**

Tests must reject duplicate source/command/node IDs, missing references, orphan sources, a mutable tag such as `latest`, malformed URLs, traversal paths, wrong source kinds, duplicate upstream commands, noncanonical order, and self-consistent extra fields.

- [ ] **Step 5: Run focused tests**

Expected: all generic source-lock model tests pass.

- [ ] **Step 6: Commit the generic contract**

```bash
git add bionodulo/nodes/catalog/source_lock.py tests/catalog/test_source_lock.py
git commit -m "feat(catalog): add immutable upstream source locks"
```

### Task 2: Add Read-Only Git Object Verification

**Files:**
- Modify: `bionodulo/nodes/catalog/source_lock.py`
- Create: `scripts/verify_tool_source_lock.py`
- Modify: `tests/catalog/test_source_lock.py`

- [ ] **Step 1: Write failing Git-verification tests**

Create a temporary Git repository with one annotated tag, one manual, and one C file. Test:

```python
def test_verify_source_lock_reads_exact_git_objects_without_checkout_mutation(tmp_path: Path) -> None:
    repository, lock_path, expected_commit = tagged_fixture_repository(tmp_path)
    before = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=repository, check=True, capture_output=True
    ).stdout

    report = verify_tool_source_lock(repository, load_tool_source_lock(lock_path))

    after = subprocess.run(
        ["git", "status", "--porcelain=v1"], cwd=repository, check=True, capture_output=True
    ).stdout
    assert report.commit == expected_commit
    assert report.verified_files == 2
    assert before == after


def test_verify_source_lock_rejects_wrong_tag_object_or_file_digest(tmp_path: Path) -> None:
    repository, lock_path, _ = tagged_fixture_repository(tmp_path)
    value = json.loads(lock_path.read_text(encoding="utf-8"))
    value["tag_object"] = "0" * 40
    with pytest.raises(SourceLockVerificationError, match="tag object"):
        verify_tool_source_lock(repository, ToolSourceLock.model_validate(value))

    value = json.loads(lock_path.read_text(encoding="utf-8"))
    value["source_files"][0]["content_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(SourceLockVerificationError, match="content digest"):
        verify_tool_source_lock(repository, ToolSourceLock.model_validate(value))
```

- [ ] **Step 2: Verify RED**

Expected: tests fail because `verify_tool_source_lock()` and the CLI do not exist.

- [ ] **Step 3: Implement verification with Git plumbing only**

The verifier must use explicit argument arrays and these read-only operations:

```text
git rev-parse --verify refs/tags/<release_tag>^{object}
git cat-file -t <tag_object>
git rev-parse <tag_object>^{commit}
git cat-file blob <commit>:<repository_path>
```

It must never run checkout, switch, reset, clean, fetch, pull, install, build, or the upstream executable. It verifies the declared tag kind and object, peeled commit, every exact file SHA-256, and that each declared implementation symbol occurs as exactly one top-level C function definition in its declared implementation file. The C selector accepts only a line beginning `int <symbol>(` and rejects missing or ambiguous matches; it is a source-lock sanity check, not the later schema-v2 evidence selector.

Return a strict `SourceLockVerificationReport` containing only tool/version, tag object, commit, lock digest, verified file count, verified command count, and verified operation count.

- [ ] **Step 4: Implement the CLI**

```bash
.venv/bin/python scripts/verify_tool_source_lock.py \
  --repository /path/to/upstream/git/repository \
  --lock bionodulo/nodes/catalog/tools/samtools/source-lock.json
```

The CLI loads exact bytes, rejects duplicate JSON keys, requires canonical bytes, verifies the repository, prints one summary line, and exits nonzero on any mismatch. It does not write files.

- [ ] **Step 5: Add bounds and command-injection tests**

Reject lock files over 1 MiB, JSON nesting over 64 levels, more than 4,096 sources/commands/operations, duplicate JSON keys, noncanonical bytes, NUL/control characters, and release tags or paths that could be interpreted as Git options. Pass `--` where Git supports it and reject values beginning with `-`.

- [ ] **Step 6: Run focused checks and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
.venv/bin/ruff check bionodulo/nodes/catalog/source_lock.py scripts/verify_tool_source_lock.py tests/catalog/test_source_lock.py
.venv/bin/mypy bionodulo/nodes/catalog/source_lock.py scripts/verify_tool_source_lock.py
git add bionodulo/nodes/catalog/source_lock.py scripts/verify_tool_source_lock.py tests/catalog/test_source_lock.py
git commit -m "feat(catalog): verify pinned upstream git sources"
```

### Task 3: Lock All 27 Samtools Operations

**Files:**
- Create: `bionodulo/nodes/catalog/tools/samtools/__init__.py`
- Create: `bionodulo/nodes/catalog/tools/samtools/source-lock.json`
- Create: `tests/catalog/tools/samtools/test_source_lock.py`

- [ ] **Step 1: Write the failing 27-ID and ownership tests**

The test loads `baseline-ledger.json`, the reviewed migration queue, and the Samtools lock. It asserts:

```python
EXPECTED_NODE_COMMANDS = {
    "samtools_ampliconclip": ("ampliconclip", "sort"),
    "samtools_bam_to_cram": ("view",),
    "samtools_bam_to_sam": ("view",),
    "samtools_bedcov": ("bedcov",),
    "samtools_calmd": ("calmd",),
    "samtools_collate": ("collate",),
    "samtools_consensus": ("consensus",),
    "samtools_coverage": ("coverage",),
    "samtools_cram_to_bam": ("view",),
    "samtools_depth": ("depth",),
    "samtools_faidx": ("faidx",),
    "samtools_fastx": ("fasta", "fastq"),
    "samtools_fixmate": ("fixmate",),
    "samtools_flagstat": ("flagstat",),
    "samtools_idxstats": ("idxstats",),
    "samtools_index": ("index",),
    "samtools_markdup": ("markdup",),
    "samtools_merge": ("merge",),
    "samtools_mpileup": ("mpileup",),
    "samtools_phase": ("phase",),
    "samtools_reheader": ("reheader",),
    "samtools_sam_to_bam": ("sort", "view"),
    "samtools_slice_bam": ("sort", "view"),
    "samtools_sort": ("sort",),
    "samtools_split": ("split",),
    "samtools_stats": ("stats",),
    "samtools_view": ("view",),
}
```

The exact set must equal the 27 `samtools_` baseline IDs and the confirmed Samtools queue lane. Every operation remains `quarantined` and `evidence_pending`; this lock must not mutate catalog maturity.

- [ ] **Step 2: Verify RED**

Expected: the Samtools lock file and package do not exist.

- [ ] **Step 3: Author the exact upstream identity**

The lock must contain:

```text
tool_id: samtools
tool_version: 1.23.1
repository_url: https://github.com/samtools/samtools
release_tag: 1.23.1
tag_kind: annotated
tag_object: 4ac78a7e9938dbef3c6f97d549758feceb0252db
commit: 6efb9b6da35224cf804921dedecf9fb8f411365d
release_date: 2026-03-18
```

Add the dispatcher `bamtk.c`, canonical manpages, and implementation files with the SHA-256 values independently verified from that commit. `samtools-fastq.1` is an alias containing `.so samtools-fasta.1`; both files are locked. The `fastq` command binding references both alias and canonical manual source IDs, while `samtools-fasta.1` is the canonical documentation source for both `fasta` and `fastq` commands.

Use these command-to-source bindings:

| Command | Documentation path | Implementation path | Symbol |
| --- | --- | --- | --- |
| `ampliconclip` | `doc/samtools-ampliconclip.1` | `bam_ampliconclip.c` | `amplicon_clip_main` |
| `bedcov` | `doc/samtools-bedcov.1` | `bedcov.c` | `main_bedcov` |
| `calmd` | `doc/samtools-calmd.1` | `bam_md.c` | `bam_fillmd` |
| `collate` | `doc/samtools-collate.1` | `bamshuf.c` | `main_bamshuf` |
| `consensus` | `doc/samtools-consensus.1` | `bam_consensus.c` | `main_consensus` |
| `coverage` | `doc/samtools-coverage.1` | `coverage.c` | `main_coverage` |
| `depth` | `doc/samtools-depth.1` | `bam2depth.c` | `main_depth` |
| `faidx` | `doc/samtools-faidx.1` | `faidx.c` | `faidx_main` |
| `fasta` | `doc/samtools-fasta.1` | `bam_fastq.c` | `main_bam2fq` |
| `fastq` | `doc/samtools-fasta.1` | `bam_fastq.c` | `main_bam2fq` |
| `fixmate` | `doc/samtools-fixmate.1` | `bam_mate.c` | `bam_mating` |
| `flagstat` | `doc/samtools-flagstat.1` | `bam_stat.c` | `bam_flagstat` |
| `idxstats` | `doc/samtools-idxstats.1` | `bam_index.c` | `bam_idxstats` |
| `index` | `doc/samtools-index.1` | `bam_index.c` | `bam_index` |
| `markdup` | `doc/samtools-markdup.1` | `bam_markdup.c` | `bam_markdup` |
| `merge` | `doc/samtools-merge.1` | `bam_sort.c` | `bam_merge` |
| `mpileup` | `doc/samtools-mpileup.1` | `bam_plcmd.c` | `bam_mpileup` |
| `phase` | `doc/samtools-phase.1` | `phase.c` | `main_phase` |
| `reheader` | `doc/samtools-reheader.1` | `bam_reheader.c` | `main_reheader` |
| `sort` | `doc/samtools-sort.1` | `bam_sort.c` | `bam_sort` |
| `split` | `doc/samtools-split.1` | `bam_split.c` | `main_split` |
| `stats` | `doc/samtools-stats.1` | `stats.c` | `main_stats` |
| `view` | `doc/samtools-view.1` | `sam_view.c` | `main_samview` |

Every command also references dispatcher source `bamtk.c`. Do not use the legacy BioNodulo wrapper, Galaxy XML, blogs, or mutable HTML as source-lock authority.

- [ ] **Step 4: Run structural tests**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
```

Expected: exact 27-ID equality, exact command mapping, canonical JSON, and no maturity changes.

- [ ] **Step 5: Verify against the pinned local clone**

Run on this host without installing or executing Samtools:

```bash
.venv/bin/python scripts/verify_tool_source_lock.py \
  --repository /tmp/bionodulo-samtools-1.23.1 \
  --lock bionodulo/nodes/catalog/tools/samtools/source-lock.json
```

Expected summary:

```text
samtools 1.23.1: 27 operations and 23 commands verified at 6efb9b6da35224cf804921dedecf9fb8f411365d
```

- [ ] **Step 6: Commit the family lock**

```bash
git add bionodulo/nodes/catalog/tools/samtools tests/catalog/tools/samtools
git commit -m "feat(catalog): lock samtools 1.23.1 sources"
```

### Task 4: Independent Review and Handoff

**Files:**
- Verify all files above

- [ ] **Step 1: Run full lightweight verification**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog
.venv/bin/ruff check bionodulo/nodes/catalog/source_lock.py bionodulo/nodes/catalog/tools/samtools scripts/verify_tool_source_lock.py tests/catalog
.venv/bin/mypy bionodulo/nodes/catalog/source_lock.py bionodulo/nodes/catalog/tools/samtools scripts/verify_tool_source_lock.py
```

- [ ] **Step 2: Run specification review**

Verify exact 27-ID coverage, no mutable refs, correct tag peeling, read-only Git behavior, exact source hashes, command/source ownership, and continued quarantine.

- [ ] **Step 3: Run a separate code-quality review**

Review parser bounds, duplicate-key handling, Git argument safety, canonical byte identity, error specificity, test realism, and separation from evidence/maturity responsibilities.

- [ ] **Step 4: Fix confirmed findings with failing regression tests**

Do not write NodeSpecs in this phase. The next Samtools plan starts only after this source lock is approved and the catalog environment foundation can produce a verified `samtools==1.23.1` Pixi lock for each supported platform.
