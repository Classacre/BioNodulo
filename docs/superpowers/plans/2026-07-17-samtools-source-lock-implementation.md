# Samtools 1.23.1 Source Lock Implementation Plan

> **Status: Superseded on 2026-07-18.** The user directed the rebuild away from
> generic verifier and environment hardening and toward quarantined runtime
> nodes. Do not execute this plan. Use
> `docs/superpowers/plans/2026-07-18-samtools-first-wave-implementation.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a reusable, read-only upstream Git source-lock verifier and bind all 27 stable Samtools node IDs to exact Samtools 1.23.1 Git objects, manpages, dispatcher ownership, and implementation files before any NodeSpec is authored.

**Architecture:** The catalog integration owner implements a format-neutral build-time source lock that proves Git revision and file identities without checking out, building, installing, or executing a tool. The Samtools lane adds a narrow verifier for its C dispatcher and opaque entrypoint markers, plus one canonical lock under its exclusive package. A source lock is not schema-v2 evidence: parameter/output claims still require compiler-owned byte or language-aware locators in the subsequent evidence plan, and every Samtools node remains quarantined.

**Tech Stack:** Python 3.11+, Pydantic v2, Git object plumbing, pytest, Ruff, mypy

---

## Execution Preconditions

- Tasks 1-2 are shared foundation work and are owned by the catalog integration owner, not a family agent.
- Tasks 3-4 run only after the migration queue has independent specification and quality approval and its reviewed commit is merged into this branch as preserved ancestry. The approved queue is commit `05db7fe84656624ae85abde713988d28f541c520`; the baseline-ledger aggregate SHA-256 is `75643eb83592eccd492d65d3c53b40d45cc6d0e04c2363f5572aeb3492927210`; the canonical queue digest is `sha256:e3930ac5de25d18b2d70340c680adc4de318a39240abc2b18859ccefa84486fd`; the rules digest is `sha256:76ff27225d51f5b0cbb0a58361b7c0419bc77cd4db39617617ab81274157e6c2`; and the artifact file SHA-256 is `34e1a5a6cc1811ffc23a49b08819b09f1d782b074b711c8be02f92b90052c781`. Do not cherry-pick that commit, copy its artifact, or regenerate a replacement. Before Task 3, run this integration gate from a full-history checkout: `git rev-parse --is-shallow-repository` must print exactly `false`, then `git merge-base --is-ancestor 05db7fe84656624ae85abde713988d28f541c520 HEAD` must exit zero. All 943 assignments must still have `disposition == "quarantined"` and `contract_status == "evidence_pending"`, and all four reviewed content identities must match. Source exports and shallow clones run the portable content tests but cannot satisfy or replace this ancestry gate. If any identity or queue state changes after the ancestry merge, amend and re-review this plan before execution.
- Use the existing repository environment from this linked worktree through `../../.venv/bin/python`, `../../.venv/bin/ruff`, and `../../.venv/bin/mypy`. Do not create a second environment inside the worktree.
- The pinned upstream repository is available read-only at `/tmp/bionodulo-samtools-1.23.1`. Do not fetch, build, install, or run Samtools on this host.

## File Structure

```text
bionodulo/nodes/catalog/source_lock.py
scripts/verify_tool_source_lock.py
tests/catalog/test_source_lock.py

bionodulo/nodes/catalog/tools/samtools/
  __init__.py
  source-lock.json
  verification.py

scripts/verify_samtools_source_lock.py

tests/catalog/tools/samtools/
  test_source_lock.py
```

`source_lock.py` owns strict parsing, canonical serialization, digesting, and read-only Git file verification. `tools/samtools/verification.py` owns only the pinned Samtools dispatcher/opaque-marker sanity checks. Package `__init__.py` remains empty.

### Task 1: Implement the Generic Source-Lock Contract

**Owner:** Catalog integration owner

**Files:**
- Create: `bionodulo/nodes/catalog/source_lock.py`
- Create: `tests/catalog/test_source_lock.py`

- [ ] **Step 1: Write all strict-model failure tests**

Start with this public API:

```python
from bionodulo.nodes.catalog.source_lock import (
    AnnotatedTagPin,
    LightweightTagPin,
    ToolSourceLock,
    canonical_source_lock_bytes,
    load_tool_source_lock,
)
```

Tests must be RED for every behavior before implementation:

```python
def test_source_lock_requires_canonical_order_and_closed_fields() -> None:
    value = minimal_lock()
    value["operations"] = tuple(reversed(value["operations"]))
    with pytest.raises(ValueError, match="operations.*canonical"):
        ToolSourceLock.model_validate(value)

    value = minimal_lock()
    value["branch"] = "develop"
    with pytest.raises(ValueError, match="extra"):
        ToolSourceLock.model_validate(value)


def test_tag_pin_is_a_closed_discriminated_union() -> None:
    annotated = minimal_lock()["revision"]
    assert isinstance(AnnotatedTagPin.model_validate(annotated), AnnotatedTagPin)

    lightweight = {
        "kind": "lightweight",
        "release_tag": "v1.0.0",
        "commit": "2" * 40,
    }
    assert isinstance(LightweightTagPin.model_validate(lightweight), LightweightTagPin)

    with pytest.raises(ValueError, match="extra"):
        LightweightTagPin.model_validate({**lightweight, "tag_object": "3" * 40})


def test_command_bindings_are_unique_but_operations_may_reuse_them() -> None:
    value = minimal_lock()
    value["operations"] += (
        {"node_id": "second_node", "upstream_commands": ("view",)},
    )
    value["operations"] = tuple(
        sorted(value["operations"], key=lambda item: item["node_id"])
    )
    lock = ToolSourceLock.model_validate(value)
    assert [item.upstream_commands for item in lock.operations] == [("view",), ("view",)]

    duplicate = minimal_lock()
    duplicate["command_bindings"] += (duplicate["command_bindings"][0],)
    with pytest.raises(ValueError, match="command.*unique"):
        ToolSourceLock.model_validate(duplicate)


def test_source_lock_collections_are_deeply_immutable() -> None:
    lock = ToolSourceLock.model_validate(minimal_lock())

    assert isinstance(lock.source_files, tuple)
    assert isinstance(lock.command_bindings, tuple)
    assert isinstance(lock.operations, tuple)
    assert isinstance(lock.source_files[0].roles, tuple)
    assert isinstance(lock.command_bindings[0].documentation_source_ids, tuple)
    assert isinstance(lock.operations[0].upstream_commands, tuple)

    with pytest.raises((AttributeError, TypeError, ValidationError)):
        lock.operations += lock.operations


