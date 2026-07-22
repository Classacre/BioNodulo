"""10x Genomics Cell Ranger 9.0.1 count contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.command_node import CommandNode

from .adapter import path_value, validate_int, validate_run_id


class CellRangerCountNode(CommandNode):
    """Run the licensed Cell Ranger count binary in a deterministic node directory."""

    # Cell Ranger 9.0.1's ``check_refdata`` preflight (pinned source:
    # ``lib/python/cellranger/preflight.py``) discovers these files relative to
    # the supplied reference directory.  Keep the directory as one staged
    # artifact, but validate the native sibling layout once it is materialized.
    REFERENCE_REQUIRED_FILES = (
        "reference.json",
        "fasta/genome.fa",
        "star/chrLength.txt",
        "star/chrNameLength.txt",
        "star/chrName.txt",
        "star/chrStart.txt",
        "star/Genome",
        "star/genomeParameters.txt",
        "star/SA",
        "star/SAindex",
    )
    REFERENCE_GTF_FILES = ("genes/genes.gtf", "genes/genes.gtf.gz")

    NODE_ID = "cellranger_count"
    DISPLAY_NAME = "Cell Ranger Count"
    CATEGORY = "single_cell"
    DESCRIPTION = "Run 10x Genomics Cell Ranger count and expose its native feature-barcode outputs."
    SEARCH_ALIASES = ["BioNodulo builtin", "Cell Ranger", "10x", "scRNA-seq", "count", "single cell"]
    RETURN_TYPES = (
        "CELL_RANGER_OUT",
        "FILE",
        "CSV",
        "DIRECTORY",
        "FILE",
        "DIRECTORY",
        "FILE",
        "BAM",
        "FILE",
    )
    RETURN_NAMES = (
        "output_dir",
        "web_summary",
        "metrics_summary",
        "filtered_feature_bc_matrix",
        "filtered_feature_bc_matrix_h5",
        "raw_feature_bc_matrix",
        "raw_feature_bc_matrix_h5",
        "possorted_bam",
        "possorted_bam_index",
    )
    REQUIRED_EXECUTABLES = ["cellranger"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    VERSION = "9.0.1"
    GIT_URL = "https://github.com/10XGenomics/cellranger.git"
    GIT_COMMIT = "6ebad209b8354353b4a9ee3eed1cb248d102af88"
    SOURCE_TAG = "cellranger-9.0.1"
    SOURCE_URL = f"https://github.com/10XGenomics/cellranger/tree/{GIT_COMMIT}"
    DOCUMENTATION_URL = (
        "https://www.10xgenomics.com/support/software/cell-ranger/9.0/analysis/running-pipelines/cr-gex-count"
    )
    RELEASE_NOTES_URL = "https://www.10xgenomics.com/support/software/cell-ranger/9.0/release-notes"
    OUTPUT_DOCUMENTATION_URL = (
        "https://www.10xgenomics.com/support/software/cell-ranger/9.0/analysis/outputs/"
        "cr-outputs-overview"
    )
    LICENSE_URL = f"https://github.com/10XGenomics/cellranger/blob/{GIT_COMMIT}/LICENSE"
    DISTRIBUTION = (
        "BYOL only: the supported Cell Ranger 9.0.1 binary and compatible reference must be "
        "obtained from 10x Genomics under its account and license terms; no Conda package or "
        "automatic download is available."
    )
    UPSTREAM_SOURCE = (
        "bin/sc_rna/count; bin/tenkit/common/_includes; lib/rust/cr_wrap/src/create_bam_arg.rs; "
        "mro/rna/sc_rna_counter_cs.mro; mro/rna/stages/counter/summarize_reports/__init__.py; "
        "lib/python/cellranger/webshim/common.py:build_metrics_summary_csv; "
        "lib/python/cellranger/preflight.py:check_refdata; lib/python/cellranger/constants.py"
    )
    SOURCE_AUTHORITIES = {
        "source": SOURCE_URL,
        "count_cli": "bin/sc_rna/count; bin/tenkit/common/_includes",
        "create_bam_cli": "lib/rust/cr_wrap/src/create_bam_arg.rs",
        "native_outputs": "mro/rna/sc_rna_counter_cs.mro",
        "metrics_summary_layout": (
            "mro/rna/stages/counter/summarize_reports/__init__.py; "
            "lib/python/cellranger/webshim/common.py:build_metrics_summary_csv"
        ),
        "reference_preflight": (
            "lib/python/cellranger/preflight.py:check_refdata; "
            "lib/python/cellranger/constants.py"
        ),
        "license": LICENSE_URL,
    }
    PACKAGE_CONSTRAINT = "external BYOL binary cellranger 9.0.1"
    ACCESS_CONSTRAINTS = (
        "10x account and license acceptance for supported binary/reference downloads",
        "complete compatible Cell Ranger reference directory staged as one input artifact",
        "linux-64 worker with the externally provisioned cellranger 9.0.1 executable",
    )
    QUARANTINE_STATUS = "byol-evidence-only-no-binary-execution"
    AUDIT_STATUS = "contract-checked-no-binary-execution"
    EXIT_SEMANTICS = (
        "Cell Ranger exit code 0 plus every declared native output is success. When create_bam is "
        "true, possorted_genome_bam.bam and exactly one BAI or CSI index are additionally required."
    )
    RUN_IN_NODE_OUTPUT_DIR = True
    SHELL = False
    EXPERIMENTAL = True
    ENVIRONMENT = {
        "provisioning": "external_worker_binary",
        "executable": "cellranger",
        "version": "9.0.1",
        "platform": "linux-64",
        "telemetry": "disabled with TENX_DISABLE_TELEMETRY=1",
        "access": "BYOL",
    }
    ENV_VARS = {"TENX_DISABLE_TELEMETRY": "1"}

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq_dir": ("DIRECTORY", {"description": "Directory containing Cell Ranger-compatible FASTQs"}),
                "transcriptome": (
                    "DIRECTORY",
                    {
                        "description": (
                            "Complete compatible Cell Ranger reference directory, staged together; "
                            "the node does not download references"
                        )
                    },
                ),
                "threads": ("INT", {"default": 16, "min": 1, "max": 64}),
                "memory": ("INT", {"default": 64, "min": 8, "description": "Local memory in GiB"}),
                "run_id": ("STRING", {"default": "cellranger_count"}),
            },
            "optional": {
                "sample": ("STRING", {"default": "", "description": "FASTQ sample prefix(es), comma-separated"}),
                "expect_cells": ("INT", {"default": None, "min": 1}),
                "create_bam": ("BOOLEAN", {"default": False}),
            },
            "hidden": {},
        }

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_dir = Path(output_dir) / cls.NODE_ID
        run_dir = node_dir / str(inputs.get("run_id", "cellranger_count"))
        outs = run_dir / "outs"
        node_dir.mkdir(parents=True, exist_ok=True)
        outputs = [
            run_dir,
            outs / "web_summary.html",
            outs / "metrics_summary.csv",
            outs / "filtered_feature_bc_matrix",
            outs / "filtered_feature_bc_matrix.h5",
            outs / "raw_feature_bc_matrix",
            outs / "raw_feature_bc_matrix.h5",
        ]
        if inputs.get("create_bam", False):
            outputs.append(outs / "possorted_genome_bam.bam")
        return outputs

    @classmethod
    def MAP_PLANNED_OUTPUTS(cls, planned_paths: list[Path], create_bam: bool) -> dict[str, Path]:
        names = list(cls.RETURN_NAMES[:7])
        if create_bam:
            names.append("possorted_bam")
        if len(planned_paths) != len(names):
            raise RuntimeError(
                f"Cell Ranger planned {len(planned_paths)} outputs; expected {len(names)}"
            )
        return dict(zip(names, planned_paths, strict=True))

    @classmethod
    def RESOLVE_BAM_INDEX(cls, run_dir: str | Path) -> Path:
        outs = Path(run_dir) / "outs"
        candidates = [
            outs / "possorted_genome_bam.bam.bai",
            outs / "possorted_genome_bam.bam.csi",
        ]
        existing = [path for path in candidates if path.is_file()]
        if len(existing) != 1:
            found = ", ".join(path.name for path in existing) or "none"
            raise RuntimeError(f"Cell Ranger must create exactly one BAM index (BAI or CSI); found {found}")
        return existing[0]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("fastq_dir", "transcriptome"):
            if not path_value(inputs.get(key)):
                return f"Input '{key}' must be a non-empty path-like value"
        validation = validate_run_id(inputs.get("run_id", "cellranger_count"))
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("threads", 16), "threads", minimum=1, maximum=64)
        if validation is not True:
            return validation
        validation = validate_int(inputs.get("memory", 64), "memory", minimum=8)
        if validation is not True:
            return validation
        if inputs.get("expect_cells") is not None:
            validation = validate_int(inputs["expect_cells"], "expect_cells", minimum=1)
            if validation is not True:
                return validation
        sample = str(inputs.get("sample", "") or "")
        if sample and any(not part for part in sample.split(",")):
            return "Input 'sample' must contain non-empty comma-separated prefixes"
        return True

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        """Validate Cell Ranger's native reference bundle before launch.

        Input directories may still be symbolic paths during editor/dry-run
        rendering and before cloud staging, so defer validation until the path
        is materialized.  Once present, the exact sibling layout required by
        Cell Ranger 9.0.1 is checked before invoking the external binary.
        """

        reference = Path(path_value(inputs.get("transcriptome")))
        if not reference.exists():
            return
        if not reference.is_dir():
            raise ValueError(f"Cell Ranger reference must be a directory: {reference}")

        missing = [
            relative
            for relative in cls.REFERENCE_REQUIRED_FILES
            if not (reference / relative).is_file()
        ]
        if not any((reference / relative).is_file() for relative in cls.REFERENCE_GTF_FILES):
            missing.append("genes/genes.gtf or genes/genes.gtf.gz")
        if missing:
            raise ValueError(
                "Cell Ranger reference is missing required file(s): "
                + ", ".join(missing)
            )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        command = [
            "cellranger",
            "count",
            "--id",
            str(inputs.get("run_id", "cellranger_count")),
            "--transcriptome",
            path_value(inputs.get("transcriptome")),
            "--fastqs",
            path_value(inputs.get("fastq_dir")),
            "--localcores",
            str(inputs.get("threads", 16)),
            "--localmem",
            str(inputs.get("memory", 64)),
        ]
        if inputs.get("sample") not in (None, ""):
            command.extend(["--sample", str(inputs["sample"])])
        if inputs.get("expect_cells") is not None:
            command.extend(["--expect-cells", str(inputs["expect_cells"])])
        command.append(f"--create-bam={'true' if inputs.get('create_bam', False) else 'false'}")
        command.append("--disable-ui")
        return command

    async def run(self, **kwargs: Any) -> Any:
        result = await super().run(**kwargs)
        if not isinstance(result, tuple):
            return result
        create_bam = bool(kwargs.get("create_bam", False))
        mapped = self.__class__.MAP_PLANNED_OUTPUTS(
            [Path(path) for path in result],
            create_bam,
        )
        if create_bam:
            mapped["possorted_bam_index"] = self.__class__.RESOLVE_BAM_INDEX(
                mapped["output_dir"]
            )
        return {"outputs": {name: str(path) for name, path in mapped.items()}}
