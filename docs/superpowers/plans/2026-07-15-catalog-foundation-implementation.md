# BioNodulo Catalog Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the strict typed catalog, immutable 943-ID reconciliation ledger, compiler, compatibility engine, quarantine gates, and dependency-free v2 canary nodes that every rebuilt node family will use.

**Architecture:** Add a new `bionodulo.nodes.contract` and `bionodulo.nodes.catalog` tree beside the legacy builtin tree. Pydantic models compile one `NodeSpec` into runtime, UI, compatibility, evidence, and release artifacts; no legacy class is exposed through v2 unless it is explicitly rebuilt and reaches `released`. Commit `44c247986f3bcfe8f8d93d0d719a53e4853d0437` is the origin-provenance baseline and `4092ad63a8f60e5b8080711a66428ba191bdc7b7` is the latest pre-one-tool behavior baseline.

**Tech Stack:** Python 3.11+, Pydantic v2, pytest, PyYAML, TypeScript 5, Vitest

---

## File structure

Create these focused units:

```text
bionodulo/nodes/contract/
  __init__.py              Public contract exports only
  artifacts.py             Artifact types, ports, cardinality, compatibility
  parameters.py            Scalar/value/secret parameter contracts
  outputs.py               Output collectors and validators
  environments.py          Pixi, Python, R, and container environment contracts
  execution.py             Typed execution plans and resource/recovery policy
  evidence.py              Authoritative source and verification records
  maturity.py              Access classes and computed gate records
  model.py                 NodeSpec composition and cross-field validation
  compiler.py              Deterministic catalog validation and projections

bionodulo/nodes/catalog/
  __init__.py              Catalog loader exports only
  artifacts.py             Canonical initial artifact registry
  registry.py              Static/lazy v2 registry
  core/values/string.py    string_primitive v2 implementation
  core/reporting/html.py   html_report v2 implementation
  core/input/file.py       input_file v2 implementation
  core/artifacts/info.py   file_info v2 implementation

bionodulo/nodes/generated/
  baseline-ledger.json     Generated 943-ID reconciliation record
  catalog.lock.json        Deterministic catalog digest and maturity summary
  catalog.runtime.json     Runtime projection
  catalog.ui.json          Frontend projection
  compatibility.json      Canonical directional compatibility graph
  node-index.json          Lazy node ID to module/symbol index

scripts/
  build_catalog_ledger.py  AST/git reconciliation tool
  compile_catalog.py       Empty-start fail-fast compiler entry point

tests/catalog/
  test_ledger.py
  test_artifacts.py
  test_parameters.py
  test_outputs.py
  test_environments.py
  test_execution.py
  test_evidence_maturity.py
  test_node_spec.py
  test_compiler.py
  test_registry.py
  test_core_canaries.py
  test_workflow_validation.py
```

### Task 1: Preserve the dirty work and establish an isolated implementation worktree

**Files:**
- Read: current `BioNodulo` worktree status
- Create externally: a new git worktree and branch

- [ ] **Step 1: Record the existing staged and unstaged state without changing it**

Run:

```bash
git status --short
git diff --cached --name-status
git diff --stat
git ls-files --others --exclude-standard
```

Expected: the pre-existing node split/repair changes remain visible; only the design/plan commits belong to this rebuild.

- [ ] **Step 2: Create an isolated worktree from the current committed design revision**

Follow `superpowers:using-git-worktrees`. Use branch `rebuild/node-catalog-v2` and a path outside the dirty repository. Do not stash, reset, clean, or commit the user's existing node changes.

Expected: the original worktree remains byte-for-byte dirty; the new worktree is clean.

- [ ] **Step 3: Verify both worktrees**

Run in the original and new worktrees:

```bash
git status --short
git branch --show-current
```

Expected: original status is unchanged; the new branch is `rebuild/node-catalog-v2` with no changes.

### Task 2: Build the immutable 943-ID ledger from git source

**Files:**
- Create: `scripts/build_catalog_ledger.py`
- Create: `tests/catalog/test_ledger.py`
- Generate: `bionodulo/nodes/generated/baseline-ledger.json`

- [ ] **Step 1: Write failing AST extraction and reconciliation tests**

```python
from pathlib import Path

from scripts.build_catalog_ledger import extract_nodes, reconcile, reconcile_repository


def test_extract_nodes_uses_nonempty_literal_node_ids() -> None:
    source = '''
class A:
    NODE_ID = "alpha"

class Empty:
    NODE_ID = ""

class B:
    NODE_ID: str = "beta"
'''
    found, anomalies = extract_nodes(source, "pkg.module")
    assert [item.node_id for item in found] == ["alpha", "beta"]
    assert anomalies == [{"kind": "empty_node_id", "module": "pkg.module", "class_name": "Empty"}]


def test_reconcile_rejects_missing_or_duplicate_ids() -> None:
    baseline = extract_nodes('class A:\n NODE_ID = "a"\n', "old")[0]
    candidate = extract_nodes('class A:\n NODE_ID = "b"\n', "new")[0]
    result = reconcile(baseline, candidate)
    assert result.missing_ids == ("a",)
    assert result.added_ids == ("b",)
    assert result.ok is False


def test_repository_baseline_contains_exactly_943_ids() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    result = reconcile_repository(
        repo_root,
        origin_ref="44c247986f3bcfe8f8d93d0d719a53e4853d0437",
        behavior_ref="4092ad63a8f60e5b8080711a66428ba191bdc7b7",
        comparison_ref="ce54d30e4fd07cf26809d99d25bdb267d121e525",
    )
    assert result.ok is True
    assert len(result.entries) == 943
    assert len({entry.node_id for entry in result.entries}) == 943
```

