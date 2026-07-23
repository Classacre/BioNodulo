"""Shared HybPiper contracts for focused owners."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin.taxonomy_family.contracts import ToolsIUCCommandContract

class _HybPiperContract(ToolsIUCCommandContract):
    """Analyze targeted sequence capture data with HybPiper."""

    LEGACY_NODE_ID = "hybpiper"
    DISPLAY_NAME = "HybPiper"
    REQUIRED_CONDA_PACKAGES = ["hybpiper"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Analyse targeted sequence capture data with HybPiper."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "HybPiper",
        "targeted sequence capture",
        "target loci assembly",
        "check targetfile",
        "fix targetfile",
        "retrieve sequences",
        "recovery heatmap",
        "paralog warnings",
    ]
    RETURN_TYPES = (
        "FASTA",
        "TEXT",
        "TSV",
        "FILE",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "DIRECTORY",
        "TEXT",
    )
    RETURN_NAMES = (
        "fixed_targetfile",
        "targetfile_ctl_file",
        "targetfile_report",
        "hybpiper_archive",
        "hybpiper_stats",
        "hybpiper_heatmaps",
        "dna_sequences",
        "aa_sequences",
        "intron_sequences",
        "supercontig_sequences",
        "dummy_output",
    )
    REQUIRED_EXECUTABLES = ["hybpiper"]
    DOCUMENTATION_URL = "https://github.com/mossmatters/HybPiper"
    CITATION_DOIS = [HYBPIPER_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{HYBPIPER_CITATION_DOI}"]
    CITATION_TEXT = HYBPIPER_CITATION_TEXT
    VERSION = "2.1.6"
    SHELL = True
    JOBS = ["check_and_fix_targetfile", "assemble", "stats"]
    STATS_TYPES = ["gene", "supercontig"]
    SEQUENCE_TYPES = ["dna", "aa", "intron", "supercontig"]

    @classmethod
    def _job(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("hybpiper_job", "assemble") or "assemble")

    @classmethod
    def _stats_types(cls, inputs: dict[str, Any]) -> list[str]:
        if "stats_type_select" not in inputs:
            return ["gene"]
        return _as_list(inputs.get("stats_type_select"))

    @classmethod
    def _sequence_types(cls, inputs: dict[str, Any]) -> list[str]:
        if "sequence_type_select" not in inputs:
            return ["dna"]
        return _as_list(inputs.get("sequence_type_select"))

    @classmethod
    def _archive_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/hybpiper_archive.tar"

    @classmethod
    def _sample_names(cls, inputs: dict[str, Any], archives: list[str]) -> list[str]:
        provided_names = _as_list(inputs.get("sample_names"))
        if len(provided_names) == len(archives):
            return provided_names
        names: list[str] = []
        for archive in archives:
            name = Path(archive).name
            for suffix in (".tar.gz", ".tgz", ".tar"):
                if name.endswith(suffix):
                    name = name[: -len(suffix)]
                    break
            names.append(name)
        return names

    @staticmethod
    def _sample_name_error(sample_name: str) -> str | None:
        if not sample_name or sub(r"[^A-Za-z0-9_-]", "", sample_name) != sample_name:
            return "HybPiper sample identifiers may only contain letters, numbers, underscores, and hyphens"
        return None

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [_shell_join(["ln", "-s", str(inputs.get("targetfile_dna", "")), "./target_file.fasta"])]
        job = cls._job(inputs)

        if job == "check_and_fix_targetfile":
            commands.extend(
                [
                    _shell_join(["hybpiper", "check_targetfile", "--targetfile_dna", "target_file.fasta"]),
                    "mv fix_targetfile*.ctl hybpiper.ctl",
                    _shell_join(
                        [
                            "hybpiper",
                            "fix_targetfile",
                            "--targetfile_dna",
                            "target_file.fasta",
                            "--allow_gene_removal",
                            "hybpiper.ctl",
                        ]
                    ),
                ]
            )
            return " && ".join(commands)

        if job == "assemble":
            sample_name = str(inputs.get("sample_name", "")).strip() or "sample"
            commands.append(
                _shell_join(
                    [
                        "hybpiper",
                        "assemble",
                        "--readfiles",
                        str(inputs.get("paired_forward", "")),
                        str(inputs.get("paired_reverse", "")),
                        "--targetfile_dna",
                        "target_file.fasta",
                        "--diamond",
                        "--cpu",
                        str(inputs.get("threads", 1)),
                        "--prefix",
                        sample_name,
                    ]
                )
            )
            commands.append(
                _shell_join(["tar", "-cvf", cls._archive_path(inputs), f"--directory={sample_name}", "."])
            )
            return " && ".join(commands)

        if job == "stats":
            archives = _as_list(inputs.get("hybpiper_results"))
            sample_names = cls._sample_names(inputs, archives)
            for archive, sample_name in zip(archives, sample_names, strict=False):
                commands.append(_shell_join(["mkdir", "-p", sample_name]))
                commands.append(_shell_join(["tar", "-xf", archive, "-C", sample_name]))
                commands.append(_shell_join(["echo", sample_name]) + " >> namelist.txt")

            for stats_type in cls._stats_types(inputs):
                commands.append(
                    _shell_join(
                        [
                            "hybpiper",
                            "stats",
                            "--targetfile_dna",
                            "target_file.fasta",
                            "--stats_filename",
                            f"stats.{stats_type}",
                            "--seq_lengths_filename",
                            f"seq_lengths.{stats_type}",
                            stats_type,
                            "namelist.txt",
                        ]
                    )
                )
                if inputs.get("heatmap", False):
                    commands.append(
                        _shell_join(
                            [
                                "hybpiper",
                                "recovery_heatmap",
                                "--heatmap_filename",
                                f"heatmap.{stats_type}",
                                "--heatmap_filetype",
                                "svg",
                                f"seq_lengths.{stats_type}.tsv",
                            ]
                        )
                    )

            for sequence_type in cls._sequence_types(inputs):
                commands.append(_shell_join(["mkdir", f"fasta.{sequence_type}"]))
                commands.append(
                    _shell_join(
                        [
                            "hybpiper",
                            "retrieve_sequences",
                            "--targetfile_dna",
                            "target_file.fasta",
                            "--sample_names",
                            "namelist.txt",
                            "--fasta_dir",
                            f"fasta.{sequence_type}",
                            sequence_type,
                        ]
                    )
                )
            out = _out(inputs)
            stats_types = cls._stats_types(inputs)
            sequence_types = cls._sequence_types(inputs)
            if stats_types:
                commands.append(_shell_join(["mkdir", "-p", f"{out}/hybpiper_stats"]))
                for stats_type in stats_types:
                    commands.append(
                        _shell_join(["cp", f"stats.{stats_type}.tsv", f"{out}/hybpiper_stats/stats.{stats_type}.tsv"])
                    )
                    commands.append(
                        _shell_join(
                            [
                                "cp",
                                f"seq_lengths.{stats_type}.tsv",
                                f"{out}/hybpiper_stats/seq_lengths.{stats_type}.tsv",
                            ]
                        )
                    )
                if inputs.get("heatmap", False):
                    commands.append(_shell_join(["mkdir", "-p", f"{out}/hybpiper_heatmaps"]))
                    for stats_type in stats_types:
                        commands.append(
                            _shell_join(
                                [
                                    "cp",
                                    f"heatmap.{stats_type}.svg",
                                    f"{out}/hybpiper_heatmaps/heatmap.{stats_type}.svg",
                                ]
                            )
                        )
            sequence_outputs = {
                "dna": "dna_sequences",
                "aa": "aa_sequences",
                "intron": "intron_sequences",
                "supercontig": "supercontig_sequences",
            }
            for sequence_type in sequence_types:
                output_name = sequence_outputs.get(sequence_type)
                if output_name:
                    commands.append(_shell_join(["cp", "-r", f"fasta.{sequence_type}", f"{out}/{output_name}"]))
            return " && ".join(commands)

        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        job = cls._job(inputs)
        if job == "check_and_fix_targetfile":
            return [out / "target_file_fixed.fasta", out / "hybpiper.ctl", out / "fix_targetfile_report.tsv"]
        if job == "assemble":
            return [out / "hybpiper_archive.tar"]

        stats_types = cls._stats_types(inputs)
        sequence_types = cls._sequence_types(inputs)
        if not stats_types and not sequence_types:
            return [out / "namelist.txt"]
        outputs: list[Path] = []
        if stats_types:
            outputs.append(out / "hybpiper_stats")
            if inputs.get("heatmap", False):
                outputs.append(out / "hybpiper_heatmaps")
        sequence_outputs = {
            "dna": out / "dna_sequences",
            "aa": out / "aa_sequences",
            "intron": out / "intron_sequences",
            "supercontig": out / "supercontig_sequences",
        }
        for sequence_type in sequence_types:
            if sequence_type in sequence_outputs:
                outputs.append(sequence_outputs[sequence_type])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("targetfile_dna", "")).strip():
            return "HybPiper target FASTA is required"
        job = cls._job(inputs)
        if job not in cls.JOBS:
            return f"Unsupported HybPiper job: {job}"

        if job == "assemble":
            if not str(inputs.get("paired_forward", "")).strip() or not str(inputs.get("paired_reverse", "")).strip():
                return "HybPiper assemble requires paired forward and reverse reads"
            sample_name = str(inputs.get("sample_name", "")).strip()
            if not sample_name:
                return "HybPiper sample name is required"
            sample_error = cls._sample_name_error(sample_name)
            return sample_error or True

        if job == "stats":
            archives = _as_list(inputs.get("hybpiper_results"))
            if not archives:
                return "At least one HybPiper assemble archive is required"
            for sample_name in cls._sample_names(inputs, archives):
                sample_error = cls._sample_name_error(sample_name)
                if sample_error:
                    return sample_error
            stats_types = cls._stats_types(inputs)
            sequence_types = cls._sequence_types(inputs)
            if not stats_types and not sequence_types:
                return "At least one HybPiper statistics or sequence output must be selected"
            if inputs.get("heatmap", False) and not stats_types:
                return "HybPiper heatmap requires at least one statistics output"
            for stats_type in stats_types:
                if stats_type not in cls.STATS_TYPES:
                    return f"Unsupported HybPiper statistics output: {stats_type}"
            for sequence_type in sequence_types:
                if sequence_type not in cls.SEQUENCE_TYPES:
                    return f"Unsupported HybPiper sequence output: {sequence_type}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "targetfile_dna": ("FASTA", {"description": "Target file in FASTA format"}),
            },
            "optional": {
                "hybpiper_job": (
                    "STRING",
                    {
                        "default": "assemble",
                        "options": cls.JOBS,
                        "description": "Galaxy HybPiper run type",
                    },
                ),
                "paired_forward": (
                    "FASTQ",
                    {"default": "", "description": "Forward reads from the Galaxy paired collection"},
                ),
                "paired_reverse": (
                    "FASTQ",
                    {"default": "", "description": "Reverse reads from the Galaxy paired collection"},
                ),
                "sample_name": (
                    "STRING",
                    {"default": "", "description": "Sample identifier used as the HybPiper assembly prefix"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "description": "CPU threads for HybPiper assemble"}),
                "hybpiper_results": (
                    "FILE",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Archives from HybPiper assemble runs",
                    },
                ),
                "sample_names": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "description": "Galaxy collection element identifiers for archive extraction",
                    },
                ),
                "stats_type_select": (
                    "STRING",
                    {
                        "default": ["gene"],
                        "multiple": True,
                        "options": cls.STATS_TYPES,
                        "description": "Statistics outputs to report",
                    },
                ),
                "heatmap": (
                    "BOOLEAN",
                    {"default": False, "description": "Produce SVG recovery heatmaps for selected statistics"},
                ),
                "sequence_type_select": (
                    "STRING",
                    {
                        "default": ["dna"],
                        "multiple": True,
                        "options": cls.SEQUENCE_TYPES,
                        "description": "Sequence collections to retrieve",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }
