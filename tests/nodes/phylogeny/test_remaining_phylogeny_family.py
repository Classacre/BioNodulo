"""Lean source and ownership checks for the remaining phylogeny wave."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from bionodulo.environments.constants import EXECUTABLE_TO_CONDA_PACKAGE, PACKAGE_MIN_VERSIONS
from bionodulo.nodes.builtin import phylogeny as facade
from bionodulo.nodes.builtin.phylogeny_family.evidence import NODE_EVIDENCE
from bionodulo.nodes.registry import NodeRegistry


EXPECTED_OWNERS = {
    "astral": "astral",
    "clustalo": "clustalo",
    "ebi_clustal_omega": "ebi_clustal_omega",
    "fasttree": "fasttree",
    "modeltest_ng": "modeltest_ng",
    "muscle": "muscle",
    "phylogenetic_tree_builder": "phylogenetic_tree_builder",
    "phylot": "phylot",
    "raxml": "raxml",
    "raxml_ng": "raxml_ng",
    "trimal": "trimal",
}


def _node_class(node_id: str) -> type:
    registry = NodeRegistry.create_isolated()
    registry.load_builtin_nodes()
    node_class = registry.get(node_id)
    assert node_class is not None
    return node_class


@pytest.mark.parametrize(("node_id", "module_name"), EXPECTED_OWNERS.items())
def test_remaining_phylogeny_nodes_have_focused_owners(node_id: str, module_name: str) -> None:
    node_class = _node_class(node_id)
    assert node_class.__module__ == f"bionodulo.nodes.builtin.phylogeny_family.{module_name}"
    assert getattr(facade, node_class.__name__) is node_class


@pytest.mark.parametrize("node_id", EXPECTED_OWNERS)
def test_remaining_phylogeny_nodes_expose_pinned_evidence(node_id: str) -> None:
    node_class = _node_class(node_id)
    evidence = NODE_EVIDENCE[node_id]

    assert node_class.SOURCE_URL == evidence.source_url
    assert node_class.SOURCE_PATHS == list(evidence.source_paths)
    assert node_class.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert node_class.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert node_class.GIT_COMMIT == evidence.git_commit
    assert node_class.SOURCE_SHA256 == evidence.source_sha256


def test_new_command_package_constraints_are_resolvable() -> None:
    assert EXECUTABLE_TO_CONDA_PACKAGE["muscle"] == "muscle"
    assert PACKAGE_MIN_VERSIONS["muscle"] == "5.3"
    assert EXECUTABLE_TO_CONDA_PACKAGE["trimal"] == "trimal"
    assert PACKAGE_MIN_VERSIONS["trimal"] == "1.4.1"


def test_clustalo_renders_and_plans_the_documented_alignment(tmp_path: Path) -> None:
    node_class = _node_class("clustalo")
    assert node_class.render_command(
        {
            "input": "proteins.fa",
            "threads": 8,
            "outfmt": "stockholm",
            "output": "/work/clustalo",
        }
    ) == [
        "clustalo",
        "-i",
        "proteins.fa",
        "-o",
        "/work/clustalo/alignment.stk",
        "--threads",
        "8",
        "--force",
        "--outfmt",
        "stockholm",
    ]
    assert node_class.PLAN_OUTPUTS({"outfmt": "stockholm"}, tmp_path) == [
        tmp_path / "clustalo" / "alignment.stk"
    ]
    assert "outfmt" in str(node_class.VALIDATE_INPUTS({"input": "a.fa", "outfmt": "unsafe"}))


def test_fasttree_captures_stdout_and_rejects_protein_gtr(tmp_path: Path) -> None:
    node_class = _node_class("fasttree")
    assert node_class.render_command(
        {"alignment": "dna.aln", "nucleotide": True, "gtr": True}
    ) == ["FastTree", "-nt", "-gtr", "-gamma", "-boot", "100", "dna.aln"]
    assert node_class.STDOUT_OUTPUT_INDEX == 0
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [tmp_path / "fasttree" / "tree.nwk"]
    assert node_class.VALIDATE_INPUTS({"alignment": "protein.aln", "gtr": True}) == (
        "Input 'gtr' requires nucleotide mode"
    )


def test_raxml_plans_the_supported_tree_for_each_mode(tmp_path: Path) -> None:
    node_class = _node_class("raxml")
    inputs = {
        "alignment": "alignment.phy",
        "threads": 6,
        "model": "GTRGAMMA",
        "prefix": "species",
        "bootstrap": True,
        "output": "/work/raxml",
    }
    assert node_class.render_command(inputs) == [
        "raxmlHPC-PTHREADS",
        "-s",
        "alignment.phy",
        "-n",
        "species",
        "-m",
        "GTRGAMMA",
        "-p",
        "12345",
        "-T",
        "6",
        "-w",
        "/work/raxml",
        "-f",
        "a",
        "-x",
        "12345",
        "-#",
        "100",
    ]
    assert node_class.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "raxml" / "RAxML_bipartitions.species"
    ]
    assert node_class.PLAN_OUTPUTS({**inputs, "bootstrap": False}, tmp_path) == [
        tmp_path / "raxml" / "RAxML_bestTree.species"
    ]


def test_astral_runtime_command_preserves_process_failure_status() -> None:
    node_class = _node_class("astral")
    command = node_class.render_command(
        {
            "input": "gene trees.nwk",
            "branch_annotate": "16",
            "lambda": 0.5,
            "output": "/work/astral",
            "_runtime_contract": True,
        }
    )
    assert "2> /work/astral/log_output.txt" in command
    assert "| tee" not in command
    assert "mv ./output.tre" not in command
    assert command.endswith("mv freqQuad.csv /work/astral/branch_annotations.tsv")


def test_modeltest_runtime_command_and_native_outputs(tmp_path: Path) -> None:
    node_class = _node_class("modeltest_ng")
    command = node_class.render_command(
        {
            "alignment": "alignment.phy",
            "datatype": "nt",
            "threads": 4,
            "models": "GTR,HKY",
            "output": "/work/modeltest_ng",
        }
    )
    assert command == [
        "modeltest-ng",
        "-i",
        "alignment.phy",
        "-d",
        "nt",
        "-p",
        "4",
        "-o",
        "/work/modeltest_ng/modeltest",
        "-m",
        "GTR,HKY",
    ]
    assert node_class.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "modeltest_ng" / "modeltest.out",
        tmp_path / "modeltest_ng" / "modeltest.log",
    ]


@pytest.mark.parametrize(
    ("node_id", "inputs", "message"),
    [
        ("muscle", {"sequences": "a.fa", "diags": True}, "not supported"),
        ("muscle", {"sequences": "a.fa", "stable": True}, "not supported"),
        (
            "raxml_ng",
            {"alignment": "a.fa", "tree_search": False},
            "requires a --tree input",
        ),
        (
            "modeltest_ng",
            {"alignment": "a.fa", "template": "raxml", "models": "GTR"},
            "mutually exclusive",
        ),
        (
            "modeltest_ng",
            {"alignment": "a.fa", "ascertainment_bias": True},
            "requires an algorithm value",
        ),
    ],
)
def test_runtime_validation_fails_closed_on_legacy_contract_gaps(
    node_id: str,
    inputs: dict[str, Any],
    message: str,
) -> None:
    assert message in str(_node_class(node_id).VALIDATE_INPUTS(inputs))


def test_conditional_native_outputs_do_not_claim_missing_artifacts(tmp_path: Path) -> None:
    trimal = _node_class("trimal")
    assert trimal.PLAN_OUTPUTS({"htmlout": False}, tmp_path) == [
        tmp_path / "trimal" / "trimmed.fasta"
    ]
    assert trimal.PLAN_OUTPUTS({"htmlout": True}, tmp_path) == [
        tmp_path / "trimal" / "trimmed.fasta",
        tmp_path / "trimal" / "stats.html",
    ]

    raxml_ng = _node_class("raxml_ng")
    assert raxml_ng.PLAN_OUTPUTS({"bootstrap_replicates": 0}, tmp_path) == [
        tmp_path / "raxml_ng" / "raxml_ng.raxml.bestTree"
    ]


def test_remote_and_in_process_nodes_record_mutable_contract_boundaries() -> None:
    ebi = _node_class("ebi_clustal_omega")
    phylot = _node_class("phylot")
    builder = _node_class("phylogenetic_tree_builder")

    assert ebi.CONTRACT_ACCESSED_DATE == "2026-07-19"
    assert ebi.GIT_COMMIT == "38a8d24200474b65f28980775f683c3c2dd3d742"
    assert phylot.CONTRACT_ACCESSED_DATE == "2026-07-19"
    assert "no live submission" in " ".join(phylot.AUDIT_CAVEATS)
    assert builder.PACKAGE_CONSTRAINTS == ("biopython==1.87",)
    assert "does not compute a clade consensus" in " ".join(builder.AUDIT_CAVEATS)
