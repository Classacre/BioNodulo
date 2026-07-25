"""Microbial gene prediction and profiling wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_phylogeny_assembly_family.evidence import pin_contract

class FragGeneScanNode(CommandNode):
    """Find complete and fragmented genes in short reads or assemblies."""

    LEGACY_NODE_ID = "fraggenescan"
    DISPLAY_NAME = "FragGeneScan"
    REQUIRED_CONDA_PACKAGES = ["fraggenescan"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find complete and fragmented genes in short reads, incomplete assemblies, or complete genomes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "FragGeneScan",
        "fraggenescan",
        "run_FragGeneScan.pl",
        "fragmented genes",
        "gene prediction",
        "short reads",
        "prokaryotic genes",
    ]
    RETURN_TYPES = ("TSV", "FASTA", "FASTA", "GFF")
    RETURN_NAMES = ("coordinates", "nucleotide_sequences", "protein_sequences", "gff")
    REQUIRED_EXECUTABLES = ["run_FragGeneScan.pl"]
    DOCUMENTATION_URL = "https://omics.informatics.indiana.edu/FragGeneScan/"
    CITATION_DOIS = [FRAGGENESCAN_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{FRAGGENESCAN_CITATION_DOI}"]
    CITATION_TEXT = FRAGGENESCAN_CITATION_TEXT
    VERSION = "1.30.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        complete = "1" if inputs.get("complete") else "0"
        return [
            "run_FragGeneScan.pl",
            "-genome",
            str(inputs.get("genome", "")),
            "-out",
            f"{_out(inputs)}/output_file_name",
            "-complete",
            complete,
            "-train",
            str(inputs.get("train", "454_5")),
            f"-thread=${{GALAXY_SLOTS:-{inputs.get('threads', 4)}}}",
        ]

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "output_file_name.out",
            out / "output_file_name.ffn",
            out / "output_file_name.faa",
            out / "output_file_name.gff",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("genome"):
            return "input FASTA is required"
        threads = inputs.get("threads", 4)
        try:
            if int(threads) < 1:
                return "threads must be >= 1"
        except (TypeError, ValueError):
            return "threads must be an integer"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("FASTA", {"description": "Input sequence file"}),
            },
            "optional": {
                "complete": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat input as complete genomic sequences"},
                ),
                "train": (
                    "STRING",
                    {
                        "default": "454_5",
                        "options": [
                            "454_5",
                            "454_10",
                            "454_30",
                            "complete",
                            "gene",
                            "illumina_1",
                            "illumina_5",
                            "illumina_10",
                            "noncoding",
                            "pwm",
                            "rgene",
                            "sanger_5",
                            "sanger_10",
                            "start",
                            "start1",
                            "stop",
                            "stop1",
                        ],
                        "description": "FragGeneScan training model",
                    },
                ),
                "threads": ("INT", {"default": 4, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class ProdigalNode(CommandNode):
    """Predict protein-coding genes in microbial genomes with Prodigal."""

    LEGACY_NODE_ID = "prodigal"
    DISPLAY_NAME = "Prodigal Gene Predictor"
    REQUIRED_CONDA_PACKAGES = ["prodigal"]
    CATEGORY = "annotation"
    DESCRIPTION = "Predict protein-coding genes in microbial genomes, draft assemblies, and metagenomic sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Prodigal",
        "prodigal",
        "gene prediction",
        "microbial genomes",
        "protein-coding genes",
        "translation initiation sites",
        "metagenomic gene prediction",
    ]
    RETURN_TYPES = ("FILE", "FASTA", "FASTA", "TSV")
    RETURN_NAMES = ("coordinates", "protein_translations", "nucleotide_sequences", "start_sites")
    REQUIRED_EXECUTABLES = ["prodigal"]
    DOCUMENTATION_URL = "https://github.com/hyattpd/Prodigal"
    CITATION_DOIS = [PRODIGAL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PRODIGAL_CITATION_DOI}"]
    CITATION_TEXT = PRODIGAL_CITATION_TEXT
    VERSION = "2.6.3+galaxy0"

    OUTPUT_FORMATS = {
        "gbk": "gbk",
        "gff": "gff3",
        "sqn": "sqn",
        "sco": "sco",
    }

    @classmethod
    def _coordinates_output(cls, inputs: dict[str, Any]) -> str:
        out_format = str(inputs.get("out_format", "gbk") or "gbk")
        ext = cls.OUTPUT_FORMATS.get(out_format, "gbk")
        return f"{_out(inputs)}/output.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["prodigal", "-i", str(inputs.get("input_fa", ""))]
        if inputs.get("input_train"):
            cmd.extend(["-t", str(inputs.get("input_train"))])
        cmd.extend(
            [
                "-o",
                cls._coordinates_output(inputs),
                "-f",
                str(inputs.get("out_format", "gbk") or "gbk"),
                "-p",
                str(inputs.get("procedure", "single") or "single"),
                "-g",
                str(inputs.get("trans_table", "11") or "11"),
                "-a",
                f"{_out(inputs)}/output.faa",
                "-d",
                f"{_out(inputs)}/output.fnn",
                "-s",
                f"{_out(inputs)}/output.start",
            ]
        )
        if inputs.get("closed"):
            cmd.append("-c")
        if inputs.get("force_nonsd"):
            cmd.append("-n")
        if inputs.get("masked_seq"):
            cmd.append("-m")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        ext = cls.OUTPUT_FORMATS.get(str(inputs.get("out_format", "gbk") or "gbk"), "gbk")
        return [
            out / f"output.{ext}",
            out / "output.faa",
            out / "output.fnn",
            out / "output.start",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_fa"):
            return "input FASTA is required"
        out_format = str(inputs.get("out_format", "gbk") or "gbk")
        if out_format not in cls.OUTPUT_FORMATS:
            return "out_format must be one of: gbk, gff, sqn, sco"
        procedure = str(inputs.get("procedure", "single") or "single")
        if procedure not in {"single", "meta"}:
            return "procedure must be one of: single, meta"
        trans_table = inputs.get("trans_table", "11") or "11"
        try:
            trans_table_int = int(trans_table)
        except (TypeError, ValueError):
            return "trans_table must be an integer from 1 to 25"
        if not 1 <= trans_table_int <= 25:
            return "trans_table must be an integer from 1 to 25"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fa": ("FASTA", {"description": "Input microbial genome, assembly, or metagenomic FASTA"}),
            },
            "optional": {
                "input_train": ("FASTA", {"default": "", "description": "Optional Prodigal training file"}),
                "out_format": (
                    "STRING",
                    {
                        "default": "gbk",
                        "options": ["gbk", "gff", "sqn", "sco"],
                        "description": "Coordinates output format",
                    },
                ),
                "procedure": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "meta"],
                        "description": "Single-genome or metagenomic prediction mode",
                    },
                ),
                "trans_table": (
                    "STRING",
                    {
                        "default": "11",
                        "options": [str(value) for value in range(1, 26)],
                        "description": "NCBI translation table",
                    },
                ),
                "closed": ("BOOLEAN", {"default": False, "description": "Do not allow partial genes at sequence edges"}),
                "force_nonsd": (
                    "BOOLEAN",
                    {"default": False, "description": "Scan for motifs instead of using the Shine-Dalgarno RBS finder"},
                ),
                "masked_seq": (
                    "BOOLEAN",
                    {"default": False, "description": "Treat runs of N as masked sequence"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class EukRepNode(CommandNode):
    """Classify eukaryotic and prokaryotic metagenomic sequences."""

    LEGACY_NODE_ID = "eukrep"
    DISPLAY_NAME = "EukRep"
    REQUIRED_CONDA_PACKAGES = ["eukrep"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Classify eukaryotic and prokaryotic sequences from metagenomic datasets with EukRep."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "EukRep",
        "eukrep",
        "metagenomic eukaryotes",
        "eukaryotic scaffolds",
        "prokaryotic sequences",
        "metagenome classification",
        "SVM k-mer classifier",
    ]
    RETURN_TYPES = ("FASTA", "FASTA", "STATS_FILE", "STATS_FILE")
    RETURN_NAMES = ("eukaryote_sequences", "prokaryote_sequences", "eukaryote_names", "prokaryote_names")
    REQUIRED_EXECUTABLES = ["EukRep"]
    DOCUMENTATION_URL = "https://github.com/patrickwest/EukRep"
    CITATION_DOIS = [EUKREP_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{EUKREP_CITATION_DOI}"]
    CITATION_TEXT = EUKREP_CITATION_TEXT
    VERSION = "0.6.7+galaxy0"
    SHELL = True

    @classmethod
    def _staged_input_name(cls, input_path: Any) -> str:
        suffixes = Path(str(input_path or "")).suffixes
        if len(suffixes) >= 2 and suffixes[-2:] == [".fa", ".gz"]:
            return "input.fa.gz"
        if len(suffixes) >= 2 and suffixes[-2:] == [".fasta", ".gz"]:
            return "input.fasta.gz"
        suffix = suffixes[-1] if suffixes else ".fa"
        return f"input{suffix}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged = cls._staged_input_name(inputs.get("input"))
        cmd = [
            "EukRep",
            "-i",
            staged,
            "-o",
            f"{_out(inputs)}/output.fa",
            "--min",
            str(inputs.get("min", 3000)),
            "--kmer_len",
            str(inputs.get("kmer_len", 5)),
        ]
        if inputs.get("prokarya"):
            cmd.extend(["--prokarya", f"{_out(inputs)}/output_prokarya.fa"])
        if inputs.get("seq_names"):
            cmd.append("--seq_names")
        cmd.extend(
            [
                "-m",
                str(inputs.get("stringency", "balanced") or "balanced"),
                "--tie",
                str(inputs.get("tie", "euk") or "euk"),
            ]
        )
        return f"ln -s {shlex.quote(str(inputs.get('input', '')))} {staged} && {_shell_join(cmd)}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "output.fa"]
        if inputs.get("prokarya"):
            outputs.append(out / "output_prokarya.fa")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input FASTA is required"
        try:
            min_length = int(inputs.get("min", 3000))
        except (TypeError, ValueError):
            return "min must be an integer"
        if min_length < 0:
            return "min must be >= 0"
        try:
            kmer_len = int(inputs.get("kmer_len", 5))
        except (TypeError, ValueError):
            return "kmer_len must be an integer"
        if not 3 <= kmer_len <= 6:
            return "kmer_len must be between 3 and 6"
        stringency = str(inputs.get("stringency", "balanced") or "balanced")
        if stringency not in {"strict", "balanced", "lenient"}:
            return "stringency must be one of: strict, balanced, lenient"
        tie = str(inputs.get("tie", "euk") or "euk")
        if tie not in {"euk", "prok", "rand", "skip"}:
            return "tie must be one of: euk, prok, rand, skip"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Metagenomic sequences in FASTA or FASTA.GZ format"}),
            },
            "optional": {
                "min": ("INT", {"default": 3000, "min": 0, "description": "Minimum sequence length for prediction"}),
                "kmer_len": ("INT", {"default": 5, "min": 3, "max": 6, "description": "K-mer length"}),
                "prokarya": ("BOOLEAN", {"default": False, "description": "Also output predicted prokaryotic sequences"}),
                "seq_names": ("BOOLEAN", {"default": False, "description": "Output sequence headers instead of full FASTA records"}),
                "stringency": (
                    "STRING",
                    {
                        "default": "balanced",
                        "options": ["strict", "balanced", "lenient"],
                        "description": "Eukaryotic scaffold classification stringency",
                    },
                ),
                "tie": (
                    "STRING",
                    {
                        "default": "euk",
                        "options": ["euk", "prok", "rand", "skip"],
                        "description": "How to handle equal eukaryotic/prokaryotic chunk predictions",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GAMMANode(CommandNode):
    """Find and annotate microbial gene matches with GAMMA."""

    LEGACY_NODE_ID = "gamma"
    DISPLAY_NAME = "GAMMA"
    REQUIRED_CONDA_PACKAGES = ["GAMMA"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find and annotate gene matches in microbial assemblies using protein-coding identity with GAMMA."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GAMMA",
        "Gene Allele Mutation Microbial Assessment",
        "gene match annotation",
        "antimicrobial resistance genes",
        "virulence genes",
        "protein coding identity",
    ]
    RETURN_TYPES = ("TSV", "GFF", "FASTA")
    RETURN_NAMES = ("gamma_out", "gamma_gff", "gamma_fasta")
    REQUIRED_EXECUTABLES = ["GAMMA.py"]
    DOCUMENTATION_URL = "https://github.com/rastanton/GAMMA"
    CITATION_DOIS = [GAMMA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GAMMA_CITATION_DOI}"]
    CITATION_TEXT = GAMMA_CITATION_TEXT
    VERSION = "2.2+galaxy0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "GAMMA.py",
            str(inputs.get("input_fasta", "")),
            str(inputs.get("input_db", "")),
            f"{_out(inputs)}/gamma_out",
        ]
        if inputs.get("all"):
            cmd.append("-a")
        cmd.extend(["-i", str(inputs.get("identity", 90))])
        if inputs.get("extended"):
            cmd.append("-e")
        if inputs.get("fasta"):
            cmd.append("-f")
        if inputs.get("gff"):
            cmd.append("-g")
        if inputs.get("headless"):
            cmd.append("-l")
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "gamma_out.gamma"]
        if inputs.get("gff"):
            outputs.append(out / "gamma_out.gff")
        if inputs.get("fasta"):
            outputs.append(out / "gamma_out.fasta")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_fasta"):
            return "input FASTA is required"
        if not inputs.get("input_db"):
            return "gene database FASTA is required"
        try:
            identity = int(inputs.get("identity", 90))
        except (TypeError, ValueError):
            return "identity must be an integer"
        if not 0 <= identity <= 100:
            return "identity must be between 0 and 100"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Genome or assembly FASTA to screen"}),
                "input_db": ("FASTA", {"description": "Multifasta coding-sequence gene database"}),
            },
            "optional": {
                "all": ("BOOLEAN", {"default": False, "description": "Include all gene matches, including overlaps"}),
                "identity": ("INT", {"default": 90, "min": 0, "max": 100, "description": "Minimum BLAT nucleotide identity percent"}),
                "extended": ("BOOLEAN", {"default": False, "description": "Return all gene mutations"}),
                "fasta": ("BOOLEAN", {"default": False, "description": "Write matched genes as FASTA"}),
                "gff": ("BOOLEAN", {"default": False, "description": "Write matched genes as GFF"}),
                "headless": ("BOOLEAN", {"default": False, "description": "Remove column headers from the GAMMA table"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class GAMMASNode(CommandNode):
    """Find nucleotide or protein gene matches with GAMMA-S."""

    LEGACY_NODE_ID = "gamma_s"
    DISPLAY_NAME = "GAMMA-S"
    REQUIRED_CONDA_PACKAGES = ["GAMMA"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find gene matches in microbial assemblies using nucleotide identity with GAMMA-S."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "GAMMA-S",
        "gamma_s",
        "Gene Allele Mutation Microbial Assessment Sequence",
        "nucleotide gene matching",
        "protein-protein comparisons",
        "gene match annotation",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("gamma_s_out",)
    REQUIRED_EXECUTABLES = ["GAMMA-S.py"]
    DOCUMENTATION_URL = "https://github.com/rastanton/GAMMA"
    CITATION_DOIS = [GAMMA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{GAMMA_CITATION_DOI}"]
    CITATION_TEXT = GAMMA_CITATION_TEXT
    VERSION = "2.2+galaxy0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "GAMMA-S.py",
            str(inputs.get("input_fasta", "")),
            str(inputs.get("input_db", "")),
            f"{_out(inputs)}/gamma-s_out",
        ]
        if inputs.get("all"):
            cmd.append("-a")
        cmd.extend(["-i", str(inputs.get("identity", 90))])
        if inputs.get("extended"):
            cmd.append("-e")
        if inputs.get("protein"):
            cmd.append("-p")
        cmd.extend(["-m", str(inputs.get("minimum", 20))])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gamma-s_out.gamma"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_fasta"):
            return "input FASTA is required"
        if not inputs.get("input_db"):
            return "gene database FASTA is required"
        for key in ("identity", "minimum"):
            try:
                value = int(inputs.get(key, 90 if key == "identity" else 20))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if not 0 <= value <= 100:
                return f"{key} must be between 0 and 100"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_fasta": ("FASTA", {"description": "Genome, assembly, or protein FASTA to screen"}),
                "input_db": ("FASTA", {"description": "Multifasta gene or protein database"}),
            },
            "optional": {
                "all": ("BOOLEAN", {"default": False, "description": "Include all gene matches, including overlaps"}),
                "identity": ("INT", {"default": 90, "min": 0, "max": 100, "description": "Minimum identity percent"}),
                "extended": ("BOOLEAN", {"default": False, "description": "Return all gene mutations"}),
                "protein": ("BOOLEAN", {"default": False, "description": "Perform protein-protein comparisons"}),
                "minimum": (
                    "INT",
                    {"default": 20, "min": 0, "max": 100, "description": "Minimum length percent match"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RedNode(CommandNode):
    """Detect and mask genomic repeats with RED."""

    LEGACY_NODE_ID = "red"
    DISPLAY_NAME = "Red"
    REQUIRED_CONDA_PACKAGES = ["red"]
    CATEGORY = "genomics"
    DESCRIPTION = "Detect and mask repeats de novo in genome FASTA sequences with RED."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Red",
        "RED",
        "REpeat Detector",
        "repeat masking",
        "de novo repeats",
        "genome masking",
    ]
    RETURN_TYPES = ("FASTA", "BED")
    RETURN_NAMES = ("masked", "bed")
    REQUIRED_EXECUTABLES = ["Red"]
    DOCUMENTATION_URL = "https://github.com/BioinformaticsToolsmith/Red"
    CITATION_DOIS = [RED_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{RED_CITATION_DOI}"]
    CITATION_TEXT = RED_CITATION_TEXT
    VERSION = "2018.09.10+galaxy1"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 1)}}}"
        cmd = [
            "Red",
            "-gnm",
            f"{out}/input/",
            "-msk",
            f"{out}/output/",
            "-rpt",
            f"{out}/output/",
            "-frm",
            "2",
            "-cor",
            slots,
        ]
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return (
            f"mkdir -p {shlex.quote(f'{out}/input')} {shlex.quote(f'{out}/output')} && "
            f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(f'{out}/input/genome.fa')} && "
            f"{command}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / "output"
        out.mkdir(parents=True, exist_ok=True)
        return [out / "genome.msk", out / "genome.bed"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "genome FASTA is required"
        try:
            threads = int(inputs.get("threads", 1))
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Genome FASTA sequence to mask"}),
            },
            "optional": {
                "threads": ("INT", {"default": 1, "min": 1, "max": 64}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class AbriTAMRNode(CommandNode):
    """Run abriTAMR antimicrobial resistance gene detection."""

    LEGACY_NODE_ID = "abritamr"
    DISPLAY_NAME = "abriTAMR"
    REQUIRED_CONDA_PACKAGES = ["abritamr"]
    CATEGORY = "annotation"
    DESCRIPTION = "Detect and collate antimicrobial resistance genes, partial genes, and virulence factors with abriTAMR."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "abriTAMR",
        "abritamr",
        "AMR gene detection",
        "AMRFinderPlus",
        "antimicrobial resistance",
        "virulence summary",
    ]
    RETURN_TYPES = ("TSV", "TSV", "TSV", "TSV", "STATS_FILE")
    RETURN_NAMES = ("abriTAMR_output", "matches_summary", "partials_summary", "virulence_summary", "log")
    REQUIRED_EXECUTABLES = ["abritamr"]
    DOCUMENTATION_URL = "https://github.com/MDU-PHL/abritamr"
    CITATION_DOIS = [ABRITAMR_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ABRITAMR_CITATION_DOI}"]
    CITATION_TEXT = ABRITAMR_CITATION_TEXT
    VERSION = "1.3.0+galaxy0"
    SHELL = True

    VALID_SPECIES = {
        "Neisseria",
        "Clostridioides_difficile",
        "Acinetobacter_baumannii",
        "Campylobacter",
        "Enterococcus_faecalis",
        "Enterococcus_faecium",
        "Escherichia",
        "Klebsiella",
        "Salmonella",
        "Staphylococcus_aureus",
        "Staphylococcus_pseudintermedius",
        "Streptococcus_agalactiae",
        "Streptococcus_pneumoniae",
        "Streptococcus_pyogenes",
    }

    @classmethod
    def _contigs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("contig"))

    @classmethod
    def _contig_labels(cls, inputs: dict[str, Any], contigs: list[str]) -> list[str]:
        labels = _as_list(inputs.get("contig_labels"))
        if len(labels) != len(contigs):
            return [Path(contig).name for contig in contigs]
        return labels

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        contigs = cls._contigs(inputs)
        labels = cls._contig_labels(inputs, contigs)
        manifest = f"{out}/input.tsv"
        printf_args = ["printf", "%s\\t%s\\n"]
        for label, contig in zip(labels, contigs):
            printf_args.extend([label, contig])
        setup = f"{_shell_join(printf_args)} > {shlex.quote(manifest)}"
        slots = f"${{GALAXY_SLOTS:-{inputs.get('jobs', 4)}}}"
        cmd = ["abritamr", "run", "--contigs", manifest]
        if inputs.get("species"):
            cmd.extend(["--species", str(inputs.get("species"))])
        if inputs.get("identity") not in (None, ""):
            cmd.extend(["--identity", str(inputs.get("identity"))])
        cmd.extend(["--jobs", slots])
        command = _shell_join(cmd).replace(shlex.quote(slots), slots)
        return f"{setup} && {command}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "abritamr.txt",
            out / "summary_matches.txt",
            out / "summary_partials.txt",
            out / "summary_virulence.txt",
        ]
        if inputs.get("log_file"):
            outputs.append(out / "abritamr.log")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not cls._contigs(inputs):
            return "at least one contig FASTA is required"
        if inputs.get("species") not in (None, "") and str(inputs.get("species")) not in cls.VALID_SPECIES:
            return "species must be one of the supported abriTAMR species"
        if inputs.get("identity") not in (None, ""):
            try:
                identity = float(inputs.get("identity"))
            except (TypeError, ValueError):
                return "identity must be a number"
            if not 0 <= identity <= 1:
                return "identity must be between 0 and 1"
        try:
            jobs = int(inputs.get("jobs", 4))
        except (TypeError, ValueError):
            return "jobs must be an integer"
        if jobs < 1:
            return "jobs must be >= 1"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        species = sorted(cls.VALID_SPECIES)
        return {
            "required": {
                "contig": ("FASTA", {"list": True, "description": "One or more isolate contig FASTA files"}),
            },
            "optional": {
                "species": (
                    "STRING",
                    {"default": "", "options": species, "description": "Species for point-mutation resistance mechanisms"},
                ),
                "identity": (
                    "FLOAT",
                    {"default": "", "min": 0, "max": 1, "description": "Minimum AMRFinder identity threshold"},
                ),
                "log_file": ("BOOLEAN", {"default": False, "description": "Return the abriTAMR log file"}),
                "jobs": ("INT", {"default": 4, "min": 1, "max": 128, "description": "Worker processes"}),
                "contig_labels": (
                    "STRING",
                    {"default": "", "list": True, "advanced": True, "description": "Optional sample labels for the manifest"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class NonpareilNode(CommandNode):
    """Estimate metagenomic coverage and redundancy with Nonpareil."""

    LEGACY_NODE_ID = "nonpareil"
    DISPLAY_NAME = "Nonpareil"
    REQUIRED_CONDA_PACKAGES = ["nonpareil"]
    CATEGORY = "metagenomics"
    DESCRIPTION = "Estimate metagenomic coverage and generate Nonpareil redundancy curves from FASTA or FASTQ reads."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Nonpareil",
        "nonpareil",
        "metagenomic coverage",
        "redundancy curve",
        "sequencing effort",
        "library complexity",
    ]
    RETURN_TYPES = ("TSV", "TSV", "STATS_FILE", "JSON", "TSV")
    RETURN_NAMES = ("summary", "all_data_output", "log", "json_output", "mating_vector_output")
    REQUIRED_EXECUTABLES = ["nonpareil", "NonpareilCurves.R"]
    DOCUMENTATION_URL = "https://nonpareil.readthedocs.io/"
    CITATION_DOIS = [NONPAREIL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{NONPAREIL_CITATION_DOI}"]
    CITATION_TEXT = NONPAREIL_CITATION_TEXT
    VERSION = "3.5.5+galaxy1"
    SHELL = True

    @classmethod
    def _summary_label(cls, inputs: dict[str, Any]) -> str:
        label = str(inputs.get("summary_label", Path(str(inputs.get("input", "nonpareil"))).name) or "nonpareil")
        return _safe_label(label)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        staged = f"{out}/input"
        summary_path = f"{out}/{cls._summary_label(inputs)}"
        slots = f"${{GALAXY_SLOTS:-{inputs.get('threads', 2)}}}"
        memory = f"${{NONPAREIL_MAX_MEMORY:-{inputs.get('max_memory', 1024)}}}"
        cmd = [
            "nonpareil",
            "-s",
            staged,
            "-T",
            str(inputs.get("algo", "kmer")),
            "-f",
            str(inputs.get("input_format", "fastq")),
            "-d",
            str(inputs.get("subsampling", 0.7)),
            "-n",
            str(inputs.get("subsample_per_point", 1024)),
            "-L",
            str(inputs.get("min_overlapping", 50)),
            "-X",
            str(inputs.get("max_query_reads", 1000)),
            "-R",
            memory,
            "-t",
            slots,
            "-b",
            f"{out}/output",
            "-a",
            f"{out}/all_data_output.tsv",
            "-C",
            f"{out}/mating_vector_output.tsv",
        ]
        if inputs.get("log_test"):
            cmd.extend(["-l", f"{out}/nonpareil.log"])
        cmd.extend(["-o", summary_path])
        if inputs.get("use_portion_in_output"):
            cmd.append("-F")
        cmd.extend(
            [
                "-m",
                str(inputs.get("min_sampling_portion", 0)),
                "-M",
                str(inputs.get("max_sampling_portion", 1)),
                "-i",
                str(inputs.get("sampling_portion_interval", 0.01)),
            ]
        )
        if inputs.get("use_rev_comp"):
            cmd.append("-c")
        if inputs.get("n_as_mismatches"):
            cmd.append("-N")
        if inputs.get("sim_thres") not in (None, ""):
            cmd.extend(["-S", str(inputs.get("sim_thres"))])
        cmd.extend(["-k", str(inputs.get("kmer_size", 24))])
        if inputs.get("proba") not in (None, ""):
            cmd.extend(["-x", str(inputs.get("proba"))])
        cmd.extend(["-r", str(inputs.get("seed", 1000))])
        command = _shell_join(cmd)
        command = command.replace(shlex.quote(memory), memory).replace(shlex.quote(slots), slots)
        parts = [
            f"ln -s {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(staged)}",
            command,
            f"cp {shlex.quote(summary_path)} {shlex.quote(f'{out}/summary.tsv')}",
        ]
        if inputs.get("json_object"):
            parts.append(f"NonpareilCurves.R --json {shlex.quote(f'{out}/curves.json')} {shlex.quote(summary_path)}")
        return " && ".join(parts)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "summary.tsv", out / "all_data_output.tsv"]
        if inputs.get("log_test"):
            outputs.append(out / "nonpareil.log")
        if inputs.get("json_object"):
            outputs.append(out / "curves.json")
        outputs.append(out / "mating_vector_output.tsv")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input sequences are required"
        algo = str(inputs.get("algo", "kmer") or "kmer")
        if algo not in {"alignment", "kmer"}:
            return "algo must be one of: alignment, kmer"
        input_format = str(inputs.get("input_format", "fastq") or "fastq")
        if input_format not in {"fasta", "fastq"}:
            return "input_format must be one of: fasta, fastq"
        for key in ("subsampling", "min_sampling_portion", "max_sampling_portion", "sampling_portion_interval"):
            try:
                value = float(inputs.get(key, {"subsampling": 0.7, "max_sampling_portion": 1, "sampling_portion_interval": 0.01}.get(key, 0)))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        for key, default in (
            ("subsample_per_point", 1024),
            ("max_query_reads", 1000),
            ("kmer_size", 24),
            ("seed", 1000),
            ("threads", 2),
            ("max_memory", 1024),
        ):
            try:
                value = int(inputs.get(key, default))
            except (TypeError, ValueError):
                return f"{key} must be an integer"
            if value < 0:
                return f"{key} must be >= 0"
            if key in {"threads", "max_memory"} and value < 1:
                return f"{key} must be >= 1"
        try:
            min_overlapping = int(inputs.get("min_overlapping", 50))
        except (TypeError, ValueError):
            return "min_overlapping must be an integer"
        if not 0 <= min_overlapping <= 100:
            return "min_overlapping must be between 0 and 100"
        for key in ("sim_thres", "proba"):
            if inputs.get(key) in (None, ""):
                continue
            try:
                value = float(inputs.get(key))
            except (TypeError, ValueError):
                return f"{key} must be a number"
            if value < 0:
                return f"{key} must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ", {"description": "Input FASTQ or FASTA sequences"}),
                "algo": ("STRING", {"default": "kmer", "options": ["kmer", "alignment"], "description": "Nonpareil algorithm"}),
                "input_format": ("STRING", {"default": "fastq", "options": ["fastq", "fasta"], "description": "Sequence file format"}),
            },
            "optional": {
                "subsampling": ("FLOAT", {"default": 0.7, "min": 0, "description": "Iterative subsampling factor"}),
                "subsample_per_point": ("INT", {"default": 1024, "min": 0, "description": "Subsamples per point"}),
                "min_overlapping": ("INT", {"default": 50, "min": 0, "max": 100, "description": "Minimum aligned overlap percent"}),
                "max_query_reads": ("INT", {"default": 1000, "min": 0, "description": "Maximum query reads"}),
                "use_portion_in_output": ("BOOLEAN", {"default": False, "description": "Report sampled portions as fractions"}),
                "min_sampling_portion": ("FLOAT", {"default": 0, "min": 0, "advanced": True}),
                "max_sampling_portion": ("FLOAT", {"default": 1, "min": 0, "advanced": True}),
                "sampling_portion_interval": ("FLOAT", {"default": 0.01, "min": 0, "advanced": True}),
                "use_rev_comp": ("BOOLEAN", {"default": False, "description": "Do not use reverse-complement matching"}),
                "n_as_mismatches": ("BOOLEAN", {"default": False, "description": "Treat Ns as mismatches"}),
                "sim_thres": ("FLOAT", {"default": "", "min": 0, "description": "Similarity threshold"}),
                "kmer_size": ("INT", {"default": 24, "min": 0, "description": "K-mer size"}),
                "proba": ("FLOAT", {"default": "", "min": 0, "description": "Probability of using a sequence as query"}),
                "seed": ("INT", {"default": 1000, "min": 0, "description": "Random seed"}),
                "threads": ("INT", {"default": 2, "min": 1, "max": 128}),
                "max_memory": ("INT", {"default": 1024, "min": 1, "description": "Fallback maximum memory in MB"}),
                "log_test": ("BOOLEAN", {"default": False, "description": "Return Nonpareil log"}),
                "json_object": ("BOOLEAN", {"default": False, "description": "Extract Nonpareil curve object as JSON"}),
                "summary_label": ("STRING", {"default": "", "advanced": True, "description": "Label used for intermediate summary file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(FragGeneScanNode)
pin_contract(ProdigalNode)
pin_contract(EukRepNode)
pin_contract(GAMMANode)
pin_contract(GAMMASNode)
pin_contract(RedNode)
pin_contract(AbriTAMRNode)
pin_contract(NonpareilNode)

__all__ = ["FragGeneScanNode","ProdigalNode","EukRepNode","GAMMANode","GAMMASNode","RedNode","AbriTAMRNode","NonpareilNode"]