- [ ] **Step 2: Run the tests and confirm failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog/test_ledger.py
```

Expected: collection fails because `scripts.build_catalog_ledger` does not exist.

- [ ] **Step 3: Implement literal AST extraction and git-ref loading**

The script must use `git ls-tree -r --name-only <ref> -- bionodulo/nodes/builtin` and `git show <ref>:<path>`, parse class-level literal `NODE_ID` assignments, retain class AST hashes, and never import a node module. Define immutable `SourceNode`, `LedgerEntry`, and `Reconciliation` dataclasses. `reconcile_repository()` must raise on duplicate IDs and compare the exact nonempty ID sets. It records that 551 IDs originate in `galaxy_parity.py`, maps their `git blame` origin commit, and records the remaining 392 native-module origins. Inheritance and alias resolution keys symbols by module plus qualified class name and follows explicit imports; it never joins globally on class name. The `feature_counts` inheritance target remains unresolved until its contract is compared with `featurecounts`, while the other 22 statically proven aliases retain separate stable IDs and explicit canonical targets.

The CLI contract is:

```bash
.venv/bin/python scripts/build_catalog_ledger.py \
  --repo . \
  --origin-ref 44c247986f3bcfe8f8d93d0d719a53e4853d0437 \
  --behavior-ref 4092ad63a8f60e5b8080711a66428ba191bdc7b7 \
  --comparison-ref ce54d30e4fd07cf26809d99d25bdb267d121e525 \
  --output bionodulo/nodes/generated/baseline-ledger.json
```

It exits nonzero for any missing, added, or duplicate nonempty ID. `--check` regenerates in memory and compares canonical bytes without writing. It records the known empty `FeatureCountsNode.NODE_ID` anomaly separately and excludes it from the 943 stable IDs.

- [ ] **Step 4: Run tests and generate the ledger**

Run the pytest and CLI commands above.

Expected: tests pass; output reports `943 stable node IDs, 0 missing, 0 added, 1 excluded empty-ID anomaly`.

- [ ] **Step 5: Commit the ledger foundation**

```bash
git add scripts/build_catalog_ledger.py tests/catalog/test_ledger.py bionodulo/nodes/generated/baseline-ledger.json
git commit -m "feat(catalog): add immutable 943-node ledger"
```

### Task 3: Implement artifact types, ports, cardinality, and compatibility

**Files:**
- Create: `bionodulo/nodes/contract/__init__.py`
- Create: `bionodulo/nodes/contract/artifacts.py`
- Create: `bionodulo/nodes/catalog/artifacts.py`
- Create: `tests/catalog/test_artifacts.py`

- [ ] **Step 1: Write failing model and compatibility tests**

```python
import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.artifacts import (
    ArtifactContainer,
    ArtifactPort,
    ArtifactRegistry,
    ArtifactType,
    Cardinality,
)


def registry() -> ArtifactRegistry:
    return ArtifactRegistry(
        types=(
            ArtifactType(type_id="artifact.file", container=ArtifactContainer.FILE),
            ArtifactType(
                type_id="alignment.bam",
                container=ArtifactContainer.FILE,
                parents=("artifact.file",),
                extensions=(".bam",),
            ),
        )
    )


def test_bam_satisfies_explicit_file_parent() -> None:
    source = ArtifactPort(port_id="bam", artifact_type="alignment.bam", cardinality=Cardinality.ONE)
    target = ArtifactPort(port_id="file", artifact_type="artifact.file", cardinality=Cardinality.ONE)
    assert registry().can_connect(source, target) is True


def test_many_cannot_connect_to_one() -> None:
    source = ArtifactPort(port_id="reads", artifact_type="artifact.file", cardinality=Cardinality.MANY)
    target = ArtifactPort(port_id="file", artifact_type="artifact.file", cardinality=Cardinality.ONE)
    assert registry().can_connect(source, target) is False