@pytest.mark.parametrize("schema_version", (True, "1"))
def test_schema_version_rejects_bool_and_string_coercion(schema_version: object) -> None:
    value = minimal_lock()
    value["schema_version"] = schema_version

    with pytest.raises(ValidationError):
        ToolSourceLock.model_validate(value)


def test_model_copy_uses_the_repository_validated_copy_contract() -> None:
    lock = ToolSourceLock.model_validate(minimal_lock())

    with pytest.raises(ValidationError):
        lock.model_copy(update={"schema_version": "1"})
```

`minimal_lock()` and every other Python-mode fixture use tuples for tuple-typed fields. Add `source_lock_fixture_contract` tests that inspect the raw fixture keys, tuple shapes, reference targets, and canonical JSON test bytes; these tests must pass after the collecting module exists and before the behavior-specific RED run. Add RED showing that direct `ToolSourceLock.model_validate()` rejects Python lists rather than silently converting them. Canonical JSON arrays are covered separately through `load_tool_source_lock()`.

Also test duplicate source IDs, repository paths, command IDs, node IDs, and per-item references; missing/orphan references; noncanonical arrays; traversal paths; wrong source roles; malformed URLs/digests/Git IDs; duplicate roles; and self-consistent unknown fields. Add explicit RED for empty `source_files`, `command_bindings`, and `operations`, plus empty nested `roles`, `documentation_source_ids`, and `upstream_commands`; zero-length and over-128-byte `tool_version`; and each unsafe key `__proto__`, `prototype`, or `constructor` nested inside every accepted JSON object shape, not only at the top level. Define JSON container depth in the tests: the root array or object is depth 1, each nested array or object increments depth by one, and scalars do not increment it. Add pure-object, pure-array, and alternating object/array fixtures proving depth 64 passes the depth preflight while opening a container at depth 65 fails with the exact depth error. One source ID and one command binding may be referenced by many command or operation bindings.

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
```

Expected: collection fails because `bionodulo.nodes.catalog.source_lock` does not exist. Record this import RED before creating the collecting stubs.

- [ ] **Step 3: Add the smallest collecting API stubs and prove behavior-specific RED**

Create only enough temporary surface for test collection; do not add validators, canonicalization, or loader behavior yet:

```python
from pydantic import BaseModel, ConfigDict


class _CollectingSourceLockModel(BaseModel):
    model_config = ConfigDict(extra="allow")


class AnnotatedTagPin(_CollectingSourceLockModel):
    kind: object
    release_tag: object
    tag_object: object
    commit: object


class LightweightTagPin(_CollectingSourceLockModel):
    kind: object
    release_tag: object
    commit: object


class ToolSourceFile(_CollectingSourceLockModel):
    source_id: object
    roles: tuple[object, ...]
    repository_path: object
    content_format: object
    content_sha256: object


class ToolCommandBinding(_CollectingSourceLockModel):
    command: object
    documentation_source_ids: tuple[object, ...]
    implementation_source_id: object
    entrypoint: object


class ToolOperationBinding(_CollectingSourceLockModel):
    node_id: object
    upstream_commands: tuple[object, ...]


class ToolSourceLock(_CollectingSourceLockModel):
    schema_version: object
    tool_id: object
    tool_version: object
    repository_url: object
    revision: AnnotatedTagPin | LightweightTagPin
    dispatcher_source_id: object
    source_files: tuple[ToolSourceFile, ...]
    command_bindings: tuple[ToolCommandBinding, ...]
    operations: tuple[ToolOperationBinding, ...]

    def lock_digest(self) -> str:
        raise NotImplementedError("source-lock digest is not implemented")


def canonical_source_lock_bytes(lock: ToolSourceLock) -> bytes:
    raise NotImplementedError("canonical source-lock bytes are not implemented")


def load_tool_source_lock(content: bytes) -> ToolSourceLock:
    raise NotImplementedError("source-lock loading is not implemented")
```

Rerun the entire Task 1 file:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/catalog/test_source_lock.py -k source_lock_fixture_contract
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
```

Expected: the fixture-contract subset still passes and full collection succeeds. Every strict-model, canonical-serialization, loader, unsafe-key, and depth behavior test reaches its intended assertion and fails because the permissive/`NotImplementedError` stub lacks that behavior. No test may remain RED because of a missing import, missing attribute, malformed fixture, or collection error; split or strengthen any test that accidentally passes under the stub. Remove the temporary permissive base while implementing Step 4.

- [ ] **Step 4: Implement strict immutable models**

Build every source-lock model on the repository's `_StrictFrozenModel` validated-copy contract, not directly on Pydantic `BaseModel`. That base supplies frozen, strict, `extra="forbid"`, `validate_default=True`, `revalidate_instances="always"` models and a repository-owned `model_copy()` override that dumps, applies updates, and calls `type(self).model_validate(...)`. Stock Pydantic `model_copy(update=...)` does not validate; do not rely on or imply otherwise. Create models with these exact fields:

```text
AnnotatedTagPin
  kind: annotated
  release_tag
  tag_object
  commit

LightweightTagPin
  kind: lightweight
  release_tag
  commit

ToolSourceFile
  source_id
  roles: documentation | implementation | dispatcher (nonempty canonical tuple)
  repository_path
  content_format: text | source_code
  content_sha256

ToolCommandBinding
  command
  documentation_source_ids
  implementation_source_id
  entrypoint

ToolOperationBinding
  node_id
  upstream_commands

ToolSourceLock
  schema_version: 1
  tool_id
  tool_version
  repository_url
  revision: AnnotatedTagPin | LightweightTagPin
  dispatcher_source_id
  source_files
  command_bindings
  operations
