from __future__ import annotations

import hashlib
import io
import json
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.build_catalog_ledger as ledger_builder
from scripts.build_catalog_ledger import (
    DuplicateNodeIdError,
    LedgerEntry,
    Reconciliation,
    canonical_json_bytes,
    extract_nodes,
    ledger_bytes,
    reconcile,
    reconcile_repository,
    resolve_aliases,
    write_or_check,
)


ORIGIN_REF = "44c247986f3bcfe8f8d93d0d719a53e4853d0437"
SPLIT_REF = "a346ded79659d5a10e3056d7cf8ea2bf482606a7"
BEHAVIOR_REF = "4092ad63a8f60e5b8080711a66428ba191bdc7b7"
COMPARISON_REF = "ce54d30e4fd07cf26809d99d25bdb267d121e525"
FORENSIC_RAW_AST_DIGEST = "1b9b2abbd518dc8ed22e53e333a74f37b93fb156266e7a1262495227ebc910c3"
REPO_ROOT = Path(__file__).resolve().parents[2]
LINKED_PROJECT_PYTHON = REPO_ROOT.parents[1] / ".venv" / "bin" / "python"
AVAILABLE_PYTHONS = tuple(
    dict.fromkeys(
        candidate
        for candidate in (
            sys.executable,
            str(LINKED_PROJECT_PYTHON) if LINKED_PROJECT_PYTHON.is_file() else None,
            shutil.which("python3.11"),
            shutil.which("python3.12"),
            shutil.which("python3.13"),
        )
        if candidate is not None
    )
)


def _ledger_cli_args(output: Path) -> list[str]:
    return [
        "scripts/build_catalog_ledger.py",
        "--repo",
        ".",
        "--origin-ref",
        ORIGIN_REF,
        "--split-ref",
        SPLIT_REF,
        "--behavior-ref",
        BEHAVIOR_REF,
        "--comparison-ref",
        COMPARISON_REF,
        "--output",
        str(output),
        "--check",
    ]


def _run_test_git(repo: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return process.stdout.strip()


def _init_test_git_repo(repo: Path) -> str:
    repo.mkdir()
    _run_test_git(repo, "init", "--quiet")
    _run_test_git(repo, "config", "user.email", "catalog-tests@example.invalid")
    _run_test_git(repo, "config", "user.name", "Catalog Tests")
    (repo / "payload.txt").write_text("first\n")
    _run_test_git(repo, "add", "payload.txt")
    _run_test_git(repo, "commit", "--quiet", "-m", "first")
    return _run_test_git(repo, "rev-parse", "HEAD")


class _FakeBatchProcess:
    def __init__(self, stdout: bytes, *, stderr: bytes = b"", returncode: int = 0) -> None:
        self.stdin: io.BytesIO | None = io.BytesIO()
        self.stdout = io.BytesIO(stdout)
        self.stderr = io.BytesIO(stderr)
        self.returncode = returncode

    def communicate(self) -> tuple[bytes, bytes]:
        return self.stdout.read(), self.stderr.read()

    def kill(self) -> None:
        self.returncode = -9

    def wait(self) -> int:
        return self.returncode


@pytest.fixture(scope="module")
def repository_reconciliation() -> Reconciliation:
    return reconcile_repository(
        REPO_ROOT,
        origin_ref=ORIGIN_REF,
        split_ref=SPLIT_REF,
        behavior_ref=BEHAVIOR_REF,
        comparison_ref=COMPARISON_REF,
    )


def test_extract_nodes_uses_class_level_literal_and_annotated_node_ids() -> None:
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
    assert found[0].qualified_class == "pkg.module.A"
    assert len(found[0].raw_class_sha256) == 64
    assert len(found[0].ast_sha256) == 64
    assert anomalies == (
        {"kind": "empty_node_id", "module": "pkg.module", "class_name": "Empty"},
    )


def test_extract_nodes_rejects_dynamic_node_id_assignment() -> None:
    source = '''
class Dynamic:
    NODE_ID = make_id()
'''

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"pkg\.module\.Dynamic NODE_ID declaration at line 3 must be a literal string",
    ):
        extract_nodes(source, "pkg.module")


def test_extract_nodes_rejects_multiple_node_id_assignments() -> None:
    source = '''
class Multiple:
    NODE_ID = "first"
    NODE_ID = "second"
'''

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"pkg\.module\.Multiple has multiple NODE_ID declarations at lines 3, 4",
    ):
        extract_nodes(source, "pkg.module")


def test_extract_nodes_rejects_conditional_node_id_assignment() -> None:
    source = '''
class Conditional:
    if enabled:
        NODE_ID = "conditional"
'''

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"pkg\.module\.Conditional has conditional NODE_ID declaration at line 4",
    ):
        extract_nodes(source, "pkg.module")


def test_extract_nodes_rejects_conditional_class_declaring_node_id() -> None:
    source = '''
if enabled:
    class ConditionalClass:
        NODE_ID = "conditional_class"
'''

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=(
            r"unsupported conditional class pkg\.module\.ConditionalClass "
            r"declaring NODE_ID at line 3"
        ),
    ):
        extract_nodes(source, "pkg.module")


