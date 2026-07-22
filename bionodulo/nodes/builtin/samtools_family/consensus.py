"""Focused Samtools 1.23.1 owner: Generate a consensus sequence from SAM/BAM/CRAM alignments."""

from __future__ import annotations

from pathlib import Path

from typing import Any

from bionodulo.nodes.builtin._bam_index import validate_colocated_bam_index
from bionodulo.nodes.builtin._reference_sidecars import (
    validate_colocated_reference_index,
)

from .adapter import (
    SamtoolsCommandNode,
    GALAXY_ALIAS,
    SAMTOOLS_GALAXY_CITATION_DOIS,
    SAMTOOLS_GALAXY_CITATION_TEXT,
    SAMTOOLS_GALAXY_CITATION_URLS,
    _add_if_value,
    _additional_threads,
    _flag_sum,
    TOOLS_IUC_GIT_COMMIT,
    validate_index_pairs,
)


_SIMPLE_DEFAULTS: dict[str, Any] = {
    "use_qual": False,
    "consensus_fraction": 0.75,
    "heterozygous_fraction": 0.15,
}

_BAYESIAN_DEFAULTS: dict[str, Any] = {
    "config": "manual",
    "cutoff": 10,
    "use_mq": True,
    "adjust_mq": True,
    "nm_halo": 50,
    "low_mq": 1,
    "high_mq": 60,
    "scale_mq": 1.0,
    "p_het": 1.0e-03,
    "p_indel": 2.0e-04,
    "het_scale": 1.0,
    "homopoly_fix": False,
    "homopoly_score": None,
    "qual_calibration": "file",
    "qual_calibration_file": None,
}

_MQ_SUBSETTING_DEFAULTS: dict[str, Any] = {
    key: _BAYESIAN_DEFAULTS[key]
    for key in ("adjust_mq", "nm_halo", "low_mq", "high_mq", "scale_mq", "homopoly_fix", "homopoly_score")
}


def _changed_settings(inputs: dict[str, Any], defaults: dict[str, Any]) -> list[str]:
    """Return supplied settings that differ from their inactive-mode defaults."""
    changed: list[str] = []
    for key, default in defaults.items():
        if key not in inputs or inputs[key] in (None, ""):
            continue
        if inputs[key] != default:
            changed.append(key)
    return changed


