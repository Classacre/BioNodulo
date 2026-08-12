from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from bionodulo.nodes.builtin.annotation_family import (
    ANNOVARNode,
    AnnotateVCFNode,
    BaktaNode,
    BcftoolsAnnotateNode,
    EggNOGMapperNode,
    FuncotateTableNode,
    FuncotatorNode,
    InterProScanNode,
    VEPAnnotateNode,
)
from scripts.gen_node_index import build_index


def test_annotation_legacy_extraction_has_six_focused_owners_and_aliases() -> None:
    owners = {
        "annotate_vcf": (
            AnnotateVCFNode,
            "bionodulo.nodes.builtin.annotation_family.annotate_vcf",
        ),
        "annovar": (ANNOVARNode, "bionodulo.nodes.builtin.annotation_family.annovar"),
        "bakta": (BaktaNode, "bionodulo.nodes.builtin.annotation_family.bakta"),
        "bcftools_annotate": (
            BcftoolsAnnotateNode,
            "bionodulo.nodes.builtin.annotation_family.bcftools_annotate",
        ),
        "eggnog_mapper": (
            EggNOGMapperNode,
            "bionodulo.nodes.builtin.annotation_family.eggnog_mapper",
        ),
        "interproscan": (
            InterProScanNode,
            "bionodulo.nodes.builtin.annotation_family.interproscan",
        ),
    }
    live_index = build_index()

    for node_id, (node_class, module_name) in owners.items():
        assert live_index[node_id] == module_name
        assert node_class.__module__ == module_name
        assert all(not base.__module__.endswith(".legacy") for base in node_class.__mro__)
        module = importlib.import_module(module_name)
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "from .legacy" not in source

    family_dir = Path(importlib.import_module("bionodulo.nodes.builtin.annotation_family").__file__).parent
    assert not (family_dir / "legacy.py").exists()


@pytest.mark.parametrize(
    ("node", "version", "commit"),
    [
        (BaktaNode, "1.9.4", "a7ac1c8641cf8a11888b0295c30f0b2e0b8f34fa"),
        (EggNOGMapperNode, "2.1.14", "6ec647a3f7dd2ceb9d7b0b4ce0a357acd2524f3e"),
        (VEPAnnotateNode, "113.4", "a6786e4357f442a81624f58d9e79f343909d717f"),
        (ANNOVARNode, "2020-06-08", ""),
        (FuncotateTableNode, "4.6.2.0", "76edc75c26504da94bbaee66584e107e76ee15de"),
        (FuncotatorNode, "4.6.2.0", "76edc75c26504da94bbaee66584e107e76ee15de"),
        (BcftoolsAnnotateNode, "1.24", "fb9f0f783e0f67d734f6fa7fe4df9d230522f196"),
        (AnnotateVCFNode, "0.3.9", "d409a9b73dc6ef5b3be45cb84604889eac0d52c5"),
        (InterProScanNode, "5.59-91.0", "e6a3ca6f4262ac1a542123ef1a278c189da2e26f"),
    ],
)
def test_remaining_annotation_nodes_have_pinned_authorities(
    node: type,
    version: str,
    commit: str,
) -> None:
    assert node.VERSION == version
    assert node.GIT_COMMIT == commit
    assert node.SOURCE_URL.startswith("https://")
    assert node.DOCUMENTATION_URL.startswith("https://")
    assert node.AUDIT_STATUS == "contract-checked-no-external-execution"
    assert node.__module__.startswith("bionodulo.nodes.builtin.annotation_family.")


def test_eggnog_requires_offline_data_and_uses_real_output_filename(tmp_path: Path) -> None:
    inputs = {
        "proteins": "/inputs/proteins.faa",
        "data_dir": "/refs/eggnog",
        "prefix": "isolate_7",
        "threads": 12,
        "mode": "diamond",
        "itype": "proteins",
        "output": "/runs/eggnog_mapper",
    }

    assert EggNOGMapperNode.render_command(inputs) == [
        "emapper.py",
        "-i",
        "/inputs/proteins.faa",
        "--output",
        "isolate_7",
        "--output_dir",
        "/runs/eggnog_mapper",
        "-m",
        "diamond",
        "--cpu",
        "12",
        "--data_dir",
        "/refs/eggnog",
        "--itype",
        "proteins",
    ]
    assert EggNOGMapperNode.PLAN_OUTPUTS(inputs, tmp_path) == [
        tmp_path / "eggnog_mapper" / "isolate_7.emapper.annotations"
    ]
    assert EggNOGMapperNode.VALIDATE_INPUTS({"proteins": "proteins.faa"}) == "data_dir is required"
    assert "diamond, mmseqs" in str(EggNOGMapperNode.VALIDATE_INPUTS({**inputs, "mode": "hmmer"}))


