"""Shared GATK 4.6.2.0 metadata and sidecar validation."""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, ClassVar

from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
    validate_colocated_sequence_dictionary,
)
from bionodulo.nodes.builtin._sidecar_staging import stage_variant_sidecars
from bionodulo.nodes.command_node import CommandNode


GATK_GIT_COMMIT = "76edc75c26504da94bbaee66584e107e76ee15de"


def _absolute_path(value: Any, *, key: str) -> Path | str:
    try:
        decoded = os.fsdecode(os.fspath(value))
    except TypeError:
        return f"Input '{key}' must be a non-empty path-like value"
    if not decoded.strip():
        return f"Input '{key}' must be a non-empty path-like value"
    return Path(os.path.abspath(os.path.normpath(decoded)))


def validate_path_input(inputs: Mapping[str, Any], *, key: str) -> bool | str:
    """Require one non-empty path-like input without checking the filesystem."""
    value = _absolute_path(inputs.get(key), key=key)
    return value if isinstance(value, str) else True


def path_values(value: Any, *, key: str, split_commas: bool = False) -> list[str] | str:
    """Normalize one or more path-like values without filesystem access."""
    if value is None:
        return []
    if isinstance(value, (str, bytes, os.PathLike)):
        try:
            decoded = os.fsdecode(os.fspath(value))
        except TypeError:
            return f"Input '{key}' must contain path-like values"
        if not decoded.strip():
            return []
        raw_values = decoded.split(",") if split_commas else [decoded]
    elif isinstance(value, Iterable) and not isinstance(value, Mapping):
        raw_values = list(value)
    else:
        return f"Input '{key}' must contain path-like values"

    paths: list[str] = []
    for item in raw_values:
        try:
            decoded = os.fsdecode(os.fspath(item)).strip()
        except TypeError:
            return f"Input '{key}' must contain path-like values"
        if not decoded:
            return f"Input '{key}' must contain non-empty path-like values"
        paths.append(decoded)
    return paths


def resolve_single_path_alias(
    inputs: Mapping[str, Any],
    *,
    canonical_key: str,
    alias_key: str,
    split_alias_commas: bool = False,
) -> str | None:
    """Resolve a compatibility alias, rejecting multiplicity and conflicts."""
    canonical = path_values(inputs.get(canonical_key), key=canonical_key)
    if isinstance(canonical, str):
        raise ValueError(canonical)
    alias = path_values(
        inputs.get(alias_key),
        key=alias_key,
        split_commas=split_alias_commas,
    )
    if isinstance(alias, str):
        raise ValueError(alias)
    if len(canonical) > 1:
        raise ValueError(f"Input '{canonical_key}' accepts exactly one path")
    if len(alias) > 1:
        raise ValueError(
            f"Compatibility input '{alias_key}' must resolve to exactly one path; "
            f"GATK GenotypeGVCFs does not accept multiple GVCFs"
        )
    if canonical and alias:
        canonical_path = _absolute_path(canonical[0], key=canonical_key)
        alias_path = _absolute_path(alias[0], key=alias_key)
        if canonical_path != alias_path:
            raise ValueError(
                f"Inputs '{canonical_key}' and compatibility alias '{alias_key}' conflict"
            )
    if canonical:
        return canonical[0]
    if alias:
        return alias[0]
    return None


def validate_gatk_bam_index(
    inputs: Mapping[str, Any],
    *,
    bam_key: str = "bam",
    index_key: str = "bam_index",
) -> bool | str:
    """Accept the two exact colocated BAI names discovered by htsjdk."""
    bam = _absolute_path(inputs.get(bam_key), key=bam_key)
    if isinstance(bam, str):
        return bam
    index = _absolute_path(inputs.get(index_key), key=index_key)

    expected = {Path(f"{bam}.bai")}
    if bam.name.lower().endswith(".bam"):
        expected.add(bam.with_suffix(".bai"))
    if isinstance(index, str):
        rendered = ", ".join(str(path) for path in sorted(expected, key=str))
        return f"{index}; expected one of: {rendered}"
    if index not in expected:
        rendered = ", ".join(str(path) for path in sorted(expected, key=str))
        return (
            f"Input '{index_key}' must be an exact colocated index for input "
            f"'{bam_key}'; expected one of: {rendered}"
        )
    return True


def validate_optional_bam_index(
    inputs: Mapping[str, Any],
    *,
    bam_key: str,
    index_key: str,
) -> bool | str:
    bams = path_values(inputs.get(bam_key), key=bam_key)
    if isinstance(bams, str):
        return bams
    indexes = path_values(inputs.get(index_key), key=index_key)
    if isinstance(indexes, str):
        return indexes
    if not bams and not indexes:
        return True
    if not bams:
        return f"Input '{index_key}' requires input '{bam_key}'"
    if not indexes:
        return f"Input '{bam_key}' requires paired input '{index_key}'"
    if len(bams) != 1 or len(indexes) != 1:
        return f"Inputs '{bam_key}' and '{index_key}' each accept exactly one path"
    return validate_gatk_bam_index(
        {bam_key: bams[0], index_key: indexes[0]},
        bam_key=bam_key,
        index_key=index_key,
    )