class SamtoolsConsensusNode(SamtoolsCommandNode):
    """Generate a consensus sequence from SAM/BAM/CRAM alignments."""

    NODE_ID = "samtools_consensus"
    DISPLAY_NAME = "Samtools Consensus"
    REQUIRED_CONDA_PACKAGES = ["samtools"]
    CATEGORY = "samtools"
    DESCRIPTION = "Generate FASTA, FASTQ, or pileup consensus sequence from SAM, BAM, or CRAM alignments."
    SEARCH_ALIASES = [GALAXY_ALIAS, "samtools", "consensus", "Bayesian", "Gap5", "consensus sequence"]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("consensus",)
    REQUIRED_EXECUTABLES = ["samtools"]
    DOCUMENTATION_URL = "https://www.htslib.org/doc/samtools-consensus.html"
    CITATION_DOIS = SAMTOOLS_GALAXY_CITATION_DOIS
    CITATION_URLS = SAMTOOLS_GALAXY_CITATION_URLS
    CITATION_TEXT = SAMTOOLS_GALAXY_CITATION_TEXT
    VERSION = "1.23.1"
    OUTPUT_FILENAMES = ("consensus.fasta",)
    STDOUT_OUTPUT_INDEX = 0
    UPSTREAM_MANPAGE = "doc/samtools-consensus.1"
    UPSTREAM_SOURCE = "bam_consensus.c"
    WRAPPER_SOURCE = "tool_collections/samtools/samtools_consensus/samtools_consensus.xml"
    WRAPPER_GIT_COMMIT = TOOLS_IUC_GIT_COMMIT

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        output_format = cls._output_format(inputs)
        cmd = [
            "samtools",
            "consensus",
            "-f",
            output_format,
            "-@",
            str(_additional_threads(inputs)),
            "--min-MQ",
            str(inputs.get("min_mq", 0)),
            "--min-BQ",
            str(inputs.get("min_bq", 0)),
        ]
        required_flags = _flag_sum(inputs.get("required_flags"))
        skipped_flags = _flag_sum(inputs.get("skipped_flags"))
        if required_flags:
            cmd.extend(["--rf", str(required_flags)])
        # ``--ff 0`` is meaningful: it disables the source default exclusion
        # mask (UNMAP,SECONDARY,QCFAIL,DUP).  Testing only the parsed integer
        # previously dropped that explicit request and silently kept filtering.
        if inputs.get("skipped_flags") not in (None, "", []):
            cmd.extend(["--ff", str(skipped_flags)])

        mode = str(inputs.get("mode", "bayesian"))
        cmd.extend(["-m", mode])
        if mode == "simple":
            cls._append_simple_options(cmd, inputs)
        else:
            cls._append_bayesian_options(cmd, inputs)

        cmd.extend(["--min-depth", str(inputs.get("min_depth", 1))])
        _add_if_value(cmd, "-r", inputs.get("region"))
        _add_if_value(cmd, "-T", inputs.get("reference"))
        _add_if_value(cmd, "--ref-qual", inputs.get("reference_quality"))
        cmd.extend(["-l", str(inputs.get("line_len", 70))])
        if inputs.get("output_all_references"):
            cmd.extend(["-a", "-a"])
        elif inputs.get("output_all"):
            cmd.append("-a")
        cmd.extend(
            [
                "--show-del",
                "yes" if inputs.get("show_deletions") else "no",
                "--show-ins",
                "yes" if inputs.get("show_insertions", True) else "no",
            ]
        )
        if inputs.get("ambig"):
            cmd.append("--ambig")
        if inputs.get("mark_insertions"):
            cmd.append("--mark-ins")
        cmd.append(str(inputs.get("input", inputs.get("bam", ""))))
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / f"consensus.{cls._output_extension(cls._output_format(inputs))}"]

    @classmethod
    def _append_simple_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if inputs.get("use_qual"):
            cmd.append("-q")
        cmd.extend(
            [
                "-c",
                str(inputs.get("consensus_fraction", 0.75)),
                "-H",
                str(inputs.get("heterozygous_fraction", 0.15)),
            ]
        )

    @classmethod
    def _append_bayesian_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        config = str(inputs.get("config", "manual") or "manual")
        if config != "manual":
            cmd.extend(["--config", config])
            return

        cmd.extend(["-C", str(inputs.get("cutoff", 10))])
        if inputs.get("use_mq", True):
            cmd.append("--use-MQ")
            cmd.append("--adj-MQ" if inputs.get("adjust_mq", True) else "--no-adj-MQ")
            cmd.extend(
                [
                    "--NM-halo",
                    str(inputs.get("nm_halo", 50)),
                    "--low-MQ",
                    str(inputs.get("low_mq", 1)),
                    "--high-MQ",
                    str(inputs.get("high_mq", 60)),
                    "--scale-MQ",
                    str(inputs.get("scale_mq", 1.0)),
                ]
            )
        else:
            cmd.append("--no-use-MQ")
        cmd.extend(
            [
                "--P-het",
                str(inputs.get("p_het", 1.0e-03)),
                "--P-indel",
                str(inputs.get("p_indel", 2.0e-04)),
                "--het-scale",
                str(inputs.get("het_scale", 1.0e00)),
            ]
        )
        if inputs.get("homopoly_fix"):
            cmd.append("-p")
        _add_if_value(cmd, "--homopoly-score", inputs.get("homopoly_score"))
        qual_calibration = inputs.get("qual_calibration")
        if qual_calibration and qual_calibration != "file":
            cmd.extend(["--qual-calibration", str(qual_calibration)])
        elif inputs.get("qual_calibration_file"):
            cmd.extend(["--qual-calibration", str(inputs["qual_calibration_file"])])

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        raw_format = str(inputs.get("format", inputs.get("output_format", "fasta")) or "fasta").lower()
        if raw_format in {"fastq", "pileup"}:
            return raw_format
        return "fasta"

    @classmethod
    def _output_extension(cls, output_format: str) -> str:
        return {"fastq": "fastq", "pileup": "pileup"}.get(output_format, "fasta")

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        if inputs.get("reference") or inputs.get("reference_index"):
            validation = validate_colocated_reference_index(inputs)
            if validation is not True:
                return validation
        input_path = str(inputs.get("input", ""))
        is_sam = input_path.lower().endswith(".sam")
        if inputs.get("region"):
            if input_path.lower().endswith(".sam"):
                return "region queries require indexed BAM or CRAM input"
            if input_path.lower().endswith(".cram"):
                validation = validate_index_pairs(
                    inputs,
                    data_key="input",
                    index_key="bam_index",
                    required=True,
                    colocated_suffix=".crai",
                )
            else:
                validation = validate_colocated_bam_index(
                    inputs,
                    bam_key="input",
                    index_key="bam_index",
                )
            if validation is not True:
                return validation
        elif inputs.get("bam_index"):
            if is_sam:
                return "bam_index is not consumed for SAM input"
            if _additional_threads(inputs) == 0:
                return "bam_index is only consumed by a region query or multi-threaded consensus"
            if str(inputs.get("input", "")).lower().endswith(".cram"):
                validation = validate_index_pairs(
                    inputs,
                    data_key="input",
                    index_key="bam_index",
                    required=False,
                    colocated_suffix=".crai",
                )
            else:
                validation = validate_colocated_bam_index(
                    inputs,
                    bam_key="input",
                    index_key="bam_index",
                )
            if validation is not True:
                return validation

        mode = str(inputs.get("mode", "bayesian") or "bayesian")
        config = str(inputs.get("config", "manual") or "manual")
        if mode == "simple":
            changed = _changed_settings(inputs, _BAYESIAN_DEFAULTS)
            if changed:
                return f"{', '.join(changed)} is only valid for Bayesian consensus modes"
        else:
            changed = _changed_settings(inputs, _SIMPLE_DEFAULTS)
            if changed:
                return f"{', '.join(changed)} is only valid for simple consensus mode"

            if mode == "bayesian_116" and config != "manual":
                return (
                    "config presets force Samtools into bayesian mode and cannot be combined "
                    "with bayesian_116"
                )

            if config != "manual":
                manual_changes = _changed_settings(
                    inputs,
                    {key: value for key, value in _BAYESIAN_DEFAULTS.items() if key != "config"},
                )
                if manual_changes:
                    return (
                        f"{', '.join(manual_changes)} is overridden by the selected config preset; "
                        "use config=manual"
                    )

            if not inputs.get("use_mq", True):
                mq_changes = _changed_settings(inputs, _MQ_SUBSETTING_DEFAULTS)
                if mq_changes:
                    return f"{', '.join(mq_changes)} has no effect when use_mq is false"

        output_format = cls._output_format(inputs)
        if output_format == "pileup":
            if inputs.get("mark_insertions"):
                return "mark_insertions is only applied to FASTA or FASTQ output"
            if inputs.get("line_len", 70) != 70:
                return "line_len is only applied to FASTA or FASTQ output"
        if inputs.get("mark_insertions") and not inputs.get("show_insertions", True):
            return "mark_insertions has no effect when show_insertions is false"
        if (
            mode == "simple"
            and inputs.get("heterozygous_fraction", 0.15) != 0.15
            and not inputs.get("ambig")
        ):
            return "heterozygous_fraction requires ambig output in simple mode"
        if inputs.get("output_all_references") and inputs.get("region"):
            return "output_all_references cannot be combined with a region query"
        if inputs.get("reference_quality", 0) != 0:
            if not inputs.get("reference"):
                return "reference_quality requires a reference FASTA"
            if output_format != "fastq":
                return "reference_quality is only represented in FASTQ output"
        if inputs.get("low_mq", 1) > inputs.get("high_mq", 60):
            return "low_mq must be less than or equal to high_mq"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (("SAM", "BAM", "CRAM"), {"description": "SAM, BAM, or CRAM alignment file"}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 64, "display": "slider"}),
            },
            "optional": {
                "bam_index": (
                    "FILE",
                    {"description": "Exact colocated BAI or CRAI required for region queries", "advanced": True},
                ),
                "format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "pileup"],
                        "description": "Consensus output format",
                    },
                ),
                "min_mq": ("INT", {"default": 0, "min": 0, "description": "Minimum mapping quality"}),
                "min_bq": ("INT", {"default": 0, "min": 0, "description": "Minimum base quality"}),
                "required_flags": (
                    "STRING",
                    {"default": "", "description": "Include reads with at least one listed SAM flag", "advanced": True},
                ),
                "skipped_flags": (
                    "STRING",
                    {
                        "default": "",
                        "description": (
                            "Comma-separated SAM flags to exclude; empty uses the Samtools default "
                            "UNMAP,SECONDARY,QCFAIL,DUP, while 0 disables exclusions"
                        ),
                        "advanced": True,
                    },
                ),
                "mode": (
                    "STRING",
                    {
                        "default": "bayesian",
                        "options": ["simple", "bayesian", "bayesian_116"],
                        "description": "Consensus algorithm",
                    },
                ),
                "use_qual": (
                    "BOOLEAN",
                    {"default": False, "description": "Weight simple-mode base counts by base quality"},
                ),
                "consensus_fraction": (
                    "FLOAT",
                    {"default": 0.75, "min": 0, "max": 1, "description": "Simple-mode minimum consensus fraction"},
                ),
                "heterozygous_fraction": (
                    "FLOAT",
                    {"default": 0.15, "min": 0, "max": 1, "description": "Simple-mode heterozygous fraction"},
                ),
                "config": (
                    "STRING",
                    {
                        "default": "manual",
                        "options": ["manual", "hiseq", "hifi", "r10.4_sup", "r10.4_dup", "ultima"],
                        "description": "Bayesian configuration preset",
                    },
                ),
                "cutoff": (
                    "INT",
                    {"default": 10, "min": 0, "max": 93, "description": "Bayesian quality cutoff threshold"},
                ),
                "use_mq": (
                    "BOOLEAN",
                    {"default": True, "description": "Use mapping qualities for Bayesian consensus", "advanced": True},
                ),
                "adjust_mq": (
                    "BOOLEAN",
                    {
                        "default": True,
                        "description": "Adjust mapping quality using nearby mismatches",
                        "advanced": True,
                    },
                ),
                "nm_halo": (
                    "INT",
                    {
                        "default": 50,
                        "min": 1,
                        "description": "Local mismatch window for MQ adjustment",
                        "advanced": True,
                    },
                ),
                "low_mq": ("INT", {"default": 1, "min": 0, "max": 60, "description": "Minimum MQ cap"}),
                "high_mq": ("INT", {"default": 60, "min": 0, "max": 60, "description": "Maximum MQ cap"}),
                "scale_mq": ("FLOAT", {"default": 1.0, "min": 0, "description": "Mapping-quality scale factor"}),
                "p_het": (
                    "FLOAT",
                    {"default": 1.0e-03, "min": 0, "max": 1, "description": "Prior probability of heterozygosity"},
                ),
                "p_indel": (
                    "FLOAT",
                    {"default": 2.0e-04, "min": 0, "max": 1, "description": "Prior probability of indels"},
                ),
                "het_scale": (
                    "FLOAT",
                    {"default": 1.0, "min": 0, "description": "Heterozygous SNP probability multiplier"},
                ),
                "homopoly_fix": (
                    "BOOLEAN",
                    {"default": False, "description": "Apply homopolymer quality correction", "advanced": True},
                ),
                "homopoly_score": (
                    "FLOAT",
                    {"default": "", "min": 0, "description": "Homopolymer quality scaling", "advanced": True},
                ),
                "qual_calibration": (
                    "STRING",
                    {
                        "default": "file",
                        "options": ["file", ":hiseq", ":hifi", ":r10.4_sup", ":r10.4_dup", ":ultima"],
                        "description": "Quality calibration preset",
                        "advanced": True,
                    },
                ),
                "qual_calibration_file": (
                    "FILE",
                    {"description": "Custom quality calibration table", "advanced": True},
                ),
                "min_depth": ("INT", {"default": 1, "min": 0, "description": "Minimum depth required to make a call"}),
                "region": ("STRING", {"default": "", "description": "Region such as chr1:100-200"}),
                "reference": ("FASTA", {"description": "Optional reference FASTA"}),
                "reference_index": (
                    "FASTA_INDEX",
                    {"description": "Exact colocated <reference>.fai index", "advanced": True},
                ),
                "reference_quality": (
                    "INT",
                    {
                        "default": 0,
                        "min": 0,
                        "max": 93,
                        "description": "FASTQ quality assigned to reference-derived bases (--ref-qual)",
                        "advanced": True,
                    },
                ),
                "line_len": ("INT", {"default": 70, "description": "Maximum FASTA/FASTQ line length"}),
                "output_all": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Output every position from start to end of references containing aligned data (-a)",
                    },
                ),
                "output_all_references": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Output every position in every reference, including references with no data (-aa)",
                        "advanced": True,
                    },
                ),
                "show_deletions": (
                    "BOOLEAN",
                    {"default": False, "description": "Show deletions as '*' instead of omitting them"},
                ),
                "show_insertions": (
                    "BOOLEAN",
                    {"default": True, "description": "Show insertions in the consensus"},
                ),
                "ambig": (
                    "BOOLEAN",
                    {"default": False, "description": "Enable IUPAC ambiguity codes in the consensus output"},
                ),
                "mark_insertions": (
                    "BOOLEAN",
                    {"default": False, "description": "Mark insertions with underscores", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