def test_extract_nodes_rejects_function_local_class_declaring_node_id() -> None:
    source = '''
def build_node():
    class LocalClass:
        NODE_ID = "local_class"
'''

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"unsupported local class pkg\.module\.LocalClass declaring NODE_ID at line 3",
    ):
        extract_nodes(source, "pkg.module")


def test_extract_nodes_ignores_ordinary_method_local_node_id_variables() -> None:
    source = '''
class Supported:
    NODE_ID = "supported"

    def build(self):
        NODE_ID = make_id()
        return NODE_ID
'''

    found, anomalies = extract_nodes(source, "pkg.module")

    assert [item.node_id for item in found] == ["supported"]
    assert anomalies == ()


def test_extract_nodes_returns_immutable_anomaly_evidence() -> None:
    _found, anomalies = extract_nodes(
        'class Empty:\n    NODE_ID = ""\n',
        "pkg.module",
    )

    with pytest.raises(TypeError):
        anomalies[0]["kind"] = "mutated"  # type: ignore[index]


@pytest.mark.parametrize(
    "binding",
    [
        "for NODE_ID in values:\n    pass",
        "with context() as NODE_ID:\n    pass",
        "import package as NODE_ID",
        "from package import value as NODE_ID",
        "def NODE_ID(self):\n    pass",
        "class NODE_ID:\n    pass",
        'NODE_ID = "temporary"\ndel NODE_ID',
        'NODE_ID += "suffix"',
        "try:\n    pass\nexcept Exception as NODE_ID:\n    pass",
        "match value:\n    case NODE_ID:\n        pass",
        'value = (NODE_ID := "walrus")',
        'global NODE_ID\nNODE_ID = "module_value"',
    ],
)
def test_extract_nodes_rejects_other_class_namespace_node_id_bindings(binding: str) -> None:
    indented = "\n".join(f"    {line}" for line in binding.splitlines())
    source = f"class Unsupported:\n{indented}\n"

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"pkg\.module\.Unsupported has (?:unsupported|conditional) NODE_ID",
    ):
        extract_nodes(source, "pkg.module")


@pytest.mark.parametrize(
    "definition",
    [
        "@(NODE_ID := decorator)\ndef method(self):\n    pass",
        'def method(self, value=(NODE_ID := "default")):\n    pass',
        'def method(self, *, value=(NODE_ID := "kw_default")):\n    pass',
        "def method(self, value: (NODE_ID := annotation)):\n    pass",
        "def method(self) -> (NODE_ID := annotation):\n    pass",
        "class Nested((NODE_ID := Base)):\n    pass",
        "class Nested(metaclass=(NODE_ID := Meta)):\n    pass",
        "@(NODE_ID := decorator)\nclass Nested:\n    pass",
        'factory = lambda value=(NODE_ID := "lambda_default"): value',
    ]
    + (
        [
            "def method[T: (NODE_ID := Bound)](self):\n    pass",
            "class Nested[T: (NODE_ID := Bound)]:\n    pass",
        ]
        if sys.version_info >= (3, 12)
        else []
    )
    + (
        [
            "def method[T = (NODE_ID := Default)](self):\n    pass",
            "class Nested[T = (NODE_ID := Default)]:\n    pass",
        ]
        if sys.version_info >= (3, 13)
        else []
    ),
)
def test_extract_nodes_rejects_node_id_effects_in_definition_headers(definition: str) -> None:
    indented = "\n".join(f"    {line}" for line in definition.splitlines())
    source = f'class Outer:\n    NODE_ID = "stable"\n{indented}\n'

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"pkg\.module\.Outer has unsupported NODE_ID class-scope binding",
    ):
        extract_nodes(source, "pkg.module")


def test_ast_hash_uses_a_version_neutral_golden_schema() -> None:
    found, _anomalies = extract_nodes('class A:\n    NODE_ID = "alpha"\n', "pkg.module")

    assert found[0].ast_sha256 == "e56fe5584149ad41156fd05ffe79dc51a63bf5fe84ba63ad94a6e2aa501ac700"


def test_required_commit_resolution_peels_a_supplied_ref_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_git(_repo: Path, *arguments: str) -> bytes:
        calls.append(arguments)
        return ("a" * 40 + "\n").encode("ascii")

    monkeypatch.setattr(ledger_builder, "_git", fake_git)

    resolved = ledger_builder._resolve_required_commit(tmp_path, "moving", "behavior")

    assert resolved == "a" * 40
    assert calls == [("rev-parse", "--verify", "moving^{commit}")]


def test_required_commit_resolution_explains_shallow_history_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git(_repo: Path, *arguments: str) -> bytes:
        if arguments == ("rev-parse", "--is-shallow-repository"):
            return b"true\n"
        raise ledger_builder.GitCommandError("unknown revision")

    monkeypatch.setattr(ledger_builder, "_git", fake_git)

    with pytest.raises(
        ledger_builder.GitCommandError,
        match=r"required comparison ref 'missing'.*fetch-depth: 0.*git fetch --unshallow",
    ):
        ledger_builder._resolve_required_commit(tmp_path, "missing", "comparison")