def validate_reference_bundle(
    inputs: Mapping[str, Any],
    *,
    reference_key: str = "reference",
    index_key: str = "reference_index",
    dictionary_key: str = "sequence_dictionary",
) -> bool | str:
    """Require the exact FASTA index and extension-replaced sequence dictionary."""
    validation = validate_colocated_reference_index(
        inputs,
        reference_key=reference_key,
        index_key=index_key,
    )
    if validation is not True:
        return validation
    return validate_colocated_sequence_dictionary(
        inputs,
        reference_key=reference_key,
        dictionary_key=dictionary_key,
    )


def validate_gatk_variant_index(
    inputs: Mapping[str, Any],
    *,
    variant_key: str,
    index_key: str,
) -> bool | str:
    """Require GATK's exact TBI for VCF.gz or Tribble IDX for VCF."""
    variant = _absolute_path(inputs.get(variant_key), key=variant_key)
    if isinstance(variant, str):
        return variant
    lower_name = variant.name.lower()
    if lower_name.endswith(".vcf.gz"):
        expected = Path(f"{variant}.tbi")
    elif lower_name.endswith(".vcf"):
        expected = Path(f"{variant}.idx")
    else:
        return f"Input '{variant_key}' must end with '.vcf' or '.vcf.gz'"

    index = _absolute_path(inputs.get(index_key), key=index_key)
    if isinstance(index, str):
        return f"{index}; expected '{expected}' for input '{variant_key}'"
    if index != expected:
        return (
            f"Input '{index_key}' must be the exact colocated index for input "
            f"'{variant_key}'; expected '{expected}'"
        )
    return True


def validate_optional_variant_index(
    inputs: Mapping[str, Any],
    *,
    variant_key: str,
    index_key: str,
) -> bool | str:
    variants = path_values(inputs.get(variant_key), key=variant_key)
    if isinstance(variants, str):
        return variants
    indexes = path_values(inputs.get(index_key), key=index_key)
    if isinstance(indexes, str):
        return indexes
    if not variants and not indexes:
        return True
    if not variants:
        return f"Input '{index_key}' requires input '{variant_key}'"
    if not indexes:
        return f"Input '{variant_key}' requires paired input '{index_key}'"
    if len(variants) != 1 or len(indexes) != 1:
        return f"Inputs '{variant_key}' and '{index_key}' each accept exactly one path"
    return validate_gatk_variant_index(
        {variant_key: variants[0], index_key: indexes[0]},
        variant_key=variant_key,
        index_key=index_key,
    )


def validate_variant_index_pairs(
    inputs: Mapping[str, Any],
    *,
    variants_key: str,
    indexes_key: str,
    split_commas: bool = False,
) -> bool | str:
    variants = path_values(
        inputs.get(variants_key),
        key=variants_key,
        split_commas=split_commas,
    )
    if isinstance(variants, str):
        return variants
    indexes = path_values(
        inputs.get(indexes_key),
        key=indexes_key,
        split_commas=split_commas,
    )
    if isinstance(indexes, str):
        return indexes
    if not variants:
        return f"Input '{variants_key}' must contain at least one variant path"
    if len(indexes) != len(variants):
        return f"Input '{indexes_key}' must contain one index for each '{variants_key}' value"
    for variant, index in zip(variants, indexes, strict=True):
        validation = validate_gatk_variant_index(
            {"variant": variant, "index": index},
            variant_key="variant",
            index_key="index",
        )
        if validation is not True:
            return str(validation).replace("'variant'", f"'{variants_key}'").replace(
                "'index'", f"'{indexes_key}'"
            )
    return True


