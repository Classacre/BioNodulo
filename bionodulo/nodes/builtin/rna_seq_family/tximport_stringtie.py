"""Gene-level import of StringTie Ballgown transcript tables with tximport."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode
from bionodulo.nodes.builtin.rna_seq_family.tximport import (
    _ordered_strings,
    _read_tsv,
)


_REQUIRED_CTAB_COLUMNS = (
    "t_id",
    "chr",
    "strand",
    "start",
    "end",
    "t_name",
    "num_exons",
    "length",
    "gene_id",
    "gene_name",
    "cov",
    "FPKM",
)

_GTF_ATTRIBUTE = re.compile(r'(?:^|;\s*)([A-Za-z][A-Za-z0-9_.-]*)\s+"([^"]*)"')


def _tx2gene_mapping(path: Path) -> dict[str, str]:
    header, rows = _read_tsv(path)
    if header != ["transcript_id", "gene_id"]:
        raise ValueError(
            "tx2gene must be a two-column TSV with header: transcript_id<TAB>gene_id"
        )
    mapping: dict[str, str] = {}
    for line_number, row in rows:
        if len(row) != 2 or not row[0].strip() or not row[1].strip():
            raise ValueError(f"tx2gene has an invalid row at line {line_number}")
        transcript, gene = row
        prior = mapping.get(transcript)
        if prior is not None:
            if prior != gene:
                raise ValueError(
                    f"tx2gene maps transcript {transcript!r} to more than one gene"
                )
            raise ValueError(f"tx2gene repeats transcript {transcript!r}")
        mapping[transcript] = gene
    if not mapping:
        raise ValueError("tx2gene must contain at least one transcript-to-gene row")
    return mapping


def _gtf_transcript_to_gene(path: Path) -> dict[str, str]:
    """Read an exact GTF transcript-to-gene contract from its attributes."""
    mapping: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\r\n")
            if not line or line.startswith("#"):
                continue
            fields = line.split("\t")
            if len(fields) != 9:
                raise ValueError(
                    f"reference_gtf must contain exactly 9 tab-separated fields at line {line_number}"
                )
            attributes = dict(_GTF_ATTRIBUTE.findall(fields[8]))
            transcript = attributes.get("transcript_id")
            if transcript is None:
                continue
            gene = attributes.get("gene_id")
            if not transcript or not gene:
                raise ValueError(
                    "reference_gtf transcript records must contain non-empty gene_id and "
                    f"transcript_id attributes at line {line_number}"
                )
            prior = mapping.get(transcript)
            if prior is not None and prior != gene:
                raise ValueError(
                    f"reference_gtf maps transcript {transcript!r} to both {prior!r} and {gene!r}"
                )
            mapping[transcript] = gene
    if not mapping:
        raise ValueError("reference_gtf contains no transcript_id to gene_id assignments")
    return mapping


def _validate_mapping_against_gtf(
    tx2gene: dict[str, str], reference: dict[str, str]
) -> None:
    unknown = sorted(set(tx2gene) - set(reference))
    if unknown:
        preview = ", ".join(unknown[:5])
        raise ValueError(
            f"tx2gene contains {len(unknown)} transcript(s) absent from reference_gtf: {preview}"
        )
    contradictions = sorted(
        transcript
        for transcript, gene in tx2gene.items()
        if reference[transcript] != gene
    )
    if contradictions:
        transcript = contradictions[0]
        raise ValueError(
            f"tx2gene contradicts reference_gtf for transcript {transcript!r}: "
            f"expected gene {reference[transcript]!r}, received {tx2gene[transcript]!r}"
        )


def _ctab_reference(path: Path) -> tuple[list[str], set[str]]:
    header, rows = _read_tsv(path)
    missing = [column for column in _REQUIRED_CTAB_COLUMNS if column not in header]
    if missing:
        raise ValueError(f"StringTie table {path} is missing columns: {', '.join(missing)}")
    indexes = {name: header.index(name) for name in _REQUIRED_CTAB_COLUMNS}
    reference: list[str] = []
    transcripts: set[str] = set()
    for line_number, row in rows:
        if len(row) != len(header):
            raise ValueError(f"StringTie table {path} has an invalid row at line {line_number}")
        transcript = row[indexes["t_name"]]
        if not transcript:
            raise ValueError(f"StringTie table {path} has an empty t_name at line {line_number}")
        if transcript in transcripts:
            raise ValueError(f"StringTie table {path} repeats transcript {transcript!r}")
        transcripts.add(transcript)
        strand = row[indexes["strand"]]
        if strand not in {"+", "-", "."}:
            raise ValueError(f"StringTie table {path} has an invalid strand at line {line_number}")
        numeric_names = ("start", "end", "num_exons", "length", "cov", "FPKM")
        numeric: dict[str, float] = {}
        try:
            for name in numeric_names:
                numeric[name] = float(row[indexes[name]])
        except ValueError:
            raise ValueError(
                f"StringTie table {path} has a non-numeric value at line {line_number}"
            ) from None
        if not all(math.isfinite(value) for value in numeric.values()):
            raise ValueError(f"StringTie table {path} has a non-finite value at line {line_number}")
        if (
            numeric["start"] < 1
            or numeric["end"] < numeric["start"]
            or numeric["num_exons"] < 1
            or numeric["length"] <= 0
            or numeric["cov"] < 0
            or numeric["FPKM"] < 0
        ):
            raise ValueError(
                f"StringTie table {path} has invalid coordinates, length, coverage, or FPKM "
                f"at line {line_number}"
            )
        reference.append(
            "\x1f".join(
                (
                    transcript,
                    row[indexes["chr"]],
                    strand,
                    row[indexes["start"]],
                    row[indexes["end"]],
                    row[indexes["length"]],
                )
            )
        )
    if not reference:
        raise ValueError(f"StringTie table {path} has no transcript rows")
    return reference, transcripts


class TximportStringTieNode(CommandNode):
    """Import reference-guided StringTie coverage using an explicit read length."""

    NODE_ID = "tximport_stringtie"
    DISPLAY_NAME = "tximport StringTie to Genes"
    CATEGORY = "rna_seq"
    DESCRIPTION = (
        "Convert reference-guided StringTie t_data.ctab coverage to gene-level tximport "
        "matrices using an explicit sequencing read length."
    )
    SEARCH_ALIASES = ["tximport", "StringTie", "t_data.ctab", "Ballgown", "gene abundance"]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "FILE", "JSON")
    RETURN_NAMES = (
        "gene_count_scale",
        "gene_abundance_fpkm",
        "gene_effective_length",
        "tximport_object",
        "import_metadata",
    )
    REQUIRED_EXECUTABLES = ["Rscript"]
    REQUIRED_CONDA_PACKAGES = ["r-base", "bioconductor-tximport", "r-jsonlite"]
    REQUIRED_R_PACKAGES = ["tximport", "jsonlite"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "r-base": "4.5.*",
        "bioconductor-tximport": "1.38.2",
        "r-jsonlite": "2.0.0",
    }
    PACKAGE_CONSTRAINTS = (
        "r-base=4.5.*",
        "bioconductor-tximport=1.38.2",
        "r-jsonlite=2.0.0",
    )
    VERSION = "1.38.2"
    GIT_URL = "https://git.bioconductor.org/packages/tximport"
    GIT_COMMIT = "1c6a0bb7ba89727d227946700dffe2c436b6e11e"
    DOCUMENTATION_URL = (
        "https://bioconductor.org/packages/3.22/bioc/vignettes/tximport/inst/doc/tximport.html"
    )
    CITATION_DOIS = ["10.12688/f1000research.7563.1"]
    CITATION_URLS = ["https://doi.org/10.12688/f1000research.7563.1"]
    CITATION_TEXT = (
        "Soneson C, Love MI, Robinson MD. Differential analyses for RNA-seq: "
        "transcript-level estimates improve gene-level inferences."
    )
    COUNTS_FROM_ABUNDANCE = ("no", "scaledTPM", "lengthScaledTPM")
    SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "tximport_stringtie.R"
    AUDIT_STATUS = "upstream-executed-tiny-fixture"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "ctab_files": (
                    "TSV",
                    {
                        "multiple": True,
                        "description": (
                            "Ordered t_data.ctab files from StringTie -e -B runs against the same GTF"
                        ),
                    },
                ),
                "sample_ids": (
                    "STRING",
                    {
                        "multiple": True,
                        "description": "Unique sample identifiers in the same order as ctab_files",
                    },
                ),
                "tx2gene": (
                    "TSV",
                    {
                        "description": (
                            "Two-column transcript_id/gene_id TSV matching the reference GTF"
                        )
                    },
                ),
                "reference_gtf": (
                    "GTF",
                    {
                        "description": (
                            "Exact reference GTF used for StringTie -e -B; transcript_id/gene_id "
                            "assignments are enforced and its SHA-256 is recorded"
                        )
                    },
                ),
                "read_length": (
                    "FLOAT",
                    {
                        "min": 1.0,
                        "description": (
                            "Sequenced read length used by tximport to reconstruct count-scale values "
                            "as coverage * transcript length / read length"
                        ),
                    },
                ),
            },
            "optional": {
                "counts_from_abundance": (
                    "STRING",
                    {
                        "default": "no",
                        "options": list(cls.COUNTS_FROM_ABUNDANCE),
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output = Path(output_dir) / cls.NODE_ID
        output.mkdir(parents=True, exist_ok=True)
        return [
            output / "gene_count_scale.tsv",
            output / "gene_abundance_fpkm.tsv",
            output / "gene_effective_length.tsv",
            output / "tximport_object.rds",
            output / "import_metadata.json",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        mode = inputs.get("counts_from_abundance", "no")
        if mode == "dtuScaledTPM":
            return (
                "dtuScaledTPM is for transcript-level DTU with txOut=TRUE; this node produces "
                "gene-level outputs"
            )
        if mode not in cls.COUNTS_FROM_ABUNDANCE:
            return "counts_from_abundance must be one of: " + ", ".join(cls.COUNTS_FROM_ABUNDANCE)
        read_length = inputs.get("read_length")
        if isinstance(read_length, bool) or not isinstance(read_length, (int, float)):
            return "read_length must be an explicit positive number"
        if not math.isfinite(float(read_length)) or float(read_length) <= 0:
            return "read_length must be an explicit positive number"
        try:
            ctab_files = [Path(path) for path in _ordered_strings(inputs.get("ctab_files"), "ctab_files")]
            sample_ids = _ordered_strings(inputs.get("sample_ids"), "sample_ids")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if len(ctab_files) != len(sample_ids):
            return "sample_ids must contain exactly one identifier for each ctab_files entry"
        if len(set(sample_ids)) != len(sample_ids):
            return "sample_ids must be unique"
        if any("\t" in sample or "\n" in sample or "\r" in sample for sample in sample_ids):
            return "sample_ids cannot contain tabs or newlines"
        for ctab_file in ctab_files:
            if not ctab_file.is_file():
                return f"ctab_files path is not a materialized file: {ctab_file}"
        tx2gene = Path(str(inputs.get("tx2gene", "")))
        if not tx2gene.is_file():
            return f"tx2gene is not a materialized file: {tx2gene}"
        reference_gtf = Path(str(inputs.get("reference_gtf", "")))
        if not reference_gtf.is_file():
            return f"reference_gtf is not a materialized file: {reference_gtf}"
        try:
            mapping = _tx2gene_mapping(tx2gene)
            reference_mapping = _gtf_transcript_to_gene(reference_gtf)
            _validate_mapping_against_gtf(mapping, reference_mapping)
            first_reference, first_transcripts = _ctab_reference(ctab_files[0])
            unmapped = first_transcripts - set(mapping)
            if unmapped:
                preview = ", ".join(sorted(unmapped)[:5])
                return f"tx2gene is missing {len(unmapped)} StringTie transcript(s): {preview}"
            absent_from_reference = first_transcripts - set(reference_mapping)
            if absent_from_reference:
                preview = ", ".join(sorted(absent_from_reference)[:5])
                return (
                    f"reference_gtf is missing {len(absent_from_reference)} StringTie "
                    f"transcript(s): {preview}"
                )
            for ctab_file in ctab_files[1:]:
                reference, _transcripts = _ctab_reference(ctab_file)
                if reference != first_reference:
                    return (
                        "all StringTie tables must contain the same transcript reference in the "
                        f"same order; mismatch in {ctab_file}"
                    )
        except (OSError, UnicodeError, ValueError) as exc:
            return str(exc)
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        ctab_files = _ordered_strings(inputs["ctab_files"], "ctab_files")
        sample_ids = _ordered_strings(inputs["sample_ids"], "sample_ids")
        manifest = outputs[0].parent / "sample_manifest.tsv"
        with manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["sample_id", "ctab_file"])
            writer.writerows(zip(sample_ids, (str(Path(path).resolve()) for path in ctab_files)))
        inputs["_sample_manifest"] = str(manifest)
        inputs["_planned_outputs"] = [str(path) for path in outputs]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        outputs = inputs.get("_planned_outputs")
        manifest = inputs.get("_sample_manifest")
        if not isinstance(outputs, list) or len(outputs) != len(cls.RETURN_TYPES) or not manifest:
            raise ValueError("PREPARE_EXECUTION must run before rendering tximport")
        return [
            "Rscript",
            "--vanilla",
            str(cls.SCRIPT_PATH),
            str(manifest),
            str(Path(str(inputs["tx2gene"])).resolve()),
            str(Path(str(inputs["reference_gtf"])).resolve()),
            str(inputs["read_length"]),
            str(inputs.get("counts_from_abundance", "no")),
            *outputs,
        ]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        sample_ids = _ordered_strings(inputs["sample_ids"], "sample_ids")
        expected_header = ["gene_id", *sample_ids]
        for path in outputs[:3]:
            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.reader(handle, delimiter="\t")
                header = next(reader, [])
                row = next(reader, None)
            if header != expected_header or row is None:
                raise RuntimeError(f"tximport StringTie matrix is empty or has wrong sample order: {path}")
        metadata = json.loads(outputs[4].read_text(encoding="utf-8"))
        if metadata.get("read_length") != float(inputs["read_length"]):
            raise RuntimeError("tximport metadata read_length does not match the requested value")
        if metadata.get("counts_from_abundance") != inputs.get("counts_from_abundance", "no"):
            raise RuntimeError("tximport metadata counts_from_abundance does not match the requested value")
        if metadata.get("sample_ids") != sample_ids:
            raise RuntimeError("tximport metadata sample order does not match requested sample_ids")
        reference_gtf = Path(str(inputs["reference_gtf"])).resolve()
        expected_sha256 = hashlib.sha256(reference_gtf.read_bytes()).hexdigest()
        if metadata.get("reference_gtf_sha256") != expected_sha256:
            raise RuntimeError("tximport metadata reference_gtf SHA-256 does not match the input")


__all__ = ["TximportStringTieNode"]
