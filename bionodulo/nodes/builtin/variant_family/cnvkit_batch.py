"""CNVkit 0.9.12 batch pipeline with explicit reference and BAM sidecars."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)

from bionodulo.nodes.builtin.cnvkit_family.adapter import (
    CNVKIT_COMMIT,
    CNVkitCommandNode,
    path_list,
    sample_id,
    validate_bam_index_list,
)


class CNVkitBatchNode(CNVkitCommandNode):
    """Build a CN reference and run the complete pipeline on test BAMs."""

    NODE_ID = "cnvkit_batch"
    DISPLAY_NAME = "CNVkit Batch Pipeline"
    DESCRIPTION = (
        "Build a flat or pooled CNV reference, then run coverage, fix, segment, and call."
    )
    SEARCH_ALIASES = ["cnvkit", "cnv", "copy number", "batch", "cbs"]
    RETURN_TYPES = ("DIRECTORY", "FILE")
    RETURN_NAMES = ("results", "reference_cnn")
    REQUIRED_EXECUTABLES = ["cnvkit.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["cnvkit", "r-base"]
    REQUIRED_EXECUTABLES = ["cnvkit.py", "Rscript"]
    REQUIRED_CONDA_PACKAGES = ["cnvkit", "r-base"]
    SOURCE_REF = CNVKIT_COMMIT
    DOCUMENTATION_URL = (
        f"https://github.com/etal/cnvkit/blob/{CNVKIT_COMMIT}/doc/pipeline.rst"
    )
    UPSTREAM_BATCH_SOURCE = "cnvlib/batch.py"
    UPSTREAM_COVERAGE_SOURCE = "cnvlib/coverage.py"
    UPSTREAM_BAM_INDEX_SOURCE = "cnvlib/samutil.py"
    SOURCE_PATHS = (
        "cnvlib/commands.py",
        "cnvlib/batch.py",
        "cnvlib/coverage.py",
        "cnvlib/samutil.py",
        "doc/pipeline.rst",
    )
    SOURCE_OUTPUTS = (
        "reference.cnn; processed target and antitarget BEDs; per-sample target and "
        "antitarget coverage CNNs; tumor CNR, CNS, called CNS, bintest CNS, and optional plots"
    )
    EXIT_SEMANTICS = (
        "BioNodulo prevalidates the exposed parser constraints; a non-zero CNVkit "
        "result or any missing reference, CNR, CNS, called-CNS, or selected plot "
        "artifact fails the node. Real CNVkit execution was not performed."
    )
    METHODS = ("hybrid", "amplicon", "wgs")
    RESULTS_DIRECTORY = "results"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "tumor_bams": (
                    "BAM",
                    {
                        "multiple": True,
                        "description": "One or more coordinate-sorted test BAMs",
                    },
                ),
                "tumor_bam_indexes": (
                    "BAI",
                    {
                        "multiple": True,
                        "description": "Exact <bam>.bai sidecar for each test BAM",
                    },
                ),
                "reference": (
                    "FASTA",
                    {"description": "Reference FASTA used to construct the CN reference"},
                ),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact <reference>.fai sidecar"},
                ),
            },
            "optional": {
                "normal_bams": (
                    "BAM",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Normal BAMs; empty builds a flat reference",
                    },
                ),
                "normal_bam_indexes": (
                    "BAI",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Exact <bam>.bai sidecar for each normal BAM",
                    },
                ),
                "targets": (
                    "BED",
                    {
                        "description": "Required capture targets for hybrid or amplicon data",
                        "advanced": True,
                    },
                ),
                "method": (
                    "STRING",
                    {"default": "hybrid", "options": list(cls.METHODS)},
                ),
                "threads": (
                    "INT",
                    {
                        "default": 1,
                        "min": 0,
                        "description": "CNVkit subprocesses; 0 selects all available CPUs",
                    },
                ),
                "diagram": (
                    "BOOLEAN",
                    {"default": False, "description": "Create per-sample diagram PDFs"},
                ),
                "scatter": (
                    "BOOLEAN",
                    {"default": False, "description": "Create per-sample scatter PNGs"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def PLAN_OUTPUTS(
        cls,
        inputs: dict[str, Any],
        output_dir: str | Path,
    ) -> list[Path]:
        results = Path(output_dir) / cls.NODE_ID / cls.RESULTS_DIRECTORY
        results.mkdir(parents=True, exist_ok=True)
        return [results, results / "reference.cnn"]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cls.require_valid_inputs(inputs)
        tumors = path_list(inputs["tumor_bams"]) or []
        normals = path_list(inputs.get("normal_bams", [])) or []
        output = Path(str(inputs.get("output", inputs.get("output_dir", "."))))
        results = output / cls.RESULTS_DIRECTORY

        command = ["cnvkit.py", "batch", *tumors, "--normal", *normals]
        command.extend(
            [
                "--fasta",
                str(inputs["reference"]),
                "--output-reference",
                str(results / "reference.cnn"),
                "--output-dir",
                str(results),
                "--processes",
                str(inputs.get("threads", 1)),
                "--seq-method",
                str(inputs.get("method", "hybrid")),
            ]
        )
        if inputs.get("targets"):
            command.extend(["--targets", str(inputs["targets"])])
        if inputs.get("scatter"):
            command.append("--scatter")
        if inputs.get("diagram"):
            command.append("--diagram")
        return command

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation

        tumors = path_list(inputs.get("tumor_bams"))
        if not tumors:
            return "tumor_bams must contain at least one non-empty path"
        validation = validate_bam_index_list(
            tumors,
            inputs.get("tumor_bam_indexes"),
            bam_key="tumor_bams",
            index_key="tumor_bam_indexes",
        )
        if validation is not True:
            return validation

        normals_value = inputs.get("normal_bams", [])
        if normals_value in (None, "", [], ()):
            normals: list[str] = []
            if inputs.get("normal_bam_indexes") not in (None, "", [], ()):
                return "normal_bam_indexes must be empty when normal_bams is empty"
        else:
            normals = path_list(normals_value) or []
            if not normals:
                return "normal_bams must contain non-empty path-like values"
            validation = validate_bam_index_list(
                normals,
                inputs.get("normal_bam_indexes"),
                bam_key="normal_bams",
                index_key="normal_bam_indexes",
            )
            if validation is not True:
                return validation

        validation = validate_colocated_reference_index(inputs)
        if validation is not True:
            return validation

        method = str(inputs.get("method", "hybrid"))
        if method not in cls.METHODS:
            return f"method must be one of: {', '.join(cls.METHODS)}"
        if method in {"hybrid", "amplicon"} and not inputs.get("targets"):
            return f"targets BED is required for CNVkit {method} batch mode"

        threads = inputs.get("threads", 1)
        if isinstance(threads, bool) or not isinstance(threads, int) or threads < 0:
            return "threads must be a non-negative integer"

        sample_ids = [sample_id(path) for path in [*tumors, *normals]]
        if len(sample_ids) != len(set(sample_ids)):
            return "tumor and normal BAMs must have unique CNVkit sample IDs"
        return True

    async def run(self, **kwargs: Any) -> tuple[Any, ...] | dict[str, Any]:
        tumors = path_list(kwargs.get("tumor_bams")) or []
        normals = path_list(kwargs.get("normal_bams", [])) or []
        result = await super().run(**kwargs)
        if not isinstance(result, tuple) or not result:
            return result

        results = Path(str(result[0]))
        expected = [results / "reference.cnn"]
        target_source = str(kwargs.get("targets") or kwargs.get("reference", ""))
        target_prefix = Path(target_source).name.rsplit(".", 1)[0]
        expected.extend(
            [
                results / f"{target_prefix}.target.bed",
                results / f"{target_prefix}.antitarget.bed",
            ]
        )
        for bam in [*tumors, *normals]:
            prefix = results / sample_id(bam)
            expected.extend(
                [
                    Path(f"{prefix}.targetcoverage.cnn"),
                    Path(f"{prefix}.antitargetcoverage.cnn"),
                ]
            )
        for bam in tumors:
            prefix = results / sample_id(bam)
            expected.extend(
                [
                    Path(f"{prefix}.cnr"),
                    Path(f"{prefix}.cns"),
                    Path(f"{prefix}.call.cns"),
                    Path(f"{prefix}.bintest.cns"),
                ]
            )
            if kwargs.get("scatter"):
                expected.append(Path(f"{prefix}-scatter.png"))
            if kwargs.get("diagram"):
                expected.append(Path(f"{prefix}-diagram.pdf"))

        missing = [path for path in expected if not path.is_file()]
        if missing:
            rendered = ", ".join(str(path) for path in missing)
            raise RuntimeError(
                f"CNVkit batch completed but did not create expected artifact(s): {rendered}"
            )
        return result


__all__ = ["CNVkitBatchNode"]
