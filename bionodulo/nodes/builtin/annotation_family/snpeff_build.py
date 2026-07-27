"""SnpEff 5.2 custom database construction from a reference FASTA + annotation."""

from __future__ import annotations

import gzip
import re
import shutil
from pathlib import Path
from typing import Any

from .adapter import (
    AnnotationCommandNode,
    path_value,
    validate_int,
    validate_materialized_file,
)
from .staging import stage_file


def _decompress_to(source: Path, destination: Path) -> Path:
    """Materialize `source` at `destination`, transparently gunzipping .gz input.

    SnpEff's build reads `sequences.fa`/`genes.<fmt>` as plain text, so a
    gzipped reference (the common form on NCBI/Ensembl FTP) must be expanded
    rather than hard-linked under a non-.gz name.
    """
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.name.lower().endswith(".gz"):
        with gzip.open(source, "rb") as handle, destination.open("wb") as out:
            shutil.copyfileobj(handle, out)
        return destination
    return stage_file(source, destination)


class SnpEffBuildNode(AnnotationCommandNode):
    """Build a SnpEff predictor database for an arbitrary reference genome.

    Exists so a workflow can annotate against its OWN reference without
    depending on SnpEff's published database registry: `snpeff` runs with
    `-noDownload` by design, so a genome that is not pre-published (or whose
    registry identifier differs across releases) is otherwise unusable.
    """

    NODE_ID = "snpeff_build"
    DISPLAY_NAME = "SnpEff Build Database"
    DESCRIPTION = (
        "Build a custom SnpEff 5.2 predictor database from a reference FASTA and its annotation."
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "SnpEff",
        "build database",
        "custom genome",
        "snpEffectPredictor",
        "variant annotation",
    ]
    RETURN_TYPES = ("FILE", "DIRECTORY", "STRING")
    RETURN_NAMES = ("predictor_database", "data_dir", "genome")
    OUTPUT_FILENAMES = ("snpEffectPredictor.bin",)
    REQUIRED_EXECUTABLES = ["snpEff", "java"]
    REQUIRED_CONDA_PACKAGES = ["snpeff", "openjdk"]
    CONDA_PACKAGE_CONSTRAINTS = {"snpeff": "5.2", "openjdk": "17.*"}
    VERSION = "5.2"
    GIT_URL = "https://github.com/pcingola/SnpEff.git"
    GIT_COMMIT = "0c5e74f9b6ca6ed3db720177eb1f95b9d47d45f2"
    DOCUMENTATION_URL = "https://pcingola.github.io/SnpEff/snpeff/build_db/"
    SOURCE_URL = (
        "https://github.com/pcingola/SnpEff/blob/"
        "0c5e74f9b6ca6ed3db720177eb1f95b9d47d45f2/"
        "src/main/java/org/snpeff/snpEffect/commandLine/SnpEffCmdBuild.java"
    )
    UPSTREAM_SOURCE = (
        "scripts/snpEff; src/main/java/org/snpeff/SnpEff.java; "
        "src/main/java/org/snpeff/snpEffect/commandLine/SnpEffCmdBuild.java"
    )
    CITATION_DOIS = ["10.4161/fly.19695"]
    CITATION_URLS = ["https://doi.org/10.4161/fly.19695"]
    CITATION_TEXT = "A program for annotating and predicting the effects of SNPs."
    REQUIRED_PATH_INPUTS = ("reference", "annotation")
    AUDIT_STATUS = "contract-checked-no-external-execution"
    _GENOME_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    _ANNOTATION_FORMATS = {"gff3": "genes.gff", "gtf22": "genes.gtf", "genbank": "genes.gbk"}
    EXIT_SEMANTICS = (
        "SnpEff build returns 0 on success and calls System.exit(-1) on a malformed or "
        "inconsistent reference/annotation pair (observed as 255 by POSIX shells); the built "
        "predictor is written into <dataDir>/<genome>/snpEffectPredictor.bin."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reference": (
                    ("FASTA", "FILE"),
                    {"description": "Reference genome FASTA (plain or gzipped)"},
                ),
                "annotation": (
                    ("GFF", "GTF", "FILE"),
                    {"description": "Gene annotation for the SAME reference (plain or gzipped)"},
                ),
                "genome": (
                    "STRING",
                    {"description": "Genome identifier to register this database under"},
                ),
            },
            "optional": {
                "annotation_format": (
                    ("gff3", "gtf22", "genbank"),
                    {"default": "gff3", "description": "Annotation format passed to snpEff build"},
                ),
                "memory": ("INT", {"default": 8, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        genome = str(inputs.get("genome", ""))
        if not cls._GENOME_ID.fullmatch(genome):
            return (
                "Input 'genome' must be an unpadded SnpEff identifier containing only "
                "letters, digits, dots, underscores, or hyphens"
            )
        annotation_format = str(inputs.get("annotation_format", "gff3"))
        if annotation_format not in cls._ANNOTATION_FORMATS:
            return (
                "Input 'annotation_format' must be one of: "
                + ", ".join(sorted(cls._ANNOTATION_FORMATS))
            )
        return validate_int(inputs.get("memory", 8), "memory", minimum=1, maximum=128)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        # snpEff build writes the predictor into <dataDir>/<genome>/, so the
        # planned output path must be that exact location rather than the node
        # root -- otherwise the tool succeeds and the declared output is missing.
        node_dir = Path(output_dir) / cls.NODE_ID
        genome = str(inputs.get("genome", "genome"))
        genome_dir = node_dir / "snpeff_data" / genome
        genome_dir.mkdir(parents=True, exist_ok=True)
        return [genome_dir / cls.OUTPUT_FILENAMES[0]]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if not outputs:
            raise ValueError("SnpEff build requires planned outputs before staging its inputs")

        for key in ("reference", "annotation"):
            validation = validate_materialized_file(inputs.get(key), key)
            if validation is not True:
                raise ValueError(str(validation))

        annotation_format = str(inputs.get("annotation_format", "gff3"))
        genome_dir = outputs[0].parent
        if genome_dir.is_symlink():
            raise ValueError("SnpEff build genome directory must not be a symbolic link")
        genome_dir.mkdir(parents=True, exist_ok=True)

        _decompress_to(Path(path_value(inputs["reference"])), genome_dir / "sequences.fa")
        _decompress_to(
            Path(path_value(inputs["annotation"])),
            genome_dir / cls._ANNOTATION_FORMATS[annotation_format],
        )
        inputs["data_dir"] = str(genome_dir.parent)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", inputs.get("output_dir", "."))))
        data_dir = path_value(inputs.get("data_dir")) or str(output / "snpeff_data")
        annotation_format = str(inputs.get("annotation_format", "gff3"))
        return [
            "snpEff",
            "build",
            f"-Xmx{inputs.get('memory', 8)}g",
            f"-{annotation_format}",
            "-noLog",
            "-noCheckCds",
            "-noCheckProtein",
            "-v",
            "-dataDir",
            data_dir,
            str(inputs["genome"]),
        ]