```

Validation requirements:

- `schema_version` is the strict integer literal `1`; boolean `True` and string `"1"` are invalid in Python and JSON inputs.
- Git object IDs are exactly 40 lowercase hexadecimal characters.
- Tool IDs, source IDs, and command IDs match `^[a-z][a-z0-9_.-]{0,127}$` in ASCII.
- `tool_version` reuses the repository `ExactVersion` and `_validate_exact_version` contract: 1-128 characters, an exact upstream version, and never an unbounded or mutable marker such as `latest`.
- Stable node IDs are 1-128 printable ASCII bytes with no outer whitespace and match `^[\x21-\x7e](?:[\x20-\x7e]{0,126}[\x21-\x7e])?$`; Task 4 additionally requires exact baseline-ledger membership.
- A release tag is at most 128 ASCII bytes and matches `^[0-9A-Za-z][0-9A-Za-z._-]{0,127}$`; it must also pass `git check-ref-format` when verified. Do not reject names based on words such as `latest`; exact ref/object identity is the source-lock guarantee.
- Repository URL is canonical HTTPS with no credentials, query, fragment, escapes, or mutable branch field.
- Repository paths are unique ASCII repository-relative POSIX paths of at most 1,024 bytes with no empty, dot, traversal, control, or backslash components.
- SHA-256 values use `sha256:` plus 64 lowercase hexadecimal characters.
- `source_files`, `command_bindings`, `operations`, `roles`, `documentation_source_ids`, and `upstream_commands` are all nonempty. Source files sort by `source_id`; commands by `command`; operations by `node_id`; source roles, documentation source IDs, and upstream commands are unique sorted tuples.
- Every source and command binding is referenced at least once. A source may serve multiple roles and bindings. Each command has one binding, while any number of operations may reuse that binding.
- Every reference resolves. Documentation references require a documentation role, implementation references require an implementation role, and the dispatcher source requires a dispatcher role.
- `canonical_source_lock_bytes()` uses ASCII canonical JSON with sorted keys, compact separators, no NaN, and one trailing newline. `lock_digest()` hashes those exact bytes.
- `load_tool_source_lock()` accepts at most 1 MiB, rejects BOM/non-UTF-8/duplicate keys, rejects `__proto__`, `prototype`, and `constructor` recursively at every object depth, validates schema version explicitly without coercion, and requires the supplied bytes to equal canonical bytes. Its depth walker uses the test definition exactly: root container depth 1, nested arrays/objects increment, scalars do not; depth 64 is accepted and attempting to open depth 65 is rejected, including mixed arrays and objects.
- Preserve strict Python-mode tuple validation. After the bounded duplicate-key/unsafe-key/depth preflight, parse the same raw bytes with Pydantic JSON mode (`ToolSourceLock.model_validate_json(...)`) so canonical JSON arrays become immutable tuples without making Python `model_validate()` accept lists. If implementation constraints require `mode="before"` validators instead, gate them narrowly to loader-supplied JSON context and add RED proving direct Python list inputs still fail.
- Add regression tests showing the inherited repository `model_copy()` rejects invalid scalar and nested updates, including `schema_version="1"` and an empty required collection. Never use an unvalidated Pydantic copy to build fixtures or trusted results.

- [ ] **Step 5: Run focused tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
../../.venv/bin/ruff check bionodulo/nodes/catalog/source_lock.py tests/catalog/test_source_lock.py
../../.venv/bin/mypy bionodulo/nodes/catalog/source_lock.py
git add bionodulo/nodes/catalog/source_lock.py tests/catalog/test_source_lock.py
git commit -m "feat(catalog): add immutable upstream source locks"
```

### Task 2: Add Bounded Read-Only Git Object Verification

**Owner:** Catalog integration owner

**Files:**
- Modify: `bionodulo/nodes/catalog/source_lock.py`
- Create: `scripts/verify_tool_source_lock.py`
- Modify: `tests/catalog/test_source_lock.py`

- [ ] **Step 1: Write all verifier and Git-safety failure tests**

Create temporary Git repositories with annotated and lightweight tags. Before production changes, record RED for:

```python
def test_verify_source_lock_reads_exact_git_objects_without_mutation(tmp_path: Path) -> None:
    repository, lock_path, expected_commit = tagged_fixture_repository(tmp_path)
    before = repository_snapshot(repository)

    lock = load_tool_source_lock(lock_path.read_bytes())
    verified = verify_tool_source_lock(repository, lock)

    assert verified.lock == lock
    assert verified.report.commit == expected_commit
    assert verified.report.verified_files == 2
    assert tuple(verified.source_bytes) == tuple(source.source_id for source in lock.source_files)
    with pytest.raises(TypeError):
        verified.source_bytes[lock.source_files[0].source_id] = b"forged"
    assert repository_snapshot(repository) == before


def test_verify_source_lock_rejects_wrong_tag_object_or_file_digest(tmp_path: Path) -> None:
    repository, value = tagged_fixture_repository_value(tmp_path)
    value["revision"]["tag_object"] = "0" * 40
    with pytest.raises(SourceLockVerificationError, match="tag object"):
        verify_tool_source_lock(repository, ToolSourceLock.model_validate(value))

    value = tagged_fixture_repository_value(tmp_path)[1]
    value["source_files"][0]["content_sha256"] = "sha256:" + "0" * 64
    with pytest.raises(SourceLockVerificationError, match="content digest"):
        verify_tool_source_lock(repository, ToolSourceLock.model_validate(value))
```

`repository_snapshot()` must not be a `git status` alias. For these bounded temporary fixtures it records every worktree entry, including ignored and untracked files, and the resolved Git directory and common Git directory, including path, file type, permission bits, symlink target or regular-file digest, `HEAD`, refs, `packed-refs`, index/config/log metadata, lock files, and every object-database entry. Exclude access time only. Compare this snapshot before and after every success, mismatch, timeout, and bound failure so ignored-file, ref, metadata, and object-database writes are detectable.

Additional RED tests must cover: lightweight tag with an unexpected ref target; invalid ref syntax containing `~`, `^`, `:`, `@{`, or `..`; injected `GIT_DIR`, `GIT_WORK_TREE`, object directory, alternate object directory, namespace, replace-ref, `GIT_CONFIG*`, `GIT_TRACE*`, and `GIT_TRACE2*` environment variables; active replace objects; exact child-environment equality in a recording fake-Git process, including `GIT_NO_LAZY_FETCH=1`, `GIT_OPTIONAL_LOCKS=0`, and `GIT_NO_REPLACE_OBJECTS=1` on every invocation; hostile trace targets remaining absent; a missing promisor object failing without any remote invocation; Git per-command timeout; a total aggregate deadline exceeded by individually sub-timeout commands; stdout or stderr overflow; a source blob over 8 MiB; aggregate verified source bytes over 64 MiB; more than 4,096 source files; a `120000 blob` symlink and a `100755 blob` executable where only `100644 blob` is allowed; attempted bytecode/cache creation; and a changed working tree that remains byte-for-byte unchanged after verification. Every case uses the full repository snapshot rather than claiming `git status` covers ignored files, refs, repository metadata, or objects.

Write CLI tests in this same RED batch. Import the initially absent verifier functions inside individual tests rather than at collection time, so the missing-script subprocess cases execute during the first RED run. Add fixture-contract tests that use the completed Task 1 loader and direct bounded Git fixture inspection, but do not import Task 2 symbols; these must prove annotated/lightweight refs, source bytes, expected modes, and repository snapshots are internally consistent before verifier behavior is attempted. Invoke every Python subprocess with `PYTHONDONTWRITEBYTECODE=1` and an isolated cache prefix outside the repository, and assert the repository snapshot is unchanged. A temporary-repository success case must assert exit zero, empty stderr, and exact stdout in this format, including its one trailing newline:

```text
<tool_id> <tool_version>: <verified_files> source file identities verified at <commit>; <declared_commands> commands and <declared_operations> operations declared; lock <lock_digest>
```

Every domain failure exits `1`, produces empty stdout, emits exactly one public error line with no traceback, and preserves both repositories. Pin these generic CLI messages exactly; `<source_id>` is replaced only by the already validated ASCII source ID:

| Category | Exact stderr |
| --- | --- |
| Lock path/open/symlink/non-regular failure | `source-lock verification failed: lock file is not a stable regular file\n` |
| Lock descriptor metadata race | `source-lock verification failed: lock file changed while reading\n` |
| Lock size | `source-lock verification failed: lock exceeds 1048576 bytes\n` |
| Canonical input | `source-lock verification failed: lock bytes are not canonical\n` |
| Per-command timeout | `source-lock verification failed: git command timed out\n` |
| Total deadline | `source-lock verification failed: aggregate verification deadline exceeded\n` |
| Git stdout overflow | `source-lock verification failed: git stdout limit exceeded\n` |
| Git stderr overflow | `source-lock verification failed: git stderr limit exceeded\n` |
| Tag identity | `source-lock verification failed: tag ref target mismatch\n` |
| Tree mode/path identity | `source-lock verification failed: source path is not a 100644 blob for <source_id>\n` |
| Returned source-key integrity | `source-lock verification failed: source bytes key mismatch\n` |
| Source content integrity | `source-lock verification failed: content digest mismatch for <source_id>\n` |

Tests cover every row, including open/race injection, per-command and total timeout as distinct cases, and both output-overflow channels. An argparse usage error alone retains argparse's exit `2` and usage stderr. Invoke `scripts/verify_tool_source_lock.py` through `subprocess.run()` before that script exists and record the expected missing-script RED failure.

- [ ] **Step 2: Run verifier tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/catalog/test_source_lock.py -k fixture_contract
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
```

Expected: the fixture-contract subset passes first. The full run then fails because verifier/result/deadline symbols and the generic CLI script are absent; record those missing-symbol/script failures before adding stubs.

- [ ] **Step 3: Add minimal verifier/result/CLI stubs and prove behavior-specific RED**

Add temporary exported shells in `source_lock.py` for `VerificationDeadline`, `SourceLockVerificationError`, `SourceLockVerificationReport`, `VerifiedToolSources`, and `verify_tool_source_lock(...)`; the verifier raises `NotImplementedError("Git source verification is not implemented")`. Add `scripts/verify_tool_source_lock.py` with argument parsing and `sys.dont_write_bytecode = True` before project imports, but have `main()` raise `NotImplementedError("source-lock CLI is not implemented")`. Do not add Git calls, result construction, error translation, or output formatting yet.

Rerun the fixture subset and then the full behavior batch:

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/catalog/test_source_lock.py -k fixture_contract
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
```

Expected: fixture-contract tests still pass; all verifier, timeout, environment, tree-mode, snapshot, result-integrity, lock-race, and CLI tests collect and reach their intended assertions, then fail on stub behavior. No failure may be a missing symbol/script or malformed fixture. Remove all `NotImplementedError` stubs while implementing Steps 4-5.

- [ ] **Step 4: Implement safe read-only verification**

Resolve the Git executable from the trusted `os.defpath` once, then invoke its absolute path with an explicit argument array. Build the child environment from an explicit minimal mapping rather than copying or filtering `os.environ`: fixed `PATH=os.defpath`, `LC_ALL=C`, `LANG=C`, an isolated non-repository `HOME`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_CONFIG_GLOBAL` pointing to `os.devnull`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_NO_LAZY_FETCH=1`, `GIT_OPTIONAL_LOCKS=0`, `GIT_TERMINAL_PROMPT=0`, and `PYTHONDONTWRITEBYTECODE=1`. Do not inherit any other `GIT_*` variable, especially repository/object/namespace/config selection, `GIT_CONFIG*`, `GIT_TRACE*`, or `GIT_TRACE2*`. Use `git --no-replace-objects -C <repo>` and never interpolate a revision expression from unchecked text.

Implement `VerificationDeadline` around one fixed `time.monotonic_ns()` expiry. A top-level direct library call may create it only when no deadline is supplied; a composed caller always supplies one. The generic CLI creates exactly one 60-second deadline immediately after argument parsing and passes that same object through lock reading, every Git spawn/output drain, and every blob hash. `verify_tool_source_lock(..., deadline=...)` never replaces or extends a supplied deadline. Each Git process also has a ten-second cap and bounded stdout/stderr capture; non-blob plumbing output and stderr are each capped at 64 KiB. Before every process, pass `min(10 seconds, aggregate time remaining)` and fail before launching when no time remains. Stream bounded outputs, check the same deadline while draining/hashing, and terminate/reap on timeout or overflow; never use an unbounded `subprocess.run(capture_output=True)` path.

Verification sequence:

```text
git check-ref-format refs/tags/<release_tag>
git show-ref --verify --hash refs/tags/<release_tag>
git cat-file -t <exact object ID>
git rev-parse --verify <exact annotated tag object>^{commit}
git --literal-pathspecs ls-tree -z --full-tree <exact commit> -- <validated repository path>
git cat-file -s <exact blob ID from ls-tree>
git cat-file blob <exact blob ID from ls-tree>
```

Use `--end-of-options`, `--literal-pathspecs`, and `--` where supported. For an annotated pin, the exact ref target must equal `tag_object`, `cat-file -t` must return `tag`, and peeling must equal `commit`. For a lightweight pin, the exact ref target and object type must be the declared `commit`. Parse the NUL-delimited `ls-tree` record structurally, require exactly one record for the exact repository path, and require exact tree identity `100644 blob <40-lowercase-hex-object-id>`; a symlink is also a Git blob but mode `120000` and must fail, as must executable mode `100755`. Read by the resulting exact blob ID. Check size before reading, stream/hash at most 8 MiB per blob and 64 MiB across the lock, allow at most 4,096 files, and compare every SHA-256 within the aggregate deadline. The verifier does not parse a language or assert biological/CLI semantics.