def test_unknown_artifact_type_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ArtifactType(type_id="BAM LIST", container=ArtifactContainer.FILE)
```

- [ ] **Step 2: Verify the tests fail**

Run:

```bash
.venv/bin/python -m pytest -q tests/catalog/test_artifacts.py
```

Expected: import failure for the new contract module.

- [ ] **Step 3: Implement strict frozen Pydantic models**

Use `ConfigDict(extra="forbid", frozen=True)`. Type IDs and port IDs must match `^[a-z][a-z0-9_.-]*$`. Define `ArtifactContainer` (`file`, `directory`), `Cardinality` (`one`, `optional_one`, `many`, `nonempty_many`), immutable `ArtifactType`, and `ArtifactPort`. `ArtifactRegistry` must reject duplicate/missing parents and determine directional compatibility through the target type's accepted source or the source type's transitive parents. Cardinality compatibility must be an explicit table.

Seed `bionodulo/nodes/catalog/artifacts.py` with only the types needed by the dependency-free canaries: `artifact.file`, `artifact.directory`, `file.text`, `report.html`, and `value.string`. Later family plans add types through reviewed registry entries.

- [ ] **Step 4: Run focused tests**

Expected: all artifact tests pass, including cycle and duplicate-parent tests added during implementation.

- [ ] **Step 5: Commit**

```bash
git add bionodulo/nodes/contract bionodulo/nodes/catalog/artifacts.py tests/catalog/test_artifacts.py
git commit -m "feat(catalog): add typed artifact compatibility"
```

### Task 4: Implement scalar parameters, value ports, and secret references

**Files:**
- Create: `bionodulo/nodes/contract/parameters.py`
- Create: `tests/catalog/test_parameters.py`

- [ ] **Step 1: Write failing validation tests**

```python
import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.parameters import ParameterSpec, SecretSpec, ValueKind, ValuePort


def test_numeric_empty_default_is_rejected() -> None:
    with pytest.raises(ValidationError):
        ParameterSpec(
            parameter_id="threads",
            kind=ValueKind.INTEGER,
            required=False,
            has_default=True,
            default="",
            minimum=1,
        )


def test_boolean_is_not_an_integer_default() -> None:
    with pytest.raises(ValidationError):
        ParameterSpec(
            parameter_id="threads",
            kind=ValueKind.INTEGER,
            required=False,
            has_default=True,
            default=True,
        )


def test_secret_declares_scope_without_value() -> None:
    secret = SecretSpec(secret_id="api_key", environment_variable="EXAMPLE_API_KEY", required=True)
    assert secret.model_dump() == {
        "secret_id": "api_key",
        "environment_variable": "EXAMPLE_API_KEY",
        "required": True,
        "description": "",
    }


def test_value_port_is_separate_from_widget_parameter() -> None:
    port = ValuePort(port_id="text", kind=ValueKind.STRING, required=True)
    assert port.connectable is True
```

- [ ] **Step 2: Run and observe failure**

Run `.venv/bin/python -m pytest -q tests/catalog/test_parameters.py`.

Expected: module import failure.

- [ ] **Step 3: Implement strict parameter semantics**

Define `ValueKind` (`string`, `integer`, `number`, `boolean`, `json`), `ParameterSpec`, `ValuePort`, and `SecretSpec`. Use explicit `has_default` to distinguish no default from a literal `null`. Validate defaults without Python's `bool`-is-`int` behavior. Validate enum choices, numeric bounds, string length/pattern, and required/default conflicts. Secret values must never be fields on the contract.

- [ ] **Step 4: Run focused tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_parameters.py
git add bionodulo/nodes/contract/parameters.py tests/catalog/test_parameters.py
git commit -m "feat(catalog): add strict parameter contracts"
```

### Task 5: Implement output collection and content-validation contracts

**Files:**
- Create: `bionodulo/nodes/contract/outputs.py`
- Create: `tests/catalog/test_outputs.py`

- [ ] **Step 1: Write failing collector tests**

```python
from pathlib import Path

import pytest

from bionodulo.nodes.contract.outputs import (
    ExactCollector,
    GlobCollector,
    OutputSpec,
    StdoutCollector,
    collect_outputs,
)


def test_collect_happens_before_existence_validation(tmp_path: Path) -> None:
    produced = tmp_path / "sample_peaks.narrowPeak"
    produced.write_text("chr1\t1\t10\n", encoding="utf-8")
    spec = OutputSpec(
        port_id="peaks",
        artifact_type="artifact.file",
        collector=GlobCollector(pattern="*_peaks.narrowPeak", minimum=1, maximum=1),
        require_nonempty=True,
    )
    result = collect_outputs((spec,), tmp_path, stdout=None)
    assert result["peaks"] == produced


def test_exact_missing_output_fails(tmp_path: Path) -> None:
    spec = OutputSpec(
        port_id="report",
        artifact_type="artifact.file",
        collector=ExactCollector(relative_path="report.html"),
    )
    with pytest.raises(FileNotFoundError, match="report"):
        collect_outputs((spec,), tmp_path, stdout=None)


def test_stdout_collector_writes_declared_file(tmp_path: Path) -> None:
    spec = OutputSpec(
        port_id="tree",
        artifact_type="artifact.file",
        collector=StdoutCollector(relative_path="tree.nwk"),
        require_nonempty=True,
    )
    result = collect_outputs((spec,), tmp_path, stdout="(A,B);\n")
    assert result["tree"].read_text(encoding="utf-8") == "(A,B);\n"
```

