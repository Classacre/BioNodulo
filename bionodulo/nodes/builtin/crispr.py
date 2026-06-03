"""CRISPR and genome-editing workflow nodes."""
from __future__ import annotations

import csv
from pathlib import Path
import re
from typing import Any

from bionodulo.nodes.base import BaseNode
from bionodulo.nodes.command_node import CommandNode


_IUPAC_PAM: dict[str, set[str]] = {
    "A": {"A"},
    "C": {"C"},
    "G": {"G"},
    "T": {"T"},
    "N": {"A", "C", "G", "T", "N"},
}


def _read_fasta(path: Path) -> dict[str, str]:
    records: dict[str, list[str]] = {}
    current: str | None = None
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(">"):
                current = stripped[1:].split()[0]
                records.setdefault(current, [])
            elif current is None:
                raise ValueError(f"FASTA sequence found before header in {path}")
            else:
                records[current].append(stripped.upper())
    return {name: "".join(parts) for name, parts in records.items()}


def _reverse_complement(sequence: str) -> str:
    return sequence.translate(str.maketrans("ACGTNacgtn", "TGCANtgcan"))[::-1].upper()


def _pam_matches(sequence: str, pam: str) -> bool:
    if len(sequence) != len(pam):
        return False
    return all(base in _IUPAC_PAM[pam_base] for base, pam_base in zip(sequence.upper(), pam, strict=True))


def _hamming_distance(left: str, right: str) -> int:
    return sum(a != b for a, b in zip(left.upper(), right.upper(), strict=True))


def _target_region(target: str, records: dict[str, str]) -> tuple[str, int, int]:
    match = re.fullmatch(r"([^:]+)(?::(\d+)-(\d+))?", target.strip())
    if not match:
        raise ValueError("target must be a contig name or contig:start-end region")
    contig = match.group(1)
    if contig not in records:
        raise ValueError(f"Target contig {contig!r} not found in genome")
    start = int(match.group(2) or 1)
    end = int(match.group(3) or len(records[contig]))
    if start < 1 or end < start:
        raise ValueError("target region must use 1-based coordinates with end >= start")
    return contig, start, min(end, len(records[contig]))


def _node_output_dir(node: BaseNode, context: Any) -> Path:
    base = Path(getattr(context, "node_dir", ".") if context else ".")
    out_dir = base / node.NODE_ID
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