Return `VerifiedToolSources`, a frozen result containing the exact validated `ToolSourceLock` value, a strict `SourceLockVerificationReport`, and a read-only source-ID-to-`bytes` mapping. Production code constructs it only inside `verify_tool_source_lock()`; downstream consumers nevertheless recheck its full integrity rather than treating Python constructor privacy as a security boundary. The mapping's keys must equal the lock's exact canonical source-ID sequence with no missing, extra, reordered, or substituted ID, and each fresh immutable `bytes` value must be rehashed against that source file's declared `content_sha256` before the result is returned. Use a `MappingProxyType` over a fresh dictionary with the same 8 MiB per-file and 64 MiB aggregate bounds. The report contains only tool/version, tag kind, optional tag object, commit, lock digest, verified file count, declared command count, and declared operation count. Tests require the exact source ID/bytes/digest binding, `verified.lock.lock_digest() == verified.report.lock_digest`, tuple-backed nested lock collections, frozen nested models, and assignment failure for the returned byte mapping. Lock/report digest equality alone is insufficient because it does not authenticate a replaceable `source_bytes` field. The generic CLI discards source contents after printing the report; family verifiers consume the complete result synchronously without reopening paths.

- [ ] **Step 5: Implement and test the non-writing CLI**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/verify_tool_source_lock.py \
  --repository /path/to/upstream/git/repository \
  --lock /absolute/path/to/source-lock.json
```

Require an absolute, lexically normalized lock path with no NUL, `.` or `..` components. `lstat` first and reject a symlink or non-regular entry before a potentially blocking open. Open it once with `os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)` where those flags exist; immediately `fstat` and require the pre-open path identity and opened descriptor to match. Where `O_NOFOLLOW` is unavailable, this `lstat`/`fstat` identity check is mandatory. Retain the same descriptor and loop on `os.read()` from it only, requesting no more than the remaining portion of the 1,048,577-byte cap until EOF or overflow. Then `fstat` the same descriptor and `lstat` the path again. Require all observed `(st_dev, st_ino, st_mode, st_nlink, st_size, st_mtime_ns, st_ctime_ns)` values and the regular-file type to remain identical; reject path replacement, descriptor metadata change, inconsistent EOF/read state, or more than 1 MiB returned. Never reopen for content or use `Path.read_bytes()`. RED covers short reads, final-component symlinks, directories/FIFOs, open failure, path swap, truncate/append/metadata change during read, and platforms without `O_NOFOLLOW`.

The CLI spends the same deadline created at top level on this descriptor read, loads exact canonical bytes, verifies the repository, and implements the exact stdout/stderr/exit contract from Step 1. Set `sys.dont_write_bytecode = True` before either CLI imports project modules, and set `PYTHONDONTWRITEBYTECODE=1` in every documented and test invocation. The CLI never writes, locks, lazily fetches, creates bytecode, or creates cache files in either repository.

- [ ] **Step 6: Run focused checks and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_source_lock.py
../../.venv/bin/ruff check bionodulo/nodes/catalog/source_lock.py scripts/verify_tool_source_lock.py tests/catalog/test_source_lock.py
../../.venv/bin/mypy bionodulo/nodes/catalog/source_lock.py scripts/verify_tool_source_lock.py
git add bionodulo/nodes/catalog/source_lock.py scripts/verify_tool_source_lock.py tests/catalog/test_source_lock.py
git commit -m "feat(catalog): verify pinned upstream git sources"
```

### Task 3: Add the Samtools Dispatcher Sanity Verifier

**Owner:** Samtools family lane

**Files:**
- Create: `bionodulo/nodes/catalog/tools/samtools/__init__.py`
- Create: `bionodulo/nodes/catalog/tools/samtools/verification.py`
- Create: `scripts/verify_samtools_source_lock.py`
- Create: `tests/catalog/tools/samtools/test_source_lock.py`

- [ ] **Step 1: Write all dispatcher and opaque-marker tests**

The family verifier accepts only compiler-owned bytes already verified by the generic source lock. It parses the pinned `bamtk.c` `else if` dispatch chain into literal command-to-entrypoint mappings, including multi-name branches such as `fasta`/`fastq` and `idxstat`/`idxstats`. The dispatcher contains aliases and unrelated commands beyond the lock's selected 23; equality means that the lock's exact 23 command names and entrypoints equal those same 23 entries selected from the parsed dispatcher, not that the 23-command lock equals the entire `bamtk.c` command set.

Before implementation, record RED for exact lock-selected 23-command equality, missing/duplicate/ambiguous selected dispatcher entries, missing opaque implementation markers, a forged lock/result digest mismatch, missing/extra/reordered source-byte keys, a forged source-byte value, deadline expiry during source-byte rehashing, dispatcher parsing, and marker scanning, and the wrapper CLI's success/mismatch/non-writing paths. Add `family_fixture_contract` tests that build the complete synthetic Samtools lock and call the completed generic verifier without importing the family module; they must prove the lock, bytes, keys, digests, modes, dispatcher fixture, and implementation fixtures are internally consistent. Test empty, control-containing, over-128-byte, and metacharacter entrypoints against `^[A-Za-z_][A-Za-z0-9_]{0,127}$`. Do not import the initially absent family module at test-collection time: import it inside each behavior test or fixture so the first CLI subprocess RED cases also execute. Include these regressions:

`validated_update()` is a test-only helper that mirrors the repository `_StrictFrozenModel` validated-copy implementation: dump with `mode="python", round_trip=True`, apply the update, then call `type(value).model_validate(...)`. It does not call stock Pydantic `BaseModel.model_copy(update=...)` or suggest that stock Pydantic copies revalidate. `verified_sources_for()` starts from the complete valid synthetic Samtools lock fixture, replaces its canonical `command_bindings` tuple through `validated_update()`, recalculates canonical lock bytes/digest through the real model, and calls the real generic verifier against the temporary pinned Git fixture. It never fabricates a `SourceLockVerificationReport` or byte mapping.

```python
def test_swapped_samtools_command_binding_is_rejected(verified_sources) -> None:
    bindings = valid_command_bindings()
    bindings["sort"] = validated_update(
        bindings["sort"], entrypoint=bindings["view"].entrypoint
    )
    verified = verified_sources_for(command_bindings=bindings)

    with pytest.raises(SamtoolsSourceBindingError, match="sort.*main_samview"):
        verify_samtools_source_bindings(verified)


def test_samtools_verifier_rejects_a_lock_from_another_verified_result(
    verified_sources,
) -> None:
    other_lock = validated_update(verified_sources.lock, tool_version="1.23.0")
    forged = dataclasses.replace(verified_sources, lock=other_lock)

    with pytest.raises(SamtoolsSourceBindingError, match="lock digest"):
        verify_samtools_source_bindings(forged)


def test_samtools_verifier_rehashes_forged_source_bytes(verified_sources) -> None:
    forged_bytes = dict(verified_sources.source_bytes)
    forged_bytes[verified_sources.lock.dispatcher_source_id] = b"forged dispatcher\n"
    forged = dataclasses.replace(
        verified_sources,
        source_bytes=MappingProxyType(forged_bytes),
    )

    with pytest.raises(SamtoolsSourceBindingError, match="source bytes.*digest"):
        verify_samtools_source_bindings(forged)
```

