# Environment Compiler Spec-Review Repairs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close every pre-integration environment-registry and Pixi 0.68.1 compiler blocker with source-backed parsing, verified host-binary execution, isolated locked capture, and protocol-v2 wire bytes.

**Architecture:** `pixi_lock_v7.py` owns bounded lock/list decoding and exact reconciliation, `pixi_identity.py` owns pinned release constants and open-file-descriptor executable verification, and `compiler.py` owns only staging and orchestration. The only public compilation path accepts exact manifest/lock bytes plus an executable path and host/target platforms; captured-byte and runner injection remain private test seams. Registry and request bytes use a strict, bounded schema-v2 protocol.

**Tech Stack:** Python 3.11+, Pydantic v2, PyYAML, `packaging`, stdlib `os`/`subprocess`/`tempfile`, pytest, Ruff, mypy

---

## File structure

- Create `bionodulo/nodes/environment_compiler/pixi_lock_v7.py`: Pixi list models, bounded v7 YAML decoding, native package models, and lock/list reconciliation.
- Create `bionodulo/nodes/environment_compiler/pixi_identity.py`: pinned release metadata, binary hashing, host identity, and verified-FD execution handle.
- Reduce `bionodulo/nodes/environment_compiler/compiler.py`: public exact-byte compiler, isolated staging, owned subprocess capture, and a private injected capture seam.
- Modify `bionodulo/nodes/catalog/environment_registry.py`: schema version 2, 1 MiB bound, nesting bound, and unsafe-key rejection.
- Modify `tests/catalog/test_environment_compiler.py`: exact upstream list/lock fixtures, field-adversarial tests, identity tests, staging tests, and host/target independence.
- Modify `tests/catalog/test_environment_registry.py`: protocol-v2 golden bytes and strict decoder boundaries.

### Task 1: Bump the environment wire protocol and close JSON boundaries

**Files:**
- Modify: `bionodulo/nodes/catalog/environment_registry.py`
- Modify: `tests/catalog/test_environment_registry.py`

- [ ] **Step 1: Write protocol-v2 and byte-bound RED tests**

Add assertions that both `EnvironmentRegistry` and `WorkflowEnvironmentRequest` require `schema_version=2`, canonical bytes contain `"schema_version":2`, version 1 is rejected, and a payload over exactly 1 MiB is rejected. Add a 64-level accepted / 65-level rejected nested JSON scanner case and unsafe-key cases for `__proto__`, `constructor`, and `prototype`.

```python
def test_registry_protocol_is_version_two() -> None:
    source = registry.derive_environment_registry((external_spec(),))
    assert source.schema_version == 2
    with pytest.raises(ValidationError, match="schema_version"):
        registry.EnvironmentRegistry.model_validate({**source.model_dump(), "schema_version": 1})


def test_registry_decoder_rejects_excessive_nesting_and_unsafe_keys() -> None:
    content = registry.derive_environment_registry((external_spec(),)).canonical_json_bytes()
    with pytest.raises(ValueError, match="nesting depth"):
        registry.decode_environment_registry(nest_unknown_value(content, depth=65), node_specs=(external_spec(),))
    with pytest.raises(ValueError, match="unsafe JSON key"):
        registry.decode_environment_registry(inject_key(content, "__proto__"), node_specs=(external_spec(),))
```

- [ ] **Step 2: Run each new test and record the expected RED**

Run:

```bash
.venv/bin/pytest -q tests/catalog/test_environment_registry.py::test_registry_protocol_is_version_two
.venv/bin/pytest -q tests/catalog/test_environment_registry.py::test_registry_decoder_rejects_excessive_nesting_and_unsafe_keys
```

Expected: schema remains 1 and the decoder lacks the requested depth/unsafe-key errors.

- [ ] **Step 3: Implement the minimal strict decoder changes**

Set `_MAX_REGISTRY_BYTES = 1024 * 1024`, `_MAX_JSON_NESTING_DEPTH = 64`, and both schema literals/construction sites to 2. Scan decoded ASCII JSON while respecting quoted strings and escapes before `json.loads`; reject depth over 64. Extend the duplicate-key hook to reject the three unsafe cross-language object keys at every nesting level. Catch recursion failures and return controlled `ValueError`s.

- [ ] **Step 4: Run registry and NodeSpec suites**

Run:

```bash
.venv/bin/pytest -q tests/catalog/test_environment_registry.py tests/catalog/test_node_spec.py
```

Expected: all pass.

- [ ] **Step 5: Commit the protocol checkpoint**

```bash
git add bionodulo/nodes/catalog/environment_registry.py tests/catalog/test_environment_registry.py
git commit -m "fix(catalog): version environment registry protocol"
```

### Task 2: Reconcile exact Pixi 0.68.1 Conda and PyPI list records

