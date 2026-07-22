"""Manta 1.6.0 structural-variant configuration and local workflow execution."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .adapter import (
    IndexedBamReferenceNode,
    option_value,
    require_success,
    run_direct_argv,
    validate_integer,
)


def _validate_manta_bai(
    inputs: dict[str, Any],
    *,
    bam_key: str,
    index_key: str,
) -> bool | str:
    """Accept either BAI sibling spelling discovered by Manta 1.6.0."""

    def normalize_path(value: Any, *, key: str) -> Path | str:
        try:
            decoded = os.fsdecode(os.fspath(value))
        except TypeError:
            return f"Input '{key}' must be a non-empty path-like value"
        if not decoded.strip():
            return f"Input '{key}' must be a non-empty path-like value"
        return Path(os.path.abspath(os.path.normpath(decoded)))

    bam = normalize_path(inputs.get(bam_key), key=bam_key)
    if isinstance(bam, str):
        return bam

    candidates = {Path(f"{bam}.bai")}
    if bam.suffix.lower() == ".bam":
        candidates.add(bam.with_suffix(".bai"))
    rendered = " or ".join(
        f"'{path}'" for path in sorted(candidates, key=lambda path: (path != Path(f"{bam}.bai"), str(path)))
    )
    index_value = inputs.get(index_key)
    if index_value in (None, ""):
        return (
            f"Input '{index_key}' must be an exact colocated index (BAI) "
            f"discovered by Manta for input '{bam_key}'; expected {rendered}"
        )
    index = normalize_path(index_value, key=index_key)
    if isinstance(index, str):
        return index
    if index not in candidates:
        return (
            f"Input '{index_key}' must be an exact colocated index (BAI) "
            f"discovered by Manta for input '{bam_key}'; expected {rendered}"
        )
    return True


def _clear_manta_generated_state(run_dir: Path) -> None:
    """Remove only Manta-owned state before configuring a fresh attempt.

    Manta 1.6.0 refuses to configure a run directory containing its generated
    ``runWorkflow.py``.  BioNodulo retries reuse a node directory, so a workflow
    failure after successful configuration would otherwise make every retry
    fail during configuration.  Keep unrelated files intact and fail closed on
    symlinks or unexpected artifact types rather than following or deleting
    them.
    """
    if run_dir.is_symlink() or (run_dir.exists() and not run_dir.is_dir()):
        raise RuntimeError(f"Manta run directory must be a regular directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    for name in ("runWorkflow.py", "runWorkflow.py.config.pickle"):
        artifact = run_dir / name
        if artifact.is_symlink() or (artifact.exists() and not artifact.is_file()):
            raise RuntimeError(
                f"Refusing to clear unexpected Manta generated artifact: {artifact}"
            )
        artifact.unlink(missing_ok=True)

    for name in ("workspace", "results"):
        artifact = run_dir / name
        if artifact.is_symlink() or (artifact.exists() and not artifact.is_dir()):
            raise RuntimeError(
                f"Refusing to clear unexpected Manta generated artifact: {artifact}"
            )
        if artifact.exists():
            shutil.rmtree(artifact)


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
    # Manta 1.6.0's pinned source rejects Python 3 and its generated workflow
    # has a python2 shebang.  Keep that documented runtime in a named Pixi
    # environment inside the workflow's single committed lock instead of
    # contaminating the modern default toolchain.
    ENVIRONMENT = {"type": "pixi", "name": "manta"}
    DOCUMENTATION_URL = "https://github.com/Illumina/manta"
    VERSION = "1.6.0"
    GIT_URL = "https://github.com/Illumina/manta.git"
    GIT_COMMIT = "ab9f5502985a29ec74cfafb4963179b9cc185e55"
    SOURCE_URL = f"https://github.com/Illumina/manta/tree/{GIT_COMMIT}"
    PACKAGE_CONSTRAINTS = ("manta==1.6.0",)
    PACKAGE_CONSTRAINT = "manta==1.6.0"
    EXIT_SEMANTICS = "Configuration, generated-workflow, or output validation failure fails the node."
    AUDIT_STATUS = "contract-checked-no-external-execution"
    CITATION_DOIS = ["10.1093/bioinformatics/btv710"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btv710"]
    CITATION_TEXT = (
        "Manta: rapid detection of structural variants and indels for germline and cancer sequencing applications."
    )
    UPSTREAM_SOURCE = "src/python/bin/configManta.py"
    UPSTREAM_OPTIONS_SOURCE = "src/python/lib/mantaOptions.py"
    UPSTREAM_INDEX_SOURCE = "src/python/lib/configureUtil.py"
    UPSTREAM_WORKFLOW_SOURCE = "src/python/lib/mantaWorkflow.py"
    UPSTREAM_RUN_DIRECTORY_SOURCE = "src/python/lib/mantaOptions.py:147-154"
    UPSTREAM_REFERENCE_SOURCE = UPSTREAM_OPTIONS_SOURCE
    UPSTREAM_BAM_INDEX_SOURCE = UPSTREAM_INDEX_SOURCE
    SHELL = True

    @classmethod
    def validate_primary_bam_index(cls, inputs: dict[str, Any]) -> bool | str:
        return _validate_manta_bai(inputs, bam_key="bam", index_key="bam_index")

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
                    {"description": ("Explicit <bam>.bai or extension-replaced <stem>.bai index for the primary BAM")},
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA with a colocated FAI"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai index"},
                ),
                "threads": ("INT", {"default": 4, "min": 1}),
            },
            "optional": {
                "normal_bam": (
                    "BAM",
                    {"description": "Normal BAM for tumor-normal mode", "advanced": True},
                ),
                "normal_bam_index": (
                    "BAI",
                    {
                        "description": ("Explicit <normal_bam>.bai or extension-replaced <stem>.bai index"),
                        "advanced": True,
                    },
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
        validation = validate_integer(inputs, "threads", 4, minimum=1)
        if validation is not True:
            return validation

        normal_bam = inputs.get("normal_bam")
        normal_bam_index = inputs.get("normal_bam_index")
        if option_value(inputs, "rna", False) and normal_bam:
            return "rna mode requires exactly one normal sample and no tumor BAM"
        if normal_bam:
            return _validate_manta_bai(
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
        kwargs["output"] = str(node_out)
        kwargs["output_dir"] = str(node_out)

        validation = self.__class__.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(f"Input validation failed: {validation}")
        _clear_manta_generated_state(node_out)
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
            raise RuntimeError(f"Manta workflow completed but did not create expected output(s): {missing}")
        return tuple(str(path) for path in outputs)
