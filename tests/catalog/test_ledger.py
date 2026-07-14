from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.build_catalog_ledger import (
    DuplicateNodeIdError,
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

class Dynamic:
    NODE_ID = make_id()
'''

    found, anomalies = extract_nodes(source, "pkg.module")

    assert [item.node_id for item in found] == ["alpha", "beta"]
    assert found[0].qualified_class == "pkg.module.A"
    assert len(found[0].raw_class_sha256) == 64
    assert len(found[0].ast_sha256) == 64
    assert anomalies == (
        {"kind": "empty_node_id", "module": "pkg.module", "class_name": "Empty"},
    )


def test_reconcile_rejects_duplicate_behavior_ids() -> None:
    first = extract_nodes('class A:\n    NODE_ID = "same"\n', "pkg.first")[0]
    second = extract_nodes('class B:\n    NODE_ID = "same"\n', "pkg.second")[0]

    with pytest.raises(DuplicateNodeIdError, match="behavior.*same"):
        reconcile(first + second, first)


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
        "templates": 22,
    }
    assert document["digests"]["forensic_reference_4092_raw_ast_sha256"] == FORENSIC_RAW_AST_DIGEST
    assert document["canonicalizer"]["version"] == 1
    assert document["canonicalizer"]["python_ast_runtime"]


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
