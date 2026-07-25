"""HiC-Pro 3.1.0 pipeline contract with a complete generated config."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from bionodulo.nodes.builtin.alignment_family.bowtie2_adapter import BOWTIE2_SUFFIX_FAMILIES
from bionodulo.nodes.builtin.alignment_family.fm_index_bundle import find_index_bundle

from .adapter import EpigenomicsCommandNode, path_value, split_values


class HICProNode(EpigenomicsCommandNode):
    """Run a local HiC-Pro installation over its documented sample hierarchy."""

    NODE_ID = "hic_pro"
    DISPLAY_NAME = "HiC-Pro Pipeline"
    DESCRIPTION = "Process Hi-C reads into valid pairs, contact matrices, and ICE-normalized results."
    SEARCH_ALIASES = ["hic-pro", "hic", "3d genome", "chromatin contacts", "contact matrix"]
    RETURN_TYPES = ("DIRECTORY",)
    RETURN_NAMES = ("hic_results",)
    REQUIRED_EXECUTABLES = ["HiC-Pro"]
    REQUIRED_CONDA_PACKAGES: list[str] = []
    INSTALLATION_REQUIRED = (
        "HiC-Pro 3.1.0 is not available from the configured conda-forge/bioconda channels; "
        "provide an upstream installation with config-system.txt."
    )

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_dir": ("DIRECTORY", {"description": "Directory containing one subdirectory per sample"}),
                "genome_id": ("STRING", {"description": "Bowtie2 index basename, for example hg38"}),
                "bowtie2_index_dir": ("INDEX_DIR", {"description": "Directory containing the complete Bowtie2 index"}),
                "chrom_sizes": ("FILE", {"description": "Chromosome sizes file"}),
                "threads": ("INT", {"default": 8, "min": 1, "max": 64}),
            },
            "optional": {
                "restriction_fragments": ("BED", {"description": "Restriction-fragment BED for digestion Hi-C"}),
                "ligation_site": ("STRING", {"description": "Ligation junction sequence paired with restriction_fragments"}),
                "pair1_ext": ("STRING", {"default": "_R1"}),
                "pair2_ext": ("STRING", {"default": "_R2"}),
                "min_mapq": ("INT", {"default": 10, "min": 0}),
                "bin_sizes": ("STRING", {"default": "20000 40000 150000 500000 1000000"}),
                "max_iter": ("INT", {"default": 100, "min": 1}),
                "sort_ram": ("STRING", {"default": "1000M"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        validation = super().VALIDATE_INPUTS(inputs)
        if validation is not True:
            return validation
        for field in ("input_dir", "bowtie2_index_dir", "chrom_sizes"):
            if path_value(inputs.get(field)) is None:
                return f"{field} is required"
        if not str(inputs.get("genome_id", "")).strip():
            return "genome_id is required"
        if int(inputs.get("threads", 8)) < 1:
            return "threads must be at least 1"
        pair1 = str(inputs.get("pair1_ext", "_R1")).strip()
        pair2 = str(inputs.get("pair2_ext", "_R2")).strip()
        if not pair1 or not pair2 or pair1 == pair2:
            return "pair1_ext and pair2_ext must be distinct non-empty strings"
        bins = split_values(inputs.get("bin_sizes", "20000 40000 150000 500000 1000000"))
        if not bins or any(not value.isascii() or not value.isdigit() or int(value) < 1 for value in bins):
            return "bin_sizes must contain positive integers"
        if bool(inputs.get("restriction_fragments")) != bool(str(inputs.get("ligation_site", "")).strip()):
            return "restriction_fragments and ligation_site must be provided together"
        if int(inputs.get("max_iter", 100)) < 1:
            return "max_iter must be at least 1"
        return True

    @classmethod
    def _config_text(cls, inputs: dict[str, Any]) -> str:
        fragments = str(inputs.get("restriction_fragments", ""))
        ligation_site = str(inputs.get("ligation_site", ""))
        lines = [
            "TMP_DIR = tmp",
            "LOGS_DIR = logs",
            "BOWTIE2_OUTPUT_DIR = bowtie_results",
            "MAPC_OUTPUT = hic_results",
            "RAW_DIR = rawdata",
            f"N_CPU = {inputs.get('threads', 8)}",
            f"SORT_RAM = {inputs.get('sort_ram', '1000M')}",
            "LOGFILE = hicpro.log",
            "JOB_NAME = ",
            "JOB_MEM = ",
            "JOB_WALLTIME = ",
            "JOB_QUEUE = ",
            "JOB_MAIL = ",
            f"PAIR1_EXT = {inputs.get('pair1_ext', '_R1')}",
            f"PAIR2_EXT = {inputs.get('pair2_ext', '_R2')}",
            f"MIN_MAPQ = {inputs.get('min_mapq', 10)}",
            f"BOWTIE2_IDX_PATH = {inputs.get('bowtie2_index_dir', '')}",
            "BOWTIE2_GLOBAL_OPTIONS = --very-sensitive -L 30 --score-min L,-0.6,-0.2 --end-to-end --reorder",
            "BOWTIE2_LOCAL_OPTIONS = --very-sensitive -L 20 --score-min L,-0.6,-0.2 --end-to-end --reorder",
            f"REFERENCE_GENOME = {inputs.get('genome_id', '')}",
            f"GENOME_SIZE = {inputs.get('chrom_sizes', '')}",
            "ALLELE_SPECIFIC_SNP = ",
            "CAPTURE_TARGET = ",
            "REPORT_CAPTURE_REPORTER = 1",
            f"GENOME_FRAGMENT = {fragments}",
            f"LIGATION_SITE = {ligation_site}",
            "MIN_FRAG_SIZE = ",
            "MAX_FRAG_SIZE = ",
            "MIN_INSERT_SIZE = ",
            "MAX_INSERT_SIZE = ",
            "MIN_CIS_DIST = ",
            "GET_ALL_INTERACTION_CLASSES = 1",
            "GET_PROCESS_SAM = 0",
            "RM_SINGLETON = 1",
            "RM_MULTI = 1",
            "RM_DUP = 1",
            f"BIN_SIZE = {' '.join(split_values(inputs.get('bin_sizes', '20000 40000 150000 500000 1000000')))}",
            "MATRIX_FORMAT = upper",
            f"MAX_ITER = {inputs.get('max_iter', 100)}",
            "FILTER_LOW_COUNT_PERC = 0.02",
            "FILTER_HIGH_COUNT_PERC = 0",
            "EPS = 0.1",
        ]
        return "\n".join(lines) + "\n"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        validation = cls.VALIDATE_INPUTS(inputs)
        if validation is not True:
            raise ValueError(str(validation))
        node_out = Path(str(inputs.get("output", ".")))
        node_out.mkdir(parents=True, exist_ok=True)
        config_file = node_out / "hicpro_config.txt"
        config_file.write_text(cls._config_text(inputs), encoding="utf-8")
        return [
            "HiC-Pro",
            "-i",
            str(inputs["input_dir"]),
            "-o",
            str(node_out / "run"),
            "-c",
            str(config_file),
        ]

    @classmethod
    def PREPARE_EXECUTION(cls, inputs: dict[str, Any], outputs: list[Path]) -> None:
        bundle = find_index_bundle(
            str(inputs["bowtie2_index_dir"]),
            label="Bowtie2",
            suffix_families=BOWTIE2_SUFFIX_FAMILIES,
        )
        if bundle.prefix.name != str(inputs["genome_id"]):
            raise ValueError(
                "genome_id must match the complete Bowtie2 index prefix "
                f"({bundle.prefix.name!r})"
            )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        node_out = Path(output_dir) / cls.NODE_ID
        node_out.mkdir(parents=True, exist_ok=True)
        return [node_out / "run" / "hic_results"]
