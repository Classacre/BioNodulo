"""Compact contracts for the focused phylogeny and assembly wrapper family."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from bionodulo.nodes.builtin import wrapped_phylogeny_assembly as legacy
from bionodulo.nodes.builtin import wrapped_phylogeny_assembly_family as family
from bionodulo.nodes.builtin.wrapped_phylogeny_assembly_family.evidence import (
    ALPHAGENOME_CREDENTIAL,
    ERROR_DETECTION_BY_ID,
    NODE_EVIDENCE,
    TOOLS_IUC_COMMIT,
)


EXPECTED_IDS = {
    "abritamr",
    "allegro",
    "alphagenome_interval_predictor",
    "alphagenome_ism_scanner",
    "alphagenome_sequence_predictor",
    "alphagenome_variant_effect",
    "alphagenome_variant_scorer",
    "amas_concat",
    "amas_remove",
    "amas_replicate",
    "amas_split",
    "amas_summary",
    "amplican",
    "art_454",
    "art_illumina",
    "art_solid",
    "assembly_stats",
    "bbtools_bbduk",
    "bbtools_bbmap",
    "bbtools_bbmerge",
    "bbtools_bbnorm",
    "bbtools_callvariants",
    "bbtools_tadpole",
    "clustalw",
    "eukrep",
    "flash",
    "fraggenescan",
    "gamma",
    "gamma_s",
    "genomescope",
    "iuc_pear",
    "minia",
    "nonpareil",
    "phyml",
    "plasclass",
    "plasflow",
    "prodigal",
    "quicktree",
    "rapidnj",
    "red",
}


def _nodes() -> list[type]:
    return [getattr(family, name) for name in family.__all__]


def test_stable_ids_have_one_focused_owner_and_legacy_reexports() -> None:
    nodes = _nodes()
    assert len(nodes) == 40
    assert {node.NODE_ID for node in nodes} == EXPECTED_IDS
    assert len({node.NODE_ID for node in nodes}) == len(nodes)
    assert all(node.__module__.startswith(f"{family.__name__}.") for node in nodes)
    assert all(getattr(legacy, node.__name__) is node for node in nodes)

    declarations: dict[str, list[Path]] = {}
    family_dir = Path(family.__file__).parent
    for path in family_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for class_node in (item for item in tree.body if isinstance(item, ast.ClassDef)):
            for item in class_node.body:
                if not isinstance(item, ast.Assign):
                    continue
                if any(isinstance(target, ast.Name) and target.id == "NODE_ID" for target in item.targets):
                    declarations.setdefault(ast.literal_eval(item.value), []).append(path)

    assert set(declarations) == EXPECTED_IDS
    assert all(len(paths) == 1 for paths in declarations.values())
    assert "NODE_ID" not in Path(legacy.__file__).read_text(encoding="utf-8")


@pytest.mark.parametrize("node", _nodes(), ids=lambda node: node.NODE_ID)
def test_every_contract_has_exact_wrapper_packages_and_failure_semantics(node: type) -> None:
    evidence = NODE_EVIDENCE[node.NODE_ID]
    package_names = [re.split(r"[<>=!~]", spec, maxsplit=1)[0] for spec in evidence.package_constraints]

    assert node.VERSION == evidence.version
    assert node.WRAPPER_GIT_COMMIT == TOOLS_IUC_COMMIT
    assert node.WRAPPER_SOURCE == evidence.wrapper_path
    assert node.WRAPPER_TOOL_ID == (evidence.wrapper_id or node.NODE_ID)
    assert node.SOURCE_URL == evidence.source_url
    assert node.PACKAGE_CONSTRAINTS == evidence.package_constraints
    assert [name.lower() for name in node.REQUIRED_CONDA_PACKAGES] == [name.lower() for name in package_names]
    assert node.WRAPPER_ERROR_DETECTION == ERROR_DETECTION_BY_ID[node.NODE_ID]
    assert node.EXIT_SEMANTICS
    assert node.AUDIT_STATUS == "contract-checked-no-external-execution"


def test_source_confirmed_defaults_do_not_invent_wrapper_choices(tmp_path: Path) -> None:
    amas_nodes = [
        family.AMASSummaryNode,
        family.AMASConcatNode,
        family.AMASSplitNode,
        family.AMASRemoveNode,
        family.AMASReplicateNode,
    ]
    for node in amas_nodes:
        assert node.INPUT_TYPES()["required"]["data_type"][1]["default"] == "aa"
        assert node.INPUT_TYPES()["required"]["data_type"][1]["options"] == ["aa", "dna"]

    assert family.FragGeneScanNode.INPUT_TYPES()["optional"]["train"][1]["default"] == "454_5"
    assert "-train 454_5" in " ".join(
        family.FragGeneScanNode.render_command(
            {"genome": "reads.fa", "output": "/work/fraggenescan"}
        )
    )

    bbduk_inputs = family.BBToolsBBDukNode.INPUT_TYPES()["optional"]
    assert bbduk_inputs["outputs_select"][1]["default"] == []
    assert family.BBToolsBBDukNode.VALIDATE_INPUTS(
        {"input_type": "single", "read1": "reads.fq"}
    ) == "at least one read output must be selected"
    assert family.BBToolsBBDukNode.PLAN_OUTPUTS({}, tmp_path) == []

    art_inputs = family.ARTIlluminaNode.INPUT_TYPES()["optional"]
    assert art_inputs["aln"][1]["default"] is False
    assert "--noALN" in family.ARTIlluminaNode.render_command(
        {"input_seq_file": "reference.fa", "output": "/work/art"}
    )
    assert family.ARTIlluminaNode.PLAN_OUTPUTS({}, tmp_path) == [
        tmp_path / "art_illumina" / "output.fq"
    ]


def test_alphagenome_contract_records_credentials_without_calling_the_api() -> None:
    alpha_nodes = [
        family.AlphaGenomeIntervalPredictorNode,
        family.AlphaGenomeISMScannerNode,
        family.AlphaGenomeSequencePredictorNode,
        family.AlphaGenomeVariantEffectNode,
        family.AlphaGenomeVariantScorerNode,
    ]
    assert all(node.CREDENTIAL_REQUIREMENTS == (ALPHAGENOME_CREDENTIAL,) for node in alpha_nodes)
    assert all("galaxy_credentials" in node.SOURCE_AUTHORITIES for node in alpha_nodes)

    variant_effect = family.AlphaGenomeVariantEffectNode
    assert variant_effect.OUTPUT_TYPES == [
        "RNA_SEQ",
        "ATAC",
        "CAGE",
        "DNASE",
        "CHIP_HISTONE",
        "CHIP_TF",
        "SPLICE_SITES",
        "PROCAP",
    ]
    assert variant_effect.VALIDATE_INPUTS(
        {"input_vcf": "variants.vcf", "output_types": ["CONTACT_MAPS"]}
    ) == "output_types contains unsupported values: CONTACT_MAPS"


@pytest.mark.parametrize(
    ("node", "inputs", "required_fragments", "expected_names"),
    [
        (
            family.QuicktreeNode,
            {"input_file": "alignment.fa", "output": "/work/quicktree"},
            ("esl-reformat -o input.quicktree stockholm alignment.fa", "quicktree -in a -out t"),
            ("output_file.nwk",),
        ),
        (
            family.BBToolsBBDukNode,
            {"input_type": "single", "read1": "reads.fq", "outputs_select": ["outu"], "output": "/work/bbduk"},
            ("bbduk.sh", "out=/work/bbduk/forward_unmatched.fastq"),
            ("forward_unmatched.fastq",),
        ),
        (
            family.AlphaGenomeIntervalPredictorNode,
            {"input_bed": "regions.bed", "test_fixture": "fixture.json", "output": "/work/alpha"},
            ("alphagenome_interval_predictor.py", "--test-fixture fixture.json"),
            ("predictions.tsv",),
        ),
    ],
)
def test_representative_commands_and_conditional_outputs_are_stable(
    node: type,
    inputs: dict[str, object],
    required_fragments: tuple[str, ...],
    expected_names: tuple[str, ...],
    tmp_path: Path,
) -> None:
    command = node.render_command(inputs)
    rendered = " ".join(command) if isinstance(command, list) else command
    assert all(fragment in rendered for fragment in required_fragments)
    assert tuple(path.name for path in node.PLAN_OUTPUTS(inputs, tmp_path)) == expected_names