def test_required_commit_resolution_explains_missing_history_recovery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_git(_repo: Path, *arguments: str) -> bytes:
        if arguments == ("rev-parse", "--is-shallow-repository"):
            return b"false\n"
        raise ledger_builder.GitCommandError("unknown revision")

    monkeypatch.setattr(ledger_builder, "_git", fake_git)

    with pytest.raises(
        ledger_builder.GitCommandError,
        match=r"required origin ref 'missing'.*fetch the commit explicitly.*git fetch --all --tags",
    ):
        ledger_builder._resolve_required_commit(tmp_path, "missing", "origin")


def test_repository_refs_are_each_resolved_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    commits = {
        "origin-name": "1" * 40,
        "split-name": "2" * 40,
        "behavior-name": "3" * 40,
        "comparison-name": "4" * 40,
    }

    def resolve(_repo: Path, ref: str, label: str) -> str:
        calls.append((ref, label))
        return commits[ref]

    monkeypatch.setattr(ledger_builder, "_resolve_required_commit", resolve)

    resolved = ledger_builder._resolve_repository_refs(
        tmp_path,
        origin_ref="origin-name",
        split_ref="split-name",
        behavior_ref="behavior-name",
        comparison_ref="comparison-name",
    )

    assert resolved.origin == "1" * 40
    assert resolved.split == "2" * 40
    assert resolved.behavior == "3" * 40
    assert resolved.comparison == "4" * 40
    assert calls == [
        ("origin-name", "origin"),
        ("split-name", "immediate split"),
        ("behavior-name", "behavior"),
        ("comparison-name", "comparison"),
    ]