**Files:**
- Modify: `bionodulo/nodes/environment_compiler/compiler.py`
- Modify: `tests/catalog/test_environment_compiler.py`

- [ ] **Step 1: Add exact upstream-shape RED fixtures**

Add one Conda fixture named `_openmp_mutex` whose lock URL and list record preserve the underscore. Add one PyPI wheel fixture whose v7 `requires_dist` contains the exact strings emitted by `Requirement::to_string()` and whose list `depends` contains the same strings. Tests must compile through the captured-byte seam and assert both artifacts are admitted.

```python
def test_conda_name_reconciliation_preserves_conda_spelling() -> None:
    record = conda_record(name="_openmp_mutex", url=OPENMP_URL, file_name=OPENMP_FILENAME)
    compiled = pixi_lock_v7._compile_captured_platform_lock(
        pixi_list_content=encoded(record),
        pixi_lock_content=lockfile(package_references=(("conda", OPENMP_URL),)),
        resolver=ResolverIdentity(name="pixi", version="0.68.1", config_digest=PIXI_X86_ARCHIVE_SHA256),
        environment_name="alignment-tools",
        target_platform=ExecutionPlatform.LINUX_AMD64,
    )
    assert compiled.artifacts[0].name == "_openmp_mutex"


def test_pypi_list_dependencies_equal_native_requires_dist() -> None:
    wheel = pypi_record(depends=["typing-extensions>=4.0 ; python_version < '3.11'"])
    compiled = pixi_lock_v7._compile_captured_platform_lock(
        pixi_list_content=encoded(python_record(), wheel),
        pixi_lock_content=lockfile(
            package_references=(("conda", str(python_record()["url"])), ("pypi", str(wheel["url"])))
        ),
        resolver=ResolverIdentity(name="pixi", version="0.68.1", config_digest=PIXI_X86_ARCHIVE_SHA256),
        environment_name="alignment-tools",
        target_platform=ExecutionPlatform.LINUX_AMD64,
    )
    assert any(artifact.kind == "pypi" for artifact in compiled.artifacts)
```

- [ ] **Step 2: Run both tests and record RED**

Expected: Conda comparison reports `-openmp-mutex` versus `_openmp_mutex`; PyPI comparison reports nonempty `depends` versus `()`.

- [ ] **Step 3: Implement kind-specific comparisons**

Compare Conda names byte-for-byte. Only normalize PyPI names. Compare PyPI list `depends` against the native `requires_dist` tuple after validating every requirement, preserving upstream order and string spelling.

- [ ] **Step 4: Run the focused compiler suite**

Run `.venv/bin/pytest -q tests/catalog/test_environment_compiler.py` and expect all tests to pass.

### Task 3: Validate every admitted v7 package field and split lock ownership

**Files:**
- Create: `bionodulo/nodes/environment_compiler/pixi_lock_v7.py`
- Modify: `bionodulo/nodes/environment_compiler/compiler.py`
- Modify: `tests/catalog/test_environment_compiler.py`

- [ ] **Step 1: Add one-field-at-a-time adversarial RED tests**

Use the exact `rattler_lock 0.29.0` `PackageRecord` shapes. Test valid and invalid forms for every currently allowed field. In particular:

- `legacy_bz2_md5`: omitted or lowercase 32-hex string; reject null, wrong length/case/type.
- `legacy_bz2_size`: omitted or unsigned u64; reject bool, negative, float, string, overflow.
- `features`: omitted or string; reject mappings, sequences, numbers, and booleans.
- `python_site_packages_path`: omitted or string; reject mappings, sequences, numbers, booleans, control characters, and unbounded text.
- `noarch`: omitted or exact `generic` / `python` where URL subdir semantics permit it.
- `flags`, `purls`, `run_exports`, `variants`, and `extra_depends`: enforce exact upstream container/scalar types, bounds, uniqueness, and canonical order where the upstream serialized type is ordered.

```python
@pytest.mark.parametrize(
    ("field", "value"),
    (("legacy_bz2_md5", {}), ("legacy_bz2_size", -1), ("features", []), ("python_site_packages_path", {})),
)
def test_v7_conda_fields_reject_values_outside_upstream_types(field: str, value: object) -> None:
    content = native_lock_with_conda_field(field, value)
    with pytest.raises(ValueError, match=field):
        pixi_lock_v7._decode_selected_packages(
            content,
            environment_name="alignment-tools",
            resolver_platform="linux-64",
        )
```

- [ ] **Step 2: Run each parameter group and record RED**

Expected: the four previously ignored fields are accepted before implementation.

- [ ] **Step 3: Implement exact field validators in the existing decoder**

Retain each validated field on the immutable native package model, even when Pixi list JSON does not expose it. Reject any allowed-but-unvalidated value. Do not invent semantic enums; use the exact pinned Rust definitions and serialized forms recorded in test comments.