- [ ] **Step 2: Implement discriminated collectors and validators**

Create frozen discriminated models for exact, glob, stdout, directory, and conditional collectors. `collect_outputs()` performs collection/normalization first, then validates declared keys, cardinality, existence, nonempty constraints, extensions, and optional parser validators. It returns an exact port-ID mapping and rejects undeclared outputs.

- [ ] **Step 3: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_outputs.py
git add bionodulo/nodes/contract/outputs.py tests/catalog/test_outputs.py
git commit -m "feat(catalog): collect outputs before validation"
```

### Task 6: Implement environment and execution-plan models

**Files:**
- Create: `bionodulo/nodes/contract/environments.py`
- Create: `bionodulo/nodes/contract/execution.py`
- Create: `tests/catalog/test_environments.py`
- Create: `tests/catalog/test_execution.py`

- [ ] **Step 1: Write failing environment and plan tests**

```python
import pytest
from pydantic import TypeAdapter, ValidationError

from bionodulo.nodes.contract.environments import ContainerEnvironment, PixiEnvironment
from bionodulo.nodes.contract.execution import ArgvPlan, ExecutionPlan, ResourceSpec


def test_pixi_environment_requires_pinned_package() -> None:
    with pytest.raises(ValidationError):
        PixiEnvironment(environment_id="samtools", packages=("samtools",), platforms=("linux-64",))


def test_container_requires_digest_not_mutable_tag() -> None:
    with pytest.raises(ValidationError):
        ContainerEnvironment(environment_id="tool", image="example/tool:latest")


def test_argv_plan_never_requires_shell() -> None:
    plan = ArgvPlan(
        executable="samtools",
        arguments=("view", "-b", "input.sam"),
        resources=ResourceSpec(cpus=1, memory_gib=2, disk_gib=10),
    )
    parsed = TypeAdapter(ExecutionPlan).validate_python(plan.model_dump())
    assert parsed.arguments == ("view", "-b", "input.sam")
```

- [ ] **Step 2: Implement environment unions**

Implement discriminated `PixiEnvironment`, `PythonEnvironment`, `REnvironment`, and `ContainerEnvironment`. Pixi packages require exact pins or bounded ranges, platforms are explicit, and container references require `@sha256:`. Include executable/import probes and a deterministic environment digest method.

- [ ] **Step 3: Implement execution-plan unions**

Implement `ArgvPlan`, `PipelinePlan`, `ScriptPlan`, `PythonPlan`, `RPlan`, `HttpPlan`, and `ContainerPlan` as a discriminated union. Add strict `ResourceSpec`, `NetworkPolicy`, `RetryPolicy`, and `CheckpointPolicy`. Shell execution is possible only through an explicit `ScriptPlan` with interpreter and reason; string commands are not accepted.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_environments.py tests/catalog/test_execution.py
git add bionodulo/nodes/contract/environments.py bionodulo/nodes/contract/execution.py tests/catalog/test_environments.py tests/catalog/test_execution.py
git commit -m "feat(catalog): add reproducible execution plans"
```

### Task 7: Implement authoritative evidence and computed maturity

**Files:**
- Create: `bionodulo/nodes/contract/evidence.py`
- Create: `bionodulo/nodes/contract/maturity.py`
- Create: `tests/catalog/test_evidence_maturity.py`

- [ ] **Step 1: Write failing evidence/maturity tests**

Write schema-v2 tests before implementation. Cover strict frozen round trips and
canonical digests; checked-in `RetainedText` provenance by path, catalog-content
SHA-256, and pointer; structured byte-range, JSON-pointer, and symbol locators;
exact documentation proof bindings; code-and-digest-only verification; and
computed maturity progression. Demonstrate that arbitrary authored technical
prose is accepted while no runtime/captured text origin exists. Demonstrate
that version-looking URL segments have no ownership semantics and that legacy
free-text locators, version locators, summaries, and reasons are rejected.

- [ ] **Step 2: Implement evidence models and maturity derivation**

Evidence source kinds are `official_manual`, `official_api_schema`,
`upstream_source`, `installed_help`, and `package_recipe`. Official documentation
must carry an exact `DocumentationVersionProof`; its URL is never parsed to
infer tool ownership or version. Claims reference a known source, canonical
contract pointer, structured content locator, authored statement provenance,
and content/value digests. Captured runtime data is represented only by closed
codes and SHA-256 digests, never retained stdout, stderr, environment values, or
host paths.

The evidence and maturity roots require `schema_version: 2`. Maturity gates are
inventoried, evidence, contract, command, environment, tool smoke, cloud, and
workflow. Every assessment, including failure, references retained evidence;
human-readable labels and reasons are computed from enums and are not
serialized. `released` is computed and cannot be supplied by callers. Access
classes include public, rate-limited, secret-required, large-reference, GPU,
BYOL, and service-license.

