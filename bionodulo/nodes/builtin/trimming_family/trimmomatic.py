"""Pinned Trimmomatic 0.40 paired-end trimming contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import output_dir as node_output_dir
from .adapter import read_paths, validate_int


class TrimmomaticNode(CommandNode):
    """Trim an ordered paired-end FASTQ pair with Trimmomatic PE."""

    NODE_ID = "trimmomatic"
    DISPLAY_NAME = "Trimmomatic"
    CATEGORY = "trimming"
    DESCRIPTION = "Trim Illumina paired-end FASTQ reads with Trimmomatic PE."
    SEARCH_ALIASES = ["trimmomatic", "trim", "adapter removal", "illumina", "paired end"]
    RETURN_TYPES = ("FASTQ", "FASTQ", "FASTQ", "FASTQ")
    RETURN_NAMES = ("R1_paired", "R1_unpaired", "R2_paired", "R2_unpaired")
    REQUIRED_EXECUTABLES = ["trimmomatic", "java"]
    REQUIRED_CONDA_PACKAGES = ["trimmomatic", "openjdk"]
    PACKAGE_CONSTRAINTS = ("trimmomatic==0.40",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "0.40"
    GIT_URL = "https://github.com/usadellab/Trimmomatic.git"
    GIT_COMMIT = "7c9e862f7a050fdde034b63363ed4a99bf70d6b3"
    DOCUMENTATION_URL = "https://github.com/usadellab/Trimmomatic/tree/v0.40"
    SOURCE_URL = (
        "https://github.com/usadellab/Trimmomatic/blob/"
        f"{GIT_COMMIT}/README.md"
    )
    CITATION_DOIS = ["10.1093/bioinformatics/btu170"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btu170"]
    UPSTREAM_README = "README.md"
    UPSTREAM_CLI_SOURCE = "src/main/java/org/usadellab/trimmomatic/TrimmomaticPE.java"
    UPSTREAM_MAIN_SOURCE = "src/main/java/org/usadellab/trimmomatic/Trimmomatic.java"
    UPSTREAM_SOURCE_PATHS = (UPSTREAM_README, UPSTREAM_CLI_SOURCE, UPSTREAM_MAIN_SOURCE)
    UPSTREAM_SOURCE_URLS = (
        SOURCE_URL,
        "https://github.com/usadellab/Trimmomatic/blob/"
        f"{GIT_COMMIT}/{UPSTREAM_CLI_SOURCE}",
        "https://github.com/usadellab/Trimmomatic/blob/"
        f"{GIT_COMMIT}/{UPSTREAM_MAIN_SOURCE}",
    )
    PRESET_SOURCE = "README.md paired-end reference command"
    PRESET_STEPS = (
        "ILLUMINACLIP:{adapters}:2:30:10",
        "LEADING:3",
        "TRAILING:3",
        "SLIDINGWINDOW:4:15",
        "MINLEN:36",
    )
    PRESET_SEMANTICS = (
        "The exposed trimming steps and values are the official README paired-end preset; "
        "Trimmomatic itself has no implicit trimming-step defaults."
    )
    AUDIT_STATUS = "contract-checked-no-external-execution"
    EXIT_SEMANTICS = (
        "Trimmomatic returns 0 after successful completion and exits 1 for usage, "
        "quality-detection, template, or uncaught processing failures."
    )
    OUTPUT_FILENAMES = (
        "R1_paired.fastq.gz",
        "R1_unpaired.fastq.gz",
        "R2_paired.fastq.gz",
        "R2_unpaired.fastq.gz",
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "Exactly two ordered paired-end FASTQs [R1, R2]"}),
                "threads": ("INT", {"default": 0, "min": 0, "max": 64, "display": "slider"}),
                "adapters": ("FILE", {"description": "Adapter FASTA passed to ILLUMINACLIP"}),
            },
            "optional": {
                "leading": ("INT", {"default": 3, "min": 0}),
                "trailing": ("INT", {"default": 3, "min": 0}),
                "quality": ("INT", {"default": 15, "min": 0}),
                "minlen": ("INT", {"default": 36, "min": 0}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        try:
            reads = read_paths(inputs.get("reads"))
            adapters = read_paths(inputs.get("adapters"), key="adapters")
        except (TypeError, ValueError) as exc:
            return str(exc)
        if len(reads) != 2:
            return "Trimmomatic PE requires exactly two reads."
        if len(adapters) != 1:
            return "adapters must be exactly one FASTA path."
        for key, default, minimum, maximum in (
            ("threads", 0, 0, 64),
            ("leading", 3, 0, None),
            ("trailing", 3, 0, None),
            ("quality", 15, 0, None),
            ("minlen", 36, 0, None),
        ):
            result = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if result is not True:
                return result
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        node_out = node_output_dir(output_dir, cls.NODE_ID)
        return [node_out / name for name in cls.OUTPUT_FILENAMES]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        if len(planned_paths) != 4:
            raise ValueError("Trimmomatic PE must plan four FASTQ outputs")
        return dict(zip(cls.RETURN_NAMES, planned_paths, strict=True))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        reads = read_paths(inputs.get("reads"))
        adapters = read_paths(inputs.get("adapters"), key="adapters")[0]
        node_out = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        outputs = [node_out / name for name in cls.OUTPUT_FILENAMES]
        return [
            "trimmomatic",
            "PE",
            "-threads",
            str(inputs.get("threads", 0)),
            reads[0],
            reads[1],
            *(str(path) for path in outputs),
            f"ILLUMINACLIP:{adapters}:2:30:10",
            f"LEADING:{inputs.get('leading', 3)}",
            f"TRAILING:{inputs.get('trailing', 3)}",
            f"SLIDINGWINDOW:4:{inputs.get('quality', 15)}",
            f"MINLEN:{inputs.get('minlen', 36)}",
        ]

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        base_output_dir = kwargs.get("output_dir")
        context = kwargs.get("context")
        if base_output_dir is None and context is not None:
            base_output_dir = getattr(context, "node_dir", ".")
        if base_output_dir is None:
            base_output_dir = "."
        await super().run(**kwargs)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS(self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir))
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