- [ ] **Step 4: Run compiler tests to GREEN**

Run `.venv/bin/pytest -q tests/catalog/test_environment_compiler.py`.

- [ ] **Step 5: Refactor the green decoder into `pixi_lock_v7.py`**

Move list Pydantic models, v7 constants, bounded YAML loader/scanner, native package types, field validators, selected-closure resolution, and reconciliation into `pixi_lock_v7.py`. Keep import-compatible re-exports only where existing callers require them. `compiler.py` must no longer contain YAML parsing or package metadata validation.

- [ ] **Step 6: Re-run compiler tests after the pure refactor**

Expected: identical passing count and digests.

- [ ] **Step 7: Commit the lock-v7 checkpoint**

```bash
git add bionodulo/nodes/environment_compiler/pixi_lock_v7.py bionodulo/nodes/environment_compiler/compiler.py tests/catalog/test_environment_compiler.py
git commit -m "fix(catalog): reconcile complete pixi lock v7 metadata"
```

### Task 4: Verify the pinned host Pixi binary from an open file descriptor

**Files:**
- Create: `bionodulo/nodes/environment_compiler/pixi_identity.py`
- Modify: `bionodulo/nodes/environment_compiler/compiler.py`
- Modify: `tests/catalog/test_environment_compiler.py`

- [ ] **Step 1: Add pinned identity and filesystem RED tests**

Assert the exact v0.68.1 tag commit, archive digests, and extracted binary digests supplied by authoritative release verification. Parameterize missing, relative, symlink, directory/FIFO, zero-byte, oversized, non-executable, wrong-hash, and path-replaced cases. Use synthetic files and a private expected-distribution argument; never download assets.

```python
def test_pixi_identity_rejects_symlink_and_wrong_binary_hash(tmp_path: Path) -> None:
    binary = write_executable(tmp_path / "pixi", b"wrong")
    with pytest.raises(ValueError, match="SHA-256"):
        pixi_identity._open_verified_pixi(
            binary,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(binary, expected_binary_sha256="sha256:" + "0" * 64),
        )
    link = tmp_path / "pixi-link"
    link.symlink_to(binary)
    with pytest.raises(ValueError, match="symlink|regular"):
        pixi_identity._open_verified_pixi(
            link,
            host_platform=ExecutionPlatform.LINUX_AMD64,
            distributions=synthetic_distribution_map(binary),
        )
```

- [ ] **Step 2: Run the identity tests and record RED**

Expected: current caller-constructed `VerifiedPixiExecutable` accepts nonexistent and wrong files.

- [ ] **Step 3: Implement `pixi_identity.py`**

Define immutable `PixiDistribution` with archive and binary SHA-256 fields. Open an absolute path with `O_RDONLY | O_CLOEXEC | O_NOFOLLOW`, require a regular executable file with size `1..MAX_PIXI_BINARY_BYTES`, hash exactly the open descriptor, and compare the expected host distribution binary digest. Re-check `fstat` metadata after hashing. Return a context-managed private verified handle retaining the descriptor; expose resolver identity derived only from pinned constants. The eventual subprocess must execute `/proc/self/fd/<fd>` with `pass_fds=(fd,)`, preventing path replacement between hash and exec.

- [ ] **Step 4: Separate host distribution from target platform**

Every identity lookup uses `host_platform`; `_PIXI_PLATFORM[target_platform]` is used only for lock selection and `--platform`. Add a green test proving an x86 verified handle is accepted for an ARM target.

- [ ] **Step 5: Run focused tests and commit**

```bash
.venv/bin/pytest -q tests/catalog/test_environment_compiler.py
git add bionodulo/nodes/environment_compiler/pixi_identity.py bionodulo/nodes/environment_compiler/compiler.py tests/catalog/test_environment_compiler.py
git commit -m "fix(catalog): verify pinned pixi host executable"
```

### Task 5: Replace source snapshots and public runner injection with isolated locked capture

**Files:**
- Modify: `bionodulo/nodes/environment_compiler/compiler.py`
- Modify: `tests/catalog/test_environment_compiler.py`

- [ ] **Step 1: Add public-API and staging RED tests**

The public compiler must accept exact bounded `pixi.toml` and `pixi.lock` bytes, a binary path, host platform, target platform, and environment name. It must not accept decoded records, an asserted digest/resolver, a workspace path, or a runner. Add tests that inspect the private capture seam and require a fresh temporary directory containing only exact `pixi.toml` and `pixi.lock`; source symlinks and `.pixi` trees are never read. Require cleanup after success and after capture failure.