The contract model does not prove authorship by inspecting prose. It retains
immutable author provenance, and the trusted Task 9 catalog loader must verify
the repository-relative path, canonical source-blob digest, JSON pointer, and
selected value. Schema-v1 data receives no permissive compatibility parser. A
one-shot offline migration must construct these facts and quarantine records
whose documentation binding cannot be proved.

- [ ] **Step 3: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_evidence_maturity.py
git add bionodulo/nodes/contract/evidence.py bionodulo/nodes/contract/maturity.py tests/catalog/test_evidence_maturity.py
git commit -m "feat(catalog): add evidence-backed maturity gates"
```

### Task 8: Compose NodeSpec and enforce cross-field invariants

**Files:**
- Create: `bionodulo/nodes/contract/model.py`
- Update: `bionodulo/nodes/contract/__init__.py`
- Create: `tests/catalog/test_node_spec.py`

- [ ] **Step 1: Write failing NodeSpec tests**

```python
import pytest
from pydantic import ValidationError

from bionodulo.nodes.contract.model import NodeIdentity, NodePresentation, NodeSpec


def minimal_spec() -> NodeSpec:
    return NodeSpec(
        identity=NodeIdentity(
            node_id="string_primitive",
            contract_version="2.0.0",
            implementation_version="1.0.0",
        ),
        presentation=NodePresentation(
            display_name="String",
            description="Emit a string value.",
            palette_path=("Core", "Values"),
            domain_tags=("core",),
            operation_kind="source",
            owner="bionodulo",
        ),
        value_inputs=(),
        artifact_inputs=(),
        parameters=(),
        secrets=(),
        outputs=(),
        environment=None,
        execution_factory="bionodulo.nodes.catalog.core.values.string:build_plan",
        evidence=None,
        maturity=None,
    )


def test_duplicate_port_ids_across_input_kinds_are_rejected() -> None:
    spec = minimal_spec().model_copy(
        update={
            "value_inputs": ({"port_id": "input", "kind": "string", "required": True},),
            "parameters": ({"parameter_id": "input", "kind": "string", "required": True},),
        }
    )
    with pytest.raises(ValidationError):
        NodeSpec.model_validate(spec.model_dump())


def test_node_id_is_stable_machine_identifier() -> None:
    with pytest.raises(ValidationError):
        NodeIdentity(node_id="Samtools Sort", contract_version="2.0.0", implementation_version="1.0.0")
```

- [ ] **Step 2: Implement NodeSpec composition**

`NodeSpec` composes identity, presentation, artifact/value inputs, parameters, secrets, outputs, environment, execution factory, evidence, and maturity. Validate unique IDs across all input kinds, valid import-path syntax, output artifact types, environment/runtime agreement, evidence source references, and explicit port aliases for migrations. Tool version and environment are optional only for BioNodulo-owned in-process core nodes.

- [ ] **Step 3: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_node_spec.py
git add bionodulo/nodes/contract/model.py bionodulo/nodes/contract/__init__.py tests/catalog/test_node_spec.py
git commit -m "feat(catalog): compose strict node specifications"
```

### Task 9: Implement the empty-start fail-fast compiler

**Files:**
- Create: `bionodulo/nodes/contract/compiler.py`
- Create: `scripts/compile_catalog.py`
- Create: `tests/catalog/test_compiler.py`

- [ ] **Step 1: Write failing compiler tests**

```python
import pytest

from bionodulo.nodes.contract.compiler import CatalogCompiler, CatalogError


def test_duplicate_node_id_is_fatal(sample_spec) -> None:
    with pytest.raises(CatalogError, match="duplicate node_id"):
        CatalogCompiler().compile((sample_spec, sample_spec))


def test_broken_module_is_fatal_not_warn_and_skip() -> None:
    def broken_importer(_module_name: str):
        raise RuntimeError("broken")

    with pytest.raises(CatalogError, match="broken"):
        CatalogCompiler(importer=broken_importer).compile_modules(("bad.module",))


def test_projection_digest_is_deterministic(sample_spec) -> None:
    first = CatalogCompiler().compile((sample_spec,))
    second = CatalogCompiler().compile((sample_spec,))
    assert first.catalog_digest == second.catalog_digest
```

- [ ] **Step 2: Implement discovery, validation, and projections**

The compiler takes an explicit module list; it does not walk with `pkgutil` and does not read prior generated JSON. It imports each declared module, calls `get_node_specs()`, validates every spec against the artifact registry and baseline ledger, and fails on any exception. Sort all projections by stable IDs and use canonical JSON (`sort_keys=True`, compact separators, UTF-8) for SHA-256.

Emit runtime, UI, compatibility, node-index, and catalog-lock projections. The UI projection preserves artifact ports as ports and parameters as widgets; no fallback-to-string conversion exists.

