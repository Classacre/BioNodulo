"""Gene-level import of Salmon quantifications with Bioconductor tximport."""

from __future__ import annotations

import csv
import json
import math
import os
from pathlib import Path
from typing import Any, Iterable

from bionodulo.nodes.command_node import CommandNode


_QUANT_COLUMNS = ("Name", "Length", "EffectiveLength", "TPM", "NumReads")


def _ordered_strings(value: Any, name: str) -> list[str]:
    if isinstance(value, (str, os.PathLike)):
        values = [value]
    elif isinstance(value, (list, tuple)):
        values = list(value)
    else:
        raise TypeError(f"{name} must be a value or ordered collection")
    result = [os.fsdecode(os.fspath(item)) for item in values]
    if not result or any(not item.strip() for item in result):
        raise ValueError(f"{name} must contain non-empty values")
    return result


def _read_tsv(path: Path) -> tuple[list[str], Iterable[tuple[int, list[str]]]]:
    handle = path.open("r", encoding="utf-8-sig", newline="")
    reader = csv.reader(handle, delimiter="\t")
    try:
        header = next(reader)
    except StopIteration:
        handle.close()
        raise ValueError(f"TSV file is empty: {path}") from None

    def rows() -> Iterable[tuple[int, list[str]]]:
        try:
            for line_number, row in enumerate(reader, start=2):
                yield line_number, row
        finally:
            handle.close()

    return header, rows()


def _mapping_transcripts(path: Path) -> set[str]:
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
    return set(mapping)


def _quant_transcripts(path: Path) -> list[str]:
    header, rows = _read_tsv(path)
    if tuple(header) != _QUANT_COLUMNS:
        raise ValueError(
            f"Salmon file {path} must have exactly these columns in order: "
            + ", ".join(_QUANT_COLUMNS)
        )
    transcripts: list[str] = []
    seen: set[str] = set()
    for line_number, row in rows:
        if len(row) != len(_QUANT_COLUMNS) or not row[0].strip():
            raise ValueError(f"Salmon file {path} has an invalid row at line {line_number}")
        transcript = row[0]
        if transcript in seen:
            raise ValueError(f"Salmon file {path} repeats transcript {transcript!r}")
        seen.add(transcript)
        transcripts.append(transcript)
        try:
            length, effective_length, tpm, estimated_reads = map(float, row[1:])
        except ValueError:
            raise ValueError(
                f"Salmon file {path} has a non-numeric value at line {line_number}"
            ) from None
        values = (length, effective_length, tpm, estimated_reads)
        if not all(math.isfinite(value) for value in values):
            raise ValueError(f"Salmon file {path} has a non-finite value at line {line_number}")
        if length <= 0 or effective_length <= 0 or tpm < 0 or estimated_reads < 0:
            raise ValueError(
                f"Salmon file {path} has invalid length, TPM, or NumReads at line {line_number}"
            )
    if not transcripts:
        raise ValueError(f"Salmon file {path} has no transcript rows")
    return transcripts