```python
def test_public_compiler_stages_exact_bytes_and_uses_locked_no_install(tmp_path: Path) -> None:
    seen: list[tuple[tuple[str, ...], Path, int]] = []

    def capture(command: tuple[str, ...], cwd: Path, executable_fd: int) -> bytes:
        seen.append((command, cwd, executable_fd))
        return encoded(arm_conda_record())

    binary = write_synthetic_pixi(tmp_path / "pixi")
    with pixi_identity._open_verified_pixi(
        binary,
        host_platform=ExecutionPlatform.LINUX_AMD64,
        distributions=synthetic_distribution_map(binary),
    ) as verified:
        compiled = compiler._compile_with_capture_for_test(
            pixi_toml_content=b"[workspace]\nname = 'fixture'\nchannels = ['conda-forge']\nplatforms = ['linux-aarch64']\n",
            pixi_lock_content=arm_lockfile(),
            capture=capture,
            verified_pixi=verified,
            target_platform=ExecutionPlatform.LINUX_ARM64,
            environment_name="alignment-tools",
        )
    assert seen[0][0][1:5] == ("list", "--locked", "--no-install", "--json")
    assert seen[0][0][8:10] == ("--platform", "linux-aarch64")
    assert not seen[0][1].exists()
    assert compiled.platform is ExecutionPlatform.LINUX_ARM64
```

- [ ] **Step 2: Run tests and record RED**

Expected: current API requires a source workspace, exposes public runner injection, and emits `--frozen`.

- [ ] **Step 3: Implement isolated orchestration**

Bound manifest bytes to 1 MiB and lock bytes to the lock decoder limit. Validate both are exact `bytes`. Create a compiler-owned `TemporaryDirectory`, write exact `pixi.toml` / `pixi.lock`, validate the staged lock, and invoke one command:

The exact command tuple starts with `f"/proc/self/fd/{verified.fd}"`, followed by `list`, `--locked`, `--no-install`, `--json`, the selected environment, target resolver platform, and the staged manifest path. Run it through `subprocess.run(command, cwd=stage, pass_fds=(verified.fd,), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)`. Bound captured stdout and controlled error text. Re-read staged manifest/lock to reject mutation, compile captured list bytes, and always clean staging. The only injected capture callable is private and named as a test seam.

- [ ] **Step 4: Delete unsafe public paths and snapshot code**

Remove public `admit_pixi_records`, public captured-byte compilation, public arbitrary runner capture, source workspace reads, `.pixi` traversal, and caller-supplied `native_lock_sha256` / resolver identity. `compiler.py` must be orchestration-only.

- [ ] **Step 5: Run focused tests and commit**

```bash
.venv/bin/pytest -q tests/catalog/test_environment_compiler.py tests/catalog/test_environments.py
git add bionodulo/nodes/environment_compiler/compiler.py tests/catalog/test_environment_compiler.py
git commit -m "fix(catalog): isolate locked pixi capture"
```

### Task 6: Verify native x86 and cross-target ARM listing locally

**Files:**
- Read only: `/home/mika/.pixi/bin/pixi`, repository `pixi.toml`, repository `pixi.lock`

- [ ] **Step 1: Verify local identity without modifying it**

Run `sha256sum /home/mika/.pixi/bin/pixi` and `/home/mika/.pixi/bin/pixi --version`. Record whether it equals the pinned x86 binary digest/version; do not download or replace it.

- [ ] **Step 2: Run locked no-install list for both targets in isolated temporary copies**

Use exact copies of the repository manifest and lock in `/tmp`, then run the local absolute binary with `list --locked --no-install --json` for `linux-64` and `linux-aarch64`. Confirm both return valid nonempty JSON and do not create an environment or mutate the copied files. Do not run `install`.

- [ ] **Step 3: Run the Python public compiler when local identity matches**

Compile both target locks using host `linux/amd64`. If the local binary is a different version/hash, report that fact and rely on the authoritative hash constants plus synthetic portable tests; do not weaken verification.

### Task 7: Final review and verification

**Files:** all touched files

- [ ] **Step 1: Run focused verification**

```bash
.venv/bin/pytest -q tests/catalog/test_environment_compiler.py tests/catalog/test_environment_registry.py tests/catalog/test_environments.py tests/catalog/test_node_spec.py
```

- [ ] **Step 2: Run full catalog verification**

```bash
.venv/bin/pytest -p no:cacheprovider -q tests/catalog
```

- [ ] **Step 3: Run static and offline checks**

Run touched-file Ruff and mypy, AST/import checks, `UV_OFFLINE=1 uv lock --check`, and `git diff --check`. Record unrelated repository-wide baseline failures separately without editing them.

- [ ] **Step 4: Review architecture and requirements**

Confirm `compiler.py` contains no YAML model decoding, release digest constants, source-workspace snapshot traversal, public runner injection, or asserted provenance. Confirm every scope item has a named RED and GREEN result.

- [ ] **Step 5: Commit any final review-only corrections**

Use a focused message, leave the worktree clean, and report all checkpoint SHAs plus exact verification evidence as `DONE` or `DONE_WITH_CONCERNS`.
