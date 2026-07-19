"""Focused cami amber node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class CamiAmberNode(CommandNode):
    """Evaluate metagenome binning results with CAMI AMBER."""

    NODE_ID = "cami_amber"
    DISPLAY_NAME = "CAMI AMBER"
    REQUIRED_CONDA_PACKAGES = ["cami-amber"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Evaluate genome reconstructions and taxonomic assignments from metagenome benchmark data with AMBER."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAMI AMBER",
        "AMBER metagenome binning evaluation",
        "Assessment of Metagenome BinnERs",
        "binning benchmark",
        "genome reconstruction metrics",
    ]
    RETURN_TYPES = ("HTML_REPORT", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("html", "result", "metrics_genome", "metrics_bin")
    REQUIRED_EXECUTABLES = ["amber.py"]
    DOCUMENTATION_URL = "https://github.com/CAMI-challenge/AMBER"
    CITATION_DOIS = ["10.1093/gigascience/giy069"]
    CITATION_URLS = [f"{DOI_URL}10.1093/gigascience/giy069"]
    CITATION_TEXT = "AMBER: Assessment of Metagenome BinnERs."
    VERSION = "2.0.7"
    SHELL = True

    NCBI_MODES = ["none", "manual", "data"]

    @classmethod
    def _binning_files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("binning_files", inputs.get("input_files")))

    @classmethod
    def _labels(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("labels"))

    @classmethod
    def _thresholds(cls, inputs: dict[str, Any], key: str) -> list[str]:
        return _as_list(inputs.get(key))

    @classmethod
    def _ncbi_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("ncbi_mode", "none") or "none")

    @classmethod
    def _ncbi_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("ncbi_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in files]
        identifiers.extend(Path(path).name for path in files[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(files)]]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", "output", "inputs", f"{out}/html_files"])]
        ncbi_mode = cls._ncbi_mode(inputs)
        if ncbi_mode == "manual":
            commands[0] = _shell_join(["mkdir", "-p", "output", "inputs", f"{out}/html_files", "ncbi"])
            ncbi_files = _as_list(inputs.get("ncbi_files"))
            for file, identifier in zip(ncbi_files, cls._ncbi_identifiers(inputs, ncbi_files), strict=False):
                commands.append(_shell_join(["ln", "-s", file, f"./ncbi/{identifier}"]))
        binning_files = cls._binning_files(inputs)
        for index, file in enumerate(binning_files):
            commands.append(_shell_join(["ln", "-s", file, f"./inputs/{index}.tsv"]))

        cmd = ["amber.py", "-g", str(inputs.get("gold_standard_file", ""))]
        labels = cls._labels(inputs)
        if labels:
            cmd.extend(["-l", ",".join(labels)])
        cmd.extend(["-p", str(inputs.get("filter", 0))])
        if str(inputs.get("min_length", "")) != "":
            cmd.extend(["-n", str(inputs.get("min_length"))])
        if str(inputs.get("desc", "")) != "":
            cmd.extend(["-d", str(inputs.get("desc"))])
        min_completeness = cls._thresholds(inputs, "min_completeness")
        if min_completeness:
            cmd.extend(["--min_completeness", ",".join(min_completeness)])
        max_contamination = cls._thresholds(inputs, "max_contamination")
        if max_contamination:
            cmd.extend(["--max_contamination", ",".join(max_contamination)])
        _add_if_value(cmd, "-r", inputs.get("remove_genomes"))
        _add_if_value(cmd, "-k", inputs.get("remove_keyword"))
        _add_if_value(cmd, "--genome_coverage", inputs.get("genome_coverage"))
        if ncbi_mode == "manual":
            cmd.extend(["--ncbi_dir", "ncbi"])
        elif ncbi_mode == "data":
            cmd.extend(["--ncbi_dir", str(inputs.get("ncbi_dir", ""))])
        cmd.extend(["-o", "output"])
        cmd.extend(f"inputs/{index}.tsv" for index in range(len(binning_files)))
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(["mv", "output/heatmap_bar.png", f"{out}/html_files"]))
        commands.extend(
            [
                _shell_join(["cp", "output/index.html", f"{out}/index.html"]),
                _shell_join(["cp", "output/results.tsv", f"{out}/results.tsv"]),
                _shell_join(["cp", "output/genome_metrics_cami1.tsv", f"{out}/genome_metrics_cami1.tsv"]),
                _shell_join(["cp", "output/bin_metrics.tsv", f"{out}/bin_metrics.tsv"]),
            ]
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "html_files").mkdir(parents=True, exist_ok=True)
        return [
            out / "index.html",
            out / "results.tsv",
            out / "genome_metrics_cami1.tsv",
            out / "bin_metrics.tsv",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gold_standard_file": ("TSV", {"description": "Gold standard CAMI biobox file with sequence lengths"}),
                "binning_files": ("TSV", {"multiple": True, "description": "CAMI biobox binning files to evaluate"}),
            },
            "optional": {
                "labels": ("STRING", {"default": [], "multiple": True, "description": "Optional labels for binning files"}),
                "filter": ("INT", {"default": 0, "min": 0, "description": "Filter out the n smallest genome bins"}),
                "min_length": ("INT", {"default": "", "min": 1, "description": "Minimum sequence length"}),
                "desc": ("STRING", {"default": "", "description": "HTML report description"}),
                "min_completeness": (
                    "INT",
                    {"default": [], "multiple": True, "min": 0, "max": 100, "description": "Minimum completeness thresholds"},
                ),
                "max_contamination": (
                    "INT",
                    {"default": [], "multiple": True, "min": 0, "max": 100, "description": "Maximum contamination thresholds"},
                ),
                "remove_genomes": ("TSV", {"default": "", "description": "Genome removal list"}),
                "remove_keyword": ("STRING", {"default": "", "description": "Keyword for genome removal list"}),
                "genome_coverage": ("TSV", {"default": "", "description": "Genome coverage table"}),
                "ncbi_mode": ("STRING", {"default": "none", "options": cls.NCBI_MODES, "description": "NCBI taxonomy source"}),
                "ncbi_files": ("TSV", {"default": [], "multiple": True, "description": "Manual NCBI nodes, merged, and names DMP files"}),
                "ncbi_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element identifiers for manual NCBI files"},
                ),
                "ncbi_dir": ("DIRECTORY", {"default": "", "description": "NCBI taxonomy directory from a data manager"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gold_standard_file", "")).strip():
            return "gold_standard_file is required"
        binning_files = cls._binning_files(inputs)
        if not binning_files:
            return "at least one binning file is required"
        labels = cls._labels(inputs)
        if labels and len(labels) != len(binning_files):
            return "labels count must match binning_files count"
        for name, minimum in {"filter": 0, "min_length": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        for name in ["min_completeness", "max_contamination"]:
            for raw in cls._thresholds(inputs, name):
                try:
                    value = int(raw)
                except (TypeError, ValueError):
                    return f"{name} values must be integers"
                if not 0 <= value <= 100:
                    return f"{name} values must be between 0 and 100"
        ncbi_mode = cls._ncbi_mode(inputs)
        if ncbi_mode not in cls.NCBI_MODES:
            return "ncbi_mode must be one of: none, manual, data"
        if ncbi_mode == "manual" and not _as_list(inputs.get("ncbi_files")):
            return "ncbi_files are required when ncbi_mode is manual"
        if ncbi_mode == "data" and not str(inputs.get("ncbi_dir", "")).strip():
            return "ncbi_dir is required when ncbi_mode is data"
        return super().VALIDATE_INPUTS(inputs)

class CamiAmberAddNode(CommandNode):
    """Add sequence lengths to a CAMI AMBER gold standard file."""

    NODE_ID = "cami_amber_add"
    DISPLAY_NAME = "CAMI AMBER add length column"
    REQUIRED_CONDA_PACKAGES = ["cami-amber"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Create an AMBER gold standard biobox file by adding sequence lengths from matching FASTA or FASTQ records."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAMI AMBER add length column",
        "AMBER gold standard length",
        "add_length_column.py",
        "biobox length column",
        "metagenome benchmark gold standard",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("file",)
    REQUIRED_EXECUTABLES = ["add_length_column.py"]
    DOCUMENTATION_URL = "https://github.com/CAMI-challenge/AMBER"
    CITATION_DOIS = ["10.1093/gigascience/giy069"]
    CITATION_URLS = [f"{DOI_URL}10.1093/gigascience/giy069"]
    CITATION_TEXT = "AMBER: Assessment of Metagenome BinnERs."
    VERSION = "2.0.7"
    SHELL = True

    @classmethod
    def _staged_name(cls, inputs: dict[str, Any], path_key: str, identifier_key: str) -> str:
        identifier = str(inputs.get(identifier_key, "") or "")
        if identifier:
            return _safe_identifier(identifier)
        return _safe_identifier(Path(str(inputs.get(path_key, ""))).name)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        gold_name = cls._staged_name(inputs, "gold_standard_file", "gold_standard_identifier")
        fasta_name = cls._staged_name(inputs, "fasta_file", "fasta_identifier")
        commands = [
            _shell_join(["mkdir", "-p", out]),
            _shell_join(["ln", "-s", str(inputs.get("gold_standard_file", "")), gold_name]),
            _shell_join(["ln", "-s", str(inputs.get("fasta_file", "")), fasta_name]),
        ]
        cmd = ["add_length_column.py", "-g", gold_name, "-f", fasta_name, ">", "gold_standard_file.tsv"]
        commands.append(_shell_join(cmd))
        commands.append(_shell_join(["cp", "gold_standard_file.tsv", f"{out}/gold_standard_file.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gold_standard_file.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gold_standard_file": ("TSV", {"description": "Input CAMI biobox gold standard file"}),
                "fasta_file": ("FILE", {"description": "Matching FASTA/FASTQ file, optionally compressed"}),
            },
            "optional": {
                "gold_standard_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier"}),
                "fasta_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("gold_standard_file", "")).strip():
            return "gold_standard_file is required"
        if not str(inputs.get("fasta_file", "")).strip():
            return "fasta_file is required"
        return super().VALIDATE_INPUTS(inputs)

class CamiAmberConvertNode(CommandNode):
    """Convert FASTA bins to CAMI AMBER biobox format."""

    NODE_ID = "cami_amber_convert"
    DISPLAY_NAME = "CAMI AMBER convert to biobox"
    REQUIRED_CONDA_PACKAGES = ["cami-amber"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Convert one or more FASTA bin files to CAMI AMBER biobox binning TSV format."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "CAMI AMBER convert to biobox",
        "AMBER biobox conversion",
        "convert_fasta_bins_to_biobox_format.py",
        "FASTA bins to biobox",
        "binning TSV",
    ]
    RETURN_TYPES = ("TSV", "DIRECTORY")
    RETURN_NAMES = ("binning_file", "binning_collection")
    REQUIRED_EXECUTABLES = ["convert_fasta_bins_to_biobox_format.py"]
    DOCUMENTATION_URL = "https://github.com/CAMI-challenge/AMBER"
    CITATION_DOIS = ["10.1093/gigascience/giy069"]
    CITATION_URLS = [f"{DOI_URL}10.1093/gigascience/giy069"]
    CITATION_TEXT = "AMBER: Assessment of Metagenome BinnERs."
    VERSION = "2.0.7"
    SHELL = True

    WORK_OPTIONS = ["single", "all"]

    @classmethod
    def _files(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("files"))

    @classmethod
    def _file_identifiers(cls, inputs: dict[str, Any], files: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("file_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in files]
        identifiers.extend(Path(path).name for path in files[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(files)]]

    @staticmethod
    def _single_output_name(identifier: str) -> str:
        return f"{identifier.split('.')[0]}.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        files = cls._files(inputs)
        identifiers = cls._file_identifiers(inputs, files)
        commands = [_shell_join(["mkdir", "-p", "output", out])]
        for path, identifier in zip(files, identifiers, strict=False):
            commands.append(_shell_join(["ln", "-s", path, identifier]))
        work = str(inputs.get("work", "single") or "single")
        if work == "single":
            for identifier in identifiers:
                commands.append(
                    _shell_join(
                        [
                            "convert_fasta_bins_to_biobox_format.py",
                            "-o",
                            f"output/{cls._single_output_name(identifier)}",
                            identifier,
                        ]
                    )
                )
            commands.append(_shell_join(["cp", "-r", "output", f"{out}/binning_collection"]))
        else:
            commands.append(_shell_join(["convert_fasta_bins_to_biobox_format.py", "-o", "output/binning.tsv", *identifiers]))
            commands.append(_shell_join(["cp", "output/binning.tsv", f"{out}/binning.tsv"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if str(inputs.get("work", "single") or "single") == "all":
            return [out / "binning.tsv"]
        (out / "binning_collection").mkdir(parents=True, exist_ok=True)
        return [out / "binning_collection"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "work": ("STRING", {"default": "single", "options": cls.WORK_OPTIONS, "description": "Convert each bin separately or merge all bins"}),
                "files": ("FASTA", {"multiple": True, "description": "FASTA bin files"}),
            },
            "optional": {
                "file_identifiers": ("STRING", {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element identifiers"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        files = cls._files(inputs)
        if not files:
            return "at least one FASTA file is required"
        work = str(inputs.get("work", "single") or "single")
        if work not in cls.WORK_OPTIONS:
            return "work must be one of: single, all"
        identifiers = _as_list(inputs.get("file_identifiers", inputs.get("element_identifiers")))
        if identifiers and len(identifiers) != len(files):
            return "file_identifiers count must match files count"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(CamiAmberNode)
pin_contract(CamiAmberAddNode)
pin_contract(CamiAmberConvertNode)

__all__ = ['CamiAmberNode', 'CamiAmberAddNode', 'CamiAmberConvertNode']
