"""Pinned NCBI BLAST+ subject-search operation with Biopython XML previewing."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .adapter import (
    BIOPYTHON_PACKAGE_CONSTRAINTS,
    BiopythonNode,
    node_output_dir,
    validate_choice,
    validate_path,
    write_summary_preview,
)


BLAST_VERSION = "2.17.0"
BLAST_GIT_URL = "https://github.com/ncbi/ncbi-cxx-toolkit-public.git"
BLAST_GIT_COMMIT = "db5563aefe2290e580da9a841950832ea3e89274"
BLAST_SOURCE_URL = (
    "https://github.com/ncbi/ncbi-cxx-toolkit-public/tree/"
    "db5563aefe2290e580da9a841950832ea3e89274"
)
BLAST_SOURCE_FILE_SHA256 = {
    "src/algo/blast/core/blast_engine.c": (
        "d4d27cd407135aab77bf14d0d185e2f1bad4b3f295a0cc5d0c8ff8eeca680238"
    ),
    "src/algo/blast/blastinput/blast_args.cpp": (
        "54ac1dcbfd6f06011f600ec59113a1f03fa2cdb3a9eb59c782cdff137575c676"
    ),
    "src/app/blast/blast_app_util.hpp": (
        "ef49a86de6066ec104fc9bc0ccdf237bcaef0fe798f846da52d90ef069148cba"
    ),
}


class BLASTSearchNode(BiopythonNode):
    """Run one local BLAST+ query-versus-subject search and return XML."""

    NODE_ID = "bp_blast"
    DISPLAY_NAME = "BLAST Search"
    DESCRIPTION = "Run a local NCBI BLAST+ query-versus-subject search and emit BLAST XML."
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "NCBI",
        "BLAST+",
        "blastn",
        "blastp",
        "sequence similarity",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("blast_xml",)
    REQUIRES_EXTERNAL_TOOLS = True
    REQUIRED_CONDA_PACKAGES = ["biopython", "blast"]
    CONDA_PACKAGE_CONSTRAINTS = {
        "biopython": BIOPYTHON_PACKAGE_CONSTRAINTS[0].split("==", 1)[1],
        "blast": BLAST_VERSION,
    }
    PACKAGE_CONSTRAINTS = (*BIOPYTHON_PACKAGE_CONSTRAINTS, f"blast=={BLAST_VERSION}")
    PACKAGE_CONSTRAINT = "; ".join(PACKAGE_CONSTRAINTS)
    PROGRAMS = ("blastn", "blastp", "blastx", "tblastn", "tblastx")
    REQUIRED_EXECUTABLES = list(PROGRAMS)
    VERSION = BLAST_VERSION
    RUNTIME_VERSION = BLAST_VERSION
    GIT_URL = BLAST_GIT_URL
    GIT_COMMIT = BLAST_GIT_COMMIT
    SOURCE_URL = BLAST_SOURCE_URL
    SOURCE_REF = "blast-2.17.0"
    SOURCE_PATHS = tuple(BLAST_SOURCE_FILE_SHA256)
    SOURCE_FILE_SHA256 = BLAST_SOURCE_FILE_SHA256
    DOCUMENTATION_URL = "https://www.ncbi.nlm.nih.gov/books/NBK279684/"
    UPSTREAM_SOURCE = "; ".join(SOURCE_PATHS)
    AUDIT_STATUS = "contract-checked-with-synthetic-argv-no-real-blast-execution"
    UPSTREAM_DEFAULTS = {"evalue": 10.0, "max_target_seqs": 500, "outfmt": "0"}
    WRAPPER_DEFAULTS = {"evalue": 0.001, "max_target_seqs": 10, "outfmt": "5"}
    OUTPUT_SEMANTICS = (
        "The node uses -subject rather than a formatted BLAST database and exposes only "
        "outfmt 5 (legacy BLAST XML). A successful artifact must exist and be non-empty."
    )
    EXIT_CODES = {
        0: "success",
        1: "input query or options error",
        2: "database or subject error",
        3: "BLAST engine error",
        4: "out of memory",
        5: "network error",
        6: "output write error",
        255: "unknown error",
    }
    EXIT_SEMANTICS = (
        "BLAST+ exit codes 1, 2, 3, 4, 5, 6, and 255 identify input/options, "
        "database/subject, engine, memory, network, output, and unknown failures. "
        "Every non-zero exit is fatal and any partial XML is removed."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "query": ("FASTA", {"label": "Query FASTA"}),
                "subject": ("FASTA", {"label": "Subject FASTA"}),
                "program": (
                    "STRING",
                    {
                        "default": "blastn",
                        "options": list(cls.PROGRAMS),
                        "label": "BLAST Program",
                    },
                ),
            },
            "optional": {
                "evalue": (
                    "FLOAT",
                    {
                        "default": 0.001,
                        "min": 0.0,
                        "step": 0.001,
                        "label": "E-value threshold",
                        "advanced": True,
                    },
                ),
                "max_hits": (
                    "INT",
                    {
                        "default": 10,
                        "min": 1,
                        "label": "Max Hits",
                        "description": "Passed to BLAST+ as -max_target_seqs",
                        "advanced": True,
                    },
                ),
                "outfmt": (
                    "STRING",
                    {
                        "default": "5",
                        "options": ["5"],
                        "label": "XML Output Format",
                        "advanced": True,
                    },
                ),
            },
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for key in ("query", "subject"):
            validation = validate_path(inputs.get(key), key)
            if validation is not True:
                return validation
        validation = validate_choice(inputs.get("program", "blastn"), "program", cls.PROGRAMS)
        if validation is not True:
            return validation
        if str(inputs.get("outfmt", "5")) != "5":
            return "Input 'outfmt' must be 5 because this node exposes BLAST XML"
        try:
            evalue = float(inputs.get("evalue", 0.001))
            max_hits = int(inputs.get("max_hits", 10))
        except (TypeError, ValueError):
            return "Inputs 'evalue' and 'max_hits' must be numeric"
        if evalue < 0:
            return "Input 'evalue' must be non-negative"
        if max_hits < 1:
            return "Input 'max_hits' must be at least 1"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, ...]:
        context = kwargs.pop("context", None)
        self.__class__.require_valid_inputs(kwargs)
        output_dir = node_output_dir(self.NODE_ID, context)
        output_path = output_dir / "blast_result.xml"
        output_path.unlink(missing_ok=True)

        program = str(kwargs.get("program", "blastn"))
        command = [
            program,
            "-query",
            str(kwargs["query"]),
            "-subject",
            str(kwargs["subject"]),
            "-evalue",
            str(kwargs.get("evalue", 0.001)),
            "-max_target_seqs",
            str(kwargs.get("max_hits", 10)),
            "-outfmt",
            "5",
            "-out",
            str(output_path.resolve()),
        ]

        succeeded = False
        try:
            if context is not None and hasattr(context, "run_command"):
                result = await context.run_command(command, cwd=str(output_dir))
            else:
                process = await asyncio.create_subprocess_exec(
                    *command,
                    cwd=str(output_dir),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                result = {
                    "returncode": process.returncode,
                    "stdout": stdout.decode(errors="replace"),
                    "stderr": stderr.decode(errors="replace"),
                }

            returncode = int(result.get("returncode", 0))
            if returncode != 0:
                label = self.EXIT_CODES.get(returncode, "unrecognized error")
                stderr = str(result.get("stderr", "")).strip()
                detail = f": {stderr}" if stderr else ""
                raise RuntimeError(f"BLAST failed with exit code {returncode} ({label}){detail}")
            if not output_path.is_file() or output_path.stat().st_size == 0:
                raise RuntimeError(
                    f"BLAST completed without producing non-empty {output_path.name}"
                )

            self._register_hits_preview(context, output_dir, output_path, program)
            succeeded = True
            return (str(output_path),)
        finally:
            if not succeeded:
                output_path.unlink(missing_ok=True)

    @staticmethod
    def _register_hits_preview(
        context: Any,
        output_dir: Path,
        output_path: Path,
        program: str,
    ) -> None:
        """Summarize valid XML without making preview parsing part of execution."""

        rows: list[list[Any]] = []
        try:
            from Bio.Blast import NCBIXML

            with output_path.open(encoding="utf-8") as handle:
                for record in NCBIXML.parse(handle):
                    query = record.query.split()[0] if record.query else "query"
                    for alignment in record.alignments:
                        for hsp in alignment.hsps:
                            identity = (
                                100.0 * hsp.identities / hsp.align_length
                                if hsp.align_length
                                else 0.0
                            )
                            rows.append(
                                [
                                    query,
                                    alignment.hit_id or alignment.hit_def.split()[0],
                                    f"{identity:.1f}%",
                                    f"{hsp.expect:.1e}",
                                    f"{hsp.score:g}",
                                ]
                            )
        except Exception:  # noqa: BLE001 - preview failure cannot invalidate BLAST XML
            rows = []

        write_summary_preview(
            context,
            output_dir,
            title=f"BLAST ({program}) — {len(rows)} hit(s)",
            note=f"BLAST XML (outfmt 5) · {output_path.name}",
            columns=["Query", "Subject", "% identity", "E-value", "Score"],
            rows=rows[:50],
            label="BLAST Hits",
        )
