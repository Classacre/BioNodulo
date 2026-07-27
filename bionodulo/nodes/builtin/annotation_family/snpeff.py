"""SnpEff 5.2 effect annotation with an explicit local genome database."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from .adapter import (
    AnnotationCommandNode,
    path_value,
    validate_int,
    validate_materialized_directory,
    validate_materialized_file,
)
from .staging import stage_file


class SnpEffNode(AnnotationCommandNode):
    """Annotate a VCF using one explicitly staged SnpEff predictor database."""

    NODE_ID = "snpeff"
    DISPLAY_NAME = "SnpEff"
    DESCRIPTION = "Annotate VCF records and predict variant effects with SnpEff 5.2."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "SnpEff",
        "variant annotation",
        "effect prediction",
        "functional effect",
    ]
    RETURN_TYPES = ("VCF", "HTML_REPORT", "TSV")
    RETURN_NAMES = ("annotated_vcf", "summary_report", "genes_report")
    OUTPUT_FILENAMES = (
        "annotated_vcf.vcf",
        "summary_report.html",
        "summary_report.genes.txt",
    )
    STDOUT_OUTPUT_INDEX = 0
    REQUIRED_EXECUTABLES = ["snpEff", "java"]
    REQUIRED_CONDA_PACKAGES = ["snpeff", "openjdk"]
    CONDA_PACKAGE_CONSTRAINTS = {"snpeff": "5.2", "openjdk": "17.*"}
    VERSION = "5.2"
    GIT_URL = "https://github.com/pcingola/SnpEff.git"
    GIT_COMMIT = "0c5e74f9b6ca6ed3db720177eb1f95b9d47d45f2"
    DOCUMENTATION_URL = "https://pcingola.github.io/SnpEff/snpeff/running/"
    SOURCE_URL = (
        "https://github.com/pcingola/SnpEff/blob/"
        "0c5e74f9b6ca6ed3db720177eb1f95b9d47d45f2/"
        "src/main/java/org/snpeff/snpEffect/commandLine/SnpEffCmdEff.java"
    )
    UPSTREAM_SOURCE = (
        "scripts/snpEff; src/main/java/org/snpeff/SnpEff.java; "
        "src/main/java/org/snpeff/snpEffect/commandLine/SnpEffCmdEff.java"
    )
    CITATION_DOIS = ["10.4161/fly.19695"]
    CITATION_URLS = ["https://doi.org/10.4161/fly.19695"]
    CITATION_TEXT = "A program for annotating and predicting the effects of SNPs."
    REQUIRED_PATH_INPUTS = ("vcf", "database")
    AUDIT_STATUS = "contract-checked-no-external-execution"
    _GENOME_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    EXIT_SEMANTICS = (
        "SnpEff returns 0 on success and calls System.exit(-1) for usage or runtime failures "
        "(observed as 255 by POSIX shells); individual record errors may still be logged during "
        "an otherwise successful run, and annotated VCF is captured directly from stdout."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (("VCF", "VCF_GZ"), {"description": "Input VCF or bgzip-compressed VCF"}),
                "genome": ("STRING", {"description": "SnpEff genome version identifier"}),
                "database": (
                    "FILE",
                    {"description": "Explicit snpEffectPredictor.bin built for the selected genome/reference"},
                ),
            },
            "optional": {
                "data_dir": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Optional SnpEff data root whose <genome> siblings are staged with the predictor"
                        )
                    },
                ),
                "memory": ("INT", {"default": 8, "min": 1, "max": 128}),
                "canonical": ("BOOLEAN", {"default": False}),
                "no_upstream": ("BOOLEAN", {"default": False}),
                "no_downstream": ("BOOLEAN", {"default": False}),
                "no_intergenic": ("BOOLEAN", {"default": False}),
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
        validation = validate_int(inputs.get("memory", 8), "memory", minimum=1, maximum=128)
        if validation is not True:
            return validation
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        if not outputs:
            raise ValueError("SnpEff requires planned outputs before staging its predictor database")

        genome = str(inputs["genome"])
        prepared_root = outputs[0].parent / "snpeff_data"
        prepared_genome = prepared_root / genome
        prepared_database = prepared_genome / "snpEffectPredictor.bin"
        if prepared_root.is_symlink():
            raise ValueError("SnpEff prepared data root must not be a symbolic link")

        for key in ("vcf", "database"):
            validation = validate_materialized_file(inputs.get(key), key)
            if validation is not True:
                raise ValueError(str(validation))

        source_database = Path(path_value(inputs["database"]))
        source_root_value = path_value(inputs.get("data_dir"))
        source_root = Path(source_root_value) if source_root_value else None
        if source_root is not None:
            validation = validate_materialized_directory(source_root, "data_dir")
            if validation is not True:
                raise ValueError(str(validation))

        prepared_root_resolved = prepared_root.resolve()
        prepared_database_resolved = prepared_database.resolve()
        source_database_resolved = source_database.resolve()
        database_is_prepared = source_database_resolved == prepared_database_resolved
        if source_database_resolved.is_relative_to(prepared_root_resolved) and not database_is_prepared:
            raise ValueError("Input 'database' must not be inside the SnpEff prepared data root")

        source_root_resolved = source_root.resolve() if source_root is not None else None
        if (
            source_root_resolved is not None
            and source_root_resolved.is_relative_to(prepared_root_resolved)
            and source_root_resolved != prepared_root_resolved
        ):
            raise ValueError("Input 'data_dir' must not be nested inside the SnpEff prepared data root")
        if database_is_prepared and source_root_resolved not in (None, prepared_root_resolved):
            raise ValueError("An already prepared SnpEff database cannot be combined with a different data_dir")

        source_genome = source_root / genome if source_root is not None else None
        if source_genome is not None:
            validation = validate_materialized_directory(source_genome, f"data_dir/{genome}")
            if validation is not True:
                raise ValueError(str(validation))
            try:
                symlink = (
                    source_genome
                    if source_genome.is_symlink()
                    else next(
                        (entry for entry in source_genome.rglob("*") if entry.is_symlink()),
                        None,
                    )
                )
            except OSError as exc:
                raise ValueError(f"Input 'data_dir/{genome}' could not be inspected: {exc}") from exc
            if symlink is not None:
                raise ValueError(f"Input 'data_dir/{genome}' must not contain symbolic links: {symlink}")

        if not database_is_prepared and source_root_resolved != prepared_root_resolved:
            if prepared_root.is_symlink() or prepared_root.is_file():
                prepared_root.unlink()
            elif prepared_root.exists():
                shutil.rmtree(prepared_root)
            if source_genome is not None and source_genome.is_dir():
                shutil.copytree(
                    source_genome,
                    prepared_genome,
                    copy_function=lambda source, destination: str(stage_file(source, Path(destination))),
                )
            else:
                prepared_genome.mkdir(parents=True, exist_ok=True)

        staged_database = stage_file(
            source_database,
            prepared_database,
        )
        # SnpEff resolves a genome through its CONFIG. Without an entry the run
        # dies with "Property: '<genome>.genome' not found", because the bundled
        # snpEff.config only knows SnpEff's own published genomes -- which is
        # every custom or workflow-built database. Declare this one explicitly.
        config_path = prepared_root / "snpEff.config"
        config_path.write_text(
            f"data.dir = {prepared_root}\n{genome}.genome : {genome}\n",
            encoding="utf-8",
        )
        source_vcf = Path(path_value(inputs["vcf"]))
        staged_vcf_name = "variants.vcf.gz" if source_vcf.name.lower().endswith(".vcf.gz") else "variants.vcf"
        staged_vcf = stage_file(source_vcf, outputs[0].parent / "inputs" / staged_vcf_name)
        inputs["config"] = str(config_path)
        inputs["data_dir"] = str(prepared_root)
        inputs["database"] = str(staged_database)
        inputs["vcf"] = str(staged_vcf)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", inputs.get("output_dir", "."))))
        data_dir = path_value(inputs.get("data_dir")) or str(output / "snpeff_data")
        config = path_value(inputs.get("config")) or str(Path(data_dir) / "snpEff.config")
        command = [
            "snpEff",
            f"-Xmx{inputs.get('memory', 8)}g",
            "-noLog",
            "-noDownload",
            "-v",
            "-c",
            config,
            "-dataDir",
            data_dir,
            "-stats",
            str(output / cls.OUTPUT_FILENAMES[1]),
        ]
        if inputs.get("canonical", False):
            command.append("-canon")
        if inputs.get("no_upstream", False):
            command.append("-no-upstream")
        if inputs.get("no_downstream", False):
            command.append("-no-downstream")
        if inputs.get("no_intergenic", False):
            command.append("-no-intergenic")
        command.extend([str(inputs["genome"]), path_value(inputs["vcf"])])
        return command