class CRISPRESSONode(CommandNode):
    """Analyze CRISPR amplicon editing outcomes with CRISPResso2."""
    NODE_ID = "crispresso2"
    DISPLAY_NAME = "CRISPRESSO2"
    CATEGORY = "crispr"
    DESCRIPTION = "Analyze CRISPR editing from amplicon sequencing. Quantifies indels, frameshifts, allele-specific outcomes."
    SEARCH_ALIASES = ["crispresso", "crispresso2", "crispr", "amplicon", "indel", "editing analysis"]
    RETURN_TYPES = ("HTML_REPORT", "DIRECTORY")
    RETURN_NAMES = ("report", "results_dir")
    REQUIRED_EXECUTABLES = ["CRISPResso"]
    REQUIRED_CONDA_PACKAGES = ["crispresso2"]
    DOCUMENTATION_URL = "https://github.com/pinellolab/CRISPResso2"
    VERSION = "2.3.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        cmd = [
            "CRISPResso",
            "-r1",
            str(inputs.get("r1", "")),
            "-a",
            str(inputs.get("amplicon_seq", "")),
            "-o",
            str(out_dir),
            "--name",
            str(inputs.get("name", "crispresso_run")),
        ]
        if inputs.get("r2"):
            cmd.extend(["-r2", str(inputs["r2"])])
        if inputs.get("guide_seq"):
            cmd.extend(["-g", str(inputs["guide_seq"])])
        if inputs.get("quant_window_center"):
            cmd.extend(["-qc", str(inputs["quant_window_center"])])
        if inputs.get("quant_window_size"):
            cmd.extend(["-w", str(inputs["quant_window_size"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        name = str(inputs.get("name", "crispresso_run"))
        run_name = f"CRISPResso_on_{name}"
        return [node_out / f"{run_name}.html", node_out / run_name]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "r1": ("FASTQ", {"description": "Forward FASTQ"}),
                "amplicon_seq": ("STRING", {"description": "Reference amplicon sequence"}),
                "name": ("STRING", {"default": "crispresso_run"}),
            },
            "optional": {
                "r2": ("FASTQ", {"description": "Reverse FASTQ (paired)"}),
                "guide_seq": ("STRING", {"default": "", "description": "gRNA sequence (20bp)"}),
                "quant_window_center": ("INT", {"default": -3, "min": -20, "max": 20}),
                "quant_window_size": ("INT", {"default": 1, "min": 0, "max": 100}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MAGeCKCountNode(CommandNode):
    """Count sgRNA reads for pooled CRISPR screens with MAGeCK."""
    NODE_ID = "mageck_count"
    DISPLAY_NAME = "MAGeCK Count"
    CATEGORY = "crispr"
    DESCRIPTION = "Count sgRNA reads from FASTQ for pooled CRISPR screens. Normalizes and generates count tables."
    SEARCH_ALIASES = ["mageck", "count", "crispr screen", "sgrna", "pooled screen"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("count_table", "normalized_counts")
    REQUIRED_EXECUTABLES = ["mageck"]
    REQUIRED_CONDA_PACKAGES = ["mageck"]
    DOCUMENTATION_URL = "https://sourceforge.net/p/mageck/wiki/Home/"
    VERSION = "0.5.9"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        prefix = str(inputs.get("output_prefix", "mageck_count"))
        cmd = [
            "mageck",
            "count",
            "-l",
            str(inputs.get("library_file", "")),
            "-n",
            f"{out_dir}/{prefix}",
        ]
        fastq_files = inputs.get("fastq_files", [])
        if isinstance(fastq_files, str):
            fastq_files = [fastq_files] if fastq_files else []
        if fastq_files:
            cmd.append("--fastq")
            cmd.extend(str(fastq) for fastq in fastq_files)
        sample_labels = inputs.get("sample_labels", "")
        if isinstance(sample_labels, (list, tuple)):
            sample_labels = ",".join(str(label) for label in sample_labels)
        if sample_labels:
            cmd.extend(["--sample-label", str(sample_labels)])
        if inputs.get("day0_label"):
            cmd.extend(["--day0-label", str(inputs["day0_label"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "mageck_count"))
        return [node_out / f"{prefix}.count.txt", node_out / f"{prefix}.count_normalized.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "library_file": ("FILE", {"description": "Library file with sgRNA sequences"}),
                "fastq_files": ("FASTQ_LIST", {"description": "FASTQ files from screen"}),
                "output_prefix": ("STRING", {"default": "mageck_count"}),
            },
            "optional": {
                "sample_labels": ("STRING", {"default": "", "description": "Comma-separated labels"}),
                "day0_label": ("STRING", {"default": "", "description": "Day 0 label for normalization"}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class MAGeCKTestNode(CommandNode):
    """Rank CRISPR screen genes from MAGeCK count tables."""
    NODE_ID = "mageck_test"
    DISPLAY_NAME = "MAGeCK Test"
    CATEGORY = "crispr"
    DESCRIPTION = "Identify essential genes from CRISPR screens using negative binomial model. Treatment vs control."
    SEARCH_ALIASES = ["mageck", "test", "crispr screen", "essential genes", "gene ranking"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("gene_summary", "sgrna_summary")
    REQUIRED_EXECUTABLES = ["mageck"]
    REQUIRED_CONDA_PACKAGES = ["mageck"]
    DOCUMENTATION_URL = "https://sourceforge.net/p/mageck/wiki/Home/"
    VERSION = "0.5.9"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = inputs.get("output", ".")
        prefix = str(inputs.get("output_prefix", "mageck_test"))
        cmd = [
            "mageck",
            "test",
            "-k",
            str(inputs.get("count_table", "")),
            "-t",
            str(inputs.get("treatment_labels", "")),
            "-c",
            str(inputs.get("control_labels", "")),
            "-n",
            f"{out_dir}/{prefix}",
        ]
        if inputs.get("norm_method"):
            cmd.extend(["--norm-method", str(inputs["norm_method"])])
        if inputs.get("adjust_method"):
            cmd.extend(["--adjust-method", str(inputs["adjust_method"])])
        if inputs.get("sort_criteria"):
            cmd.extend(["--sort-criteria", str(inputs["sort_criteria"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        prefix = str(inputs.get("output_prefix", "mageck_test"))
        return [node_out / f"{prefix}.gene_summary.txt", node_out / f"{prefix}.sgrna_summary.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "count_table": ("TSV", {"description": "MAGeCK count table"}),
                "treatment_labels": ("STRING", {"description": "Treatment sample labels (comma)"}),
                "control_labels": ("STRING", {"description": "Control sample labels (comma)"}),
                "output_prefix": ("STRING", {"default": "mageck_test"}),
            },
            "optional": {
                "norm_method": ("STRING", {"default": "median", "options": ["median", "total", "control", "none"]}),
                "adjust_method": ("STRING", {"default": "fdr", "options": ["fdr", "holm", "pounds"]}),
                "sort_criteria": ("STRING", {"default": "neg", "options": ["neg", "pos"]}),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class CasOffinderNode(CommandNode):
    """Detect candidate CRISPR guide off-target sites with Cas-OFFinder."""
    NODE_ID = "cas_offinder"
    DISPLAY_NAME = "Cas-OFFinder"
    CATEGORY = "crispr"
    DESCRIPTION = "Fast off-target detection for CRISPR gRNAs. Multiple PAMs and mismatch tolerance."
    SEARCH_ALIASES = ["cas-offinder", "off target", "crispr safety", "grna", "guide rna"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("offtarget_sites",)
    REQUIRED_EXECUTABLES = ["cas-offinder"]
    REQUIRED_CONDA_PACKAGES = ["cas-offinder"]
    DOCUMENTATION_URL = "https://github.com/snugel/cas-offinder"
    VERSION = "2.4.1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        out_dir = Path(str(inputs.get("output", ".")))
        out_dir.mkdir(parents=True, exist_ok=True)
        input_file = out_dir / "cas_offinder_input.txt"
        output_file = out_dir / "offtarget_sites.txt"
        guide_seq = str(inputs.get("guide_seq", ""))
        pam_sequence = str(inputs.get("pam_sequence", "NNG"))
        search_pattern = f"{'N' * len(guide_seq)}{pam_sequence}"
        query_sequence = f"{guide_seq}{pam_sequence}"

        input_file.write_text(
            "\n".join([
                str(inputs.get("genome_fasta", "")),
                search_pattern,
                f"{query_sequence} {inputs.get('mismatches', 3)}",
            ])
            + "\n",
            encoding="utf-8",
        )
        return [
            "cas-offinder",
            str(input_file),
            str(inputs.get("device", "C")),
            str(output_file),
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "offtarget_sites.txt"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "guide_seq": ("STRING", {"description": "Guide RNA sequence without PAM"}),
                "genome_fasta": ("FASTA", {"description": "Target genome FASTA or 2bit directory"}),
                "mismatches": ("INT", {"default": 3, "min": 0, "max": 10}),
            },
            "optional": {
                "pam_sequence": ("STRING", {"default": "NNG", "description": "PAM pattern (N=wildcard)"}),
                "device": (
                    "STRING",
                    {"default": "C", "options": ["C", "G", "A"], "description": "C=CPU, G=GPU, A=accelerator"},
                ),
            },
            "hidden": {
                "output": ("STRING", {}),
            },
        }


class GuideRNADesignNode(BaseNode):
    """Design CRISPR/Cas9 guide RNAs from a target region."""

    NODE_ID = "guide_rna_design"
    DISPLAY_NAME = "Guide RNA Design"
    CATEGORY = "crispr"
    DESCRIPTION = "Design guide RNAs for CRISPR/Cas9 targeting a region or gene."
    SEARCH_ALIASES = ["guide rna", "grna", "sgrna", "cas9", "crispr design", "pam", "off target"]
    RETURN_TYPES = ("TSV", "TSV")
    RETURN_NAMES = ("guides", "off_targets")
    REQUIRES_EXTERNAL_TOOLS = False
    REQUIRED_CONDA_PACKAGES = ["biopython"]
    DOCUMENTATION_URL = "https://biopython.org/"
    VERSION = "1.0.0"

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "target": ("STRING", {"description": "Target contig or contig:start-end region"}),
                "pam": ("STRING", {"default": "NGG", "description": "PAM pattern using A/C/G/T/N"}),
                "genome": ("FASTA", {"description": "Genome FASTA"}),
            },
            "optional": {
                "guide_length": ("INT", {"default": 20, "min": 1, "max": 40}),
                "max_guides": ("INT", {"default": 50, "min": 1, "max": 1000}),
                "mismatches": ("INT", {"default": 3, "min": 0, "max": 10}),
            },
            "hidden": {},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        if int(inputs.get("guide_length", 20) or 0) <= 0:
            return "guide_length must be greater than zero"
        if int(inputs.get("max_guides", 50) or 0) <= 0:
            return "max_guides must be greater than zero"
        if int(inputs.get("mismatches", 3) or 0) < 0:
            return "mismatches must be zero or greater"
        pam = str(inputs.get("pam", "NGG") or "NGG").upper()
        if not pam or any(base not in _IUPAC_PAM for base in pam):
            return "pam may only contain A, C, G, T, or N"
        return True

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "guides.tsv", node_out / "off_targets.tsv"]

    async def run(self, **kwargs: Any) -> tuple[str, str]:
        context = kwargs.pop("context", None)
        validation = self.VALIDATE_INPUTS(kwargs)
        if validation is not True:
            raise ValueError(str(validation))

        target = str(kwargs["target"])
        pam = str(kwargs.get("pam", "NGG") or "NGG").upper()
        guide_length = int(kwargs.get("guide_length", 20) or 20)
        max_guides = int(kwargs.get("max_guides", 50) or 50)
        max_mismatches = int(kwargs.get("mismatches", 3) or 3)
        records = _read_fasta(Path(str(kwargs["genome"])))
        target_contig, target_start, target_end = _target_region(target, records)
        target_slice = records[target_contig][target_start - 1:target_end]

        guides = self._find_guides(target_slice, target_contig, target_start, pam, guide_length, max_guides, target)
        off_targets = self._find_off_targets(guides, records, pam, guide_length, max_mismatches)

        off_target_counts: dict[str, int] = {}
        for off_target in off_targets:
            off_target_counts[off_target["guide_id"]] = off_target_counts.get(off_target["guide_id"], 0) + 1
        for guide in guides:
            guide["off_target_count"] = str(off_target_counts.get(guide["guide_id"], 0))

        output_dir = _node_output_dir(self, context)
        guides_path = output_dir / "guides.tsv"
        off_targets_path = output_dir / "off_targets.tsv"
        self._write_tsv(
            guides_path,
            ["guide_id", "sequence", "pam", "contig", "start", "end", "strand", "gc_content", "target", "off_target_count"],
            guides,
        )
        self._write_tsv(
            off_targets_path,
            ["guide_id", "sequence", "contig", "start", "end", "strand", "pam", "mismatches"],
            off_targets,
        )
        return (str(guides_path), str(off_targets_path))

    @classmethod
    def _find_guides(
        cls,
        sequence: str,
        contig: str,
        region_start: int,
        pam: str,
        guide_length: int,
        max_guides: int,
        target: str,
    ) -> list[dict[str, str]]:
        guides: list[dict[str, str]] = []
        pam_length = len(pam)
        for offset in range(0, len(sequence) - guide_length - pam_length + 1):
            guide_sequence = sequence[offset:offset + guide_length].upper()
            pam_sequence = sequence[offset + guide_length:offset + guide_length + pam_length].upper()
            if not _pam_matches(pam_sequence, pam):
                continue
            guides.append({
                "guide_id": f"guide_{len(guides) + 1}",
                "sequence": guide_sequence,
                "pam": pam_sequence,
                "contig": contig,
                "start": str(region_start + offset),
                "end": str(region_start + offset + guide_length + pam_length - 1),
                "strand": "+",
                "gc_content": f"{cls._gc_content(guide_sequence):.2f}",
                "target": target,
                "off_target_count": "0",
            })
            if len(guides) >= max_guides:
                break
        return guides

    @classmethod
    def _find_off_targets(
        cls,
        guides: list[dict[str, str]],
        records: dict[str, str],
        pam: str,
        guide_length: int,
        max_mismatches: int,
    ) -> list[dict[str, str]]:
        off_targets: list[dict[str, str]] = []
        pam_length = len(pam)
        for guide in guides:
            guide_sequence = guide["sequence"]
            guide_contig = guide["contig"]
            guide_start = int(guide["start"])
            for contig, sequence in records.items():
                for offset in range(0, len(sequence) - guide_length - pam_length + 1):
                    candidate = sequence[offset:offset + guide_length].upper()
                    candidate_pam = sequence[offset + guide_length:offset + guide_length + pam_length].upper()
                    cls._append_off_target(
                        off_targets,
                        guide,
                        guide_sequence,
                        guide_contig,
                        guide_start,
                        contig,
                        offset,
                        candidate,
                        candidate_pam,
                        pam,
                        "+",
                        guide_length,
                        pam_length,
                        max_mismatches,
                    )
                    reverse_candidate = _reverse_complement(sequence[offset:offset + guide_length])
                    reverse_pam = _reverse_complement(sequence[offset + guide_length:offset + guide_length + pam_length])
                    cls._append_off_target(
                        off_targets,
                        guide,
                        guide_sequence,
                        guide_contig,
                        guide_start,
                        contig,
                        offset,
                        reverse_candidate,
                        reverse_pam,
                        pam,
                        "-",
                        guide_length,
                        pam_length,
                        max_mismatches,
                    )
        return off_targets

    @staticmethod
    def _append_off_target(
        off_targets: list[dict[str, str]],
        guide: dict[str, str],
        guide_sequence: str,
        guide_contig: str,
        guide_start: int,
        contig: str,
        offset: int,
        candidate: str,
        candidate_pam: str,
        pam: str,
        strand: str,
        guide_length: int,
        pam_length: int,
        max_mismatches: int,
    ) -> None:
        if not _pam_matches(candidate_pam, pam):
            return
        mismatches = _hamming_distance(guide_sequence, candidate)
        if mismatches > max_mismatches:
            return
        start = offset + 1
        if contig == guide_contig and start == guide_start and strand == "+":
            return
        off_targets.append({
            "guide_id": guide["guide_id"],
            "sequence": candidate,
            "contig": contig,
            "start": str(start),
            "end": str(offset + guide_length + pam_length),
            "strand": strand,
            "pam": candidate_pam,
            "mismatches": str(mismatches),
        })

    @staticmethod
    def _gc_content(sequence: str) -> float:
        if not sequence:
            return 0.0
        return 100 * sum(base in {"G", "C"} for base in sequence.upper()) / len(sequence)

    @staticmethod
    def _write_tsv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