class GATKCommandNode(CommandNode):
    """Pinned source identity and output planning shared by focused GATK nodes."""

    CATEGORY = "variant"
    REQUIRED_EXECUTABLES = ["gatk"]
    REQUIRED_CONDA_PACKAGES = ["gatk4"]
    VERSION = "4.6.2.0"
    GIT_URL = "https://github.com/broadinstitute/gatk.git"
    GIT_COMMIT = GATK_GIT_COMMIT
    GIT_TAG = "4.6.2.0"
    SOURCE_REF = f"tag {GIT_TAG} at {GIT_COMMIT}"
    SOURCE_REVISION = GIT_COMMIT
    SOURCE_URL = f"https://github.com/broadinstitute/gatk/tree/{GATK_GIT_COMMIT}"
    PACKAGE_CONSTRAINTS = ("gatk4==4.6.2.0",)
    PACKAGE_CONSTRAINT = "gatk4==4.6.2.0"
    EXIT_SEMANTICS = "Input validation or a non-zero GATK result fails the node."
    AUDIT_STATUS = "contract-checked-no-external-execution"
    SHELL = False

    OUTPUT_FILENAMES: ClassVar[tuple[str, ...]] = ()
    UPSTREAM_SOURCE = ""

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / filename for filename in cls.OUTPUT_FILENAMES]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Stage reference, alignment, and indexed resource bundles together.

        GATK/htsjdk discovers these sidecars from the path passed on the
        command line.  Keeping the explicit ports is useful for graph
        validation; this hook makes the same contract true after cloud input
        materialization, where each uploaded object may start in a different
        directory.
        """
        # Capture whether both spellings referred to the same original path.
        # Staging rewrites the canonical path; only an equivalent compatibility
        # alias may be rewritten along with it.  A conflicting alias must remain
        # visible to ``VALIDATE_INPUTS`` instead of being silently overwritten.
        gvcf_alias_matches = False
        if inputs.get("gvcf") not in (None, "") and inputs.get("gvcfs") not in (None, ""):
            canonical_values = path_values(inputs.get("gvcf"), key="gvcf")
            alias_values = path_values(
                inputs.get("gvcfs"),
                key="gvcfs",
                split_commas=True,
            )
            if (
                isinstance(canonical_values, list)
                and isinstance(alias_values, list)
                and len(canonical_values) == 1
                and len(alias_values) == 1
            ):
                canonical_path = _absolute_path(canonical_values[0], key="gvcf")
                alias_path = _absolute_path(alias_values[0], key="gvcfs")
                gvcf_alias_matches = (
                    isinstance(canonical_path, Path)
                    and isinstance(alias_path, Path)
                    and canonical_path == alias_path
                )

        bam_pairs = tuple(
            pair
            for pair in (
                ("bam", "bam_index", "primary"),
                ("tumor_bam", "tumor_bam_index", "tumor"),
                ("normal_bam", "normal_bam_index", "normal"),
            )
            if inputs.get(pair[0]) not in (None, "") or inputs.get(pair[1]) not in (None, "")
        )
        variant_pairs: list[tuple[str, str, str, bool]] = [
            ("dbsnp", "dbsnp_index", "dbsnp", False),
            ("germline_resource", "germline_resource_index", "germline_resource", False),
            ("panel_of_normals", "panel_of_normals_index", "panel_of_normals", False),
            ("known_sites", "known_sites_indexes", "known_sites", True),
        ]
        # GenotypeGVCFs has a compatibility alias (gvcfs) for its canonical
        # scalar input.  Stage whichever spelling the user supplied, while
        # retaining a single canonical value for post-stage validation.
        if inputs.get("gvcf") not in (None, ""):
            variant_pairs.append(("gvcf", "gvcf_index", "gvcf", False))
        elif inputs.get("gvcfs") not in (None, ""):
            variant_pairs.append(("gvcfs", "gvcf_index", "gvcf", True))

        stage_variant_sidecars(
            inputs,
            outputs,
            bam_pairs=bam_pairs,
            variant_pairs=tuple(variant_pairs),
        )
        if gvcf_alias_matches:
            # Avoid a false alias-conflict after the canonical path has been
            # rewritten by staging.
            inputs["gvcfs"] = inputs["gvcf"]

    @classmethod
    def output_path(cls, inputs: Mapping[str, Any], index: int = 0) -> Path:
        output_dir = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return output_dir / cls.OUTPUT_FILENAMES[index]

    @classmethod
    def checked_command(cls, inputs: dict[str, Any], tool: str) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        return ["gatk", tool]

    @staticmethod
    def validate_choice(value: Any, *, key: str, choices: tuple[str, ...]) -> bool | str:
        if str(value) not in choices:
            return f"Input '{key}' must be one of: {', '.join(choices)}"
        return True

    @staticmethod
    def validate_int(
        value: Any,
        *,
        key: str,
        minimum: int | None = None,
        maximum: int | None = None,
    ) -> bool | str:
        if isinstance(value, bool) or not isinstance(value, int):
            return f"Input '{key}' must be an integer"
        if minimum is not None and value < minimum:
            return f"Input '{key}' must be at least {minimum}"
        if maximum is not None and value > maximum:
            return f"Input '{key}' must be at most {maximum}"
        return True

    @staticmethod
    def validate_number(
        value: Any,
        *,
        key: str,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> bool | str:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return f"Input '{key}' must be a number"
        number = float(value)
        if minimum is not None and number < minimum:
            return f"Input '{key}' must be at least {minimum:g}"
        if maximum is not None and number > maximum:
            return f"Input '{key}' must be at most {maximum:g}"
        return True