class TximportSalmonNode(CommandNode):
    """Summarize Salmon transcript estimates to genes without relabeling them raw counts."""

    NODE_ID = "tximport_salmon"
    DISPLAY_NAME = "tximport Salmon to Genes"
    CATEGORY = "rna_seq"
    DESCRIPTION = (
        "Import Salmon quant.sf files with Bioconductor tximport and produce gene-level "
        "estimated or abundance-derived count-scale, TPM, and effective-length matrices."
    )
    SEARCH_ALIASES = [
        "tximport",
        "Salmon",
        "quant.sf",
        "transcript to gene",
        "gene abundance",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "FILE", "JSON")
    RETURN_NAMES = (
        "gene_count_scale",
        "gene_abundance_tpm",
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
    SCRIPT_PATH = Path(__file__).resolve().parents[2] / "scripts" / "tximport_salmon.R"
    AUDIT_STATUS = "upstream-executed-tiny-fixture"
    EXIT_SEMANTICS = (
        "Fails on malformed Salmon tables, inconsistent transcript sets, incomplete transcript "
        "mapping, invalid mode, non-finite upstream results, non-zero R exit, or missing outputs."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "quant_files": (
                    "COUNTS",
                    {
                        "multiple": True,
                        "description": "Ordered Salmon quant.sf files produced from one transcriptome",
                    },
                ),
                "sample_ids": (
                    "STRING",
                    {
                        "multiple": True,
                        "description": "Unique sample identifiers in the same order as quant_files",
                    },
                ),
                "tx2gene": (
                    "TSV",
                    {
                        "description": (
                            "Two-column TSV with exact header transcript_id and gene_id; every "
                            "quantified transcript must be mapped"
                        )
                    },
                ),
            },
            "optional": {
                "counts_from_abundance": (
                    "STRING",
                    {
                        "default": "no",
                        "options": list(cls.COUNTS_FROM_ABUNDANCE),
                        "description": (
                            "no retains summed estimated counts and requires tximport-aware length "
                            "offset handling downstream; scaled modes create count-scale values from TPM"
                        ),
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
            output / "gene_abundance_tpm.tsv",
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
        try:
            quant_files = [Path(path) for path in _ordered_strings(inputs.get("quant_files"), "quant_files")]
            sample_ids = _ordered_strings(inputs.get("sample_ids"), "sample_ids")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if len(quant_files) != len(sample_ids):
            return "sample_ids must contain exactly one identifier for each quant_files entry"
        if len(set(sample_ids)) != len(sample_ids):
            return "sample_ids must be unique"
        if any("\t" in sample or "\n" in sample or "\r" in sample for sample in sample_ids):
            return "sample_ids cannot contain tabs or newlines"
        for quant_file in quant_files:
            if not quant_file.is_file():
                return f"quant_files path is not a materialized file: {quant_file}"
        tx2gene = Path(str(inputs.get("tx2gene", "")))
        if not tx2gene.is_file():
            return f"tx2gene is not a materialized file: {tx2gene}"
        try:
            mapped = _mapping_transcripts(tx2gene)
            first_transcripts = _quant_transcripts(quant_files[0])
            first_set = set(first_transcripts)
            unmapped = first_set - mapped
            if unmapped:
                preview = ", ".join(sorted(unmapped)[:5])
                return f"tx2gene is missing {len(unmapped)} quantified transcript(s): {preview}"
            for quant_file in quant_files[1:]:
                transcripts = _quant_transcripts(quant_file)
                if transcripts != first_transcripts:
                    return (
                        "all Salmon files must contain the same transcripts in the same order; "
                        f"mismatch in {quant_file}"
                    )
        except (OSError, UnicodeError, ValueError) as exc:
            return str(exc)
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        quant_files = _ordered_strings(inputs["quant_files"], "quant_files")
        sample_ids = _ordered_strings(inputs["sample_ids"], "sample_ids")
        manifest = outputs[0].parent / "sample_manifest.tsv"
        with manifest.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
            writer.writerow(["sample_id", "quant_file"])
            writer.writerows(zip(sample_ids, (str(Path(path).resolve()) for path in quant_files)))
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
            str(inputs.get("counts_from_abundance", "no")),
            *outputs,
        ]

    @classmethod
    def VERIFY_OUTPUTS(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        sample_ids = _ordered_strings(inputs["sample_ids"], "sample_ids")
        expected_header = ["gene_id", *sample_ids]
        for path in outputs[:3]:
            if path.stat().st_size == 0:
                raise RuntimeError(f"tximport created an empty matrix: {path}")
            with path.open("r", encoding="utf-8", newline="") as handle:
                header = next(csv.reader(handle, delimiter="\t"), [])
                if header != expected_header:
                    raise RuntimeError(
                        f"tximport matrix header mismatch in {path}: expected {expected_header!r}"
                    )
                if next(handle, None) is None:
                    raise RuntimeError(f"tximport matrix has no gene rows: {path}")
        metadata = json.loads(outputs[4].read_text(encoding="utf-8"))
        mode = inputs.get("counts_from_abundance", "no")
        if metadata.get("counts_from_abundance") != mode:
            raise RuntimeError("tximport metadata does not match the requested counts_from_abundance")
        if metadata.get("sample_ids") != sample_ids:
            raise RuntimeError("tximport metadata sample order does not match requested sample_ids")


__all__ = ["TximportSalmonNode"]
