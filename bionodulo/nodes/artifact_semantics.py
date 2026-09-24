"""Runtime evidence for coordinate-bearing text artifacts.

This module validates a deliberately small, standards-backed surface: the
coordinate-bearing core of BED, GFF3, and GTF.  It does not infer an assembly
from chromosome names and does not rewrite the source artifact.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


ArtifactFormat = Literal["bed", "gff3", "gtf"]
CoordinateSystem = Literal["zero_based_half_open", "one_based_closed"]
EvidenceLevel = Literal["observed", "declared", "unknown"]

FORMAT_COORDINATES: dict[ArtifactFormat, CoordinateSystem] = {
    "bed": "zero_based_half_open",
    "gff3": "one_based_closed",
    "gtf": "one_based_closed",
}

SPECIFICATIONS = {
    "bed": {
        "title": "GA4GH Browser Extensible Data (BED) v1",
        "version": "5 January 2022, repository print 9ddbc52",
        "url": "https://samtools.github.io/hts-specs/BEDv1.pdf",
    },
    "gff3": {
        "title": "Sequence Ontology GFF3 specification",
        "version": "3.1.26",
        "url": "https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md",
    },
    "gtf": {
        "title": "Ensembl GFF/GTF format documentation",
        "version": "GTF / GFF version 2 documentation, accessed 2026-09-23",
        "url": "https://www.ensembl.org/info/website/upload/gff.html",
    },
}


class ArtifactValidationError(ValueError):
    """The artifact contradicts or fails the requested semantic contract."""


@dataclass(frozen=True)
class EvidenceClaim:
    value: str | None
    level: EvidenceLevel
    basis: str


@dataclass(frozen=True)
class SequenceObservation:
    seqid: str
    record_count: int
    minimum_start: int
    maximum_end: int
    total_interval_bases: int


@dataclass(frozen=True)
class ReferenceRegionDeclaration:
    seqid: str
    start: int
    end: int


@dataclass(frozen=True)
class ArtifactValidationResult:
    """Immutable result; nested collections are tuples, not mutable mappings."""

    schema_version: str
    source_path: str
    source_sha256: str
    source_size_bytes: int
    artifact_format: ArtifactFormat
    coordinate_system: EvidenceClaim
    coordinate_validity: EvidenceClaim
    reference_assembly: EvidenceClaim
    sequence_observations: tuple[SequenceObservation, ...]
    reference_region_declarations: tuple[ReferenceRegionDeclaration, ...]
    records_scanned: int
    lines_scanned: int
    scan_scope: Literal["full_scan", "bounded_probe"]
    max_records: int | None
    specification_title: str
    specification_version: str
    specification_url: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _integer(text: str, *, field: str, line_number: int) -> int:
    try:
        return int(text)
    except ValueError as exc:
        raise ArtifactValidationError(
            f"line {line_number}: {field} must be an integer, got {text!r}"
        ) from exc


def _parse_sequence_region(
    line: str, line_number: int
) -> ReferenceRegionDeclaration:
    fields = line.split()
    if len(fields) != 4:
        raise ArtifactValidationError(
            f"line {line_number}: ##sequence-region requires seqid, start, and end"
        )
    start = _integer(fields[2], field="sequence-region start", line_number=line_number)
    end = _integer(fields[3], field="sequence-region end", line_number=line_number)
    if not fields[1] or start < 1 or end < start:
        raise ArtifactValidationError(
            f"line {line_number}: invalid 1-based closed ##sequence-region"
        )
    return ReferenceRegionDeclaration(fields[1], start, end)


def validate_artifact_semantics(
    source: str | Path,
    *,
    artifact_format: ArtifactFormat,
    declared_coordinate_system: str | None = None,
    declared_assembly: str | None = None,
    max_records: int | None = None,
) -> ArtifactValidationResult:
    """Validate coordinate semantics without changing ``source``.

    ``max_records=None`` performs a full record scan.  A positive cap validates
    only that record prefix and is reported as ``bounded_probe`` even when the
    cap happens to meet EOF, avoiding an unsupported whole-file claim.
    """

    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise ArtifactValidationError(f"input artifact does not exist: {path}")
    if artifact_format not in FORMAT_COORDINATES:
        raise ArtifactValidationError(f"unsupported artifact format: {artifact_format}")
    if max_records is not None and (
        isinstance(max_records, bool)
        or not isinstance(max_records, int)
        or max_records < 1
    ):
        raise ArtifactValidationError("max_records must be a positive integer or omitted")

    expected_coordinates = FORMAT_COORDINATES[artifact_format]
    declared_coordinates = (declared_coordinate_system or "").strip()
    if declared_coordinates in ("", "unknown"):
        declared_coordinates = ""
    elif declared_coordinates not in set(FORMAT_COORDINATES.values()):
        raise ArtifactValidationError(
            f"unsupported declared coordinate system: {declared_coordinates}"
        )
    elif declared_coordinates != expected_coordinates:
        raise ArtifactValidationError(
            f"declared coordinate system {declared_coordinates!r} contradicts "
            f"the {artifact_format} standard ({expected_coordinates})"
        )

    source_hash = _sha256(path)
    source_size = path.stat().st_size
    records = 0
    lines = 0
    first_nonempty_seen = False
    gff3_version_seen = False
    in_fasta = False
    genome_build: str | None = None
    observations: dict[str, list[int]] = {}
    regions: dict[str, ReferenceRegionDeclaration] = {}

    try:
        handle = path.open("r", encoding="utf-8-sig", errors="strict", newline="")
        with handle:
            for line_number, raw_line in enumerate(handle, start=1):
                lines = line_number
                line = raw_line.rstrip("\r\n")
                if not line.strip():
                    continue

                if in_fasta:
                    continue

                if artifact_format == "gff3" and not first_nonempty_seen:
                    first_nonempty_seen = True
                    if re.fullmatch(r"##gff-version 3(?:\.\d+(?:\.\d+)?)?", line) is None:
                        raise ArtifactValidationError(
                            "line 1/non-empty: GFF3 must begin with a ##gff-version 3 directive"
                        )

                if line.startswith("#"):
                    if artifact_format == "gff3":
                        if line.startswith("##gff-version"):
                            if gff3_version_seen:
                                raise ArtifactValidationError(
                                    f"line {line_number}: duplicate ##gff-version directive"
                                )
                            if re.fullmatch(r"##gff-version 3(?:\.\d+(?:\.\d+)?)?", line) is None:
                                raise ArtifactValidationError(
                                    f"line {line_number}: only GFF version 3 is supported"
                                )
                            gff3_version_seen = True
                        elif line == "##FASTA":
                            in_fasta = True
                        elif line.startswith("##sequence-region"):
                            region = _parse_sequence_region(line, line_number)
                            previous = regions.get(region.seqid)
                            if previous is not None and previous != region:
                                raise ArtifactValidationError(
                                    f"line {line_number}: contradictory ##sequence-region for {region.seqid}"
                                )
                            regions[region.seqid] = region
                        elif line.startswith("##genome-build"):
                            fields = line.split(maxsplit=2)
                            if len(fields) != 3 or not fields[2].strip():
                                raise ArtifactValidationError(
                                    f"line {line_number}: ##genome-build requires source and build name"
                                )
                            candidate = fields[2].strip()
                            if genome_build is not None and candidate.casefold() != genome_build.casefold():
                                raise ArtifactValidationError(
                                    f"line {line_number}: contradictory ##genome-build declarations"
                                )
                            genome_build = candidate
                    continue
                if artifact_format == "bed" and (
                    line.startswith("track ") or line.startswith("browser ")
                ):
                    continue

                if artifact_format == "bed":
                    fields = line.split()
                    if not 3 <= len(fields) <= 12:
                        raise ArtifactValidationError(
                            f"line {line_number}: BED coordinate core requires 3 to 12 fields"
                        )
                    seqid = fields[0]
                    start = _integer(fields[1], field="chromStart", line_number=line_number)
                    end = _integer(fields[2], field="chromEnd", line_number=line_number)
                    if not seqid or start < 0 or end < start:
                        raise ArtifactValidationError(
                            f"line {line_number}: invalid 0-based half-open BED interval"
                        )
                    interval_bases = end - start
                else:
                    fields = line.split("\t")
                    if len(fields) != 9:
                        raise ArtifactValidationError(
                            f"line {line_number}: {artifact_format.upper()} records require exactly 9 tab-separated fields"
                        )
                    seqid = fields[0]
                    start = _integer(fields[3], field="start", line_number=line_number)
                    end = _integer(fields[4], field="end", line_number=line_number)
                    if not seqid or seqid == "." or start < 1 or end < start:
                        raise ArtifactValidationError(
                            f"line {line_number}: invalid 1-based closed {artifact_format.upper()} interval"
                        )
                    if not fields[2] or fields[2] == ".":
                        raise ArtifactValidationError(
                            f"line {line_number}: feature type must be present"
                        )
                    if fields[6] not in {"+", "-", ".", "?"}:
                        raise ArtifactValidationError(
                            f"line {line_number}: invalid strand {fields[6]!r}"
                        )
                    if fields[7] not in {"0", "1", "2", "."}:
                        raise ArtifactValidationError(
                            f"line {line_number}: invalid phase {fields[7]!r}"
                        )
                    interval_bases = end - start + 1

                current = observations.setdefault(seqid, [0, start, end, 0])
                current[0] += 1
                current[1] = min(current[1], start)
                current[2] = max(current[2], end)
                current[3] += interval_bases
                records += 1
                if max_records is not None and records >= max_records:
                    break
    except UnicodeDecodeError as exc:
        raise ArtifactValidationError(
            f"artifact is not valid UTF-8 near byte {exc.start}"
        ) from exc

    if artifact_format == "gff3" and not gff3_version_seen:
        raise ArtifactValidationError("GFF3 is missing its required ##gff-version directive")
    if records == 0:
        raise ArtifactValidationError("artifact contains no coordinate records to validate")

    for seqid, observed in observations.items():
        region = regions.get(seqid)
        if region is not None and (
            observed[1] < region.start or observed[2] > region.end
        ):
            raise ArtifactValidationError(
                f"observed coordinates for {seqid} fall outside its ##sequence-region"
            )

    if _sha256(path) != source_hash or path.stat().st_size != source_size:
        raise ArtifactValidationError("source artifact changed during semantic validation")

    requested_assembly = (declared_assembly or "").strip()
    if requested_assembly and genome_build and requested_assembly.casefold() != genome_build.casefold():
        raise ArtifactValidationError(
            f"declared assembly {requested_assembly!r} contradicts GFF3 ##genome-build {genome_build!r}"
        )
    assembly = genome_build or requested_assembly or None
    if genome_build:
        assembly_claim = EvidenceClaim(
            assembly,
            "declared",
            "GFF3 ##genome-build declaration; reference sequence identity was not independently verified",
        )
    elif requested_assembly:
        assembly_claim = EvidenceClaim(
            assembly,
            "declared",
            "node parameter; reference sequence identity was not independently verified",
        )
    else:
        assembly_claim = EvidenceClaim(
            None,
            "unknown",
            "sequence names and coordinate ranges do not establish assembly identity",
        )

    scope = "bounded_probe" if max_records is not None else "full_scan"
    spec = SPECIFICATIONS[artifact_format]
    return ArtifactValidationResult(
        schema_version="1.0",
        source_path=str(path),
        source_sha256=source_hash,
        source_size_bytes=source_size,
        artifact_format=artifact_format,
        coordinate_system=EvidenceClaim(
            expected_coordinates,
            "declared",
            f"requested {artifact_format} format interpreted under the cited normative specification",
        ),
        coordinate_validity=EvidenceClaim(
            "valid",
            "observed",
            (
                "all coordinate records were scanned"
                if scope == "full_scan"
                else f"only the first {records} coordinate records were scanned"
            ),
        ),
        reference_assembly=assembly_claim,
        sequence_observations=tuple(
            SequenceObservation(seqid, values[0], values[1], values[2], values[3])
            for seqid, values in sorted(observations.items())
        ),
        reference_region_declarations=tuple(regions[key] for key in sorted(regions)),
        records_scanned=records,
        lines_scanned=lines,
        scan_scope=scope,
        max_records=max_records,
        specification_title=spec["title"],
        specification_version=spec["version"],
        specification_url=spec["url"],
    )


def write_artifact_semantic_evidence(
    result: ArtifactValidationResult, output_dir: str | Path
) -> tuple[Path, Path, str]:
    """Write deterministic JSON plus a detached SHA-256 checksum file."""

    source = Path(result.source_path)
    if _sha256(source) != result.source_sha256:
        raise ArtifactValidationError("source artifact changed during semantic validation")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    evidence_path = destination / f"{source.name}.semantic-evidence.json"
    payload = json.dumps(
        result.to_dict(), sort_keys=True, indent=2, ensure_ascii=False
    ).encode("utf-8") + b"\n"
    evidence_hash = hashlib.sha256(payload).hexdigest()
    evidence_path.write_bytes(payload)
    checksum_path = destination / f"{evidence_path.name}.sha256"
    checksum_path.write_text(
        f"{evidence_hash}  {evidence_path.name}\n", encoding="ascii"
    )
    if _sha256(source) != result.source_sha256:
        raise ArtifactValidationError("source artifact changed while evidence was written")
    return evidence_path, checksum_path, evidence_hash
