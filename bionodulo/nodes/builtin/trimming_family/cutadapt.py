"""Pinned Cutadapt 5.2 single-end and paired-end trimming contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import output_dir, read_paths, validate_int


class CutadaptNode(CommandNode):
    """Trim one FASTQ or an ordered paired-end FASTQ pair with Cutadapt."""

    NODE_ID = "cutadapt"
    DISPLAY_NAME = "Cutadapt"
    CATEGORY = "trimming"
    DESCRIPTION = "Remove documented 3-prime adapter sequences from single-end or paired-end FASTQ reads."
    SEARCH_ALIASES = ["cutadapt", "trim adapters", "adapter", "fastq", "paired end"]
    RETURN_TYPES = ("FASTQ_LIST",)
    RETURN_NAMES = ("trimmed_reads",)
    REQUIRED_EXECUTABLES = ["cutadapt"]
    REQUIRED_CONDA_PACKAGES = ["cutadapt"]
    PACKAGE_CONSTRAINTS = ("cutadapt==5.2",)
    PACKAGE_CONSTRAINT = PACKAGE_CONSTRAINTS[0]
    VERSION = "5.2"
    GIT_URL = "https://github.com/marcelm/cutadapt.git"
    GIT_COMMIT = "ef852629f667637439f28761499bb56126e390a1"
    DOCUMENTATION_URL = "https://cutadapt.readthedocs.io/en/v5.2/"
    CITATION_DOIS = ["10.14806/ej.17.1.200"]
    CITATION_URLS = ["https://doi.org/10.14806/ej.17.1.200"]
    UPSTREAM_CLI_SOURCE = "src/cutadapt/cli.py"
    UPSTREAM_REFERENCE = "doc/reference.rst"
    DEFAULT_ADAPTER_R1 = "AGATCGGAAGAGCACACGTCTGAACTCCAGTCA"
    DEFAULT_ADAPTER_R2 = "AGATCGGAAGAGCGTCGTGTAGGGAAAGAGTGT"
    READ1_FILENAME = "trimmed_reads.fastq.gz"
    READ2_FILENAME = "trimmed_reads_2.fastq.gz"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "One FASTQ or an ordered paired-end collection [R1, R2]"}),
                "threads": ("INT", {"default": 4, "min": 0, "max": 64, "display": "slider"}),
                "adapter_r1": ("STRING", {"default": cls.DEFAULT_ADAPTER_R1}),
            },
            "optional": {
                "adapter_r2": ("STRING", {"default": cls.DEFAULT_ADAPTER_R2}),
                "minimum_length": ("INT", {"default": 20, "min": 0}),
                "quality_cutoff": ("INT", {"default": 20, "min": 0}),
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
        except (TypeError, ValueError) as exc:
            return str(exc)
        if len(reads) not in (1, 2):
            return "Cutadapt requires exactly one single-end FASTQ or two paired FASTQs."
        adapter_r1 = inputs.get("adapter_r1", cls.DEFAULT_ADAPTER_R1)
        if not isinstance(adapter_r1, str) or not adapter_r1.strip():
            return "adapter_r1 must be a non-empty Cutadapt adapter specification."
        if len(reads) == 2:
            adapter_r2 = inputs.get("adapter_r2", cls.DEFAULT_ADAPTER_R2)
            if not isinstance(adapter_r2, str) or not adapter_r2.strip():
                return "adapter_r2 must be a non-empty Cutadapt adapter specification for paired reads."
        for key, default, minimum, maximum in (
            ("threads", 4, 0, 64),
            ("minimum_length", 20, 0, None),
            ("quality_cutoff", 20, 0, None),
        ):
            value = inputs.get(key, default)
            if value is None and key != "threads":
                continue
            result = validate_int(value, key, minimum=minimum, maximum=maximum)
            if result is not True:
                return result
        return True

    @classmethod
    def _output_paths(cls, inputs: dict[str, Any], base_output_dir: str | Path) -> list[Path]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        node_out = output_dir(base_output_dir, cls.NODE_ID)
        paths = [node_out / cls.READ1_FILENAME]
        if len(read_paths(inputs.get("reads"))) == 2:
            paths.append(node_out / cls.READ2_FILENAME)
        return paths

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        return cls._output_paths(inputs, output_dir)

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        if len(planned_paths) not in (1, 2):
            raise ValueError("Cutadapt must plan one or two trimmed FASTQs")
        return {"trimmed_reads": list(planned_paths)}

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        reads = read_paths(inputs.get("reads"))
        node_out = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["cutadapt", "-a", str(inputs.get("adapter_r1", cls.DEFAULT_ADAPTER_R1))]
        if len(reads) == 2:
            command.extend(["-A", str(inputs.get("adapter_r2", cls.DEFAULT_ADAPTER_R2))])
        command.extend(["-o", str(node_out / cls.READ1_FILENAME)])
        if len(reads) == 2:
            command.extend(["-p", str(node_out / cls.READ2_FILENAME)])
        command.extend(["-j", str(inputs.get("threads", 4))])
        if inputs.get("minimum_length", 20) is not None:
            command.extend(["-m", str(inputs.get("minimum_length", 20))])
        if inputs.get("quality_cutoff", 20) is not None:
            command.extend(["-q", str(inputs.get("quality_cutoff", 20))])
        command.extend(reads)
        return command

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        base_output_dir = kwargs.get("output_dir")
        context = kwargs.get("context")
        if base_output_dir is None and context is not None:
            base_output_dir = getattr(context, "node_dir", ".")
        if base_output_dir is None:
            base_output_dir = "."
        await super().run(**kwargs)
        paths = self.__class__._output_paths(kwargs, base_output_dir)
        return {"outputs": {"trimmed_reads": [str(path) for path in paths]}}