def test_git_batch_reader_reads_blob_by_oid(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    commit = _init_test_git_repo(repo)
    blob = ledger_builder._tree_blobs(repo, commit, "payload.txt")["payload.txt"]

    with ledger_builder._GitBatchReader(repo) as batch:
        content = batch.read_blob(blob)

    assert content == b"first\n"


def test_resolved_symbolic_ref_keeps_batch_reads_on_one_snapshot(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    first_commit = _init_test_git_repo(repo)
    resolved = ledger_builder._resolve_required_commit(repo, "HEAD", "behavior")
    (repo / "payload.txt").write_text("second\n")
    _run_test_git(repo, "add", "payload.txt")
    _run_test_git(repo, "commit", "--quiet", "-m", "second")

    blob = ledger_builder._tree_blobs(repo, resolved, "payload.txt")["payload.txt"]
    with ledger_builder._GitBatchReader(repo) as batch:
        content = batch.read_blob(blob)

    assert resolved == first_commit
    assert _run_test_git(repo, "rev-parse", "HEAD") != resolved
    assert content == b"first\n"


def test_resolved_snapshot_ignores_git_replacement_objects(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    first_commit = _init_test_git_repo(repo)
    (repo / "payload.txt").write_text("replacement\n")
    _run_test_git(repo, "add", "payload.txt")
    _run_test_git(repo, "commit", "--quiet", "-m", "replacement")
    replacement_commit = _run_test_git(repo, "rev-parse", "HEAD")
    _run_test_git(repo, "replace", first_commit, replacement_commit)

    resolved = ledger_builder._resolve_required_commit(repo, first_commit, "behavior")
    blob = ledger_builder._tree_blobs(repo, resolved, "payload.txt")["payload.txt"]
    with ledger_builder._GitBatchReader(repo) as batch:
        content = batch.read_blob(blob)

    assert resolved == first_commit
    assert content == b"first\n"


def test_git_batch_reader_rejects_a_missing_object(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_test_git_repo(repo)

    with ledger_builder._GitBatchReader(repo) as batch:
        with pytest.raises(
            ledger_builder.GitCommandError,
            match=r"cat-file --batch could not find object 000000",
        ):
            batch.read_blob("0" * 40)


def test_git_batch_reader_rejects_truncated_blob_content(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_id = "a" * 40
    process = _FakeBatchProcess(f"{object_id} blob 5\nabc".encode("ascii"))
    monkeypatch.setattr(ledger_builder.subprocess, "Popen", lambda *_args, **_kwargs: process)

    with ledger_builder._GitBatchReader(tmp_path) as batch:
        with pytest.raises(
            ledger_builder.GitCommandError,
            match=r"truncated blob content: expected 5 bytes, received 3",
        ):
            batch.read_blob(object_id)


def test_git_batch_reader_rejects_negative_blob_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_id = "a" * 40
    process = _FakeBatchProcess(f"{object_id} blob -1\n".encode("ascii"))
    monkeypatch.setattr(ledger_builder.subprocess, "Popen", lambda *_args, **_kwargs: process)

    with ledger_builder._GitBatchReader(tmp_path) as batch:
        with pytest.raises(
            ledger_builder.GitCommandError,
            match=r"invalid blob size b'-1'",
        ):
            batch.read_blob(object_id)


def test_git_batch_reader_surfaces_nonzero_exit_on_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = _FakeBatchProcess(b"", stderr=b"fatal: batch failed\n", returncode=2)
    monkeypatch.setattr(ledger_builder.subprocess, "Popen", lambda *_args, **_kwargs: process)

    with pytest.raises(
        ledger_builder.GitCommandError,
        match=r"cat-file --batch close failed.*exit 2: fatal: batch failed",
    ):
        with ledger_builder._GitBatchReader(tmp_path):
            pass


def test_ref_inventory_reads_tree_blobs_through_the_batch_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_id = "a" * 40
    source_path = "bionodulo/nodes/builtin/example.py"
    calls: list[str] = []

    class Batch:
        def read_blob(self, requested: str) -> bytes:
            calls.append(requested)
            return b'class Example:\n    NODE_ID = "example"\n'

    monkeypatch.setattr(
        ledger_builder,
        "_tree_blobs",
        lambda *_args: {source_path: object_id},
    )

    inventory = ledger_builder._load_ref_inventory(tmp_path, "b" * 40, Batch())

    assert [item.node_id for item in inventory.declarations] == ["example"]
    assert inventory.declarations[0].git_blob == object_id
    assert calls == [object_id]
    with pytest.raises(TypeError):
        inventory.module_sources["new.module"] = "source"  # type: ignore[index]


def test_template_inventory_reads_tree_blobs_through_the_batch_reader(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object_id = "c" * 40
    source_path = "templates/example.json"
    calls: list[str] = []

    class Batch:
        def read_blob(self, requested: str) -> bytes:
            calls.append(requested)
            return b'{"nodes":[{"id":"one","type":"alpha"}],"edges":[]}'

    monkeypatch.setattr(
        ledger_builder,
        "_tree_blobs",
        lambda *_args: {source_path: object_id},
    )

    references, templates, examples, instances, edges = ledger_builder._template_references(
        tmp_path,
        "d" * 40,
        {"alpha"},
        Batch(),
    )

    assert len(references["alpha"]) == 1
    assert (templates, examples, instances, edges) == (1, 0, 1, 0)
    assert calls == [object_id]


def test_strict_workflow_json_rejects_duplicate_object_keys() -> None:
    raw = b'{"nodes":[],"nodes":[],"edges":[]}'

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=r"workflow templates/duplicate.json contains duplicate JSON object key 'nodes'",
    ):
        ledger_builder._strict_json_loads(raw, source_path="templates/duplicate.json")


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_strict_workflow_json_rejects_non_finite_numbers(constant: str) -> None:
    raw = f'{{"nodes":[],"edges":[],"value":{constant}}}'.encode("ascii")

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=rf"workflow templates/non-finite.json contains non-finite JSON constant {constant}",
    ):
        ledger_builder._strict_json_loads(raw, source_path="templates/non-finite.json")


@pytest.mark.parametrize("number", ["1e999", "-1e999"])
def test_strict_workflow_json_rejects_numbers_that_overflow_to_infinity(number: str) -> None:
    raw = f'{{"nodes":[],"edges":[],"value":{number}}}'.encode("ascii")

    with pytest.raises(
        ledger_builder.ReconciliationError,
        match=rf"workflow templates/overflow.json contains non-finite JSON number {number}",
    ):
        ledger_builder._strict_json_loads(raw, source_path="templates/overflow.json")


@pytest.mark.parametrize(
    "policy",
    [
        ledger_builder._ALLOWED_HISTORICAL_COLLISIONS,
        ledger_builder._CURRENT_PATH_REPAIRS,
        ledger_builder._CURRENT_EMPTY_ANOMALY,
    ],
)
def test_catalog_policy_mappings_are_immutable(policy: object) -> None:
    with pytest.raises(TypeError):
        policy["test_mutation"] = object()  # type: ignore[index]


@pytest.mark.parametrize("python_executable", AVAILABLE_PYTHONS)
def test_cli_ast_self_test_is_portable_across_available_runtimes(python_executable: str) -> None:
    process = subprocess.run(
        [python_executable, "scripts/build_catalog_ledger.py", "--self-test"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.strip() == (
        "AST canonicalizer self-test passed: "
        "e56fe5584149ad41156fd05ffe79dc51a63bf5fe84ba63ad94a6e2aa501ac700"
    )
    assert process.stderr == ""


def test_full_cli_ledger_check_uses_the_active_runtime() -> None:
    output = REPO_ROOT / "bionodulo" / "nodes" / "generated" / "baseline-ledger.json"

    process = subprocess.run(
        [sys.executable, *_ledger_cli_args(output)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 0, process.stderr
    assert process.stdout.startswith("Ledger is current: 943 stable node IDs")
    assert process.stderr == ""


def test_real_cli_check_rejects_missing_and_stale_outputs(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    missing_process = subprocess.run(
        [sys.executable, *_ledger_cli_args(missing)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert missing_process.returncode == 1
    assert "STALE:" in missing_process.stderr
    assert not missing.exists()

    stale = tmp_path / "stale.json"
    stale.write_bytes(b"stale\n")
    stale_process = subprocess.run(
        [sys.executable, *_ledger_cli_args(stale)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert stale_process.returncode == 1
    assert "STALE:" in stale_process.stderr
    assert stale.read_bytes() == b"stale\n"


def test_reconcile_rejects_duplicate_behavior_ids() -> None:
    first = extract_nodes('class A:\n    NODE_ID = "same"\n', "pkg.first")[0]
    second = extract_nodes('class B:\n    NODE_ID = "same"\n', "pkg.second")[0]

    with pytest.raises(DuplicateNodeIdError, match="behavior.*same"):
        reconcile(first + second, first)


@pytest.mark.parametrize("label", ["origin", "immediate split"])
def test_unexpected_historical_duplicates_fail_closed(label: str) -> None:
    first = extract_nodes('class A:\n    NODE_ID = "unexpected"\n', "pkg.first")[0]
    second = extract_nodes('class B:\n    NODE_ID = "unexpected"\n', "pkg.second")[0]

    with pytest.raises(DuplicateNodeIdError, match=f"{label}.*unexpected"):
        ledger_builder._validate_duplicate_allowlist(first + second, label, {})


def test_reconcile_reports_missing_added_and_semantic_drift() -> None:
    baseline = extract_nodes(
        'class A:\n    NODE_ID = "same"\n    VALUE = 1\nclass B:\n    NODE_ID = "missing"\n',
        "old",
    )[0]
    candidate = extract_nodes(
        'class A:\n    NODE_ID = "same"\n    VALUE = 2\nclass C:\n    NODE_ID = "added"\n',
        "new",
    )[0]

    result = reconcile(baseline, candidate)

    assert result.missing_ids == ("missing",)
    assert result.added_ids == ("added",)
    assert result.source_drift_ids == ("same",)
    assert result.ok is False


def test_ledger_entry_defaults_to_an_inventoried_quarantined_migration() -> None:
    source = extract_nodes('class A:\n    NODE_ID = "alpha"\n', "pkg.module")[0][0]
    entry = LedgerEntry(
        node_id="alpha",
        behavior=source,
        origin=source,
        origin_declarations=(source,),
        split_locations=(source,),
        comparison_locations=(source,),
    )

    assert entry.as_dict()["rebuild"] == {
        "contract_version": None,
        "disposition": "quarantined",
        "evidence_record": None,
        "family": None,
        "operation": None,
        "status": "inventoried",
    }


def test_alias_resolution_is_module_and_import_aware() -> None:
    aliases = resolve_aliases(
        {
            "pkg.left": 'class Parent:\n    NODE_ID = "left"\n',
            "pkg.right": 'class Parent:\n    NODE_ID = "right"\n',
            "pkg.alias": '''
from pkg.right import Parent as ImportedParent

class Alias(ImportedParent):
    NODE_ID = "alias"
    DISPLAY_NAME = "Alias"
    CATEGORY = "Tests"
    DESCRIPTION = "Static compatibility alias"
''',
        }
    )

    assert aliases["alias"].alias_of == "right"
    assert aliases["alias"].status == "proven"
    assert aliases["left"].alias_of is None
    assert aliases["right"].alias_of is None


def test_alias_resolution_follows_qualified_module_imports() -> None:
    aliases = resolve_aliases(
        {
            "pkg.right": 'class Parent:\n    NODE_ID = "right"\n',
            "pkg.alias": '''
import pkg.right

class QualifiedAlias(pkg.right.Parent):
    NODE_ID = "qualified_alias"
''',
        }
    )

    assert aliases["qualified_alias"].alias_of == "right"


def test_alias_resolution_preserves_nested_qualified_class_identity() -> None:
    aliases = resolve_aliases(
        {
            "pkg.base": '''
class Outer:
    class Parent:
        NODE_ID = "nested_parent"
''',
            "pkg.other": 'class Parent:\n    NODE_ID = "simple_parent"\n',
            "pkg.alias": '''
from pkg.base import Outer

class NestedAlias(Outer.Parent):
    NODE_ID = "nested_alias"
''',
        }
    )

    assert aliases["nested_alias"].alias_of == "nested_parent"
    assert aliases["nested_alias"].alias_of != "simple_parent"


def test_alias_resolution_prefers_enclosing_lexical_class_scope() -> None:
    aliases = resolve_aliases(
        {
            "pkg.module": '''
class Parent:
    NODE_ID = "global_parent"

class Outer:
    class Parent:
        NODE_ID = "nested_parent"

    class Alias(Parent):
        NODE_ID = "nested_alias"
''',
        }
    )

    assert aliases["nested_alias"].alias_of == "nested_parent"
    assert aliases["nested_alias"].alias_of != "global_parent"


def test_repository_baseline_contains_exactly_943_ids(
    repository_reconciliation: Reconciliation,
) -> None:
    result = repository_reconciliation

    assert result.ok is True
    assert len(result.entries) == 943
    assert len({entry.node_id for entry in result.entries}) == 943
    assert [entry.node_id for entry in result.entries] == sorted(entry.node_id for entry in result.entries)
    assert result.missing_ids == ()
    assert result.added_ids == ()
    assert result.source_drift_ids == ()


def test_repository_records_the_empty_featurecounts_anomaly(
    repository_reconciliation: Reconciliation,
) -> None:
    assert repository_reconciliation.anomalies == (
        {
            "blob": "dabde718fe7a0d7e0c98d7682840783b886c6e1b",
            "class_name": "FeatureCountsNode",
            "kind": "empty_node_id",
            "line": 279,
            "module": "bionodulo.nodes.builtin.rna_seq",
            "path": "bionodulo/nodes/builtin/rna_seq.py",
        },
    )


def test_repository_records_origin_collision_without_accepting_behavior_duplicates(
    repository_reconciliation: Reconciliation,
) -> None:
    result = repository_reconciliation
    collision = next(item for item in result.origin_collisions if item.node_id == "deeptools_bamcoverage")
    paths = {declaration.source_path for declaration in collision.declarations}
    entry = next(item for item in result.entries if item.node_id == "deeptools_bamcoverage")

    assert paths == {
        "bionodulo/nodes/builtin/chip_seq.py",
        "bionodulo/nodes/builtin/epigenomics.py",
    }
    assert len(entry.origin_declarations) == 2
    assert entry.origin.source_path == "bionodulo/nodes/builtin/epigenomics.py"
    assert len(entry.split_locations) == 2
    assert len(entry.comparison_locations) == 1


def test_repository_records_source_provenance_and_exact_aliases(
    repository_reconciliation: Reconciliation,
) -> None:
    result = repository_reconciliation
    entries = {entry.node_id: entry for entry in result.entries}
    samtools_sort = entries["samtools_sort"]
    proven = {entry.node_id: entry.alias_of for entry in result.entries if entry.alias_of is not None}

    assert samtools_sort.behavior.qualified_class.startswith("bionodulo.nodes.builtin.")
    assert len(samtools_sort.behavior.git_blob) == 40
    assert len(samtools_sort.behavior.raw_class_sha256) == 64
    assert len(samtools_sort.behavior.ast_sha256) == 64
    assert samtools_sort.origin.provenance in {"monolith", "native"}
    assert len(samtools_sort.origin.blame_commit or "") == 40
    assert len(proven) == 22
    assert proven["alphafold"] == "alphafold_db"
    assert proven["BayeScan"] == "bayescan"
    assert entries["feature_counts"].alias_of is None
    assert entries["feature_counts"].semantic_candidates == ("featurecounts",)


def test_all_943_entries_are_inventoried_and_quarantined(
    repository_reconciliation: Reconciliation,
) -> None:
    rebuild_states = {json.dumps(entry.as_dict()["rebuild"], sort_keys=True) for entry in repository_reconciliation.entries}

    assert len(repository_reconciliation.entries) == 943
    assert rebuild_states == {
        json.dumps(
            {
                "contract_version": None,
                "disposition": "quarantined",
                "evidence_record": None,
                "family": None,
                "operation": None,
                "status": "inventoried",
            },
            sort_keys=True,
        )
    }


def test_repository_records_reproducible_current_repair_projection(
    repository_reconciliation: Reconciliation,
) -> None:
    result = repository_reconciliation
    current_by_id = {entry.node_id: entry.current for entry in result.entries}

    assert len(current_by_id) == 943
    assert all(current is not None for current in current_by_id.values())
    assert result.current_snapshot.kind == "forensic_path_import_repair_projection"
    assert result.current_snapshot.base_ref == COMPARISON_REF
    assert len(result.current_snapshot.base_builtin_tree) == 40
    assert len(result.current_snapshot.repair_map_sha256) == 64
    assert len(result.current_snapshot.projected_inventory_sha256) == 64
    assert len(result.current_snapshot.snapshot_sha256) == 64
    assert "not proof of runtime correctness" in result.current_snapshot.limitations
    assert {
        node_id: current.source_path
        for node_id, current in current_by_id.items()
        if node_id in {"break_continue", "if_condition", "try_catch", "while_loop", "type_cast"}
    } == {
        "break_continue": "bionodulo/nodes/builtin/flow_control/break_.py",
        "if_condition": "bionodulo/nodes/builtin/flow_control/if_.py",
        "try_catch": "bionodulo/nodes/builtin/flow_control/try_.py",
        "type_cast": "bionodulo/nodes/builtin/utils/dev/type_.py",
        "while_loop": "bionodulo/nodes/builtin/flow_control/while_.py",
    }


def test_current_source_validation_rejects_duplicate_ids(tmp_path: Path) -> None:
    builtin = tmp_path / "bionodulo" / "nodes" / "builtin"
    builtin.mkdir(parents=True)
    source = 'class A:\n    NODE_ID = "alpha"\n'
    (builtin / "one.py").write_text(source)
    (builtin / "duplicate.py").write_text(source)
    comparison = extract_nodes(
        source,
        "bionodulo.nodes.builtin.one",
        source_path="bionodulo/nodes/builtin/one.py",
        git_blob="a" * 40,
    )[0][0]

    with pytest.raises(DuplicateNodeIdError, match="current repaired source.*alpha"):
        ledger_builder.validate_current_source(tmp_path, (comparison,))


@pytest.mark.parametrize(
    "anomalies",
    [
        (),
        (("rna_seq/featurecountsnode.py", "WrongFeatureCountsNode"),),
        (("rna_seq/wrong.py", "FeatureCountsNode"),),
        (
            ("rna_seq/featurecountsnode.py", "FeatureCountsNode"),
            ("rna_seq/extra.py", "ExtraEmptyNode"),
        ),
    ],
)
def test_current_source_validation_requires_the_exact_empty_id_anomaly(
    tmp_path: Path,
    anomalies: tuple[tuple[str, str], ...],
) -> None:
    builtin = tmp_path / "bionodulo" / "nodes" / "builtin"
    builtin.mkdir(parents=True)
    source = 'class A:\n    NODE_ID = "alpha"\n'
    (builtin / "one.py").write_text(source)
    for relative_path, class_name in anomalies:
        anomaly_path = builtin / relative_path
        anomaly_path.parent.mkdir(parents=True, exist_ok=True)
        anomaly_path.write_text(f'class {class_name}:\n    NODE_ID = ""\n')
    comparison = extract_nodes(
        source,
        "bionodulo.nodes.builtin.one",
        source_path="bionodulo/nodes/builtin/one.py",
        git_blob="a" * 40,
    )[0][0]

    with pytest.raises(ledger_builder.ReconciliationError, match="current source anomalies"):
        ledger_builder.validate_current_source(tmp_path, (comparison,))


def test_repository_records_all_template_instances_and_edge_ports(
    repository_reconciliation: Reconciliation,
) -> None:
    result = repository_reconciliation
    entries = {entry.node_id: entry for entry in result.entries}
    example = next(
        ref
        for ref in entries["fastqc"].template_references
        if ref.source_path == "examples/workflows/fastq_qc_pipeline.bionodulo.json"
    )

    assert result.template_count == 22
    assert result.example_workflow_count == 1
    assert sum(len(entry.template_references) for entry in result.entries) == 329
    assert example.kind == "example"
    assert example.instance_id == "fastqc_001"
    assert example.input_ports == ("reads",)
    assert example.output_ports == ("report_dir",)


def test_workflow_references_reject_duplicate_instance_ids() -> None:
    document = {
        "nodes": [
            {"id": "same", "type": "alpha"},
            {"id": "same", "type": "alpha"},
        ],
        "edges": [],
    }

    with pytest.raises(ledger_builder.ReconciliationError, match="duplicate workflow instance ID.*same"):
        ledger_builder.extract_workflow_references(
            document,
            source_path="templates/duplicate.json",
            source_blob="a" * 40,
            kind="template",
            valid_node_ids={"alpha"},
        )


@pytest.mark.parametrize("dangling_side", ["from", "to"])
def test_workflow_references_reject_dangling_edge_endpoints(dangling_side: str) -> None:
    edge = {
        "from": {"node": "known", "output": "result"},
        "to": {"node": "known", "input": "value"},
    }
    edge[dangling_side]["node"] = "missing"
    document = {"nodes": [{"id": "known", "type": "alpha"}], "edges": [edge]}

    with pytest.raises(ledger_builder.ReconciliationError, match="dangling edge endpoint.*missing"):
        ledger_builder.extract_workflow_references(
            document,
            source_path="templates/dangling.json",
            source_blob="b" * 40,
            kind="template",
            valid_node_ids={"alpha"},
        )


def test_ledger_bytes_are_canonical_and_deterministic(
    repository_reconciliation: Reconciliation,
) -> None:
    first = ledger_bytes(repository_reconciliation)
    second = ledger_bytes(repository_reconciliation)
    document = json.loads(first)
    aggregate_sha256 = document.pop("aggregate_sha256")

    assert first == second
    assert first.endswith(b"\n")
    assert aggregate_sha256 == hashlib.sha256(canonical_json_bytes(document)).hexdigest()
    assert document["summary"] == {
        "added_ids": 0,
        "behavior_declarations": 943,
        "current_sources": 943,
        "empty_id_anomalies": 1,
        "example_workflows": 1,
        "missing_ids": 0,
        "native_origins": 392,
        "origin_collisions": 1,
        "origin_monolith_ids": 551,
        "proven_aliases": 22,
        "source_semantic_drift": 0,
        "stable_node_ids": 943,
        "template_instances": 329,
        "template_edges": 291,
        "templates": 22,
    }
    assert document["digests"]["forensic_reference_4092_raw_ast_sha256"] == FORENSIC_RAW_AST_DIGEST
    assert document["canonicalizer"] == {
        "ast_normalization": "canonical JSON AST; empty sequences omitted",
        "json_encoding": "sort_keys,compact,ascii,newline",
        "name": "bionodulo.catalog-ledger",
        "runtime_compatibility": ["3.11", "3.12", "3.13"],
        "version": 2,
    }


def test_check_and_atomic_write_behavior(tmp_path: Path) -> None:
    output = tmp_path / "nested" / "ledger.json"
    expected = b'{"stable":true}\n'

    assert write_or_check(output, expected, check=True) is False
    assert output.exists() is False
    assert write_or_check(output, expected, check=False) is True
    assert output.read_bytes() == expected
    assert write_or_check(output, expected, check=True) is True

    stale = b'{"stable":false}\n'
    assert write_or_check(output, stale, check=True) is False
    assert output.read_bytes() == expected


def test_atomic_write_uses_portable_default_mode(tmp_path: Path) -> None:
    output = tmp_path / "ledger.json"

    write_or_check(output, b"new\n", check=False)

    assert output.stat().st_mode & 0o777 == 0o644


def test_atomic_write_preserves_existing_mode(tmp_path: Path) -> None:
    output = tmp_path / "ledger.json"
    output.write_bytes(b"old\n")
    output.chmod(0o640)

    write_or_check(output, b"new\n", check=False)

    assert output.read_bytes() == b"new\n"
    assert output.stat().st_mode & 0o777 == 0o640


def test_atomic_write_fsyncs_file_then_parent_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    synced_modes: list[int] = []

    def record_fsync(file_descriptor: int) -> None:
        synced_modes.append(ledger_builder.os.fstat(file_descriptor).st_mode)

    monkeypatch.setattr(ledger_builder.os, "fsync", record_fsync)

    write_or_check(tmp_path / "ledger.json", b"new\n", check=False)

    assert len(synced_modes) == 2
    assert stat.S_ISREG(synced_modes[0])
    assert stat.S_ISDIR(synced_modes[1])


def test_atomic_write_cleans_temporary_file_after_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_fsync(_file_descriptor: int) -> None:
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(ledger_builder.os, "fsync", fail_fsync)
    output = tmp_path / "ledger.json"

    with pytest.raises(OSError, match="simulated fsync failure"):
        write_or_check(output, b"new\n", check=False)

    assert not output.exists()
    assert tuple(tmp_path.iterdir()) == ()


@pytest.mark.parametrize("initial", [None, b"stale\n"])
def test_cli_check_reports_missing_and_stale_bytes_without_writing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    initial: bytes | None,
) -> None:
    output = tmp_path / "ledger.json"
    if initial is not None:
        output.write_bytes(initial)
    expected = b'{"canonical":true}\n'
    monkeypatch.setattr(ledger_builder, "reconcile_repository", lambda *_args, **_kwargs: Reconciliation())
    monkeypatch.setattr(ledger_builder, "ledger_bytes", lambda _result: expected)

    exit_code = ledger_builder.main(["--repo", str(tmp_path), "--output", str(output), "--check"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "STALE:" in captured.err
    assert output.exists() is (initial is not None)
    if initial is not None:
        assert output.read_bytes() == initial


def test_cli_check_reports_current_bytes_and_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "ledger.json"
    expected = b'{"canonical":true}\n'
    output.write_bytes(expected)
    snapshot = ledger_builder.CurrentSnapshot(
        kind="forensic_path_import_repair_projection",
        base_ref="c" * 40,
        base_builtin_tree="d" * 40,
        repairs=(),
        repair_map_sha256="e" * 64,
        projected_inventory_sha256="f" * 64,
        limitations="not proof of runtime correctness",
        snapshot_sha256="0" * 64,
    )
    result = Reconciliation(current_snapshot=snapshot)
    validated: list[Path] = []
    monkeypatch.setattr(ledger_builder, "reconcile_repository", lambda *_args, **_kwargs: result)
    monkeypatch.setattr(ledger_builder, "ledger_bytes", lambda _result: expected)

    def validate(path: Path, _expected: object) -> str:
        validated.append(path)
        return snapshot.projected_inventory_sha256

    monkeypatch.setattr(ledger_builder, "validate_current_source", validate)
    current_root = tmp_path / "dirty-current"

    exit_code = ledger_builder.main(
        [
            "--repo",
            str(tmp_path),
            "--output",
            str(output),
            "--validate-current-source",
            str(current_root),
            "--check",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert "Ledger is current" in captured.out
    assert "current repair projection validated" in captured.out
    assert captured.err == ""
    assert validated == [current_root]


def test_cli_missing_check_reconciles_before_reporting_stale(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "missing.json"
    calls: list[Path] = []

    def reconcile_call(repo: Path, **_kwargs: object) -> Reconciliation:
        calls.append(repo)
        return Reconciliation()

    monkeypatch.setattr(ledger_builder, "reconcile_repository", reconcile_call)
    monkeypatch.setattr(ledger_builder, "ledger_bytes", lambda _result: b'{"canonical":true}\n')

    exit_code = ledger_builder.main(["--repo", str(tmp_path), "--output", str(output), "--check"])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert calls == [tmp_path.resolve()]
    assert "STALE:" in captured.err
    assert not output.exists()


def test_cli_current_source_validation_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "ledger.json"
    output.write_bytes(b"existing\n")
    snapshot = ledger_builder.CurrentSnapshot(
        kind="forensic_path_import_repair_projection",
        base_ref="c" * 40,
        base_builtin_tree="d" * 40,
        repairs=(),
        repair_map_sha256="e" * 64,
        projected_inventory_sha256="f" * 64,
        limitations="not proof of runtime correctness",
        snapshot_sha256="0" * 64,
    )
    monkeypatch.setattr(
        ledger_builder,
        "reconcile_repository",
        lambda *_args, **_kwargs: Reconciliation(current_snapshot=snapshot),
    )

    def fail_validation(_path: Path, _expected: object) -> str:
        raise ledger_builder.ReconciliationError("current source drift")

    monkeypatch.setattr(ledger_builder, "validate_current_source", fail_validation)

    exit_code = ledger_builder.main(
        [
            "--repo",
            str(tmp_path),
            "--output",
            str(output),
            "--validate-current-source",
            str(tmp_path / "dirty-current"),
            "--check",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "ERROR: current source drift" in captured.err
