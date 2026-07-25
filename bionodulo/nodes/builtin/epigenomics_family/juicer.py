"""Juicer 2.0 CPU pipeline contract."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.alignment_family.adapter import find_index_prefix

from .adapter import EpigenomicsCommandNode, path_value, stage_file


class JuicerNode(EpigenomicsCommandNode):
    """Run the pinned CPU Juicer script with an explicit BWA reference bundle."""

    NODE_ID = "juicer"
    DISPLAY_NAME = "Juicer Pipeline"
    DESCRIPTION = "Process Hi-C FASTQs into high-MAPQ and all-contact .hic files, statistics, and deduplicated BAM."
    SEARCH_ALIASES = ["juicer", "hic", "juicebox", "hiccups", "arrowhead", "tad", "loops"]
    RETURN_TYPES = ("FILE", "FILE", "BAM", "TSV")
    RETURN_NAMES = ("hic_file", "all_contacts_hic", "deduplicated_bam", "statistics")
    REQUIRED_EXECUTABLES = ["juicer.sh", "bwa", "samtools", "java"]
    REQUIRED_CONDA_PACKAGES = ["bwa", "samtools", "openjdk"]
    INSTALLATION_REQUIRED = (
        "Juicer 2.0 is not available from the configured conda-forge/bioconda channels; "
        "installation_dir must contain the pinned scripts/common and juicer_tools layout."
    )
    SIDECAR_POLICY = "bwa_index must contain one FASTA and all five colocated BWA index sidecars."
    REQUIRED_INSTALLATION_FILES = (
        "scripts/common/adjust_insert_size.awk",
        "scripts/common/check.sh",
        "scripts/common/chimeric_sam.awk",
        "scripts/common/countligations.sh",
        "scripts/common/dups_sam.awk",
        "scripts/common/juicer_postprocessing.sh",
        "scripts/common/juicer_tools",
        "scripts/common/juicer_tools.jar",
        "scripts/common/sam_to_pre.awk",
        "scripts/common/stats_sub.awk",
    )
    EXECUTABLE_INSTALLATION_FILES = (
        "scripts/common/check.sh",
        "scripts/common/juicer_postprocessing.sh",
        "scripts/common/juicer_tools",
    )
    PARALLEL_HIC_INSTALLATION_FILES = ("scripts/common/index_by_chr.awk",)

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fastq_dir": ("DIRECTORY", {"description": "Directory of paired *_R1*.fastq and *_R2*.fastq files, or a top directory containing fastq/"}),
                "bwa_index": ("INDEX_DIR", {"description": "Complete BWA FASTA/index bundle"}),
                "genome_id": ("STRING", {"description": "Genome label written into the .hic metadata"}),
                "chrom_sizes": ("FILE", {"description": "Chromosome sizes passed with -p"}),
                "installation_dir": ("DIRECTORY", {"description": "Juicer parent directory used by -D"}),
                "restriction_site": ("STRING", {"default": "none", "description": "Enzyme name such as MboI, or none"}),
            },
            "optional": {
                "restriction_sites_bed": ("FILE", {"description": "Juicer restriction-site positions file required for enzyme protocols"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 128}),
                "hic_threads": ("INT", {"default": 1, "min": 1, "max": 128}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for field in ("fastq_dir", "bwa_index", "chrom_sizes", "installation_dir"):
            if path_value(inputs.get(field)) is None:
                return f"{field} is required"
        if not str(inputs.get("genome_id", "")).strip():
            return "genome_id is required"
        restriction_site = str(inputs.get("restriction_site", "none")).strip()
        if not restriction_site:
            return "restriction_site is required"
        if restriction_site != "none" and path_value(inputs.get("restriction_sites_bed")) is None:
            return "restriction_sites_bed is required unless restriction_site is none"
        if int(inputs.get("threads", 8)) < 1 or int(inputs.get("hic_threads", 1)) < 1:
            return "threads and hic_threads must be at least 1"
        return True

    @classmethod
    def _run_dir(cls, inputs: dict[str, Any]) -> Path:
        return Path(str(inputs.get("_run_dir", Path(str(inputs.get("output", "."))) / "run")))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        reference = inputs.get("_reference_prefix")
        if reference is None:
            reference = Path(str(inputs["bwa_index"])) / "reference.fa"
        cmd = [
            "juicer.sh",
            "-g",
            str(inputs["genome_id"]),
            "-d",
            str(cls._run_dir(inputs)),
            "-s",
            str(inputs.get("restriction_site", "none")),
            "-p",
            str(inputs["chrom_sizes"]),
            "-D",
            str(inputs["installation_dir"]),
            "-z",
            str(reference),
            "-t",
            str(inputs.get("threads", 8)),
        ]
        if int(inputs.get("hic_threads", 1)) > 1:
            cmd.extend(["-T", str(inputs["hic_threads"])])
        if inputs.get("restriction_sites_bed"):
            cmd.extend(["-y", str(inputs["restriction_sites_bed"])])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        aligned = node_out / "run" / "aligned"
        return [
            aligned / "inter_30.hic",
            aligned / "inter.hic",
            aligned / "merged_dedup.bam",
            aligned / "inter_30.txt",
        ]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        installation_dir = Path(str(inputs["installation_dir"]))
        if not installation_dir.is_dir():
            raise NotADirectoryError(f"Juicer installation directory not found: {installation_dir}")
        required_files = list(cls.REQUIRED_INSTALLATION_FILES)
        executable_files = list(cls.EXECUTABLE_INSTALLATION_FILES)
        if int(inputs.get("hic_threads", 1)) > 1:
            required_files.extend(cls.PARALLEL_HIC_INSTALLATION_FILES)
            executable_files.extend(cls.PARALLEL_HIC_INSTALLATION_FILES)
        missing = [
            relative
            for relative in required_files
            if not (installation_dir / relative).is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "Juicer installation is missing required files: " + ", ".join(missing)
            )
        non_executable = [
            relative
            for relative in executable_files
            if not os.access(installation_dir / relative, os.X_OK)
        ]
        if non_executable:
            raise PermissionError(
                "Juicer installation files are not executable: " + ", ".join(non_executable)
            )

        source = Path(str(inputs["fastq_dir"]))
        source_fastq = source / "fastq" if (source / "fastq").is_dir() else source
        if not source_fastq.is_dir():
            raise NotADirectoryError(f"Juicer FASTQ directory not found: {source_fastq}")
        fastq_pattern = re.compile(r"^(?P<prefix>.+)_R(?P<mate>[12])(?P<suffix>.*\.fastq(?:\.gz)?)$")
        pairs: dict[tuple[str, str], dict[str, Path]] = {}
        for path in sorted(source_fastq.iterdir()):
            if not path.is_file():
                continue
            match = fastq_pattern.fullmatch(path.name)
            if match is None:
                continue
            key = (match.group("prefix"), match.group("suffix"))
            pairs.setdefault(key, {})[match.group("mate")] = path
        if not pairs:
            raise ValueError(
                f"No Juicer-compatible *_R1*.fastq and *_R2*.fastq pairs found in {source_fastq}"
            )
        incomplete = [
            f"{prefix}_R[12]{suffix}"
            for (prefix, suffix), mates in pairs.items()
            if set(mates) != {"1", "2"}
        ]
        if incomplete:
            raise ValueError("Unpaired Juicer FASTQs: " + ", ".join(incomplete))

        reference_prefix = find_index_prefix(str(inputs["bwa_index"]))
        run_dir = outputs[0].parents[1]
        target_fastq = run_dir / "fastq"
        target_fastq.mkdir(parents=True, exist_ok=True)
        for mates in pairs.values():
            for candidate in mates.values():
                stage_file(candidate, target_fastq / candidate.name)
        inputs["_run_dir"] = str(run_dir)
        inputs["_reference_prefix"] = str(reference_prefix)