- [ ] **Step 3: Add CLI check/write modes**

```bash
.venv/bin/python scripts/compile_catalog.py --check
.venv/bin/python scripts/compile_catalog.py --write
```

`--check` compares byte-for-byte and exits nonzero on stale output. `--write` writes all files through temporary siblings followed by `os.replace` so a partial generation never leaves mixed digests.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_compiler.py
git add bionodulo/nodes/contract/compiler.py scripts/compile_catalog.py tests/catalog/test_compiler.py
git commit -m "feat(catalog): add fail-fast catalog compiler"
```

### Task 10: Rebuild the dependency-free canary nodes

**Files:**
- Create: `bionodulo/nodes/catalog/core/values/string.py`
- Create: `bionodulo/nodes/catalog/core/reporting/html.py`
- Create: `bionodulo/nodes/catalog/core/input/file.py`
- Create: `bionodulo/nodes/catalog/core/artifacts/info.py`
- Create package `__init__.py` files with no re-exports
- Create: `tests/catalog/test_core_canaries.py`

- [ ] **Step 1: Write failing spec and execution tests**

```python
from pathlib import Path

import importlib

import pytest

from bionodulo.nodes.catalog.core.artifacts.info import FILE_INFO_SPEC, run_file_info
from bionodulo.nodes.catalog.core.input.file import INPUT_FILE_SPEC, run_input_file
from bionodulo.nodes.catalog.core.reporting.html import HTML_REPORT_SPEC, run_html_report
from bionodulo.nodes.catalog.core.values.string import STRING_SPEC, run_string


@pytest.mark.asyncio
async def test_dependency_free_string_to_html_chain(tmp_path: Path) -> None:
    text = await run_string(value="bionodulo-cloud-canary-v1")
    report = await run_html_report(text_sections=text, output_dir=tmp_path)
    assert report.name == "report.html"
    assert "bionodulo-cloud-canary-v1" in report.read_text(encoding="utf-8")
    assert STRING_SPEC.identity.node_id == "string_primitive"
    assert HTML_REPORT_SPEC.identity.node_id == "html_report"


@pytest.mark.asyncio
async def test_file_canary_preserves_artifact_identity(tmp_path: Path) -> None:
    source = tmp_path / "canary.txt"
    source.write_text("canary\n", encoding="utf-8")
    selected = await run_input_file(file=source)
    info = await run_file_info(file=selected)
    assert info["size"] == 7
    assert info["sha256"]
    assert INPUT_FILE_SPEC.identity.node_id == "input_file"
    assert FILE_INFO_SPEC.identity.node_id == "file_info"
```

- [ ] **Step 2: Implement four strict core specs and functions**

Preserve the stable IDs and legacy port IDs needed by the canaries. Use BioNodulo-owned `PythonPlan`/in-process functions, no external environment, exact output port IDs, escaped HTML, and SHA-256 file identity. Add authoritative evidence pointing to BioNodulo source/design rather than inventing upstream tool citations.

- [ ] **Step 3: Register explicit modules and compile**

The catalog's module list initially contains exactly these four modules. Generate projections; unreconstructed baseline IDs remain ledger-only and quarantined.

- [ ] **Step 4: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_core_canaries.py
.venv/bin/python scripts/compile_catalog.py --write
git add bionodulo/nodes/catalog bionodulo/nodes/generated tests/catalog/test_core_canaries.py
git commit -m "feat(catalog): rebuild dependency-free canary nodes"
```

### Task 11: Add the lazy v2 registry and quarantine enforcement

**Files:**
- Create: `bionodulo/nodes/catalog/registry.py`
- Create: `tests/catalog/test_registry.py`

- [ ] **Step 1: Write failing registry tests**

```python
import pytest

from bionodulo.nodes.catalog.registry import CatalogRegistry, QuarantinedNodeError, UnknownNodeError


def test_registry_imports_only_requested_node(compiled_catalog, monkeypatch) -> None:
    imported: list[str] = []

    def importer(name: str):
        imported.append(name)
        return importlib.import_module(name)

    registry = CatalogRegistry(compiled_catalog, importer=importer)
    registry.resolve("string_primitive", allow_quarantined=True)
    assert imported == ["bionodulo.nodes.catalog.core.values.string"]


def test_normal_resolution_rejects_quarantined(compiled_catalog) -> None:
    registry = CatalogRegistry(compiled_catalog)
    with pytest.raises(QuarantinedNodeError):
        registry.resolve("string_primitive")


def test_unknown_id_never_falls_back_to_legacy(compiled_catalog) -> None:
    registry = CatalogRegistry(compiled_catalog)
    with pytest.raises(UnknownNodeError):
        registry.resolve("not_a_node")
```

- [ ] **Step 2: Implement static lookup and development-only override**

Load only generated `node-index.json` and `catalog.runtime.json`, verify matching catalog digests, and import one requested module/symbol. Default resolution requires `released`. The quarantine override is an explicit constructor option used only by tests/internal lab; no environment-variable fallback silently enables it. Never fall back to legacy for a missing or failed v2 node.