The wrapper CLI success case asserts exit zero, empty stderr, and exactly one stdout line with one trailing newline:

```text
<tool_id> <tool_version>: <verified_files> files and <selected_lock_commands> dispatcher commands verified; <declared_operations> operations declared at <commit>
```

Every family mismatch, integrity failure, timeout, or bound failure exits `1`, leaves stdout empty, and emits exactly one stable public error line on stderr with no traceback. Pin these family messages exactly: `samtools source-lock verification failed: aggregate verification deadline exceeded\n`; `samtools source-lock verification failed: source bytes key mismatch\n`; `samtools source-lock verification failed: source bytes digest mismatch for <source_id>\n`; `samtools source-lock verification failed: dispatcher parse failed\n`; `samtools source-lock verification failed: dispatcher binding mismatch for <command>\n`; and `samtools source-lock verification failed: implementation marker mismatch for <entrypoint>\n`. Generic Git/lock errors propagated through the wrapper retain the generic `source-lock verification failed: ...\n` line and exit `1`; argparse usage alone retains exit `2`. The same bounded lock-read, bytecode suppression, aggregate deadline, and full repository-snapshot assertions used by the generic CLI apply here.

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/tools/samtools/test_source_lock.py -k family_fixture_contract
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/tools/samtools/test_source_lock.py
```

Expected: the fixture-contract subset passes first. Full collection then succeeds because family imports are inside behavior tests, and the full run is RED only because those per-test imports and CLI subprocesses find the Samtools verifier/wrapper absent. Malformed source bytes or lock fixtures are not an acceptable explanation.

- [ ] **Step 3: Add minimal family parser/verifier/CLI stubs and prove behavior-specific RED**

Add temporary symbols only: `SamtoolsSourceBindingError`, `parse_samtools_dispatcher(...)`, and `verify_samtools_source_bindings(...)` in `verification.py`, plus a wrapper script with argument parsing and `sys.dont_write_bytecode = True` before project imports. The parser and verifier raise `NotImplementedError("Samtools source binding verification is not implemented")`, and the wrapper `main()` raises `NotImplementedError("Samtools source-lock CLI is not implemented")`; do not parse bytes, construct results, reset deadlines, or format final errors yet.

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/tools/samtools/test_source_lock.py -k family_fixture_contract
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/tools/samtools/test_source_lock.py
```

Expected: the fixture-contract subset still passes; every dispatcher, byte-integrity, deadline-phase, marker, and CLI behavior test collects and fails at its intended assertion on stub behavior, never on missing symbols, malformed fixtures, or a missing script. Remove all temporary stubs while implementing Step 4.

- [ ] **Step 4: Implement the narrow family verifier**

`parse_samtools_dispatcher()` is intentionally specific to the pinned `bamtk.c` structure. It accepts the shared `VerificationDeadline` and returns literal command names and entrypoint identifiers, checking that same deadline during scanning; it rejects any unparsed or ambiguous selected branch. `verify_samtools_source_bindings()` accepts only the exact immutable `VerifiedToolSources` result plus the already-created shared deadline and performs all integrity checks before dispatcher or entrypoint parsing: recompute `verified.lock.lock_digest()` and require equality with `verified.report.lock_digest`; require `tuple(verified.source_bytes)` to equal exactly the canonical source-ID tuple from `verified.lock.source_files`; then rehash every byte value and compare it with that source file's `content_sha256`, checking the shared deadline while hashing. Missing, extra, reordered, non-`bytes`, oversized, aggregate-oversized, or digest-mismatched values fail. Lock/report digest equality alone is insufficient. No family helper creates, extends, or resets a deadline.

Only after those checks, consume command, dispatcher, and implementation metadata from `verified.lock`; never accept separately supplied bindings or reopen a file. Parse all discoverable dispatcher branches, checking the shared deadline while parsing, select by the lock's exact 23 command names, and require that selected 23-name-to-entrypoint mapping to equal the lock mapping. Additional `bamtk.c` aliases or unrelated commands remain outside the equality comparison. Then perform one downgraded opaque sanity check: the exact line prefix `int <entrypoint>(` occurs once in the declared, hash-verified implementation bytes, checking the same deadline during every marker scan. An expiry during rehashing, dispatcher parsing, or marker scanning must produce the corresponding stable deadline error; no phase may create a replacement deadline. This marker is not called a C parser or evidence proof. A subsequent evidence compiler must use language-aware symbol selection or exact content locators before a node can pass `evidence_verified`.

`scripts/verify_samtools_source_lock.py` is the composed entrypoint: create exactly one 60-second `VerificationDeadline` immediately after argument parsing, bounded-read canonical lock bytes against it, pass that same object to generic Git verification, then pass the same returned result and unchanged deadline to `verify_samtools_source_bindings()` for source-byte rehashing, dispatcher parsing, and implementation-marker scans. The wrapper never lets generic verification or a family phase create/reset a deadline. It then prints the exact Step 1 summary that distinguishes 44 verified file identities, 23 verified dispatcher command bindings, and 27 declared operation mappings. The generic CLI reports file identity only and must not claim that Samtools command dispatch was verified. Neither CLI claims parameter, output, environment, or biological correctness, advances evidence maturity, or authorizes a node's release.

- [ ] **Step 5: Run focused tests and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
../../.venv/bin/ruff check \
  bionodulo/nodes/catalog/tools/samtools/verification.py \
  scripts/verify_samtools_source_lock.py \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
../../.venv/bin/mypy \
  bionodulo/nodes/catalog/tools/samtools/verification.py \
  scripts/verify_samtools_source_lock.py \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
