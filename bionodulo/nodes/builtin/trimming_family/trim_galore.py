"""Pinned Trim Galore 0.6.10 read-trimming contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import output_dir, read_paths, validate_int


class TrimGaloreNode(CommandNode):
    """Trim one FASTQ or an ordered pair with optional RRBS and FastQC modes."""

    NODE_ID = "trim_galore"
    DISPLAY_NAME = "Trim Galore"
    CATEGORY = "trimming"
    DESCRIPTION = "Adapter and quality trimming for FASTQ reads with bisulfite-aware Trim Galore modes."
    SEARCH_ALIASES = ["trim galore", "trim_galore", "bisulfite", "rrbs", "cutadapt", "adapter", "quality trim"]
    RETURN_TYPES = ("FASTQ_LIST", "FILE_LIST", "FILE_LIST")
    RETURN_NAMES = ("trimmed_reads", "fastqc_report", "trimming_reports")
    REQUIRED_EXECUTABLES = ["trim_galore", "cutadapt", "fastqc"]
    REQUIRED_CONDA_PACKAGES = ["trim-galore", "cutadapt", "fastqc"]
    PACKAGE_CONSTRAINTS = ("trim-galore==0.6.10", "cutadapt==5.2", "fastqc==0.12.1")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    VERSION = "0.6.10"
    GIT_URL = "https://github.com/FelixKrueger/TrimGalore.git"
    GIT_COMMIT = "4edff97d22f3837d42a29e4afbfaeb6e07ffb11b"
    DOCUMENTATION_URL = "https://github.com/FelixKrueger/TrimGalore/tree/0.6.10"
    UPSTREAM_CLI_SOURCE = "trim_galore"
    UPSTREAM_USER_GUIDE = "Docs/Trim_Galore_User_Guide.md"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ_LIST", {"description": "One FASTQ or an ordered paired-end collection [R1, R2]"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 8, "display": "slider"}),
            },
            "optional": {
                "paired": ("BOOLEAN", {"default": True, "description": "Run paired-end validation"}),
                "quality": ("INT", {"default": 20, "min": 0, "max": 40}),
                "length": ("INT", {"default": 20, "min": 0}),
                "clip_r1": ("INT", {"default": 0, "min": 0, "max": 99}),
                "clip_r2": ("INT", {"default": 0, "min": 0, "max": 99}),
                "three_prime_clip_r1": ("INT", {"default": 0, "min": 0, "max": 99}),
                "three_prime_clip_r2": ("INT", {"default": 0, "min": 0, "max": 99}),
                "rrbs": ("BOOLEAN", {"default": False, "description": "Enable MspI-digested RRBS mode"}),
                "non_directional": (
                    "BOOLEAN",
                    {"default": False, "description": "Enable non-directional RRBS handling; requires rrbs"},
                ),
                "gzip": (
                    "BOOLEAN",
                    {"default": True, "description": "Force gzip output; gzip inputs remain compressed regardless"},
                ),
                "fastqc": ("BOOLEAN", {"default": True, "description": "Run FastQC on final trimmed reads"}),
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

        paired = inputs.get("paired", True)
        if not isinstance(paired, bool):
            return "paired must be a boolean."
        expected = 2 if paired else 1
        if len(reads) != expected:
            mode = "paired" if paired else "single-end"
            return f"{mode} mode requires exactly {expected} read{'s' if expected != 1 else ''}."

        for key, minimum, maximum in (
            ("threads", 1, 8),
            ("quality", 0, 40),
            ("length", 0, None),
            ("clip_r1", 0, 99),
            ("clip_r2", 0, 99),
            ("three_prime_clip_r1", 0, 99),
            ("three_prime_clip_r2", 0, 99),
        ):
            default = 1 if key == "threads" else 20 if key in {"quality", "length"} else 0
            result = validate_int(inputs.get(key, default), key, minimum=minimum, maximum=maximum)
            if result is not True:
                return result

        for key in ("rrbs", "non_directional", "gzip", "fastqc"):
            if not isinstance(inputs.get(key, key in {"gzip", "fastqc"}), bool):
                return f"{key} must be a boolean."
        if inputs.get("non_directional", False) and not inputs.get("rrbs", False):
            return "non_directional requires rrbs."
        if not paired and (inputs.get("clip_r2", 0) or inputs.get("three_prime_clip_r2", 0)):
            return "read 2 clipping requires paired mode."
        return True

    @staticmethod
    def _stem(path: str) -> str:
        name = Path(path).name
        for suffix in (".fastq.gz", ".fq.gz", ".fastq", ".fq", ".gz"):
            if name.endswith(suffix):
                return name[: -len(suffix)] or "reads"
        return name or "reads"

    @classmethod
    def _artifact_paths(
        cls,
        inputs: dict[str, Any],
        base_output_dir: str | Path,
    ) -> tuple[list[Path], list[Path], list[Path]]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        reads = read_paths(inputs.get("reads"))
        paired = bool(inputs.get("paired", True))
        force_gzip = bool(inputs.get("gzip", True))
        node_out = output_dir(base_output_dir, cls.NODE_ID)
        trimmed: list[Path] = []
        for index, read in enumerate(reads, start=1):
            stem = cls._stem(read)
            suffix = ".fq.gz" if force_gzip or read.lower().endswith(".gz") else ".fq"
            if paired:
                trimmed.append(node_out / f"{stem}_val_{index}{suffix}")
            else:
                trimmed.append(node_out / f"{stem}_trimmed{suffix}")

        reports = [node_out / f"{Path(read).name}_trimming_report.txt" for read in reads]
        fastqc_reports: list[Path] = []
        if inputs.get("fastqc", True):
            for path in trimmed:
                name = path.name[:-3] if path.name.endswith(".gz") else path.name
                for suffix in (".fastq", ".fq"):
                    if name.endswith(suffix):
                        name = name[: -len(suffix)]
                        break
                fastqc_reports.append(node_out / f"{name}_fastqc.html")
        return trimmed, fastqc_reports, reports

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        trimmed, fastqc_reports, reports = cls._artifact_paths(inputs, output_dir)
        return [*trimmed, *fastqc_reports, *reports]

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Any]:
        return {
            "trimmed_reads": [
                path
                for path in planned_paths
                if not path.name.endswith("_fastqc.html") and not path.name.endswith("_trimming_report.txt")
            ],
            "fastqc_report": [path for path in planned_paths if path.name.endswith("_fastqc.html")],
            "trimming_reports": [path for path in planned_paths if path.name.endswith("_trimming_report.txt")],
        }

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))

        command = ["trim_galore"]
        if inputs.get("paired", True):
            command.append("--paired")
        command.extend(["--cores", str(inputs.get("threads", 1))])
        for key, flag in (
            ("quality", "--quality"),
            ("length", "--length"),
            ("clip_r1", "--clip_R1"),
            ("clip_r2", "--clip_R2"),
            ("three_prime_clip_r1", "--three_prime_clip_R1"),
            ("three_prime_clip_r2", "--three_prime_clip_R2"),
        ):
            value = int(inputs.get(key, 0) or 0)
            if value > 0:
                command.extend([flag, str(value)])
        if inputs.get("rrbs", False):
            command.append("--rrbs")
        if inputs.get("non_directional", False):
            command.append("--non_directional")
        if inputs.get("gzip", True):
            command.append("--gzip")
        if inputs.get("fastqc", True):
            command.append("--fastqc")
        command.extend(["-o", str(inputs.get("output", inputs.get("output_dir", ".")))])
        command.extend(read_paths(inputs.get("reads")))
        return command

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        base_output_dir = kwargs.get("output_dir")
        context = kwargs.get("context")
        if base_output_dir is None and context is not None:
            base_output_dir = getattr(context, "node_dir", ".")
        if base_output_dir is None:
            base_output_dir = "."

        await super().run(**kwargs)
        planned = self.__class__.PLAN_OUTPUTS(kwargs, base_output_dir)
        mapped = self.__class__.MAP_PLANNED_OUTPUTS(planned)
        return {"outputs": {name: [str(path) for path in paths] for name, paths in mapped.items()}}
