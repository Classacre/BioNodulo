from __future__ import annotations

from pathlib import Path

from bionodulo.nodes.builtin.variant_family.delly import DellyNode
from bionodulo.nodes.builtin.variant_family.freebayes import FreeBayesNode
from bionodulo.nodes.builtin.variant_family.gatk_base_recalibrator import (
    GatkBaseRecalibratorNode,
)
from bionodulo.nodes.builtin.variant_family.gatk_genotype_gvcfs import (
    GatkGenotypeGVCFsNode,
)
from bionodulo.nodes.builtin.variant_family.gatk_haplotype_caller import (
    GatkHaplotypeCallerNode,
)
from bionodulo.nodes.builtin._sidecar_staging import stage_variant_pair


def _write(path: Path, content: bytes = b"fixture") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def _reference_bundle(source: Path) -> dict[str, Path]:
    return {
        "reference": _write(source / "GRCh38.fa"),
        "reference_index": _write(source / "GRCh38.fa.fai"),
        "sequence_dictionary": _write(source / "GRCh38.dict"),
    }


def _bam_bundle(source: Path, stem: str = "sample") -> dict[str, Path]:
    bam = _write(source / f"{stem}.bam")
    return {"bam": bam, "bam_index": _write(source / f"{stem}.bam.bai")}


def test_freebayes_prepare_stages_bam_and_reference_siblings(tmp_path: Path) -> None:
    source = tmp_path / "uploaded"
    inputs = {
        **_bam_bundle(source),
        "reference": _write(source / "GRCh38.fa"),
        "reference_index": _write(source / "GRCh38.fa.fai"),
    }
    outputs = FreeBayesNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    FreeBayesNode.PREPARE_EXECUTION(inputs, outputs)

    staged_bam = Path(str(inputs["bam"]))
    staged_reference = Path(str(inputs["reference"]))
    assert staged_bam == staged_bam.parent / "primary.bam"
    assert Path(str(inputs["bam_index"])) == Path(f"{staged_bam}.bai")
    assert staged_reference == staged_reference.parent / "reference.fa"
    assert Path(str(inputs["reference_index"])) == Path(f"{staged_reference}.fai")
    assert staged_bam.read_bytes() == b"fixture"
    assert staged_reference.read_bytes() == b"fixture"
    assert FreeBayesNode.VALIDATE_INPUTS(inputs) is True


def test_delly_prepare_stages_matched_control_pair(tmp_path: Path) -> None:
    source = tmp_path / "uploaded"
    primary = _bam_bundle(source, "tumor")
    normal = _bam_bundle(source, "normal")
    inputs = {
        **primary,
        "reference": _write(source / "ref.fa"),
        "reference_index": _write(source / "ref.fa.fai"),
        "normal_bam": normal["bam"],
        "normal_bam_index": normal["bam_index"],
    }
    outputs = DellyNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    DellyNode.PREPARE_EXECUTION(inputs, outputs)

    normal_bam = Path(str(inputs["normal_bam"]))
    assert normal_bam.name == "normal.bam"
    assert Path(str(inputs["normal_bam_index"])) == Path(f"{normal_bam}.bai")
    assert normal_bam.parent == Path(str(inputs["bam"])).parent
    assert DellyNode.VALIDATE_INPUTS(inputs) is True


def test_gatk_prepare_stages_dictionary_and_dbsnp_index(tmp_path: Path) -> None:
    source = tmp_path / "uploaded"
    reference = _reference_bundle(source)
    bam = _bam_bundle(source)
    dbsnp = _write(source / "dbsnp.vcf.gz")
    dbsnp_index = _write(source / "dbsnp.vcf.gz.tbi")
    inputs = {
        **reference,
        **bam,
        "threads": 4,
        "dbsnp": dbsnp,
        "dbsnp_index": dbsnp_index,
    }
    outputs = GatkHaplotypeCallerNode.PLAN_OUTPUTS(inputs, tmp_path / "run")

    GatkHaplotypeCallerNode.PREPARE_EXECUTION(inputs, outputs)

    staged_reference = Path(str(inputs["reference"]))
    assert Path(str(inputs["reference_index"])) == Path(f"{staged_reference}.fai")
    assert Path(str(inputs["sequence_dictionary"])) == staged_reference.with_suffix(".dict")
    staged_dbsnp = Path(str(inputs["dbsnp"]))
    assert Path(str(inputs["dbsnp_index"])) == Path(f"{staged_dbsnp}.tbi")
    assert GatkHaplotypeCallerNode.VALIDATE_INPUTS(inputs) is True


