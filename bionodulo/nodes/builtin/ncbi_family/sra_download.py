"""SRA Toolkit 3.4.1 prefetch plus fasterq-dump node."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.base import BaseNode

from .adapter import coerce_bool, coerce_ids, node_output_dir, run_command


SRA_TOOLKIT_VERSION = "3.4.1"
SRA_TOOLKIT_GIT_URL = "https://github.com/ncbi/sra-tools.git"
SRA_TOOLKIT_GIT_COMMIT = "ded4303eb477047590b219f6a2e8397b12d58cc0"
SRA_TOOLKIT_SOURCE_TAG = "3.4.1"
SRA_TOOLKIT_DOCUMENTATION_URL = "https://github.com/ncbi/sra-tools/wiki/08.-prefetch-and-fasterq-dump"
SRA_OUTPUT_FORMATS = ("fastq", "fasta")
SRA_RUN_ACCESSION = re.compile(r"^(?:SRR|ERR|DRR)\d+$", re.IGNORECASE)


def normalized_accessions(value: Any) -> list[str]:
    return [accession.upper() for accession in coerce_ids(value)]


def collect_output_files(output_dir: Path, accession: str, output_format: str) -> list[str]:
    extension = ".fastq" if output_format == "fastq" else ".fasta"
    return [
        str(path)
        for path in sorted(output_dir.glob(f"{accession}*{extension}"), key=lambda item: item.name)
        if path.is_file()
    ]


class SRADownloadNode(BaseNode):
    """Prefetch and convert one or more SRA run accessions, one at a time."""

    NODE_ID = "sra_download"
    DISPLAY_NAME = "SRA Download"
    CATEGORY = "databases"
    DESCRIPTION = "Prefetch SRA runs and convert them to FASTQ or FASTA with SRA Toolkit 3.4.1."
    SEARCH_ALIASES = [
        "sra",
        "sequence read archive",
        "download",
        "fastq",
        "fasta",
        "reads",
        "prefetch",
        "fasterq-dump",
    ]
    RETURN_TYPES = ("FILE_LIST", "JSON")
    RETURN_NAMES = ("files", "download_report")
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_EXECUTABLES = ["prefetch", "fasterq-dump"]
    REQUIRED_CONDA_PACKAGES = ["sra-tools"]
    CONDA_PACKAGE_CONSTRAINTS = {"sra-tools": SRA_TOOLKIT_VERSION}
    PACKAGE_CONSTRAINT = f"sra-tools = {SRA_TOOLKIT_VERSION}"
    EXPERIMENTAL = True
    VERSION = SRA_TOOLKIT_VERSION
    GIT_URL = SRA_TOOLKIT_GIT_URL
    GIT_COMMIT = SRA_TOOLKIT_GIT_COMMIT
    SOURCE_TAG = SRA_TOOLKIT_SOURCE_TAG
    DOCUMENTATION_URL = SRA_TOOLKIT_DOCUMENTATION_URL
    SOURCE_URL = f"https://github.com/ncbi/sra-tools/tree/{SRA_TOOLKIT_SOURCE_TAG}"
    UPSTREAM_SOURCE = (
        "tools/external/prefetch/prefetch.c; tools/external/fasterq-dump/fasterq-dump.c; "
        "tools/external/fasterq-dump/readme.txt"
    )
    EXIT_SEMANTICS = (
        "By default any prefetch failure, fasterq-dump failure, exception, or missing output is fatal after "
        "writing the report; continue_on_error explicitly permits partial results."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "accessions": (
                    "STRING",
                    {"default": "", "description": "SRR, ERR, or DRR run accessions"},
                ),
            },
            "optional": {
                "output_format": (list(SRA_OUTPUT_FORMATS), {"default": "fastq"}),
                "split_files": (
                    "BOOLEAN",
                    {"default": False, "description": "Use --split-files instead of default split-3"},
                ),
                "skip_technical": (
                    "BOOLEAN",
                    {"default": True, "description": "Keep fasterq-dump's default biological-read filtering"},
                ),
                "threads": ("INT", {"default": 6, "min": 1}),
                "continue_on_error": ("BOOLEAN", {"default": False, "advanced": True}),
                "accession": (
                    "STRING",
                    {"default": "", "advanced": True, "description": "Backward-compatible single run"},
                ),
                "format": (
                    "STRING",
                    {"default": "", "options": list(SRA_OUTPUT_FORMATS), "advanced": True},
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        accessions = normalized_accessions(inputs.get("accessions", "") or inputs.get("accession", ""))
        if not accessions:
            return "Input 'accessions' must contain at least one SRA run accession"
        invalid = [accession for accession in accessions if not SRA_RUN_ACCESSION.fullmatch(accession)]
        if invalid:
            return f"Input 'accessions' contains invalid run accession: {invalid[0]}"
        output_format = str(inputs.get("output_format", "") or inputs.get("format", "") or "fastq").lower()
        if output_format not in SRA_OUTPUT_FORMATS:
            return f"Input 'output_format' must be one of: {', '.join(SRA_OUTPUT_FORMATS)}"
        threads = inputs.get("threads", 6)
        if isinstance(threads, bool) or not isinstance(threads, int):
            return "Input 'threads' must be an integer"
        if threads < 1:
            return "Input 'threads' must be at least 1"
        return True

    @classmethod
    def render_prefetch_command(cls, accession: str, output_dir: Path) -> list[str]:
        return [
            "prefetch",
            accession,
            "--output-directory",
            str(output_dir),
        ]

    @classmethod
    def render_fasterq_command(
        cls,
        *,
        accession: str,
        output_dir: Path,
        output_format: str,
        split_files: bool,
        skip_technical: bool,
        threads: int,
    ) -> list[str]:
        command = [
            "fasterq-dump",
            str(output_dir / accession),
            "--outdir",
            str(output_dir),
            "--threads",
            str(threads),
        ]
        if output_format == "fasta":
            command.append("--fasta")
        if split_files:
            command.append("--split-files")
        if not skip_technical:
            command.append("--include-technical")
        return command

    async def run(self, **kwargs: Any) -> dict[str, Any]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        accessions = normalized_accessions(kwargs.get("accessions", "") or kwargs.get("accession", ""))
        output_format = str(kwargs.get("output_format", "") or kwargs.get("format", "") or "fastq").lower()
        split_files = coerce_bool(kwargs.get("split_files", False))
        skip_technical = coerce_bool(kwargs.get("skip_technical", True))
        continue_on_error = coerce_bool(kwargs.get("continue_on_error", False))
        threads = int(kwargs.get("threads", 6))
        output_dir = node_output_dir(self, context)
        downloaded_files: list[str] = []
        reports: list[dict[str, Any]] = []
        fatal_error = ""

        for accession in accessions:
            report: dict[str, Any] = {"accession": accession, "status": "pending", "files": []}
            try:
                prefetch_command = self.render_prefetch_command(accession, output_dir)
                prefetch_result = await run_command(prefetch_command, output_dir, context)
                if prefetch_result["returncode"] != 0:
                    report["status"] = "prefetch_failed"
                    report["error"] = prefetch_result["stderr"]
                else:
                    dump_command = self.render_fasterq_command(
                        accession=accession,
                        output_dir=output_dir,
                        output_format=output_format,
                        split_files=split_files,
                        skip_technical=skip_technical,
                        threads=threads,
                    )
                    dump_result = await run_command(dump_command, output_dir, context)
                    if dump_result["returncode"] != 0:
                        report["status"] = "dump_failed"
                        report["error"] = dump_result["stderr"]
                    else:
                        files = collect_output_files(output_dir, accession, output_format)
                        if not files:
                            report["status"] = "missing_output"
                            report["error"] = "fasterq-dump completed without producing expected files"
                        else:
                            report["status"] = "completed"
                            report["files"] = files
                            downloaded_files.extend(files)
            except Exception as exc:
                report["status"] = "error"
                report["error"] = str(exc)

            reports.append(report)
            if report["status"] != "completed" and not continue_on_error:
                fatal_error = f"{accession}: {report.get('error', report['status'])}"
                break

        report_payload = {
            "tool_version": SRA_TOOLKIT_VERSION,
            "output_format": output_format,
            "continue_on_error": continue_on_error,
            "requested_accessions": accessions,
            "completed_accessions": [report["accession"] for report in reports if report["status"] == "completed"],
            "files": downloaded_files,
            "runs": reports,
        }
        report_path = output_dir / "download_report.json"
        report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        if fatal_error:
            raise RuntimeError(f"SRA Download failed for {fatal_error}; report: {report_path}")
        return {
            "outputs": {
                "files": downloaded_files,
                "download_report": str(report_path),
            }
        }
