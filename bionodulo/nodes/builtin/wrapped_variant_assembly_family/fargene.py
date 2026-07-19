"""Focused fargene node contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from .evidence import pin_contract

class FargeneNode(CommandNode):
    """Identify fragmented antibiotic resistance genes with fARGene."""

    NODE_ID = "fargene"
    DISPLAY_NAME = "fargene"
    REQUIRED_CONDA_PACKAGES = ["fargene", "tar"]
    CATEGORY = "annotation"
    DESCRIPTION = "Identify and reconstruct antibiotic resistance genes from metagenomic reads or contigs with fARGene."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "fARGene",
        "fragmented antibiotic resistance genes",
        "antibiotic resistance gene identifier",
        "ARG prediction",
        "metagenomic resistance genes",
    ]
    RETURN_TYPES = ("TXT", "TGZ", "TXT", "DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("summary", "retrieved_fragments", "fargene_log", "hmmsearchresults", "predicted_genes")
    REQUIRED_EXECUTABLES = ["fargene", "tar"]
    DOCUMENTATION_URL = "https://github.com/fannyhb/fargene"
    CITATION_DOIS = ["10.1186/s40168-019-0670-1"]
    CITATION_URLS = [f"{DOI_URL}10.1186/s40168-019-0670-1"]
    CITATION_TEXT = "Identification and reconstruction of novel antibiotic resistance genes from metagenomes."
    VERSION = "0.1"
    SHELL = True

    INPUT_TYPES_ALLOWED = ["paired", "collection", "sequence"]
    MODELS = ["class_a", "class_b_1_2", "class_b_3", "class_c", "class_d_1", "class_d_2", "qnr"]

    @classmethod
    def _input_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_type", "") or "")

    @classmethod
    def _identifier(cls, inputs: dict[str, Any], path_key: str, identifier_key: str) -> str:
        identifier = str(inputs.get(identifier_key, "") or "")
        if identifier:
            return _safe_identifier(identifier)
        return _safe_identifier(Path(str(inputs.get(path_key, ""))).name)

    @classmethod
    def _sequence_identifiers(cls, inputs: dict[str, Any], sequences: list[str]) -> list[str]:
        identifiers = _as_list(inputs.get("sequence_identifiers", inputs.get("element_identifiers")))
        if not identifiers:
            identifiers = [Path(path).name for path in sequences]
        identifiers.extend(Path(path).name for path in sequences[len(identifiers) :])
        return [_safe_identifier(identifier) for identifier in identifiers[: len(sequences)]]

    @classmethod
    def _collection_entries(cls, inputs: dict[str, Any]) -> list[tuple[str, str, str]]:
        entries = []
        for index, item in enumerate(inputs.get("input_collection") or []):
            if isinstance(item, dict):
                identifier = _safe_identifier(str(item.get("identifier", item.get("name", f"pair_{index + 1}"))))
                entries.append((str(item.get("forward", "")), str(item.get("reverse", "")), identifier))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                entries.append((str(item[0]), str(item[1]), f"pair_{index + 1}"))
        return entries

    @classmethod
    def _add_optional_flags(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        if float(inputs.get("meta_score", 0.0) or 0.0) != 0.0:
            cmd.extend(["--meta-score", str(inputs.get("meta_score"))])
        if float(inputs.get("score", 0.0) or 0.0) != 0.0:
            cmd.extend(["--score", str(inputs.get("score"))])
        if inputs.get("protein"):
            cmd.append("--protein")
        if int(inputs.get("min_orf_length", 90) or 90) != 90:
            cmd.extend(["--min-orf-length", str(inputs.get("min_orf_length"))])
        for key, flag in [
            ("retrieve_whole", "--retrieve-whole"),
            ("no_orf_predict", "--no-orf-predict"),
            ("no_quality_filtering", "--no-quality-filtering"),
            ("no_assembly", "--no-assembly"),
            ("orf_finder", "--orf-finder"),
            ("store_peptides", "--store-peptides"),
        ]:
            if inputs.get(key):
                cmd.append(flag)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        commands = [_shell_join(["mkdir", "-p", out])]
        input_type = cls._input_type(inputs)
        if input_type == "paired":
            r1_name = f"{cls._identifier(inputs, 'R1', 'R1_identifier')}.fastq"
            r2_name = f"{cls._identifier(inputs, 'R2', 'R2_identifier')}.fastq"
            commands.append(_shell_join(["ln", "-fs", str(inputs.get("R1", "")), r1_name]))
            commands.append(_shell_join(["ln", "-fs", str(inputs.get("R2", "")), r2_name]))
        elif input_type == "collection":
            for forward, reverse, identifier in cls._collection_entries(inputs):
                commands.append(_shell_join(["ln", "-fs", forward, f"{identifier}_1.fastq"]))
                commands.append(_shell_join(["ln", "-fs", reverse, f"{identifier}_2.fastq"]))
        elif input_type == "sequence":
            sequences = _as_list(inputs.get("input_sequence"))
            for path, identifier in zip(sequences, cls._sequence_identifiers(inputs, sequences), strict=False):
                commands.append(_shell_join(["ln", "-fs", path, f"{identifier}.fasta"]))

        cmd = ["fargene", "--infiles"]
        if input_type in {"paired", "collection"}:
            cmd.extend(["*.fastq", "--meta"])
        else:
            cmd.append("*.fasta")
        cmd.extend(
            [
                "--hmm-model",
                str(inputs.get("models", "class_a")),
                "--output",
                "fargene_output",
                "--tmp-dir",
                "tmp",
                "-p",
                f"${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}",
            ]
        )
        cls._add_optional_flags(cmd, inputs)
        command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-", "${GALAXY_SLOTS:-").replace("}'", "}")
        if input_type in {"paired", "collection"}:
            command += " && tar -czf retrievedFragments.tar.gz fargene_output/retrievedFragments"
        command += " 2>&1"
        commands.append(command)
        commands.append(_shell_join(["cp", "fargene_output/results_summary.txt", f"{out}/results_summary.txt"]))
        if input_type in {"paired", "collection"}:
            commands.append(_shell_join(["cp", "retrievedFragments.tar.gz", f"{out}/retrievedFragments.tar.gz"]))
        commands.append(_shell_join(["cp", "fargene_analysis.log", f"{out}/fargene_analysis.log"]))
        commands.append(_shell_join(["cp", "-r", "fargene_output/hmmsearchresults", f"{out}/hmmsearchresults"]))
        commands.append(_shell_join(["cp", "-r", "fargene_output/predictedGenes", f"{out}/predictedGenes"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        (out / "hmmsearchresults").mkdir(parents=True, exist_ok=True)
        (out / "predictedGenes").mkdir(parents=True, exist_ok=True)
        outputs = [out / "results_summary.txt"]
        if cls._input_type(inputs) in {"paired", "collection"}:
            outputs.append(out / "retrievedFragments.tar.gz")
        outputs.extend([out / "fargene_analysis.log", out / "hmmsearchresults", out / "predictedGenes"])
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": ("STRING", {"options": cls.INPUT_TYPES_ALLOWED, "description": "Paired reads, paired collection, or contigs/genomes"}),
                "models": ("STRING", {"default": "class_a", "options": cls.MODELS, "description": "Resistance gene HMM model"}),
            },
            "optional": {
                "R1": ("FASTQ", {"default": "", "description": "Forward reads for paired input"}),
                "R2": ("FASTQ", {"default": "", "description": "Reverse reads for paired input"}),
                "R1_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier for R1"}),
                "R2_identifier": ("STRING", {"default": "", "advanced": True, "description": "Galaxy element identifier for R2"}),
                "input_collection": ("FASTQ_LIST", {"default": [], "multiple": True, "description": "Paired read collection"}),
                "input_sequence": ("FASTA", {"default": [], "multiple": True, "description": "Input contigs or genomes"}),
                "sequence_identifiers": (
                    "STRING",
                    {"default": [], "multiple": True, "advanced": True, "description": "Galaxy element identifiers for sequences"},
                ),
                "score": ("FLOAT", {"default": 0.0, "min": 0, "description": "Threshold for classifying nearly complete genes"}),
                "meta_score": ("FLOAT", {"default": 0.0, "min": 0, "description": "Fragment score per amino acid"}),
                "protein": ("BOOLEAN", {"default": False, "description": "Use protein mode"}),
                "min_orf_length": ("INT", {"default": 90, "min": 1, "description": "Minimum predicted ORF length"}),
                "retrieve_whole": ("BOOLEAN", {"default": False, "description": "Retrieve whole sequence where a hit is detected"}),
                "no_orf_predict": ("BOOLEAN", {"default": False, "description": "Disable ORF prediction"}),
                "no_quality_filtering": ("BOOLEAN", {"default": False, "description": "Disable metagenomic quality filtering"}),
                "no_assembly": ("BOOLEAN", {"default": False, "description": "Skip assembly and contig retrieval"}),
                "orf_finder": ("BOOLEAN", {"default": False, "description": "Use NCBI ORFfinder instead of prodigal"}),
                "store_peptides": ("BOOLEAN", {"default": False, "description": "Store translated sequences"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        input_type = cls._input_type(inputs)
        if input_type not in cls.INPUT_TYPES_ALLOWED:
            return "input_type must be one of: paired, collection, sequence"
        if input_type == "paired" and (not str(inputs.get("R1", "")).strip() or not str(inputs.get("R2", "")).strip()):
            return "R1 and R2 are required for paired input"
        if input_type == "collection" and not cls._collection_entries(inputs):
            return "input_collection is required for collection input"
        if input_type == "sequence" and not _as_list(inputs.get("input_sequence")):
            return "input_sequence is required for sequence input"
        model = str(inputs.get("models", "class_a") or "class_a")
        if model not in cls.MODELS:
            return "models must be one of: class_a, class_b_1_2, class_b_3, class_c, class_d_1, class_d_2, qnr"
        for name, minimum in {"score": 0, "meta_score": 0, "min_orf_length": 1, "threads": 1}.items():
            raw = inputs.get(name)
            if raw is None or str(raw) == "":
                continue
            try:
                value = float(raw) if name in {"score", "meta_score"} else int(raw)
            except (TypeError, ValueError):
                return f"{name} must be a number" if name in {"score", "meta_score"} else f"{name} must be an integer"
            if value < minimum:
                return f"{name} must be >= {minimum}"
        return super().VALIDATE_INPUTS(inputs)

pin_contract(FargeneNode)

__all__ = ['FargeneNode']
