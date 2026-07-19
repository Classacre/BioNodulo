"""Kraken2 2.17.1 database preparation and build operations."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from .adapter import (
    MetagenomicsCommandNode,
    add_flag,
    path_value,
    validate_choice,
    validate_int,
    validate_number,
)


OPERATIONS = (
    "download-taxonomy",
    "download-library",
    "add-to-library",
    "build",
    "clean",
    "standard",
    "special",
)
LIBRARIES = (
    "archaea",
    "bacteria",
    "plasmid",
    "viral",
    "human",
    "fungi",
    "plant",
    "protozoa",
    "nr",
    "nt",
    "UniVec",
    "UniVec_Core",
)
SPECIAL_DATABASES = ("greengenes", "silva", "rdp")
FINAL_DATABASE_FILES = ("hash.k2d", "opts.k2d", "taxo.k2d")


class Kraken2BuildNode(MetagenomicsCommandNode):
    """Apply one documented Kraken2 database operation to an immutable DAG copy."""

    NODE_ID = "kraken2_build"
    DISPLAY_NAME = "Kraken2 Build DB"
    DESCRIPTION = "Prepare or build a Kraken2 2.17.1 database directory."
    SEARCH_ALIASES = ["BioNodulo builtin", "Kraken2", "kraken2-build", "database", "taxonomy"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("database",)
    REQUIRED_EXECUTABLES = ["kraken2-build"]
    REQUIRED_CONDA_PACKAGES = ["kraken2"]
    VERSION = "2.17.1"
    BIOCONDA_VERSION = VERSION
    BIOCONDA_CONSTRAINT = "kraken2=2.17.1"
    GIT_URL = "https://github.com/DerrickWood/kraken2.git"
    GIT_COMMIT = "5e2aa928d00b96d61f204d517437637863da1d8c"
    UPSTREAM_TAG = "v2.17.1"
    DOCUMENTATION_URL = (
        "https://github.com/DerrickWood/kraken2/blob/"
        "5e2aa928d00b96d61f204d517437637863da1d8c/docs/MANUAL.markdown"
    )
    UPSTREAM_SOURCE = "scripts/kraken2-build; docs/MANUAL.markdown"
    NETWORK_SEMANTICS = (
        "download-taxonomy, download-library, standard, and special access NCBI or upstream databases; "
        "use_ftp changes the documented download transport."
    )
    EXIT_SEMANTICS = (
        "kraken2-build non-zero exit is fatal; build, standard, and special additionally require "
        "hash.k2d, opts.k2d, and taxo.k2d."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "operation": ("STRING", {"default": "build", "options": list(OPERATIONS)}),
            },
            "optional": {
                "database": (
                    "DIRECTORY",
                    {"default": "", "description": "Prior Kraken2 work directory copied before this operation"},
                ),
                "library": ("STRING", {"default": "bacteria", "options": list(LIBRARIES)}),
                "special_database": (
                    "STRING",
                    {"default": "silva", "options": list(SPECIAL_DATABASES)},
                ),
                "reference_fasta": ("FILE", {"default": "", "description": "One FASTA for --add-to-library"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 256}),
                "kmer_len": ("INT", {"default": 35, "min": 1}),
                "minimizer_len": ("INT", {"default": 31, "min": 1}),
                "minimizer_spaces": ("INT", {"default": 7, "min": 0}),
                "protein": ("BOOLEAN", {"default": False}),
                "no_masking": ("BOOLEAN", {"default": False}),
                "max_db_size": ("INT", {"default": 0, "min": 0}),
                "use_ftp": ("BOOLEAN", {"default": False}),
                "skip_maps": ("BOOLEAN", {"default": False}),
                "load_factor": ("FLOAT", {"default": 0.7, "min": 0.0, "max": 1.0}),
                "fast_build": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        return [node_dir / "database"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        operation = str(inputs.get("operation", "build"))
        validation = validate_choice(operation, "operation", OPERATIONS)
        if validation is not True:
            return validation
        if operation == "download-library":
            validation = validate_choice(inputs.get("library", "bacteria"), "library", LIBRARIES)
            if validation is not True:
                return validation
        if operation == "special":
            validation = validate_choice(inputs.get("special_database", "silva"), "special_database", SPECIAL_DATABASES)
            if validation is not True:
                return validation
        if operation == "add-to-library" and not path_value(inputs.get("reference_fasta")):
            return "Input 'reference_fasta' is required for operation='add-to-library'"
        if operation in {"build", "clean"} and not path_value(inputs.get("database")):
            return f"Input 'database' is required for operation='{operation}'"
        for key, default, minimum in (
            ("threads", 1, 1),
            ("kmer_len", 35, 1),
            ("minimizer_len", 31, 1),
            ("minimizer_spaces", 7, 0),
            ("max_db_size", 0, 0),
        ):
            validation = validate_int(inputs.get(key, default), key, minimum=minimum)
            if validation is not True:
                return validation
        if inputs.get("minimizer_len", 31) > inputs.get("kmer_len", 35):
            return "Input 'minimizer_len' must not exceed 'kmer_len'"
        return validate_number(inputs.get("load_factor", 0.7), "load_factor", minimum=0.0, maximum=1.0)

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        destination = outputs[0]
        source_text = path_value(inputs.get("database"))
        if source_text:
            source = Path(source_text)
            if source.resolve() != destination.resolve():
                shutil.copytree(source, destination, dirs_exist_ok=True)
        destination.mkdir(parents=True, exist_ok=True)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        output = Path(str(inputs.get("output", inputs.get("output_dir", ".")))) / "database"
        operation = str(inputs.get("operation", "build"))
        command = ["kraken2-build"]
        if operation == "download-taxonomy":
            command.append("--download-taxonomy")
        elif operation == "download-library":
            command.extend(["--download-library", str(inputs.get("library", "bacteria"))])
        elif operation == "add-to-library":
            command.extend(["--add-to-library", path_value(inputs.get("reference_fasta"))])
        elif operation == "build":
            command.append("--build")
        elif operation == "clean":
            command.append("--clean")
        elif operation == "standard":
            command.append("--standard")
        else:
            command.extend(["--special", str(inputs.get("special_database", "silva"))])
        command.extend(["--db", str(output), "--threads", str(inputs.get("threads", 1))])
        if operation in {"build", "standard", "special"}:
            command.extend(
                [
                    "--kmer-len",
                    str(inputs.get("kmer_len", 35)),
                    "--minimizer-len",
                    str(inputs.get("minimizer_len", 31)),
                    "--minimizer-spaces",
                    str(inputs.get("minimizer_spaces", 7)),
                    "--load-factor",
                    str(inputs.get("load_factor", 0.7)),
                ]
            )
            max_db_size = int(inputs.get("max_db_size", 0) or 0)
            if max_db_size:
                command.extend(["--max-db-size", str(max_db_size)])
            add_flag(command, "--fast-build", inputs.get("fast_build"))
        add_flag(command, "--protein", inputs.get("protein"))
        add_flag(command, "--no-masking", inputs.get("no_masking"))
        add_flag(command, "--use-ftp", inputs.get("use_ftp"))
        if operation == "download-taxonomy":
            add_flag(command, "--skip-maps", inputs.get("skip_maps"))
        return command

    async def run(self, **kwargs: Any) -> tuple[str]:
        operation = str(kwargs.get("operation", "build"))
        outputs = await super().run(**kwargs)
        database = Path(outputs[0])
        if operation in {"build", "standard", "special"}:
            missing = [name for name in FINAL_DATABASE_FILES if not (database / name).is_file()]
            if missing:
                raise RuntimeError(f"Kraken2 build did not create required database files: {', '.join(missing)}")
        return outputs