- [ ] **Step 3: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_registry.py
git add bionodulo/nodes/catalog/registry.py tests/catalog/test_registry.py
git commit -m "feat(catalog): enforce lazy quarantined registry"
```

### Task 12: Add canonical workflow and edge validation without switching production yet

**Files:**
- Create: `bionodulo/workflow/catalog_validation.py`
- Create: `tests/catalog/test_workflow_validation.py`

- [ ] **Step 1: Write failing exact-port/type tests**

```python
from bionodulo.workflow.catalog_validation import validate_catalog_workflow


def test_nonexistent_source_port_is_rejected(canary_catalog) -> None:
    workflow = {
        "nodes": [
            {"id": "a", "type": "string_primitive", "inputs": {"value": "x"}},
            {"id": "b", "type": "html_report", "inputs": {}},
        ],
        "edges": [{"source": "a", "sourceHandle": "missing", "target": "b", "targetHandle": "text_sections"}],
    }
    errors = validate_catalog_workflow(workflow, canary_catalog)
    assert [error.code for error in errors] == ["unknown_source_port"]


def test_quarantined_node_is_rejected(canary_catalog) -> None:
    workflow = {"nodes": [{"id": "a", "type": "string_primitive", "inputs": {"value": "x"}}], "edges": []}
    errors = validate_catalog_workflow(workflow, canary_catalog)
    assert [error.code for error in errors] == ["node_quarantined"]
```

- [ ] **Step 2: Implement exact validation**

Validate node IDs, unique instance IDs, parameter names/types/defaults, exact source/output and target/input port IDs, artifact/value compatibility, cardinality, required inputs, cycles, and quarantine status. Return stable structured error codes with node/edge references. Keep the existing validator unchanged until the coordinated cutover.

- [ ] **Step 3: Run tests and commit**

```bash
.venv/bin/python -m pytest -q tests/catalog/test_workflow_validation.py
git add bionodulo/workflow/catalog_validation.py tests/catalog/test_workflow_validation.py
git commit -m "feat(workflow): validate exact catalog contracts"
```

### Task 13: Generate frontend types and remove compatibility guessing behind a v2 flag

**Files:**
- Create: `web/src/generated/catalog.ui.json`
- Create: `web/src/generated/compatibility.json`
- Create: `web/src/catalog/types.ts`
- Create: `web/src/catalog/compatibility.ts`
- Create: `web/src/catalog/compatibility.test.ts`
- Modify: `web/src/components/canvas/WorkflowCanvas.tsx`
- Modify: `web/src/hooks/data/useObjectInfo.ts`

- [ ] **Step 1: Write failing Vitest compatibility tests**

```typescript
import { describe, expect, it } from "vitest";
import { canConnect } from "./compatibility";

describe("catalog compatibility", () => {
  it("accepts an explicitly compatible edge", () => {
    expect(canConnect("value.string", "one", "value.string", "one")).toBe(true);
  });

  it("rejects many-to-one and unrelated type families", () => {
    expect(canConnect("sequence.fastq", "many", "alignment.bam", "one")).toBe(false);
  });
});
```

- [ ] **Step 2: Generate/copy compiler projections into the SPA build**

Extend `scripts/compile_catalog.py --write` to write the same canonical UI and compatibility JSON into `web/src/generated` and assert the embedded digest equals `catalog.lock.json`. Define TypeScript types that preserve artifact ports, value ports, parameters, secrets, outputs, cardinality, maturity, and access class.

- [ ] **Step 3: Implement table-driven compatibility**

`canConnect()` looks up exact generated type/cardinality pairs and defaults to `false` for unknown values. Add a v2 catalog path in `WorkflowCanvas.tsx` that uses this function and supports multiple incoming edges only when the target cardinality accepts many. Keep the old path reachable only while the legacy app remains the active release.

- [ ] **Step 4: Make v2 metadata drift fail closed**

`useObjectInfo.ts` must reject schema/digest mismatch and show a maintenance/error state. It must not normalize malformed metadata or retain last-good metadata under a different contract digest. Add a hook test that supplies mismatched `catalogDigest` and asserts no nodes are returned.

- [ ] **Step 5: Run tests and commit**

```bash
npm --prefix web test -- --run src/catalog/compatibility.test.ts
npm --prefix web run build
git add web/src/generated web/src/catalog web/src/components/canvas/WorkflowCanvas.tsx web/src/hooks/data/useObjectInfo.ts scripts/compile_catalog.py
git commit -m "feat(web): consume canonical catalog compatibility"
```

### Task 14: Add deterministic pre-build contract identity and CI gates

**Files:**
- Create: `bionodulo/release/__init__.py`
- Create: `bionodulo/release/contract.py`
- Create: `scripts/build_contract_manifest.py`
- Create: `tests/catalog/test_contract_manifest.py`
- Modify: `bionodulo/api/routes.py`
- Create: `tests/catalog/test_release_api.py`
- Modify: `.github/workflows/ci.yml`

- [ ] **Step 1: Write failing deterministic release tests**

```python
from bionodulo.release.contract import build_contract_manifest


