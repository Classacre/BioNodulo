"""Ensembl Variant Effect Predictor 113.4 using a staged offline cache."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapter import (
    AnnotationCommandNode,
    path_value,
    validate_choice,
    validate_int,
    validate_materialized_directory,
    validate_materialized_file,
)
from .staging import stage_file


class VEPNode(AnnotationCommandNode):
    """Annotate variants with VEP using one explicit full cache directory."""

    NODE_ID = "vep"
    DISPLAY_NAME = "VEP"
    DESCRIPTION = "Ensembl Variant Effect Predictor 113.4 with an explicit offline cache."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "VEP",
        "variant effect predictor",
        "Ensembl",
        "variant annotation",
        "ClinVar",
    ]
    RETURN_TYPES = ("FILE", "HTML_REPORT")
    RETURN_NAMES = ("annotated_vcf", "vep_report")
    REQUIRED_EXECUTABLES = ["vep"]
    REQUIRED_CONDA_PACKAGES = ["ensembl-vep"]
    CONDA_PACKAGE_CONSTRAINTS = {"ensembl-vep": "113.4"}
    VERSION = "113.4"
    GIT_URL = "https://github.com/Ensembl/ensembl-vep.git"
    GIT_COMMIT = "a6786e4357f442a81624f58d9e79f343909d717f"
    DOCUMENTATION_URL = "https://www.ensembl.org/info/docs/tools/vep/script/vep_options.html"
    SOURCE_URL = (
        "https://github.com/Ensembl/ensembl-vep/blob/"
        "a6786e4357f442a81624f58d9e79f343909d717f/modules/Bio/EnsEMBL/VEP/Config.pm"
    )
    UPSTREAM_SOURCE = (
        "modules/Bio/EnsEMBL/VEP/Config.pm; modules/Bio/EnsEMBL/VEP/CacheDir.pm; "
        "modules/Bio/EnsEMBL/VEP/Runner.pm; "
        "modules/Bio/EnsEMBL/VEP/AnnotationSource/Cache/BaseSerialized.pm"
    )
    CITATION_DOIS = ["10.1186/s13059-016-0974-4"]
    CITATION_URLS = ["https://doi.org/10.1186/s13059-016-0974-4"]
    CITATION_TEXT = "The Ensembl Variant Effect Predictor."
    REQUIRED_PATH_INPUTS = ("vcf", "cache_dir")
    OUTPUT_FORMATS = ("vcf", "tab")
    PREDICTION_FORMATS = ("b", "s", "p")
    CACHE_VERSION = 113
    CACHE_SOURCE = "ensembl"
    AUDIT_STATUS = "contract-checked-no-external-execution"
    _IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    _TRANSCRIPT_SHARD = re.compile(r"^[0-9]+-[0-9]+[.](?:gz|sereal)$")
    EXIT_SEMANTICS = (
        "VEP exits non-zero for an absent cache, cache/assembly mismatch, invalid option combination, "
        "or unreadable custom annotation; BioNodulo also requires both output and stats files. "
        "VEP's --everything remains cache-dependent and silently omits unavailable annotations, "
        "including HGVS when an offline cache has no auto-detected FASTA."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "vcf": (("VCF", "VCF_GZ"), {"description": "Input VCF"}),
                "cache_dir": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Exact standard-Ensembl version/assembly VEP cache leaf, for example "
                            "homo_sapiens/113_GRCh38; RefSeq and merged cache modes are not exposed"
                        )
                    },
                ),
            },
            "optional": {
                "assembly": ("STRING", {"default": "GRCh38"}),
                "species": ("STRING", {"default": "homo_sapiens"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
                "everything": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": (
                            "Pass VEP --everything; individual fields remain conditional on cache "
                            "capabilities and an auto-detected cache FASTA"
                        ),
                    },
                ),
                "symbol": ("BOOLEAN", {"default": False}),
                "af": ("BOOLEAN", {"default": False}),
                "max_af": ("BOOLEAN", {"default": False}),
                "sift": ("STRING", {"default": "", "options": ["", *cls.PREDICTION_FORMATS]}),
                "polyphen": (
                    "STRING",
                    {"default": "", "options": ["", *cls.PREDICTION_FORMATS]},
                ),
                "clinvar": ("VCF_GZ", {"description": "Sorted, bgzip-compressed ClinVar VCF"}),
                "clinvar_index": (
                    "VCF_INDEX",
                    {"description": "Exact <clinvar>.tbi index required with a ClinVar VCF"},
                ),
                "output_format": ("STRING", {"default": "vcf", "options": list(cls.OUTPUT_FORMATS)}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("assembly", "species"):
            value = str(inputs.get(key, "GRCh38" if key == "assembly" else "homo_sapiens"))
            if not cls._IDENTIFIER.fullmatch(value):
                return (
                    f"Input '{key}' must be an unpadded identifier containing only letters, "
                    "digits, dots, underscores, or hyphens"
                )
        validation = validate_int(inputs.get("threads", 1), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        validation = validate_choice(inputs.get("output_format", "vcf"), "output_format", cls.OUTPUT_FORMATS)
        if validation is not True:
            return validation
        for key in ("sift", "polyphen"):
            value = inputs.get(key, "")
            if value not in (None, ""):
                validation = validate_choice(value, key, cls.PREDICTION_FORMATS)
                if validation is not True:
                    return validation

        assembly = str(inputs.get("assembly", "GRCh38"))
        cache_dir = Path(path_value(inputs["cache_dir"]))
        expected_leaf = f"{cls.CACHE_VERSION}_{assembly}"
        if cache_dir.name != expected_leaf:
            return f"Input 'cache_dir' must be the exact VEP cache leaf named '{expected_leaf}', not a cache root"
        species = str(inputs.get("species", "homo_sapiens"))
        if cache_dir.parent.name in {f"{species}_refseq", f"{species}_merged"}:
            return (
                "Input 'cache_dir' uses a RefSeq or merged cache, but this node exposes only "
                "VEP's standard Ensembl cache mode"
            )

        clinvar = path_value(inputs.get("clinvar"))
        clinvar_index = path_value(inputs.get("clinvar_index"))
        if clinvar:
            if not clinvar.endswith(".vcf.gz"):
                return "Input 'clinvar' must use the .vcf.gz filename suffix"
            if Path(clinvar_index).name != f"{Path(clinvar).name}.tbi":
                return "Input 'clinvar_index' must be named exactly '<clinvar>.tbi'"
            return True
        if clinvar_index:
            return "Input 'clinvar_index' requires 'clinvar'"
        return True

    @classmethod
    def _validate_materialized_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        validation = validate_materialized_file(inputs.get("vcf"), "vcf")
        if validation is not True:
            return validation
        validation = validate_materialized_directory(inputs.get("cache_dir"), "cache_dir")
        if validation is not True:
            return validation

        assembly = str(inputs.get("assembly", "GRCh38"))
        species = str(inputs.get("species", "homo_sapiens"))
        cache_dir = Path(path_value(inputs["cache_dir"]))
        info_path = cache_dir / "info.txt"
        validation = validate_materialized_file(info_path, "cache_dir/info.txt")
        if validation is not True:
            return validation
        try:
            info: dict[str, str] = {}
            for line in info_path.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#"):
                    continue
                fields = line.split("\t", 1)
                if len(fields) == 2 and fields[1] != "-":
                    info[fields[0]] = fields[1]
        except (OSError, UnicodeError) as exc:
            return f"Input 'cache_dir/info.txt' must be readable UTF-8 text: {exc}"
        if info.get("assembly") not in (None, assembly):
            return (
                "Input 'cache_dir/info.txt' assembly "
                f"'{info['assembly']}' does not match requested assembly '{assembly}'"
            )
        if info.get("species") not in (None, species):
            return (
                f"Input 'cache_dir/info.txt' species '{info['species']}' does not match requested species '{species}'"
            )

        serialiser = info.get("serialiser_type", "storable").lower()
        if serialiser not in {"storable", "sereal"}:
            return f"Input 'cache_dir/info.txt' has unsupported serialiser_type '{serialiser}'"
        shard_suffix = "sereal" if serialiser == "sereal" else "gz"
        try:
            matching_shards = (
                shard
                for region in cache_dir.iterdir()
                if not region.name.startswith(".") and region.is_dir()
                for shard in region.iterdir()
                if cls._TRANSCRIPT_SHARD.fullmatch(shard.name) and shard.suffix == f".{shard_suffix}"
            )
            has_readable_shard = any(
                validate_materialized_file(shard, "cache transcript shard") is True for shard in matching_shards
            )
        except OSError as exc:
            return f"Input 'cache_dir' could not be inspected: {exc}"
        if not has_readable_shard:
            return (
                "Input 'cache_dir' must contain a readable, non-empty sequence-region "
                f"transcript shard '<start>-<end>.{shard_suffix}'"
            )

        has_variation = any(key.startswith("variation_col") for key in info)
        if (inputs.get("af", False) or inputs.get("max_af", False)) and not has_variation:
            return "Input 'cache_dir' does not record variation columns required for AF annotations"
        for key in ("sift", "polyphen"):
            if inputs.get(key) not in (None, "") and not info.get(key):
                return f"Input 'cache_dir' does not record the requested {key.upper()} capability"

        clinvar = path_value(inputs.get("clinvar"))
        if clinvar:
            validation = validate_materialized_file(clinvar, "clinvar")
            if validation is not True:
                return validation
            validation = validate_materialized_file(inputs.get("clinvar_index"), "clinvar_index")
            if validation is not True:
                return validation
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        validation = cls._validate_materialized_inputs(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        if not inputs.get("clinvar"):
            return
        if not outputs:
            raise ValueError("VEP requires planned outputs before staging ClinVar inputs")
        staged_dir = outputs[0].parent / "custom_annotations"
        clinvar = stage_file(path_value(inputs["clinvar"]), staged_dir / "clinvar.vcf.gz")
        clinvar_index = stage_file(
            path_value(inputs["clinvar_index"]),
            staged_dir / "clinvar.vcf.gz.tbi",
        )
        inputs["clinvar"] = str(clinvar)
        inputs["clinvar_index"] = str(clinvar_index)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        output_format = str(inputs.get("output_format", "vcf"))
        validation = validate_choice(output_format, "output_format", cls.OUTPUT_FORMATS)
        if validation is not True:
            raise ValueError(str(validation))
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / f"annotated_vcf.{output_format}", node_dir / "vep_report.html"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        output = Path(path_value(inputs.get("output", inputs.get("output_dir", "."))))
        output_format = str(inputs.get("output_format", "vcf"))
        command = [
            "vep",
            "--input_file",
            path_value(inputs["vcf"]),
            "--output_file",
            str(output / f"annotated_vcf.{output_format}"),
            "--format",
            "vcf",
            f"--{output_format}",
            "--fork",
            str(inputs.get("threads", 1)),
            "--species",
            str(inputs.get("species", "homo_sapiens")),
            "--assembly",
            str(inputs.get("assembly", "GRCh38")),
            "--offline",
            "--full_cache_dir",
            path_value(inputs["cache_dir"]),
            "--force_overwrite",
        ]
        if inputs.get("everything", False):
            command.append("--everything")
        else:
            if inputs.get("symbol", False):
                command.append("--symbol")
            if inputs.get("af", False):
                command.append("--af")
            if inputs.get("max_af", False):
                command.append("--max_af")
            for key, flag in (("sift", "--sift"), ("polyphen", "--polyphen")):
                value = inputs.get(key, "")
                if value not in (None, ""):
                    command.extend([flag, str(value)])
        if inputs.get("clinvar"):
            command.extend(
                [
                    "--custom",
                    (f"file={path_value(inputs['clinvar'])},short_name=ClinVar,format=vcf,type=exact,fields=CLNSIG"),
                ]
            )
        command.extend(["--stats_file", str(output / "vep_report.html")])
        return command
