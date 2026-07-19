"""Manta 1.6.0 structural-variant configuration and local workflow execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .adapter import (
    IndexedBamReferenceNode,
    option_value,
    require_success,
    run_direct_argv,
    validate_integer,
)
from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index


class MantaNode(IndexedBamReferenceNode):
    """Configure and run Manta while preserving its native VCF outputs."""

    NODE_ID = "manta"
    DISPLAY_NAME = "Manta SV Caller"
    DESCRIPTION = "Call germline, tumor-normal, or RNA structural variants with Manta"
    SEARCH_ALIASES = [
        "manta",
        "structural variant",
        "sv caller",
        "illumina sv",
        "germline sv",
        "somatic sv",
        "rna sv",
    ]
    RETURN_TYPES = ("VCF_GZ", "VCF_INDEX", "VCF_GZ", "VCF_INDEX")
    RETURN_NAMES = (
        "candidate_sv",
        "candidate_sv_index",
        "primary_sv",
        "primary_sv_index",
    )
    REQUIRED_EXECUTABLES = ["configManta.py"]
    REQUIRED_CONDA_PACKAGES = ["manta"]
    DOCUMENTATION_URL = "https://github.com/Illumina/manta"
    VERSION = "1.6.0"
    GIT_URL = "https://github.com/Illumina/manta.git"
    GIT_COMMIT = "ab9f5502985a29ec74cfafb4963179b9cc185e55"
    CITATION_DOIS = ["10.1093/bioinformatics/btv710"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btv710"]
    CITATION_TEXT = "Manta: rapid detection of structural variants and indels for germline and cancer sequencing applications."
    UPSTREAM_SOURCE = "src/python/bin/configManta.py"
    UPSTREAM_OPTIONS_SOURCE = "src/python/lib/mantaOptions.py"
    UPSTREAM_INDEX_SOURCE = "src/python/lib/configureUtil.py"
    UPSTREAM_WORKFLOW_SOURCE = "src/python/lib/mantaWorkflow.py"
    UPSTREAM_REFERENCE_SOURCE = UPSTREAM_OPTIONS_SOURCE
    UPSTREAM_BAM_INDEX_SOURCE = UPSTREAM_INDEX_SOURCE
    SHELL = True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "bam": (
                    "BAM",
                    {"description": "Normal BAM, or tumor BAM when normal_bam is provided"},
                ),
                "bam_index": (
                    "BAI",
                    {"description": "Exact <bam>.bai index for the primary BAM"},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with a colocated FAI"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai index"},
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "optional": {
                "normal_bam": (
                    "BAM",
                    {"description": "Normal BAM for tumor-normal mode", "advanced": True},
                ),
                "normal_bam_index": (
                    "BAI",
                    {"description": "Exact <normal_bam>.bai index", "advanced": True},
                ),
                "exome": (
                    "BOOLEAN",
                    {"default": False, "description": "Use exome/targeted defaults"},
                ),
                "rna": (
                    "BOOLEAN",
                    {"default": False, "description": "Use single-normal RNA mode"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def _primary_vcf_name(cls, inputs: dict[str, Any]) -> str:
        if option_value(inputs, "rna", False):
            return "rnaSV.vcf.gz"
        if inputs.get("normal_bam"):
            return "somaticSV.vcf.gz"
        return "diploidSV.vcf.gz"

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        variants_dir = Path(output_dir) / cls.NODE_ID / "results" / "variants"
        variants_dir.mkdir(parents=True, exist_ok=True)
        candidate = variants_dir / "candidateSV.vcf.gz"
        primary = variants_dir / cls._primary_vcf_name(inputs)
        return [candidate, Path(f"{candidate}.tbi"), primary, Path(f"{primary}.tbi")]

    @classmethod
    def _render_config_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        command = ["configManta.py"]
        if inputs.get("normal_bam"):
            command.extend(
                [
                    "--normalBam",
                    str(inputs["normal_bam"]),
                    "--tumorBam",
                    str(inputs["bam"]),
                ]
            )
        else:
            command.extend(["--bam", str(inputs["bam"])])
        command.extend(
            [
                "--referenceFasta",
                str(inputs["reference"]),
                "--runDir",
                str(output),
            ]
        )
        if option_value(inputs, "exome", False):
            command.append("--exome")
        if option_value(inputs, "rna", False):
            command.append("--rna")
        return command

    @classmethod
    def _render_workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        return [
            str(output / "runWorkflow.py"),
            "-m",
            "local",
            "-j",
            str(option_value(inputs, "threads", 4)),
        ]

    @classmethod
    def render_config_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        return cls._render_config_command(inputs)

    @classmethod
    def render_workflow_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        return cls._render_workflow_command(inputs)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        return [
            *cls._render_config_command(inputs),
            "&&",
            *cls._render_workflow_command(inputs),
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        validation = validate_integer(inputs, "threads", 4, minimum=1, maximum=64)
        if validation is not True:
            return validation

        normal_bam = inputs.get("normal_bam")
        normal_bam_index = inputs.get("normal_bam_index")
        if option_value(inputs, "rna", False) and normal_bam:
            return "rna mode requires exactly one normal sample and no tumor BAM"
        if normal_bam:
            return validate_colocated_bam_index(
                inputs,
                bam_key="normal_bam",
                index_key="normal_bam_index",
            )
        if normal_bam_index:
            return "Input 'normal_bam_index' requires input 'normal_bam'"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        """Run configuration and the generated workflow as two direct argv calls."""
        context = kwargs.pop("context", None)
        output_dir = kwargs.pop("output_dir", None)
        if output_dir is None and context is not None:
            output_dir = getattr(context, "node_dir", ".")
        output_root = Path(output_dir or ".")
        node_out = output_root / self.__class__.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        kwargs["output"] = str(node_out)
        kwargs["output_dir"] = str(node_out)

        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        outputs = self.__class__.PLAN_OUTPUTS(kwargs, output_root)

        commands = (
            ("Manta configuration", self.__class__._render_config_command(kwargs), "config"),
            ("Manta workflow", self.__class__._render_workflow_command(kwargs), "workflow"),
        )
        for label, command, log_stem in commands:
            result = await run_direct_argv(
                command,
                context=context,
                cwd=output_root,
                env=self.__class__.ENV_VARS or None,
                stdout_path=node_out / f"{log_stem}.stdout.log",
                stderr_path=node_out / f"{log_stem}.stderr.log",
            )
            require_success(result, label=label)

        missing_outputs = [path for path in outputs if not path.exists()]
        if missing_outputs:
            missing = ", ".join(str(path) for path in missing_outputs)
            raise RuntimeError(
                f"Manta workflow completed but did not create expected output(s): {missing}"
            )
        return tuple(str(path) for path in outputs)