def test_gatk_prepare_stages_known_site_lists_and_gvcf_alias(tmp_path: Path) -> None:
    source = tmp_path / "uploaded"
    reference = _reference_bundle(source)
    bam = _bam_bundle(source)
    known_a = _write(source / "known-a.vcf.gz")
    known_a_index = _write(source / "known-a.vcf.gz.tbi")
    known_b = _write(source / "known-b.vcf")
    known_b_index = _write(source / "known-b.vcf.idx")
    base_inputs = {
        **reference,
        **bam,
        "known_sites": [known_a, known_b],
        "known_sites_indexes": [known_a_index, known_b_index],
    }
    base_outputs = GatkBaseRecalibratorNode.PLAN_OUTPUTS(base_inputs, tmp_path / "base")
    GatkBaseRecalibratorNode.PREPARE_EXECUTION(base_inputs, base_outputs)

    staged_sites = [Path(value) for value in base_inputs["known_sites"]]
    staged_indexes = [Path(value) for value in base_inputs["known_sites_indexes"]]
    assert [Path(f"{site}{index.suffix}") for site, index in zip(staged_sites, staged_indexes, strict=True)] == staged_indexes
    assert GatkBaseRecalibratorNode.VALIDATE_INPUTS(base_inputs) is True

    gvcf = _write(source / "sample.g.vcf.gz")
    gvcf_index = _write(source / "sample.g.vcf.gz.tbi")
    alias_inputs = {
        **reference,
        "gvcfs": [gvcf],
        "gvcf_index": gvcf_index,
    }
    alias_outputs = GatkGenotypeGVCFsNode.PLAN_OUTPUTS(alias_inputs, tmp_path / "gvcf")
    GatkGenotypeGVCFsNode.PREPARE_EXECUTION(alias_inputs, alias_outputs)

    staged_gvcf = Path(alias_inputs["gvcfs"][0])
    assert Path(f"{staged_gvcf}.tbi") == Path(alias_inputs["gvcf_index"])
    assert GatkGenotypeGVCFsNode.VALIDATE_INPUTS(alias_inputs) is True


def test_gatk_prepare_does_not_hide_conflicting_gvcf_alias(tmp_path: Path) -> None:
    source = tmp_path / "uploaded"
    reference = _reference_bundle(source)
    canonical = _write(source / "canonical.g.vcf.gz")
    canonical_index = _write(source / "canonical.g.vcf.gz.tbi")
    conflicting = _write(source / "conflicting.g.vcf.gz")
    inputs = {
        **reference,
        "gvcf": canonical,
        "gvcf_index": canonical_index,
        "gvcfs": [conflicting],
    }
    outputs = GatkGenotypeGVCFsNode.PLAN_OUTPUTS(inputs, tmp_path / "conflict")

    GatkGenotypeGVCFsNode.PREPARE_EXECUTION(inputs, outputs)

    assert GatkGenotypeGVCFsNode.VALIDATE_INPUTS(inputs) is not True
    assert inputs["gvcfs"] == [conflicting]


def test_variant_staging_preflights_all_pairs_before_writing(tmp_path: Path) -> None:
    source = tmp_path / "uploaded"
    first = _write(source / "first.vcf.gz")
    first_index = _write(source / "first.vcf.gz.tbi")
    missing = source / "missing.vcf.gz"
    missing_index = source / "missing.vcf.gz.tbi"
    inputs = {
        "variants": [first, missing],
        "indexes": [first_index, missing_index],
    }

    stage_variant_pair(
        inputs,
        tmp_path / "run" / "inputs",
        variant_key="variants",
        index_key="indexes",
        role="resource",
    )

    assert inputs["variants"] == [first, missing]
    assert not (tmp_path / "run" / "inputs").exists()