def test_contract_manifest_binds_catalog_evidence_locks_and_source() -> None:
    digest = "sha256:" + "1" * 64
    manifest = build_contract_manifest(
        catalog_digest=digest,
        template_digest="sha256:" + "2" * 64,
        evidence_digest="sha256:" + "3" * 64,
        compatibility_digest="sha256:" + "4" * 64,
        fixture_digest="sha256:" + "5" * 64,
        environment_locks={"linux-64": "sha256:" + "6" * 64},
        app_commit="4092ad63a8f60e5b8080711a66428ba191bdc7b7",
        website_commit="59804da000000000000000000000000000000000",
        workflow_protocol_version=2,
        dispatch_contract_version=2,
    )
    assert manifest.catalog_digest == digest
    assert manifest.contract_id.startswith("sha256:")
    assert manifest.model_dump_json() == build_contract_manifest(
        catalog_digest=digest,
        template_digest="sha256:" + "2" * 64,
        evidence_digest="sha256:" + "3" * 64,
        compatibility_digest="sha256:" + "4" * 64,
        fixture_digest="sha256:" + "5" * 64,
        environment_locks={"linux-64": "sha256:" + "6" * 64},
        app_commit="4092ad63a8f60e5b8080711a66428ba191bdc7b7",
        website_commit="59804da000000000000000000000000000000000",
        workflow_protocol_version=2,
        dispatch_contract_version=2,
    ).model_dump_json()
```

- [ ] **Step 2: Implement canonical release manifest generation**

Hash sorted template, catalog, evidence, compatibility, fixture, and per-platform environment-lock bytes. Require immutable app and website source commits plus protocol versions. Write canonical `contract.json` atomically and derive `contract_id` from sorted compact JSON excluding only the `contract_id` field itself. Images embed this pre-build contract; the website release orchestrator later creates the signed post-build bundle containing final artifact digests.

- [ ] **Step 3: Expose embedded contract identity**

Expose a read-only editor-Lambda/API release endpoint that returns contract ID, catalog digest, template digest, and protocol versions from the embedded `contract.json`. It must not infer identity from mutable image tags or return secret configuration. Add a route test asserting exact embedded values and `Cache-Control: no-store`.

- [ ] **Step 4: Add fail-fast CI checks**

CI commands:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/build_catalog_ledger.py --check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/compile_catalog.py --check
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog
npm --prefix web test -- --run src/catalog/compatibility.test.ts
```

Any warning, changed generated file, import failure, or ledger mismatch fails CI.

- [ ] **Step 5: Commit**

```bash
git add bionodulo/release bionodulo/api/routes.py scripts/build_contract_manifest.py tests/catalog/test_contract_manifest.py tests/catalog/test_release_api.py .github/workflows/ci.yml
git commit -m "feat(release): bind catalog to immutable contract"
```

### Task 15: Verify the complete foundation and hand off family reconstruction

**Files:**
- Verify all files above
- Update: `bionodulo/nodes/generated/catalog.lock.json`

- [ ] **Step 1: Run local verification**

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/catalog
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/compile_catalog.py --check
.venv/bin/ruff check bionodulo/nodes/contract bionodulo/nodes/catalog scripts/build_catalog_ledger.py scripts/compile_catalog.py tests/catalog
.venv/bin/mypy bionodulo/nodes/contract bionodulo/nodes/catalog
npm --prefix web test -- --run src/catalog/compatibility.test.ts
npm --prefix web run build
```

Expected: all commands pass; the catalog lock reports `943 inventoried`, `4 rebuilt`, `939 quarantined`, and one excluded empty-ID anomaly.

- [ ] **Step 2: Run independent code review**

Use `superpowers:requesting-code-review`. Review against both the design spec and this plan, with special attention to lossy projection, accidental legacy fallback, generated-file seeding, and boolean/numeric validation.

- [ ] **Step 3: Fix findings with TDD and rerun verification**

Each defect receives a failing regression test before the change. Rerun the complete command set.

- [ ] **Step 4: Commit verification corrections**

```bash
git add bionodulo scripts tests web .github/workflows/ci.yml
git commit -m "test(catalog): verify v2 foundation gates"
```

- [ ] **Step 5: Produce the family migration queue**

Run the inventory generator from the next plan against `baseline-ledger.json`. The first dependency-light workflow wave is:

```text
core inputs/artifact staging
  -> FastQC + fastp
  -> BWA-MEM2
  -> samtools sort/index/stats
  -> mosdepth
  -> bcftools mpileup/call/filter/norm/index
  -> MultiQC/core reporting
```

Do not expose these nodes until their evidence, command, environment, real-tool, cloud, and workflow gates all pass.