def test_funcotator_stages_reference_and_vcf_sidecars_together(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    reference = source / "GRCh38.fa"
    reference_index = source / "GRCh38.fa.fai"
    sequence_dictionary = source / "GRCh38.dict"
    vcf = source / "somatic.vcf.gz"
    vcf_index = source / "somatic.vcf.gz.tbi"
    for path in (reference, reference_index, sequence_dictionary, vcf, vcf_index):
        path.write_text(path.name, encoding="utf-8")

    inputs: dict[str, object] = {
        "vcf": str(vcf),
        "vcf_index": str(vcf_index),
        "reference": str(reference),
        "reference_index": str(reference_index),
        "sequence_dictionary": str(sequence_dictionary),
        "data_sources": str(tmp_path / "funcotator-data"),
        "ref_version": "hg38",
        "output_format": "MAF",
        "output": str(tmp_path / "run" / "funcotate_table"),
    }
    outputs = FuncotateTableNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    assert FuncotateTableNode.VALIDATE_INPUTS(inputs) is True
    FuncotateTableNode.PREPARE_EXECUTION(inputs, outputs)

    staged = outputs[0].parent / "inputs"
    assert Path(str(inputs["reference"])) == staged / "GRCh38.fa"
    assert Path(str(inputs["reference_index"])) == staged / "GRCh38.fa.fai"
    assert Path(str(inputs["sequence_dictionary"])) == staged / "GRCh38.dict"
    assert Path(str(inputs["vcf"])) == staged / "somatic.vcf.gz"
    assert Path(str(inputs["vcf_index"])) == staged / "somatic.vcf.gz.tbi"
    assert FuncotateTableNode.VALIDATE_INPUTS(inputs) is True


def test_funcotator_rejects_mismatched_explicit_sidecars() -> None:
    inputs = {
        "vcf": "/inputs/somatic.vcf.gz",
        "vcf_index": "/inputs/other.vcf.gz.tbi",
        "reference": "/refs/GRCh38.fa",
        "reference_index": "/refs/GRCh38.fa.fai",
        "sequence_dictionary": "/refs/GRCh38.dict",
        "data_sources": "/refs/funcotator",
        "ref_version": "hg38",
    }
    assert "exact colocated index" in str(FuncotateTableNode.VALIDATE_INPUTS(inputs))


def test_vcfanno_stages_explicit_sources_under_configured_basenames(tmp_path: Path) -> None:
    files_dir = tmp_path / "files"
    indexes_dir = tmp_path / "indexes"
    files_dir.mkdir()
    indexes_dir.mkdir()
    genes = files_dir / "genes.vcf.gz"
    scores = files_dir / "scores.bed.gz"
    genes_index = indexes_dir / "genes.vcf.gz.tbi"
    scores_index = indexes_dir / "scores.bed.gz.csi"
    for path in (genes, scores, genes_index, scores_index):
        path.write_text(path.name, encoding="utf-8")
    config = tmp_path / "annotation.toml"
    config.write_text(
        '[[annotation]]\nfile="genes.vcf.gz"\nfields=["GENE"]\nops=["self"]\n'
        '[[annotation]]\nfile="scores.bed.gz"\ncolumns=[4]\nnames=["SCORE"]\nops=["mean"]\n',
        encoding="utf-8",
    )

    inputs: dict[str, object] = {
        "vcf": "/inputs/query.vcf.gz",
        "mode": "vcfanno",
        "vcfanno_config": str(config),
        "annotation_files": [str(genes), str(scores)],
        "annotation_indexes": [str(genes_index), str(scores_index)],
        "threads": 4,
        "output": str(tmp_path / "run" / "annotate_vcf"),
    }
    outputs = AnnotateVCFNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    assert AnnotateVCFNode.VALIDATE_INPUTS(inputs) is True
    AnnotateVCFNode.PREPARE_EXECUTION(inputs, outputs)
    staged_dir = outputs[0].parent / "annotation_sources"
    assert [Path(path) for path in inputs["annotation_files"]] == [
        staged_dir / "genes.vcf.gz",
        staged_dir / "scores.bed.gz",
    ]
    assert [Path(path) for path in inputs["annotation_indexes"]] == [
        staged_dir / "genes.vcf.gz.tbi",
        staged_dir / "scores.bed.gz.csi",
    ]
    assert Path(str(inputs["vcfanno_config"])) == staged_dir / "vcfanno.toml"
    command = AnnotateVCFNode.render_command(inputs)
    assert command[command.index("-base-path") + 1] == str(staged_dir)


def test_vcfanno_config_must_reference_staged_basenames(tmp_path: Path) -> None:
    config = tmp_path / "annotation.toml"
    config.write_text(
        '[[annotation]]\nfile="refs/genes.vcf.gz"\nfields=["GENE"]\nops=["self"]\n',
        encoding="utf-8",
    )
    validation = AnnotateVCFNode.VALIDATE_INPUTS(
        {
            "vcf": "/inputs/query.vcf.gz",
            "mode": "vcfanno",
            "vcfanno_config": str(config),
            "annotation_files": ["/uploads/genes.vcf.gz"],
            "annotation_indexes": ["/uploads/genes.vcf.gz.tbi"],
        }
    )
    assert validation == "vcfanno_config annotation files must use staged basenames without directories"