git add bionodulo/nodes/catalog/tools/samtools scripts/verify_samtools_source_lock.py tests/catalog/tools/samtools
git commit -m "test(catalog): verify samtools command ownership"
```

### Task 4: Lock All 27 Samtools Operations

**Owner:** Samtools family lane

**Files:**
- Create: `bionodulo/nodes/catalog/tools/samtools/source-lock.json`
- Modify: `tests/catalog/tools/samtools/test_source_lock.py`

- [ ] **Step 1: Write the failing 27-ID and ownership tests**

The portable unit test loads `baseline-ledger.json`, the approved migration-queue bytes present in the source tree, and the wished-for Samtools lock. It never invokes `git merge-base` or assumes repository history is present. It asserts `baseline_ledger["aggregate_sha256"] == "75643eb83592eccd492d65d3c53b40d45cc6d0e04c2363f5572aeb3492927210"`, the queue's exact embedded baseline/queue/rules identities, and SHA-256 `34e1a5a6cc1811ffc23a49b08819b09f1d782b074b711c8be02f92b90052c781` over the exact queue artifact bytes. It then asserts `len(queue["assignments"]) == 943` and that every assignment, not only Samtools, still has `disposition == "quarantined"` and `contract_status == "evidence_pending"`. These content tests must pass in source exports and shallow clones. Only after that whole-queue invariant does it assert this exact Samtools mapping:

```python
EXPECTED_NODE_COMMANDS = {
    "samtools_ampliconclip": ("ampliconclip", "collate", "fixmate", "sort"),
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
    "samtools_fastx": ("fasta", "fastq", "sort"),
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

The exact node set must equal the 27 `samtools_` baseline and approved queue IDs. Those 27 remain part of the all-943 `quarantined`/`evidence_pending` invariant; source locking must not alter any queue assignment or maturity state.

The full-history ancestry command remains the mandatory Execution Preconditions gate, not a portable unit test. A separate test may run it only under an explicit `repository_history` marker in CI jobs that guarantee `git rev-parse --is-shallow-repository` is `false`; default unit-test selection excludes that marker, and its absence never weakens the integration gate.

- [ ] **Step 2: Run tests and verify RED**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/tools/samtools/test_source_lock.py
```

Expected: the Samtools lock file does not exist.

- [ ] **Step 3: Author the exact immutable revision**

```json
{
  "kind": "annotated",
  "release_tag": "1.23.1",
  "tag_object": "4ac78a7e9938dbef3c6f97d549758feceb0252db",
  "commit": "6efb9b6da35224cf804921dedecf9fb8f411365d"
}
```

The enclosing lock uses `tool_id` `samtools`, `tool_version` `1.23.1`, and repository URL `https://github.com/samtools/samtools`. It contains no release date, branch, mutable ref, evidence claim, or maturity assertion. Creating and verifying it is explicitly insufficient to mark any node `released` or to claim parameter, output, environment, runtime, or biological correctness.

- [ ] **Step 4: Author the exact 44-file source table**

Use these exact content identities; do not fetch or substitute newer files:

```text
bam2depth.c sha256:088faff6c5c37dfbf16bd278d4a2d19d8fd86cc35786d579d4fd26006b9486cd
bam_ampliconclip.c sha256:c48ac868c488edebb0c9a59cb1e3cf9a451f6d9086b749d17b76af9ac302c38a
bam_consensus.c sha256:d58bef6fc9460bf2a23fce448a0f36525f1d7716e7e5d993578b8df69df4d84e
bam_fastq.c sha256:227134159604f9a29975a64d7b899f85da27fe2117c91f2503fdb7059d688695
bam_index.c sha256:ac7e0f4157c655c654cc8f264e66bb749c6938a9e3b7eaa85c40440207e4718b
bam_markdup.c sha256:9352675009926d2ba35c4d18d9322d0972eb1663fd61c2ffe5c65fa3e1c52d3d
bam_mate.c sha256:d01338f188c64a9f9d62308e084465d3252374374d15e1651791d42b89f15ecb
bam_md.c sha256:3f2ade44f1d26a8b511a6b27194103eb838d6836a8ea84041f08ac402bf8206a
bam_plcmd.c sha256:6d51e9dd20f49d205ef9342a568a9880cd5c6df036fe5d89a7f0e312b94ab7db
bam_reheader.c sha256:0dbbdb8c973eeb462db1e03c858180b15a690338692ede383d70a4bc8b041bef
bam_sort.c sha256:398e25e740dd3fb1ed0379c352c8da19248342ceb4ddf2931bb0a260f2b0a7d6
bam_split.c sha256:d2d6495f0420fac64933ec6cda5d615c675a69a291fc7c4c7d95b829a7840897
bam_stat.c sha256:9a5623b2f3534045627ed7f6ed658a7e3645ab395ef6f5819dbbfca215f50c62
bamshuf.c sha256:098fc15d22e0997f9707464858a12c645d7d2e4b60245393474218f2a3c999ef
bamtk.c sha256:41a44dca3d105fe8b454d78bfa4469ae691de64df7aabd24495c70ba52bd864c
bedcov.c sha256:70ea5a6cff47bd5125f0ad492f8b36fb8d314970eed5c7a0d89b7bedf4872a06
coverage.c sha256:22cda7bb3a7b1581dfaa4f1c493018d1b36c2d0648221fd910075a913f995d88
doc/samtools-ampliconclip.1 sha256:af564b82af88dd161a59e26da678f956f0d7de6636ac7ea8f6e1e618f01475bc
doc/samtools-bedcov.1 sha256:bca67d7043f2d458ce6e33bb14c4c5fccdab6f58c74d66966dea49e9cdc846ca
doc/samtools-calmd.1 sha256:d22538e0a63d0eea3dd674a8c9efb416703eb21c5e2d87a4b334615faf95137d
doc/samtools-collate.1 sha256:4a4546a49904ea0ee117f6eb3d136eb0dcb5de574563955399c1dd14517aab6d
doc/samtools-consensus.1 sha256:b78ce4bc85e9e5cd4091453aa9ade8bca67fa201fab1bde3da88ec288785c97e
doc/samtools-coverage.1 sha256:3c21142d430bb96c3e4c7944c0192047ff7ad23022ef302a04375f87da995522
doc/samtools-depth.1 sha256:c33e62cf3551e929e38c9a1e366f1ba54fd5065575f7084628dadb8540a6c603
doc/samtools-faidx.1 sha256:80e96f97d23755ac272824996430a67c7654ea342d40d7973c4ab1de08346248
doc/samtools-fasta.1 sha256:89b3ef7044638f9fa8c168c43f794872876262976525b569bd90fcb206331061
doc/samtools-fastq.1 sha256:8f9967a5488028f0fd31aba1bd4441d6bb00d57933cad7099456b12bdcb23e2c
doc/samtools-fixmate.1 sha256:f91e0ae8f6e8d25d3431744386f71f1b2edf8d6009c4e7e19b5354d078134a7d
doc/samtools-flagstat.1 sha256:38ac635d440c7d8a0758842ac217512e39df136a26c3cfafd9830afe69e26965
doc/samtools-idxstats.1 sha256:00b88570bcaaf6573dac063b46b6a4c6613c0232909f0f770e1db55c9f38d8c7
doc/samtools-index.1 sha256:4eaf8f0b0298291d52ef5706056e74012dccfaa97d8fbf9a6777fac1585d1e6e
doc/samtools-markdup.1 sha256:42f3cd5f96188ece990929e1115584e2f8ad8d0ece63411a62b6176dfd2a8667
doc/samtools-merge.1 sha256:4f7f8e2e356f9b75ba1a26685995c096ce824781fe734e324b5be4b9efe70b0b
doc/samtools-mpileup.1 sha256:2f52e469c64fe59b96b9c8c6116508fbc8577cdfae01e3577b7611b263b3c551
doc/samtools-phase.1 sha256:1a4b531b5d4cb70310d6d2f583ffeb10ce226518d6b0f995d0dd6702f7c10e12
doc/samtools-reheader.1 sha256:33a6b9fa23d9d278272a169355a36aa259e2187f025c44dcd216c1a3e9154f6f
doc/samtools-sort.1 sha256:38a72be83b39bf93e8aee8a23d5c197ff0f296a9a251bc2d56a7afbebaa2434c
doc/samtools-split.1 sha256:a0ed3c5c135d4cde3868c566db4b2e3f30ff3988b19ef48175770497645008e0
doc/samtools-stats.1 sha256:bde9c0528f8de5353bf8f112adc001b6ef9a03bc6d8f6eb3ee3b51b4a9c8fa01
doc/samtools-view.1 sha256:c4efdd51e9ad6a9f5ae1d8f752f3ed5412816cce1ff51063d108c603b99db05a
faidx.c sha256:9af86df7a660c54494a192240280d0cb1be3859842c930a9072ac6285e40cad9
phase.c sha256:71dcef380a1d15e9c9da0bd0418a06c344058489ba652f7b27ccfc7e784251b5
sam_view.c sha256:49102b2145657ed84e519423934050119990ca5aaf7a823df2cc4a63cb0e9c35
stats.c sha256:81d67e5aa1ce22521a0c9973614fa0cb25bc163f265d7c7bd4b5d259676e24f5
```

Source IDs are derived exactly as follows:

- `bamtk.c` is `samtools-dispatch-bamtk`, with role `dispatcher` and format `source_code`.
- For `doc/samtools-NAME.1`, remove the literal `doc/samtools-` prefix and `.1` suffix and prepend `samtools-doc-`. Thus the alias file is `samtools-doc-fastq`. Every document has role `documentation` and format `text`.
- For a C implementation basename `NAME.c`, remove `.c` without changing underscores and prepend `samtools-src-`. Thus `bam_ampliconclip.c` is `samtools-src-bam_ampliconclip`. Every such file has role `implementation` and format `source_code`.

The `fastq` command references both `samtools-doc-fasta` and `samtools-doc-fastq`. Shared implementation source IDs are reused rather than duplicated.

- [ ] **Step 5: Author and verify exact command bindings**

| Command | Documentation path | Implementation path | Entrypoint |
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
| `fastq` | `doc/samtools-fasta.1`, `doc/samtools-fastq.1` | `bam_fastq.c` | `main_bam2fq` |
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

Every binding uses dispatcher source `samtools-dispatch-bamtk` and passes the Samtools-specific dispatcher verifier. Do not use legacy BioNodulo source, Galaxy wrappers, blogs, or mutable web pages as source-lock authority.

- [ ] **Step 6: Run structural and pinned-source verification**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python scripts/verify_samtools_source_lock.py \
  --repository /tmp/bionodulo-samtools-1.23.1 \
  --lock "$PWD/bionodulo/nodes/catalog/tools/samtools/source-lock.json"
```

Expected summary:

```text
samtools 1.23.1: 44 files and 23 dispatcher commands verified; 27 operations declared at 6efb9b6da35224cf804921dedecf9fb8f411365d
```

Expected process contract: exit `0`, stdout equals exactly that line plus one `\n`, stderr is empty, the bounded aggregate deadline is respected, no bytecode/cache appears in either repository, and the full worktree/Git-metadata/ref/object snapshots are unchanged. Every verification failure exits `1` under the Task 3 stderr contract with empty stdout and the same no-write acceptance checks.

- [ ] **Step 7: Commit the family lock**

```bash
git add bionodulo/nodes/catalog/tools/samtools/source-lock.json tests/catalog/tools/samtools/test_source_lock.py
git commit -m "feat(catalog): lock samtools 1.23.1 sources"
```

### Task 5: Independent Review and Handoff

**Files:**
- Verify all files above

- [ ] **Step 1: Run full lightweight verification**

```bash
PYTHONDONTWRITEBYTECODE=1 ../../.venv/bin/python -m pytest -p no:cacheprovider -q \
  -m "not repository_history" \
  tests/catalog
../../.venv/bin/ruff check \
  bionodulo/nodes/catalog/source_lock.py \
  bionodulo/nodes/catalog/tools/samtools \
  scripts/verify_tool_source_lock.py \
  scripts/verify_samtools_source_lock.py \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
../../.venv/bin/mypy \
  bionodulo/nodes/catalog/source_lock.py \
  bionodulo/nodes/catalog/tools/samtools \
  scripts/verify_tool_source_lock.py \
  scripts/verify_samtools_source_lock.py \
  tests/catalog/test_source_lock.py \
  tests/catalog/tools/samtools/test_source_lock.py
```

- [ ] **Step 2: Run specification review**

Verify exact 27-ID coverage, all-943 queue quarantine/evidence-pending state, 44 exact source ID/byte/digest bindings, the lock-selected 23 command bindings, annotated tag peeling, exact `100644 blob` tree modes, safe Git plumbing, per-command/output/file/aggregate byte bounds, the single composed deadline, dispatcher ownership, and zero source-lock claims about parameters, outputs, environments, biological behavior, maturity, or release readiness. In the full-history integration checkout, separately rerun the exact Execution Preconditions shallow/full-history and `merge-base --is-ancestor` commands; portable unit tests do not perform that history check.

- [ ] **Step 3: Run a separate code-quality review**

Review the import-RED, collecting-stub RED, and behavior-specific RED checkpoints for Tasks 1-3 so missing symbols cannot mask malformed fixtures. Review the exact depth-64/depth-65 definition, recursive unsafe/duplicate-key handling, strict Python versus JSON-mode collection behavior, and validated-copy semantics. Review exact-from-scratch Git child environments, literal path handling, argument safety, race-safe descriptor-only lock reads, per-command bounds, the one non-resettable composed deadline, bytecode suppression, every stable public CLI error row, and full worktree/Git-dir/common-dir snapshots. `git status` equality alone is not no-write acceptance. Also review canonical bytes, exact source reuse, error specificity, family/foundation ownership, and test realism.

- [ ] **Step 4: Fix confirmed findings with failing regression tests**

Do not write NodeSpecs or release nodes in this phase. Source locking establishes upstream Git/file/selected-dispatch identity only; it does not establish parameter, output, environment, runtime, or biological correctness. A separate evidence/contract plan begins only after this source lock is approved and the catalog environment foundation can produce verified `samtools==1.23.1` Pixi locks for each supported platform.
