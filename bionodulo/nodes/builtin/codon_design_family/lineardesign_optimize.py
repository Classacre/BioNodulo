"""Run the LinearDesign dynamic-programming mRNA design tool (not bundled)."""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from .adapter import (
    DNA_ALPHABET,
    CodonDesignNode,
    STOP_CODONS,
    gc_fraction,
    codons_of,
    read_sequence_input,
    require_dna_cds,
    translate_cds,
    validate_sequence_literal,
    wrap_sequence,
    write_json,
)

REPO_URL = "https://github.com/LinearDesignSoftware/LinearDesign"
DEFAULT_COMMIT = "f0126ca89a8b853088b4bccfd2cc8c378d3678be"
BINARY_NAME = "lineardesign"
ENV_CHECKOUT_DIR = "BIONODULO_LINEARDESIGN_DIR"
FASTA_LINE_WIDTH = 60

LICENSE_CONSTRAINT = (
    "LinearDesign is NOT redistributed with BioNodulo: its license permits academic and research "
    "use but prohibits redistribution of the code without written permission, so this node clones "
    "the official repository at run time and your usage must comply with that license."
)

SEQUENCE_LINE_RE = re.compile(r"^mRNA sequence:\s*([A-Za-z]+)\s*$")
ENERGY_LINE_RE = re.compile(
    r"^mRNA folding free energy:\s*(-?\d+(?:\.\d+)?)\s*kcal/mol;\s*mRNA CAI:\s*(\d+(?:\.\d+)?)\s*$"
)


def build_command(binary_path: Path, lambda_param: float) -> list[str]:
    return [str(binary_path), "--lambda", str(lambda_param)]


def parse_lineardesign_stdout(stdout: str) -> list[dict[str, Any]]:
    """Parse LinearDesign stdout (single- or multi-record) into designed records."""
    records: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None

    def ensure_current() -> dict[str, Any]:
        nonlocal current
        if current is None:
            current = {"id": f"seq{len(records) + 1}"}
        return current

    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(">"):
            if current is not None and current.get("mrna"):
                records.append(current)
            current = {"id": line[1:].strip().split()[0] if len(line) > 1 else f"seq{len(records) + 1}"}
            continue
        sequence_match = SEQUENCE_LINE_RE.match(line)
        if sequence_match:
            ensure_current()["mrna"] = sequence_match.group(1).upper()
            continue
        energy_match = ENERGY_LINE_RE.match(line)
        if energy_match:
            record = ensure_current()
            record["mfe_kcal_mol"] = float(energy_match.group(1))
            record["cai"] = float(energy_match.group(2))
            continue
        if line.startswith("mRNA structure:"):
            ensure_current()["structure"] = line.split(":", 1)[1].strip()
    if current is not None and current.get("mrna"):
        records.append(current)
    if not records:
        raise ValueError(f"LinearDesign stdout contained no designed mRNA sequence lines: {stdout[:200]!r}")
    for record in records:
        record["cds"] = record.pop("mrna").replace("U", "T")
    return records


