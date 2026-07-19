"""10x Genomics Space Ranger 3.1.3 count contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int, validate_run_id


class SpaceRangerNode(CommandNode):
    """Run the known-slide, brightfield ``spaceranger count`` mode."""

    NODE_ID = "spaceranger_count"
    DISPLAY_NAME = "Space Ranger Count"
    CATEGORY = "spatial_transcriptomics"
    DESCRIPTION = "Process one 10x Visium capture area with Space Ranger 3.1.3."
    SEARCH_ALIASES = ["BioNodulo builtin", "Space Ranger", "10x Visium", "spatial transcriptomics"]
    RETURN_TYPES = ("DIRECTORY", "BAM", "FILE")
    RETURN_NAMES = ("spaceranger_out", "possorted_bam", "possorted_bam_index")
    REQUIRED_EXECUTABLES = ["spaceranger"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "3.1.3"
    DOCUMENTATION_URL = "https://www.10xgenomics.com/support/software/space-ranger/3.1/analysis/running-pipelines/command-line-arguments"
    RELEASE_NOTES_URL = "https://www.10xgenomics.com/support/software/space-ranger/3.1/release-notes"
    OUTPUT_DOCUMENTATION_URL = (
        "https://www.10xgenomics.com/support/software/space-ranger/3.1/analysis/outputs/output-overview"
    )
    GIT_URL = "https://github.com/10XGenomics/spaceranger.git"
    UPSTREAM_SOURCE = "Space Ranger 3.1 command-line arguments, count workflow, outputs, and v3.1.3 release notes"
    PACKAGE_CONSTRAINT = "external Space Ranger 3.1.3 binary; unavailable from conda-forge and Bioconda"
    DISTRIBUTION = "Restricted 10x Genomics source/binary distribution; worker provisioning is external."
    ENVIRONMENT = {
        "provisioning": "external_worker_binary",
        "executable": "spaceranger",
        "version": "3.1.3",
        "platform": "linux-64",
        "cpu_features": ["AVX"],
        "telemetry": "disabled with TENX_DISABLE_TELEMETRY=1",
    }
    ENV_VARS = {"TENX_DISABLE_TELEMETRY": "1"}
    SHELL = False
    EXPERIMENTAL = True
    EXIT_SEMANTICS = (
        "Space Ranger exit code 0 plus the native outs directory is success. When create_bam is true, "
        "the native possorted BAM and its BAI or CSI index are also required and exposed as explicit outputs."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "sample_id": ("STRING", {"default": "visium_sample", "description": "Run identifier"}),
                "transcriptome": ("DIRECTORY", {"description": "10x-compatible reference directory"}),
                "fastqs_dir": ("DIRECTORY", {"description": "Directory containing input FASTQs"}),
                "he_image": ("FILE", {"description": "H&E brightfield TIFF or JPEG"}),
                "slide": ("STRING", {"description": "Visium slide serial"}),
                "area": ("STRING", {"description": "Capture area identifier"}),
            },
            "optional": {
                "sample_prefix": ("STRING", {"default": "", "description": "FASTQ filename prefix"}),
                "slidefile": (
                    "FILE",
                    {"default": "", "advanced": True, "description": "GPR/VLF slide design file for offline runs"},
                ),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
                "memory": ("INT", {"default": 32, "min": 1, "description": "Local memory in GiB"}),
                "create_bam": ("BOOLEAN", {"default": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        node_dir.mkdir(parents=True, exist_ok=True)
        outs = node_dir / "outs"
        outputs = [outs]
        if inputs.get("create_bam", True):
            outputs.append(outs / "possorted_genome_bam.bam")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path]) -> dict[str, Path]:
        names = {
            "outs": "spaceranger_out",
            "possorted_genome_bam.bam": "possorted_bam",
            "possorted_genome_bam.bam.bai": "possorted_bam_index",
            "possorted_genome_bam.bam.csi": "possorted_bam_index",
        }
        return {names[path.name]: path for path in planned_paths}

    @classmethod
    def RESOLVE_BAM_INDEX(cls, outs: str | Path) -> Path:
        output_dir = Path(outs)
        candidates = [
            output_dir / "possorted_genome_bam.bam.bai",
            output_dir / "possorted_genome_bam.bam.csi",
        ]
        existing = [path for path in candidates if path.is_file()]
        if len(existing) != 1:
            found = ", ".join(path.name for path in existing) or "none"
            raise RuntimeError(f"Space Ranger must create exactly one BAM index (BAI or CSI); found {found}")
        return existing[0]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_run_id(inputs.get("sample_id", "visium_sample"), "sample_id")
        if validation is not True:
            return validation
        for key in ("transcriptome", "fastqs_dir", "he_image"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        for key in ("slide", "area"):
            if not str(inputs.get(key, "") or "").strip():
                return f"Input '{key}' must not be empty"
        validation = validate_int(inputs.get("threads", 8), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        return validate_int(inputs.get("memory", 32), "memory", minimum=1)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = [
            "spaceranger",
            "count",
            "--id",
            str(inputs.get("sample_id", "visium_sample")),
            "--transcriptome",
            path_value(inputs.get("transcriptome")),
            "--fastqs",
            path_value(inputs.get("fastqs_dir")),
            "--image",
            path_value(inputs.get("he_image")),
            "--slide",
            str(inputs.get("slide", "")),
            "--area",
            str(inputs.get("area", "")),
            "--localcores",
            str(inputs.get("threads", 8)),
            "--localmem",
            str(inputs.get("memory", 32)),
            "--output-dir",
            path_value(inputs.get("output")),
            f"--create-bam={'true' if inputs.get('create_bam', True) else 'false'}",
            "--disable-ui",
        ]
        sample_prefix = str(inputs.get("sample_prefix", "") or "").strip()
        if sample_prefix:
            command.extend(["--sample", sample_prefix])
        slidefile = path_value(inputs.get("slidefile"))
        if slidefile:
            command.extend(["--slidefile", slidefile])
        return command

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        mapped = self.__class__.MAP_PLANNED_OUTPUTS([Path(path) for path in result])
        if kwargs.get("create_bam", True):
            mapped["possorted_bam_index"] = self.__class__.RESOLVE_BAM_INDEX(mapped["spaceranger_out"])
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