class LinearDesignOptimizeNode(CodonDesignNode):
    """Translate a CDS to protein and run LinearDesign on it."""

    NODE_ID = "lineardesign_optimize"
    DISPLAY_NAME = "LinearDesign Optimize"
    DESCRIPTION = (
        "Translate one CDS to its protein and run LinearDesign (Zhang et al. 2023), the "
        "dynamic-programming mRNA design algorithm balancing MFE and CAI via --lambda, "
        "mirroring the README usage `cat FASTA_FILE | ./lineardesign --lambda L` on a protein "
        "FASTA fed through stdin. A single terminal stop codon is stripped before translation; "
        "internal stop codons are rejected. " + LICENSE_CONSTRAINT
    )
    SEARCH_ALIASES = [
        "BioNodulo builtin",
        "LinearDesign",
        "mRNA design",
        "MFE",
        "CAI",
        "codon optimization",
        "dynamic programming",
        "vaccine design",
    ]
    RETURN_TYPES = ("FASTA", "JSON")
    RETURN_NAMES = ("designed_cds", "report")
    OUTPUT_FILENAMES = ("designed_cds.fasta", "lineardesign_report.json")
    REQUIRES_EXTERNAL_TOOLS = True
    DOCUMENTATION_URL = "https://github.com/LinearDesignSoftware/LinearDesign"
    CITATION_DOIS = ["10.1038/s41586-023-06127-z"]
    CITATION_URLS = ["https://doi.org/10.1038/s41586-023-06127-z"]
    CITATION_TEXT = "Algorithm for optimized mRNA design improves stability and immunogenicity."

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "cds": (
                    "STRING",
                    {"multiline": True, "default": "", "description": "CDS sequence, or a path to a FASTA/plain CDS file"},
                ),
            },
            "optional": {
                "lambda_param": (
                    "FLOAT",
                    {"default": 1.0, "min": 0.0, "max": 10000.0, "description": "LinearDesign lambda balancing MFE and CAI"},
                ),
                "gc_target": (
                    "FLOAT",
                    {
                        "default": None,
                        "min": 0.0,
                        "max": 1.0,
                        "description": "Advisory only: LinearDesign has no GC flag; the designed CDS GC is reported",
                    },
                ),
                "commit": (
                    "STRING",
                    {
                        "default": DEFAULT_COMMIT,
                        "description": "LinearDesign checkout pinned to this commit; 'main' tracks the cloned main HEAD",
                    },
                ),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if not str(inputs.get("cds", "") or "").strip():
            return "Input 'cds' must be a non-empty sequence or file path"
        validation = validate_sequence_literal(
            inputs.get("cds"), "cds", alphabet=DNA_ALPHABET, divisible_by_3=True
        )
        if validation is not True:
            return validation
        validation = cls.validate_float(inputs.get("lambda_param", 1.0), "lambda_param", minimum=0.0, maximum=10000.0)
        if validation is not True:
            return validation
        gc_target = inputs.get("gc_target")
        if gc_target is not None:
            validation = cls.validate_float(gc_target, "gc_target", minimum=0.0, maximum=1.0)
            if validation is not True:
                return validation
        if not str(inputs.get("commit", DEFAULT_COMMIT) or "").strip():
            return "Input 'commit' must be 'main' or a commit hash"
        return True

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))
        context = kwargs.get("context")
        cds = require_dna_cds(read_sequence_input(kwargs.get("cds"), "cds"), "cds")
        codon_list = codons_of(cds)
        if codon_list and codon_list[-1] in STOP_CODONS:
            codon_list = codon_list[:-1]
        protein = translate_cds("".join(codon_list))
        if "*" in protein:
            raise ValueError(
                f"Input 'cds' contains an internal stop codon at protein position {protein.index('*') + 1}"
            )
        lambda_param = float(kwargs.get("lambda_param", 1.0))
        pinned_commit = str(kwargs.get("commit", DEFAULT_COMMIT) or DEFAULT_COMMIT).strip()

        node_dir = Path(getattr(context, "node_dir", ".") if context else ".")
        protein_fasta = node_dir / "protein.fasta"
        protein_fasta.parent.mkdir(parents=True, exist_ok=True)
        protein_fasta.write_text(
            "".join(
                [">protein\n", *[f"{protein[offset:offset + 60]}\n" for offset in range(0, len(protein), 60)]]
            ),
            encoding="utf-8",
        )

        checkout = self._resolve_checkout(node_dir, pinned_commit)
        binary = checkout / BINARY_NAME
        if not binary.is_file():
            if sys.platform != "linux":
                raise RuntimeError(
                    "Linux worker required: the LinearDesign repository ships a prebuilt Linux "
                    f"binary and none was found at {binary}. Point BIONODULO_LINEARDESIGN_DIR at a "
                    "checkout containing a locally built 'lineardesign' executable to run elsewhere."
                )
            raise RuntimeError(
                f"LinearDesign binary not found at {binary}; build it with 'make' inside the checkout"
            )

        command = build_command(binary, lambda_param)
        completed = subprocess.run(
            command,
            input=protein_fasta.read_text(encoding="utf-8"),
            capture_output=True,
            text=True,
            cwd=str(checkout),
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(
                f"LinearDesign failed with exit code {completed.returncode}: {completed.stderr.strip()[:500]}"
            )
        records = parse_lineardesign_stdout(completed.stdout)

        designed_records = [(record["id"], record["cds"]) for record in records]
        fasta_path = self.node_output_path(context, "designed_cds.fasta")
        lines: list[str] = []
        for identifier, sequence in designed_records:
            lines.append(f">{identifier}")
            lines.extend(wrap_sequence(sequence, FASTA_LINE_WIDTH))
        fasta_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report = {
            "lambda": lambda_param,
            "gc_target": None if kwargs.get("gc_target") is None else float(kwargs.get("gc_target")),
            "commit": pinned_commit,
            "checkout_dir": str(checkout),
            "command": command,
            "protein_length": len(protein),
            "input_cds_length_nt": len(cds),
            "records": [
                {
                    "id": record["id"],
                    "cds": record["cds"],
                    "cds_length_nt": len(record["cds"]),
                    "gc": gc_fraction(record["cds"]),
                    "mfe_kcal_mol": record.get("mfe_kcal_mol"),
                    "cai": record.get("cai"),
                    "structure": record.get("structure"),
                }
                for record in records
            ],
            "raw_stdout": completed.stdout,
            "raw_stderr": completed.stderr,
            "license_constraint": LICENSE_CONSTRAINT,
        }
        report_path = self.node_output_path(context, "lineardesign_report.json")
        write_json(report_path, report)
        return (str(fasta_path), str(report_path))

    @staticmethod
    def _resolve_checkout(node_dir: Path, pinned_commit: str) -> Path:
        env_dir = os.environ.get(ENV_CHECKOUT_DIR, "").strip()
        if env_dir:
            candidate = Path(env_dir).expanduser()
            if not candidate.is_dir():
                raise ValueError(f"{ENV_CHECKOUT_DIR} does not point at a directory: {candidate}")
            return candidate
        checkout = node_dir / "lineardesign_optimize" / "LinearDesign"
        if not checkout.is_dir():
            checkout.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                ["git", "clone", "--depth", "1", REPO_URL, str(checkout)],
                check=True,
                capture_output=True,
                text=True,
            )
        if pinned_commit not in ("", "main", "HEAD"):
            subprocess.run(
                ["git", "-C", str(checkout), "fetch", "--depth", "1", "origin", pinned_commit],
                check=True,
                capture_output=True,
                text=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "checkout", "--detach", pinned_commit],
                check=True,
                capture_output=True,
                text=True,
            )
        return checkout
