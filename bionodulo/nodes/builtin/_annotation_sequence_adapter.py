"""Shared implementations for focused annotation and sequence owners."""
# ruff: noqa: E402,F401,F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *
from bionodulo.nodes.builtin._annotation_sequence_contracts import ToolsIUCCommandContract

class _AegeanCanonGff3Contract(ToolsIUCCommandContract):
    """Canonicalize GFF3 files with AEGeAn CanonGFF3."""

    LEGACY_NODE_ID = "aegean_canongff3"
    DISPLAY_NAME = "AEGeAn CanonGFF3"
    REQUIRED_CONDA_PACKAGES = ["aegean"]
    CATEGORY = "annotation"
    DESCRIPTION = "Clean GFF3 annotations so they contain canonical protein-coding gene features."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AEGeAn",
        "CanonGFF3",
        "canon-gff3",
        "aegean_canongff3",
        "canonical protein-coding genes",
        "GFF3 cleanup",
        "infer gene features",
    ]
    RETURN_TYPES = ("GFF3",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["canon-gff3"]
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AEGEAN_CITATION_URL]
    CITATION_TEXT = AEGEAN_CITATION_TEXT
    VERSION = "0.16.0+galaxy2"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/canonical.gff3"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["canon-gff3"]
        cmd.extend(_as_list(inputs.get("gff3file")))
        if inputs.get("infer"):
            cmd.append("--infer")
        _add_if_value(cmd, "-s", inputs.get("source"))
        cmd.extend(["-o", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "canonical.gff3"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("gff3file")):
            return "at least one GFF3 input file is required"
        source = str(inputs.get("source", "") or "")
        if source and re.fullmatch(r"\w+", source) is None:
            return "source may only contain letters, numbers, and underscores"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gff3file": (
                    "GFF3_LIST",
                    {
                        "multiple": True,
                        "description": "One or more GFF3 annotation files to canonicalize",
                    },
                ),
            },
            "optional": {
                "infer": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Infer missing gene features for transcripts lacking an explicit parent gene",
                    },
                ),
                "source": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Reset the source column of each feature to this alphanumeric or underscore label",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _AegeanGaevalContract(ToolsIUCCommandContract):
    """Evaluate gene model support with AEGeAn GAEVAL."""

    LEGACY_NODE_ID = "aegean_gaeval"
    DISPLAY_NAME = "AEGeAn GAEVAL"
    REQUIRED_CONDA_PACKAGES = ["aegean"]
    CATEGORY = "annotation"
    DESCRIPTION = "Compute gene model coverage and integrity scores from transcript alignments."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AEGeAn",
        "GAEVAL",
        "gaeval",
        "aegean_gaeval",
        "gene model integrity",
        "transcript alignment support",
        "annotation evaluation",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["gaeval"]
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [AEGEAN_CITATION_URL]
    CITATION_TEXT = AEGEAN_CITATION_TEXT
    VERSION = "0.16.0+galaxy2"

    WEIGHT_DEFAULTS = {
        "alpha": 0.6,
        "beta": 0.3,
        "gamma": 0.05,
        "epsilon": 0.05,
    }
    EXPECTED_DEFAULTS = {
        "expcds": 400,
        "exp5putr": 200,
        "exp3putr": 100,
    }

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/gaeval.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "gaeval",
            str(inputs.get("alignmentgff3", "")),
            str(inputs.get("genesgff3", "")),
            "-a",
            str(inputs.get("alpha", cls.WEIGHT_DEFAULTS["alpha"])),
            "-b",
            str(inputs.get("beta", cls.WEIGHT_DEFAULTS["beta"])),
            "-g",
            str(inputs.get("gamma", cls.WEIGHT_DEFAULTS["gamma"])),
            "-e",
            str(inputs.get("epsilon", cls.WEIGHT_DEFAULTS["epsilon"])),
            "-c",
            str(inputs.get("expcds", cls.EXPECTED_DEFAULTS["expcds"])),
            "-5",
            str(inputs.get("exp5putr", cls.EXPECTED_DEFAULTS["exp5putr"])),
            "-3",
            str(inputs.get("exp3putr", cls.EXPECTED_DEFAULTS["exp3putr"])),
            ">",
            cls._output_path(inputs),
        ]
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "gaeval.tsv"]

    @classmethod
    def _validate_range(cls, inputs: dict[str, Any], key: str, minimum: float, maximum: float) -> bool | str:
        value = inputs.get(key)
        if value is None or value == "":
            return True
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return f"{key} must be numeric"
        if numeric < minimum or numeric > maximum:
            return f"{key} must be between {minimum:g} and {maximum:g}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignmentgff3", "")).strip():
            return "alignmentgff3 is required"
        if not str(inputs.get("genesgff3", "")).strip():
            return "genesgff3 is required"
        for key in cls.WEIGHT_DEFAULTS:
            result = cls._validate_range(inputs, key, 0, 1)
            if result is not True:
                return result
        for key in cls.EXPECTED_DEFAULTS:
            result = cls._validate_range(inputs, key, 0, 1000)
            if result is not True:
                return result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignmentgff3": ("GFF3", {"description": "Transcript alignment GFF3 file"}),
                "genesgff3": ("GFF3", {"description": "Gene prediction or annotation GFF3 file"}),
            },
            "optional": {
                "alpha": (
                    "FLOAT",
                    {
                        "default": cls.WEIGHT_DEFAULTS["alpha"],
                        "min": 0,
                        "max": 1,
                        "description": "Weight for intron confirmation or expected CDS length support",
                    },
                ),
                "beta": (
                    "FLOAT",
                    {
                        "default": cls.WEIGHT_DEFAULTS["beta"],
                        "min": 0,
                        "max": 1,
                        "description": "Weight for exon coverage in the integrity score",
                    },
                ),
                "gamma": (
                    "FLOAT",
                    {
                        "default": cls.WEIGHT_DEFAULTS["gamma"],
                        "min": 0,
                        "max": 1,
                        "description": "Weight for expected 5 prime UTR length support",
                    },
                ),
                "epsilon": (
                    "FLOAT",
                    {
                        "default": cls.WEIGHT_DEFAULTS["epsilon"],
                        "min": 0,
                        "max": 1,
                        "description": "Weight for expected 3 prime UTR length support",
                    },
                ),
                "expcds": (
                    "INT",
                    {
                        "default": cls.EXPECTED_DEFAULTS["expcds"],
                        "min": 0,
                        "max": 1000,
                        "description": "Expected CDS length in base pairs",
                    },
                ),
                "exp5putr": (
                    "INT",
                    {
                        "default": cls.EXPECTED_DEFAULTS["exp5putr"],
                        "min": 0,
                        "max": 1000,
                        "description": "Expected 5 prime UTR length in base pairs",
                    },
                ),
                "exp3putr": (
                    "INT",
                    {
                        "default": cls.EXPECTED_DEFAULTS["exp3putr"],
                        "min": 0,
                        "max": 1000,
                        "description": "Expected 3 prime UTR length in base pairs",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _AegeanLocusPocusContract(ToolsIUCCommandContract):
    """Calculate interval loci from GFF3 annotations with AEGeAn LocusPocus."""

    LEGACY_NODE_ID = "aegean_locuspocus"
    DISPLAY_NAME = "AEGeAn LocusPocus"
    REQUIRED_CONDA_PACKAGES = ["aegean"]
    CATEGORY = "annotation"
    DESCRIPTION = "Calculate interval locus coordinates from GFF3 gene annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AEGeAn",
        "LocusPocus",
        "locuspocus",
        "aegean_locuspocus",
        "iLoci",
        "interval loci",
        "gene locus coordinates",
    ]
    RETURN_TYPES = ("GFF3", "TSV", "TSV", "TSV")
    RETURN_NAMES = ("output", "output_ilens", "output_genemap", "output_transmap")
    REQUIRED_EXECUTABLES = ["locuspocus"]
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS = [LOCUSPOCUS_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{LOCUSPOCUS_CITATION_DOI}"]
    CITATION_TEXT = LOCUSPOCUS_CITATION_TEXT
    VERSION = "0.16.0+galaxy2"

    MODES = ["", "--skipends", "--endsonly"]
    REFINE_OPTIONS = ["", "--refine"]
    OUTPUT_FILES = ["ilens", "genemap", "transmap"]
    OPTIONAL_OUTPUT_NAMES = {
        "ilens": "ilens.tsv",
        "genemap": "genemap.tsv",
        "transmap": "transmap.tsv",
    }

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/loci.gff3"

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        return _as_list(inputs.get("outputfiles"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        cmd = [
            "locuspocus",
            str(inputs.get("genesgff3", "")),
            "-l",
            str(inputs.get("delta", 500)),
        ]
        mode = str(inputs.get("mode", "") or "")
        if mode:
            cmd.append(mode)
        if inputs.get("skipiloci"):
            cmd.append("--skipiiloci")
        if str(inputs.get("refine", "") or "") == "--refine" and inputs.get("cds"):
            cmd.append("--cds")
        cmd.extend(["-m", str(inputs.get("minoverlap", 1))])
        cmd.extend(["-f", str(inputs.get("filter", "gene") or "gene")])
        _add_if_value(cmd, "-p", inputs.get("parent"))
        if inputs.get("pseudo"):
            cmd.append("--pseudo")
        selected = cls._selected_outputs(inputs)
        for output_name in cls.OUTPUT_FILES:
            if output_name in selected:
                cmd.extend([f"--{output_name}", f"{out}/{cls.OPTIONAL_OUTPUT_NAMES[output_name]}"])
        _add_if_value(cmd, "-n", inputs.get("namefmt"))
        if inputs.get("retainids"):
            cmd.append("--retainids")
        cmd.extend(["-o", cls._output_path(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "loci.gff3"]
        selected = cls._selected_outputs(inputs)
        for output_name in cls.OUTPUT_FILES:
            if output_name in selected:
                outputs.append(out / cls.OPTIONAL_OUTPUT_NAMES[output_name])
        return outputs

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, minimum: int, maximum: int) -> bool | str:
        value = inputs.get(key)
        if value is None or value == "":
            return True
        try:
            integer = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if integer < minimum or integer > maximum:
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("genesgff3", "")).strip():
            return "genesgff3 is required"
        for key, minimum, maximum in (("delta", 0, 1000), ("minoverlap", 1, 20)):
            result = cls._validate_int_range(inputs, key, minimum, maximum)
            if result is not True:
                return result
        mode = str(inputs.get("mode", "") or "")
        if mode not in cls.MODES:
            return f"mode must be one of: {', '.join(cls.MODES)}"
        refine = str(inputs.get("refine", "") or "")
        if refine not in cls.REFINE_OPTIONS:
            return f"refine must be one of: {', '.join(cls.REFINE_OPTIONS)}"
        unsupported_outputs = [value for value in cls._selected_outputs(inputs) if value not in cls.OUTPUT_FILES]
        if unsupported_outputs:
            return f"outputfiles contains unsupported values: {', '.join(unsupported_outputs)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genesgff3": ("GFF3", {"description": "Gene annotation GFF3 file"}),
            },
            "optional": {
                "delta": (
                    "INT",
                    {"default": 500, "min": 0, "max": 1000, "description": "Gene locus extension in base pairs"},
                ),
                "mode": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.MODES,
                        "description": "Mode for reporting unannotated interval loci at sequence ends",
                    },
                ),
                "skipiloci": ("BOOLEAN", {"default": False, "description": "Do not report intergenic iLoci"}),
                "refine": (
                    "STRING",
                    {
                        "default": "",
                        "options": cls.REFINE_OPTIONS,
                        "description": "Enable refine mode for overlapping genes",
                    },
                ),
                "cds": (
                    "BOOLEAN",
                    {"default": False, "description": "In refine mode, use CDS rather than UTRs for overlap handling"},
                ),
                "minoverlap": (
                    "INT",
                    {
                        "default": 1,
                        "min": 1,
                        "max": 20,
                        "description": "Minimum overlapping nucleotides for grouping genes in one iLocus",
                    },
                ),
                "filter": (
                    "STRING",
                    {"default": "gene", "description": "Comma-separated feature types used to annotate intervals"},
                ),
                "parent": (
                    "STRING",
                    {"default": "", "description": "Create missing parent features with a child:parent type mapping"},
                ),
                "pseudo": ("BOOLEAN", {"default": False, "description": "Correct erroneously labeled pseudogenes"}),
                "retainids": ("BOOLEAN", {"default": False, "description": "Retain original feature IDs"}),
                "namefmt": (
                    "STRING",
                    {"default": "", "description": "Format string for newly created locus IDs, such as locus%lu"},
                ),
                "outputfiles": (
                    "STRING_LIST",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.OUTPUT_FILES,
                        "description": "Optional LocusPocus side-output tables to emit",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _AegeanParsevalContract(ToolsIUCCommandContract):
    """Compare two GFF3 gene annotation sets with AEGeAn ParsEval."""

    LEGACY_NODE_ID = "aegean_parseval"
    DISPLAY_NAME = "AEGeAn ParsEval"
    REQUIRED_CONDA_PACKAGES = ["aegean"]
    CATEGORY = "annotation"
    DESCRIPTION = "Compare two GFF3 gene annotation sets for the same sequence."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "AEGeAn",
        "ParsEval",
        "parseval",
        "aegean_parseval",
        "gene annotation comparison",
        "gene structure comparison",
        "GFF3 annotation comparison",
    ]
    RETURN_TYPES = ("TXT", "HTML_REPORT")
    RETURN_NAMES = ("output_txt", "output_html")
    REQUIRED_EXECUTABLES = ["parseval"]
    DOCUMENTATION_URL = AEGEAN_CITATION_URL
    CITATION_DOIS = [PARSEVAL_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PARSEVAL_CITATION_DOI}"]
    CITATION_TEXT = PARSEVAL_CITATION_TEXT
    VERSION = "0.16.0+galaxy2"

    OUTPUT_TYPES = ["text", "html"]

    @classmethod
    def _output_type(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_type", "text") or "text")

    @classmethod
    def _text_output(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/parseval.txt"

    @classmethod
    def _html_output(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/parseval.html"

    @classmethod
    def _html_files_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/parseval_html.files"

    @classmethod
    def _base_cmd(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "parseval",
            str(inputs.get("referencegff3", "")),
            str(inputs.get("predictiongff3", "")),
            "--delta",
            str(inputs.get("delta", 0)),
            "--maxtrans",
            str(inputs.get("maxtrans", 32)),
            "-w",
        ]
        _add_if_value(cmd, "--refrlabel", inputs.get("refrlabel"))
        _add_if_value(cmd, "--predlabel", inputs.get("predlabel"))
        return cmd

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        output_type = cls._output_type(inputs)
        cmd = cls._base_cmd(inputs)
        if output_type == "html":
            html_files = cls._html_files_path(inputs)
            html_index = f"{html_files}/index.html"
            cmd.extend(["-f", "html", "-o", html_files])
            return " && ".join(
                [
                    _shell_join(["mkdir", "-p", html_files]),
                    _shell_join(cmd),
                    f"echo {shlex.quote('</div> </body> </html>')} >> {shlex.quote(html_index)}",
                    _shell_join(["cp", html_index, cls._html_output(inputs)]),
                ]
            )
        cmd.extend(["-f", "text", "-o", cls._text_output(inputs)])
        return _shell_join(cmd)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        if cls._output_type(inputs) == "html":
            return [out / "parseval.html"]
        return [out / "parseval.txt"]

    @classmethod
    def _validate_int_range(cls, inputs: dict[str, Any], key: str, minimum: int, maximum: int) -> bool | str:
        value = inputs.get(key)
        if value is None or value == "":
            return True
        try:
            integer = int(value)
        except (TypeError, ValueError):
            return f"{key} must be an integer"
        if integer < minimum or integer > maximum:
            return f"{key} must be between {minimum} and {maximum}"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("referencegff3", "")).strip():
            return "referencegff3 is required"
        if not str(inputs.get("predictiongff3", "")).strip():
            return "predictiongff3 is required"
        for key, minimum, maximum in (("delta", 0, 20), ("maxtrans", 1, 50)):
            result = cls._validate_int_range(inputs, key, minimum, maximum)
            if result is not True:
                return result
        output_type = cls._output_type(inputs)
        if output_type not in cls.OUTPUT_TYPES:
            return f"output_type must be one of: {', '.join(cls.OUTPUT_TYPES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "referencegff3": ("GFF3", {"description": "Reference annotation GFF3 file"}),
                "predictiongff3": ("GFF3", {"description": "Prediction annotation GFF3 file"}),
            },
            "optional": {
                "delta": (
                    "INT",
                    {"default": 0, "min": 0, "max": 20, "description": "Number of nucleotides to extend gene loci"},
                ),
                "maxtrans": (
                    "INT",
                    {"default": 32, "min": 1, "max": 50, "description": "Maximum transcripts allowed per locus"},
                ),
                "output_type": (
                    "STRING",
                    {
                        "default": "text",
                        "options": cls.OUTPUT_TYPES,
                        "description": "Generate plain text or HTML ParsEval output",
                    },
                ),
                "refrlabel": (
                    "STRING",
                    {"default": "", "description": "Optional label for the reference annotations"},
                ),
                "predlabel": (
                    "STRING",
                    {"default": "", "description": "Optional label for the prediction annotations"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _AugustusContract(ToolsIUCCommandContract):
    """Predict genes with the Galaxy IUC AUGUSTUS wrapper behavior."""

    LEGACY_NODE_ID = "augustus"
    DISPLAY_NAME = "Augustus"
    REQUIRED_CONDA_PACKAGES = ["augustus"]
    CATEGORY = "annotation"
    DESCRIPTION = "Predict genes in prokaryotic and eukaryotic genomes with AUGUSTUS."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Augustus",
        "AUGUSTUS",
        "augustus",
        "ab initio gene prediction",
        "gene prediction",
        "eukaryotic genome annotation",
        "extrinsic hints",
    ]
    RETURN_TYPES = ("GTF", "FASTA", "FASTA")
    RETURN_NAMES = ("output", "protein_output", "codingseq_output")
    REQUIRED_EXECUTABLES = ["augustus", "python"]
    DOCUMENTATION_URL = AUGUSTUS_DOCUMENTATION_URL
    CITATION_DOIS = AUGUSTUS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in AUGUSTUS_CITATION_DOIS]
    CITATION_TEXT = AUGUSTUS_CITATION_TEXT
    VERSION = "3.5.0+galaxy0"
    SHELL = True

    MODEL_MODES = ["builtin", "history"]
    STRANDS = ["both", "forward", "backward"]
    GENE_MODELS = ["complete", "partial", "intronless", "atleastone", "exactlyone"]
    OUTPUT_SELECTIONS = ["protein", "codingseq", "introns", "start", "stop", "cds"]
    DEFAULT_OUTPUTS = ["protein", "codingseq", "cds"]
    OUTPUT_FORMATS = ["gtf", "gff3"]
    ORGANISMS = [
        "human",
        "fly",
        "generic",
        "arabidopsis",
        "rice",
        "maize",
        "chicken",
        "zebrafish",
        "caenorhabditis",
        "s_aureus",
        "E_coli_K12",
        "template_prokaryotic",
    ]

    @classmethod
    def _selected_outputs(cls, inputs: dict[str, Any]) -> list[str]:
        if "outputs" in inputs:
            return _as_list(inputs.get("outputs"))
        return list(cls.DEFAULT_OUTPUTS)

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        if "output_format" in inputs:
            return str(inputs.get("output_format") or "gtf")
        return "gff3" if inputs.get("gff") else "gtf"

    @classmethod
    def _main_filename(cls, inputs: dict[str, Any]) -> str:
        return "augustus.gff3" if cls._output_format(inputs) == "gff3" else "augustus.gtf"

    @classmethod
    def _main_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._main_filename(inputs)}"

    @classmethod
    def _protein_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/protein.fasta"

    @classmethod
    def _codingseq_output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/codingseq.fasta"

    @classmethod
    def _model_mode(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("model_mode", inputs.get("augustus_mode", "builtin")) or "builtin")

    @classmethod
    def _history_model_stage(cls, inputs: dict[str, Any]) -> list[str]:
        if cls._model_mode(inputs) != "history":
            return []
        custom_model = str(inputs.get("custom_model", "") or "")
        return [
            "cp -r $(dirname $(command -v augustus))/../config/ augustus_dir/",
            "mkdir -p augustus_dir/species/",
            f"tar -C augustus_dir/species/ -xzvf {shlex.quote(custom_model)} > /dev/null",
            "export AUGUSTUS_CONFIG_PATH=./augustus_dir/",
        ]

    @classmethod
    def _augustus_command(cls, inputs: dict[str, Any]) -> str:
        selected = set(cls._selected_outputs(inputs))
        output_format = cls._output_format(inputs)
        cmd = [
            "augustus",
            f"--strand={str(inputs.get('strand', 'both') or 'both')}",
            f"--noInFrameStop={'true' if inputs.get('noInFrameStop') else 'false'}",
            "--gff3=on" if output_format == "gff3" else "--gff3=off",
            "--uniqueGeneId=true",
        ]
        for output in cls.OUTPUT_SELECTIONS:
            cmd.append(f"--{output}={'on' if output in selected else 'off'}")
        cmd.append(f"--singlestrand={'true' if inputs.get('singlestrand') else 'false'}")
        cmd.append(str(inputs.get("input_genome", "") or ""))
        cmd.append("--UTR=on" if inputs.get("utr") else "--UTR=off")
        cmd.append(f"--genemodel={str(inputs.get('genemodel', 'partial') or 'partial')}")
        cmd.append(f"--softmasking={'1' if inputs.get('softmasking', True) else '0'}")
        hintsfile = str(inputs.get("hintsfile", "") or "")
        extrinsiccfg = str(inputs.get("extrinsiccfg", "") or "")
        if hintsfile or extrinsiccfg:
            cmd.extend(["--hintsfile", hintsfile, "--extrinsicCfgFile", extrinsiccfg])
        if inputs.get("range_start") not in (None, "") or inputs.get("range_stop") not in (None, ""):
            cmd.append(f"--predictionStart={inputs.get('range_start', '')}")
            cmd.append(f"--predictionEnd={inputs.get('range_stop', '')}")
        if cls._model_mode(inputs) == "history":
            cmd.append("--species=local")
        else:
            cmd.append(f"--species={str(inputs.get('organism', 'human') or 'human')}")
        return _shell_join(cmd)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = cls._history_model_stage(inputs)
        selected = set(cls._selected_outputs(inputs))
        augustus_pipe = f"{cls._augustus_command(inputs)} | tee {shlex.quote(cls._main_output_path(inputs))}"
        extract_cmd = ["python", str(inputs.get("extract_features_path", "extract_features.py") or "extract_features.py")]
        if "protein" in selected:
            extract_cmd.extend(["--protein", cls._protein_output_path(inputs)])
        if "codingseq" in selected:
            extract_cmd.extend(["--codingseq", cls._codingseq_output_path(inputs)])
        if "protein" in selected or "codingseq" in selected:
            augustus_pipe = f"{augustus_pipe} | {_shell_join(extract_cmd)}"
        commands.append(augustus_pipe)
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        selected = set(cls._selected_outputs(inputs))
        outputs = [out / cls._main_filename(inputs)]
        if "protein" in selected:
            outputs.append(out / "protein.fasta")
        if "codingseq" in selected:
            outputs.append(out / "codingseq.fasta")
        return outputs

    @classmethod
    def _validate_range_inputs(cls, inputs: dict[str, Any]) -> bool | str:
        start_raw = inputs.get("range_start")
        stop_raw = inputs.get("range_stop")
        if start_raw in (None, "") and stop_raw in (None, ""):
            return True
        if start_raw in (None, ""):
            return "range_start is required when range_stop is provided"
        if stop_raw in (None, ""):
            return "range_stop is required when range_start is provided"
        try:
            start = int(start_raw)
            stop = int(stop_raw)
        except (TypeError, ValueError):
            return "range_start and range_stop must be integers"
        if start < 1:
            return "range_start must be greater than or equal to 1"
        if stop <= start:
            return "range_stop must be greater than range_start"
        return True

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input_genome", "") or "").strip():
            return "input_genome is required"
        model_mode = cls._model_mode(inputs)
        if model_mode not in cls.MODEL_MODES:
            return f"model_mode must be one of: {', '.join(cls.MODEL_MODES)}"
        if model_mode == "history" and not str(inputs.get("custom_model", "") or "").strip():
            return "custom_model is required when model_mode is history"
        strand = str(inputs.get("strand", "both") or "both")
        if strand not in cls.STRANDS:
            return f"strand must be one of: {', '.join(cls.STRANDS)}"
        genemodel = str(inputs.get("genemodel", "partial") or "partial")
        if genemodel not in cls.GENE_MODELS:
            return f"genemodel must be one of: {', '.join(cls.GENE_MODELS)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMATS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMATS)}"
        invalid_outputs = [output for output in cls._selected_outputs(inputs) if output not in cls.OUTPUT_SELECTIONS]
        if invalid_outputs:
            return f"outputs values must be one of: {', '.join(cls.OUTPUT_SELECTIONS)}"
        hintsfile = str(inputs.get("hintsfile", "") or "")
        extrinsiccfg = str(inputs.get("extrinsiccfg", "") or "")
        if hintsfile and not extrinsiccfg:
            return "extrinsiccfg is required when hintsfile is provided"
        if extrinsiccfg and not hintsfile:
            return "hintsfile is required when extrinsiccfg is provided"
        range_result = cls._validate_range_inputs(inputs)
        if range_result is not True:
            return range_result
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_genome": ("FASTA", {"description": "Genome FASTA or FASTA.GZ sequence to annotate"}),
                "model_mode": (
                    "STRING",
                    {
                        "default": "builtin",
                        "options": cls.MODEL_MODES,
                        "description": "Use a predefined AUGUSTUS species model or a trained model archive from history",
                    },
                ),
            },
            "optional": {
                "organism": (
                    "STRING",
                    {
                        "default": "human",
                        "options": cls.ORGANISMS,
                        "description": "Built-in AUGUSTUS species model name; any installed species name may be entered",
                    },
                ),
                "custom_model": ("FILE", {"default": "", "description": "AUGUSTUS trained model archive"}),
                "strand": (
                    "STRING",
                    {"default": "both", "options": cls.STRANDS, "description": "Predict genes on both or one strand"},
                ),
                "genemodel": (
                    "STRING",
                    {
                        "default": "partial",
                        "options": cls.GENE_MODELS,
                        "description": "AUGUSTUS gene model completeness mode",
                    },
                ),
                "outputs": (
                    "STRING_LIST",
                    {
                        "default": cls.DEFAULT_OUTPUTS,
                        "options": cls.OUTPUT_SELECTIONS,
                        "multiple": True,
                        "description": "AUGUSTUS feature comments to emit and optional FASTA files to extract",
                    },
                ),
                "output_format": (
                    "STRING",
                    {"default": "gtf", "options": cls.OUTPUT_FORMATS, "description": "Main annotation output format"},
                ),
                "noInFrameStop": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not report transcripts with in-frame stop codons"},
                ),
                "singlestrand": (
                    "BOOLEAN",
                    {"default": False, "description": "Predict genes independently on each strand"},
                ),
                "utr": (
                    "BOOLEAN",
                    {"default": False, "description": "Predict untranslated regions in addition to coding sequence"},
                ),
                "softmasking": (
                    "BOOLEAN",
                    {"default": True, "description": "Treat lowercase bases as repeat-masked sequence"},
                ),
                "hintsfile": ("GFF", {"default": "", "description": "Optional extrinsic hints GFF file"}),
                "extrinsiccfg": (
                    "FILE",
                    {"default": "", "description": "Extrinsic configuration file for hints"},
                ),
                "range_start": (
                    "INT",
                    {"default": "", "min": 1, "description": "Optional first nucleotide position to predict"},
                ),
                "range_stop": (
                    "INT",
                    {"default": "", "min": 1, "description": "Optional last nucleotide position to predict"},
                ),
                "extract_features_path": (
                    "STRING",
                    {"default": "extract_features.py", "advanced": True, "description": "Path to Galaxy extract_features.py helper"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _AugustusTrainingContract(ToolsIUCCommandContract):
    """Train an AUGUSTUS species model from MAKER annotations."""

    LEGACY_NODE_ID = "augustus_training"
    DISPLAY_NAME = "Train Augustus"
    REQUIRED_CONDA_PACKAGES = ["augustus", "maker"]
    CATEGORY = "annotation"
    DESCRIPTION = "Train an AUGUSTUS species model from genome sequence and MAKER gene annotations."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Train Augustus",
        "AUGUSTUS training",
        "augustus_training",
        "MAKER",
        "maker2zff",
        "autoAugTrain.pl",
        "gene predictor training",
    ]
    RETURN_TYPES = ("FILE",)
    RETURN_NAMES = ("output_tar",)
    REQUIRED_EXECUTABLES = ["augustus", "maker2zff", "zff2gff3.pl", "autoAugTrain.pl", "perl", "tar"]
    DOCUMENTATION_URL = AUGUSTUS_DOCUMENTATION_URL
    CITATION_DOIS = AUGUSTUS_CITATION_DOIS
    CITATION_URLS = [f"{DOI_URL}{doi}" for doi in AUGUSTUS_CITATION_DOIS]
    CITATION_TEXT = AUGUSTUS_CITATION_TEXT
    VERSION = "3.5.0+galaxy0"
    SHELL = True

    OUTPUT_FILENAME = "output_tar.augustus"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls.OUTPUT_FILENAME}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        genome = str(inputs.get("genome", "") or "")
        maker_gff = str(inputs.get("maker_gff", "") or "")
        return " && ".join(
            [
                "cp -r $(dirname $(command -v augustus))/../config/ augustus_dir/",
                "export AUGUSTUS_CONFIG_PATH=$(pwd)/augustus_dir/",
                _shell_join(["maker2zff", maker_gff]),
                "zff2gff3.pl genome.ann | perl -plne 's/\\t(\\S+)$/\\t\\.\\t$1/' > genome.gff3",
                f"autoAugTrain.pl --genome={shlex.quote(genome)} --species=local --trainingset=genome.gff3 -v",
                f"cd augustus_dir/species/ && tar cvfz {shlex.quote(cls._output_path(inputs))} local",
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls.OUTPUT_FILENAME]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("genome", "") or "").strip():
            return "genome is required"
        if not str(inputs.get("maker_gff", "") or "").strip():
            return "maker_gff is required"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "genome": ("FASTA", {"description": "Genome FASTA sequence used for AUGUSTUS training"}),
                "maker_gff": ("GFF", {"description": "MAKER GFF/GFF3 annotation used as the training set"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ArribaContract(ToolsIUCCommandContract):
    """Detect gene fusions from STAR-aligned RNA-Seq data."""

    LEGACY_NODE_ID = "arriba"
    DISPLAY_NAME = "Arriba"
    REQUIRED_CONDA_PACKAGES = ["arriba"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Detect gene fusions from STAR aligned RNA-Seq data with Arriba."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Arriba",
        "arriba",
        "gene fusions",
        "fusion transcript",
        "STAR Chimeric.out.sam",
        "RNA-Seq fusion detection",
        "aberrant transcripts",
    ]
    RETURN_TYPES = ("TSV", "TSV", "VCF", "DIRECTORY", "PDF")
    RETURN_NAMES = ("fusions_tsv", "discarded_fusions_tsv", "fusions_vcf", "fusion_bams", "fusions_pdf")
    REQUIRED_EXECUTABLES = [
        "arriba",
        "samtools",
        "convert_fusions_to_vcf.sh",
        "extract_fusion-supporting_alignments.sh",
        "draw_fusions.R",
    ]
    DOCUMENTATION_URL = ARRIBA_DOCUMENTATION_URL
    CITATION_DOIS = [ARRIBA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ARRIBA_CITATION_DOI}"]
    CITATION_TEXT = ARRIBA_CITATION_TEXT
    VERSION = "2.5.1+galaxy0"
    SHELL = True

    FILTER_OPTIONS = [
        "top_expressed_viral_contigs",
        "viral_contigs",
        "low_coverage_viral_contigs",
        "uninteresting_contigs",
        "no_genomic_support",
        "short_anchor",
        "select_best",
        "many_spliced",
        "long_gap",
        "merge_adjacent",
        "hairpin",
        "small_insert_size",
        "same_gene",
        "genomic_support",
        "read_through",
        "no_coverage",
        "mismatches",
        "homopolymer",
        "low_entropy",
        "multimappers",
        "inconsistently_clipped",
        "duplicates",
        "homologs",
        "blacklist",
        "mismappers",
        "spliced",
        "relative_support",
        "min_support",
        "known_fusions",
        "end_to_end",
        "non_coding_neighbors",
        "isoforms",
        "intronic",
        "in_vitro",
        "intragenic_exonic",
        "internal_tandem_duplication",
    ]
    STRANDEDNESS_OPTIONS = ["auto", "yes", "no", "reverse"]
    YES_NO_OPTIONS = ["yes", "no"]
    TRANSCRIPT_SELECTION_OPTIONS = ["coverage", "provided", "canonical"]
    MIN_CONFIDENCE_OPTIONS = ["none", "low", "medium", "high"]
    TRUE_FALSE_OPTIONS = ["TRUE", "FALSE"]
    VALUE_FLAGS = [
        ("gtf_features", "-G"),
        ("strandedness", "-s"),
        ("genome_contigs", "-i"),
        ("viral_contigs", "-v"),
        ("max_evalue", "-E"),
        ("min_supporting_reads", "-S"),
        ("max_mismappers", "-m"),
        ("max_homolog_identity", "-L"),
        ("homopolymer_length", "-H"),
        ("read_through_distance", "-R"),
        ("min_anchor_length", "-A"),
        ("many_spliced_events", "-M"),
        ("max_kmer_content", "-K"),
        ("max_mismatch_pvalue", "-V"),
        ("fragment_length", "-F"),
        ("max_reads", "-U"),
        ("quantile", "-Q"),
        ("exonic_fraction", "-e"),
        ("top_n", "-T"),
        ("covered_fraction", "-C"),
        ("max_itd_length", "-l"),
        ("min_itd_allele_fraction", "-z"),
        ("min_itd_supporting_reads", "-Z"),
    ]
    BOOLEAN_FLAGS = [
        ("duplicate_marking", "-u"),
        ("fill_discarded_columns", "-X"),
        ("fill_the_gaps", "-I"),
    ]
    DRAW_VALUE_OPTIONS = [
        ("transcript_selection", "--transcriptSelection", "transcriptSelection"),
        ("min_confidence_for_circos_plot", "--minConfidenceForCircosPlot", "minConfidenceForCircosPlot"),
        ("squish_introns", "--squishIntrons", "squishIntrons"),
        ("merge_domains_overlapping_by", "--mergeDomainsOverlappingBy", "mergeDomainsOverlappingBy"),
        ("sample_name", "--sampleName", "sampleName"),
        ("print_exon_labels", "--printExonLabels", "printExonLabels"),
        ("coverage_range", "--coverageRange", "coverageRange"),
        ("render_3d_effect", "--render3dEffect", "render3dEffect"),
        ("optimize_domain_colors", "--optimizeDomainColors", "optimizeDomainColors"),
        ("color1", "--color1", "color1"),
        ("color2", "--color2", "color2"),
        ("pdf_width", "--pdfWidth", "pdfWidth"),
        ("pdf_height", "--pdfHeight", "pdfHeight"),
        ("font_family", "--fontFamily", "fontFamily"),
        ("font_size", "--fontSize", "fontSize"),
        ("fixed_scale", "--fixedScale", "fixedScale"),
        ("plot_panels", "--plotPanels", "plotPanels"),
    ]

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _bool_default_true(cls, inputs: dict[str, Any], name: str) -> bool:
        return bool(inputs.get(name, True))

    @classmethod
    def _do_viz(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get("do_viz", inputs.get("visualization", "no")) or "no") == "yes"

    @classmethod
    def _filters(cls, inputs: dict[str, Any]) -> list[str]:
        filters = _as_list(inputs.get("filters"))
        if not str(inputs.get("blacklist", "") or "").strip() and "blacklist" not in filters:
            filters.append("blacklist")
        return filters

    @classmethod
    def _link_command(cls, source: str, target: str) -> str:
        return _shell_join(["ln", "-sf", source, target])

    @staticmethod
    def _flag_value(flag: str, value: Any) -> str:
        return f"{flag}={shlex.quote(str(value))}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [
            cls._link_command(str(inputs.get("genome_assembly", "") or ""), "genome.fa"),
            cls._link_command(str(inputs.get("annotation", "") or ""), "genome.gtf"),
        ]

        blacklist = str(inputs.get("blacklist", "") or "")
        blacklist_arg = blacklist
        if blacklist.endswith(".gz"):
            blacklist_arg = "blacklist.tsv.gz"
            commands.append(cls._link_command(blacklist, blacklist_arg))

        known_fusions = str(inputs.get("known_fusions", "") or "")
        known_fusions_arg = known_fusions
        if known_fusions.endswith(".gz"):
            known_fusions_arg = "known_fusions.tsv.gz"
            commands.append(cls._link_command(known_fusions, known_fusions_arg))

        tags = str(inputs.get("tags", "") or "")
        tags_arg = tags
        if tags.endswith(".gz"):
            tags_arg = "tags.tsv.gz"
            commands.append(cls._link_command(tags, tags_arg))

        cmd = [
            "arriba",
            "-x",
            str(inputs.get("input", "") or ""),
        ]
        _add_if_value(cmd, "-c", inputs.get("chimeric"))
        cmd.extend(["-a", "genome.fa", "-g", "genome.gtf"])
        _add_if_value(cmd, "-b", blacklist_arg)
        filters = cls._filters(inputs)
        if filters:
            cmd.extend(["-f", ",".join(filters)])
        _add_if_value(cmd, "-p", inputs.get("protein_domains"))
        _add_if_value(cmd, "-k", known_fusions_arg)
        _add_if_value(cmd, "-t", tags_arg)
        if str(inputs.get("use_wgs", "no") or "no") == "yes":
            _add_if_value(cmd, "-d", inputs.get("wgs"))
            _add_if_value(cmd, "-D", inputs.get("max_genomic_breakpoint_distance"))
        cmd.extend(["-o", cls._path(inputs, "fusions.tsv")])
        if cls._bool_default_true(inputs, "output_fusions_discarded"):
            cmd.extend(["-O", cls._path(inputs, "fusions.discarded.tsv")])
        for name, flag in cls.VALUE_FLAGS:
            _add_if_value(cmd, flag, inputs.get(name))
        for name, flag in cls.BOOLEAN_FLAGS:
            if inputs.get(name):
                cmd.append(flag)
        commands.append(_shell_join(cmd))

        sorted_bam = cls._path(inputs, "Aligned.sortedByCoord.out.bam")
        needs_sorted_bam = bool(inputs.get("output_fusion_bams")) or cls._do_viz(inputs)
        if needs_sorted_bam:
            sort_cmd = _shell_join(
                [
                    "samtools",
                    "sort",
                    "-@",
                    "${GALAXY_SLOTS:-1}",
                    "-m",
                    "4G",
                    "-T",
                    "tmp",
                    "-O",
                    "bam",
                    str(inputs.get("input", "") or ""),
                    ">",
                    sorted_bam,
                ]
            ).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}")
            commands.append(sort_cmd)
            commands.append(_shell_join(["samtools", "index", sorted_bam]))
        if cls._bool_default_true(inputs, "output_fusions_vcf"):
            commands.append(
                _shell_join(
                    [
                        "convert_fusions_to_vcf.sh",
                        "genome.fa",
                        cls._path(inputs, "fusions.tsv"),
                        cls._path(inputs, "fusions.vcf"),
                    ]
                )
            )
        if inputs.get("output_fusion_bams"):
            fusion_bams = cls._path(inputs, "fusion_bams")
            commands.append(_shell_join(["mkdir", "-p", fusion_bams]))
            commands.append(
                _shell_join(
                    [
                        "extract_fusion-supporting_alignments.sh",
                        cls._path(inputs, "fusions.tsv"),
                        sorted_bam,
                        f"{fusion_bams}/fusion",
                    ]
                )
            )
        if cls._do_viz(inputs):
            draw_cmd = [
                "draw_fusions.R",
                cls._flag_value("--fusions", cls._path(inputs, "fusions.tsv")),
                cls._flag_value("--alignments", sorted_bam),
                "--annotation=genome.gtf",
                cls._flag_value("--output", cls._path(inputs, "fusions.pdf")),
            ]
            if inputs.get("cytobands") not in (None, ""):
                draw_cmd.append(cls._flag_value("--cytobands", inputs.get("cytobands")))
            if inputs.get("protein_domains") not in (None, ""):
                draw_cmd.append(cls._flag_value("--proteinDomains", inputs.get("protein_domains")))
            squish_introns = str(inputs.get("squish_introns", "") or "")
            for name, flag, alias in cls.DRAW_VALUE_OPTIONS:
                value = inputs.get(name, inputs.get(alias))
                if name == "plot_panels" and value is True:
                    value = "TRUE"
                if value not in (None, "", False):
                    draw_cmd.append(cls._flag_value(flag, value))
                if name == "squish_introns":
                    squish_introns = str(value or squish_introns)
                    if squish_introns == "FALSE":
                        show_intergenic_vicinity = inputs.get(
                            "show_intergenic_vicinity",
                            inputs.get("showIntergenicVicinity"),
                        )
                        if show_intergenic_vicinity not in (None, ""):
                            draw_cmd.append(cls._flag_value("--showIntergenicVicinity", show_intergenic_vicinity))
            commands.append(" ".join(draw_cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [out / "fusions.tsv"]
        if cls._bool_default_true(inputs, "output_fusions_discarded"):
            outputs.append(out / "fusions.discarded.tsv")
        if cls._bool_default_true(inputs, "output_fusions_vcf"):
            outputs.append(out / "fusions.vcf")
        if inputs.get("output_fusion_bams"):
            outputs.append(out / "fusion_bams")
        if cls._do_viz(inputs):
            outputs.append(out / "fusions.pdf")
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "") or "").strip():
            return "input is required"
        if not str(inputs.get("genome_assembly", "") or "").strip():
            return "genome_assembly is required"
        if not str(inputs.get("annotation", "") or "").strip():
            return "annotation is required"
        invalid_filters = [value for value in _as_list(inputs.get("filters")) if value not in cls.FILTER_OPTIONS]
        if invalid_filters:
            return "filters values must be one of the supported Arriba filter names"
        strandedness = str(inputs.get("strandedness", "") or "")
        if strandedness and strandedness not in cls.STRANDEDNESS_OPTIONS:
            return f"strandedness must be one of: {', '.join(cls.STRANDEDNESS_OPTIONS)}"
        if str(inputs.get("use_wgs", "no") or "no") == "yes" and not str(inputs.get("wgs", "") or "").strip():
            return "wgs is required when use_wgs is yes"
        do_viz = str(inputs.get("do_viz", "no") or "no")
        if do_viz not in cls.YES_NO_OPTIONS:
            return f"do_viz must be one of: {', '.join(cls.YES_NO_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("BAM", {"description": "STAR Aligned.out SAM/BAM/CRAM file"}),
                "genome_assembly": ("FASTA", {"description": "Genome assembly FASTA used for STAR alignment"}),
                "annotation": ("GTF", {"description": "Gene annotation in GTF format"}),
            },
            "optional": {
                "chimeric": ("BAM", {"default": "", "description": "STAR Chimeric.out.sam for SeparateSAMold mode"}),
                "blacklist": ("TSV", {"default": "", "description": "Optional Arriba blacklist table"}),
                "protein_domains": ("GFF", {"default": "", "description": "Protein domain annotation in GFF3 format"}),
                "known_fusions": ("TSV", {"default": "", "description": "Known fusions table"}),
                "tags": ("TSV", {"default": "", "description": "Fusion tag table"}),
                "use_wgs": ("STRING", {"default": "no", "options": cls.YES_NO_OPTIONS}),
                "wgs": ("FILE", {"default": "", "description": "Optional WGS structural variant calls"}),
                "max_genomic_breakpoint_distance": ("INT", {"default": 100000, "min": 0, "advanced": True}),
                "filters": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.FILTER_OPTIONS,
                        "description": "Arriba filters to disable",
                    },
                ),
                "gtf_features": ("STRING", {"default": "", "advanced": True}),
                "strandedness": ("STRING", {"default": "", "options": cls.STRANDEDNESS_OPTIONS, "advanced": True}),
                "genome_contigs": ("STRING", {"default": "", "advanced": True}),
                "viral_contigs": ("STRING", {"default": "", "advanced": True}),
                "max_evalue": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "min_supporting_reads": ("INT", {"default": "", "min": 1, "advanced": True}),
                "max_mismappers": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "max_homolog_identity": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "homopolymer_length": ("INT", {"default": "", "min": 1, "advanced": True}),
                "read_through_distance": ("INT", {"default": "", "min": 1, "advanced": True}),
                "min_anchor_length": ("INT", {"default": "", "min": 1, "advanced": True}),
                "many_spliced_events": ("INT", {"default": "", "min": 1, "advanced": True}),
                "max_kmer_content": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "max_mismatch_pvalue": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "fragment_length": ("INT", {"default": "", "min": 1, "advanced": True}),
                "max_reads": ("INT", {"default": "", "min": 1, "advanced": True}),
                "quantile": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "exonic_fraction": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "top_n": ("INT", {"default": "", "min": 1, "advanced": True}),
                "covered_fraction": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "max_itd_length": ("INT", {"default": "", "min": 1, "advanced": True}),
                "min_itd_allele_fraction": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "min_itd_supporting_reads": ("INT", {"default": "", "min": 1, "advanced": True}),
                "duplicate_marking": ("BOOLEAN", {"default": False, "advanced": True}),
                "fill_discarded_columns": ("BOOLEAN", {"default": False, "advanced": True}),
                "fill_the_gaps": ("BOOLEAN", {"default": False, "advanced": True}),
                "output_fusions_discarded": ("BOOLEAN", {"default": True}),
                "output_fusions_vcf": ("BOOLEAN", {"default": True}),
                "output_fusion_bams": ("BOOLEAN", {"default": False}),
                "do_viz": ("STRING", {"default": "no", "options": cls.YES_NO_OPTIONS}),
                "cytobands": ("TSV", {"default": "", "advanced": True}),
                "sample_name": ("STRING", {"default": "", "advanced": True}),
                "transcript_selection": (
                    "STRING",
                    {"default": "provided", "options": cls.TRANSCRIPT_SELECTION_OPTIONS, "advanced": True},
                ),
                "min_confidence_for_circos_plot": (
                    "STRING",
                    {"default": "", "options": cls.MIN_CONFIDENCE_OPTIONS, "advanced": True},
                ),
                "squish_introns": ("STRING", {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True}),
                "show_intergenic_vicinity": ("STRING", {"default": "", "advanced": True}),
                "merge_domains_overlapping_by": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "print_exon_labels": ("STRING", {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True}),
                "coverage_range": ("STRING", {"default": "", "advanced": True}),
                "render_3d_effect": ("STRING", {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True}),
                "optimize_domain_colors": (
                    "STRING",
                    {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True},
                ),
                "color1": ("STRING", {"default": "", "advanced": True}),
                "color2": ("STRING", {"default": "", "advanced": True}),
                "pdf_width": ("FLOAT", {"default": "", "min": 1, "advanced": True}),
                "pdf_height": ("FLOAT", {"default": "", "min": 1, "advanced": True}),
                "font_family": ("STRING", {"default": "", "advanced": True}),
                "font_size": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "fixed_scale": ("INT", {"default": "", "min": 0, "advanced": True}),
                "plot_panels": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ArribaDrawFusionsContract(ToolsIUCCommandContract):
    """Render Arriba fusion predictions to PDF."""

    LEGACY_NODE_ID = "arriba_draw_fusions"
    DISPLAY_NAME = "Arriba Draw Fusions"
    REQUIRED_CONDA_PACKAGES = ["arriba"]
    CATEGORY = "visualization"
    DESCRIPTION = "Render Arriba fusion predictions as transcript visualization PDFs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Arriba Draw Fusions",
        "arriba_draw_fusions",
        "draw_fusions.R",
        "fusion visualization",
        "RNA-Seq fusion plot",
        "fusions.pdf",
    ]
    RETURN_TYPES = ("PDF",)
    RETURN_NAMES = ("fusions_pdf",)
    REQUIRED_EXECUTABLES = ["draw_fusions.R", "samtools"]
    DOCUMENTATION_URL = "https://github.com/suhrig/arriba/wiki/06-Visualization"
    CITATION_DOIS = [ARRIBA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ARRIBA_CITATION_DOI}"]
    CITATION_TEXT = ARRIBA_CITATION_TEXT
    VERSION = "2.5.1+galaxy0"
    SHELL = True

    ALIGNMENT_FORMATS = ["bam", "sam"]
    DRAW_VALUE_OPTIONS = _ArribaContract.DRAW_VALUE_OPTIONS
    TRANSCRIPT_SELECTION_OPTIONS = _ArribaContract.TRANSCRIPT_SELECTION_OPTIONS
    MIN_CONFIDENCE_OPTIONS = _ArribaContract.MIN_CONFIDENCE_OPTIONS
    TRUE_FALSE_OPTIONS = _ArribaContract.TRUE_FALSE_OPTIONS

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @staticmethod
    def _flag_value(flag: str, value: Any) -> str:
        return _ArribaContract._flag_value(flag, value)

    @classmethod
    def _alignment_format(cls, inputs: dict[str, Any]) -> str:
        explicit_format = str(inputs.get("alignments_format", "") or "").lower()
        if explicit_format:
            return explicit_format
        suffixes = "".join(Path(str(inputs.get("alignments", "") or "")).suffixes).lower()
        return "sam" if suffixes.endswith(".sam") else "bam"

    @classmethod
    def _sorted_bam(cls, inputs: dict[str, Any]) -> str:
        return cls._path(inputs, "Aligned.sortedByCoord.out.bam")

    @classmethod
    def _draw_command(cls, inputs: dict[str, Any]) -> str:
        draw_cmd = [
            "draw_fusions.R",
            cls._flag_value("--fusions", inputs.get("fusions", "")),
            cls._flag_value("--alignments", cls._sorted_bam(inputs)),
            cls._flag_value("--annotation", inputs.get("annotation", "")),
            cls._flag_value("--output", cls._path(inputs, "fusions.pdf")),
        ]
        if inputs.get("cytobands") not in (None, ""):
            draw_cmd.append(cls._flag_value("--cytobands", inputs.get("cytobands")))
        if inputs.get("protein_domains") not in (None, ""):
            draw_cmd.append(cls._flag_value("--proteinDomains", inputs.get("protein_domains")))
        squish_introns = str(inputs.get("squish_introns", "") or "")
        for name, flag, alias in cls.DRAW_VALUE_OPTIONS:
            value = inputs.get(name, inputs.get(alias))
            if name == "plot_panels" and value is True:
                value = "TRUE"
            if value not in (None, "", False):
                draw_cmd.append(cls._flag_value(flag, value))
            if name == "squish_introns":
                squish_introns = str(value or squish_introns)
                if squish_introns == "FALSE":
                    show_intergenic_vicinity = inputs.get(
                        "show_intergenic_vicinity",
                        inputs.get("showIntergenicVicinity"),
                    )
                    if show_intergenic_vicinity not in (None, ""):
                        draw_cmd.append(cls._flag_value("--showIntergenicVicinity", show_intergenic_vicinity))
        return " ".join(draw_cmd)

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands: list[str] = []
        alignments = str(inputs.get("alignments", "") or "")
        if cls._alignment_format(inputs) == "sam":
            commands.extend(
                [
                    _shell_join(["ln", "-sf", str(inputs.get("genome_assembly", "") or ""), "genome.fa"]),
                    "samtools faidx genome.fa",
                    _shell_join(
                        [
                            "samtools",
                            "view",
                            "-b",
                            "-@",
                            "${GALAXY_SLOTS:-1}",
                            "-t",
                            "genome.fa.fai",
                            alignments,
                            "|",
                            "samtools",
                            "sort",
                            "-O",
                            "bam",
                            "-@",
                            "${GALAXY_SLOTS:-1}",
                            "-T",
                            "${TMPDIR:-.}",
                            "-o",
                            cls._sorted_bam(inputs),
                        ]
                    )
                    .replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}")
                    .replace("'${TMPDIR:-.}'", "${TMPDIR:-.}"),
                    _shell_join(["samtools", "index", cls._sorted_bam(inputs)]),
                ]
            )
        else:
            commands.extend(
                [
                    _shell_join(["ln", "-sf", alignments, cls._sorted_bam(inputs)]),
                    _shell_join(
                        [
                            "ln",
                            "-sf",
                            str(inputs.get("alignments_index", "") or ""),
                            f"{cls._sorted_bam(inputs)}.bai",
                        ]
                    ),
                ]
            )
        commands.append(cls._draw_command(inputs))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "fusions.pdf"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("fusions", "") or "").strip():
            return "fusions is required"
        if not str(inputs.get("alignments", "") or "").strip():
            return "alignments is required"
        if not str(inputs.get("annotation", "") or "").strip():
            return "annotation is required"
        alignments_format = cls._alignment_format(inputs)
        if alignments_format not in cls.ALIGNMENT_FORMATS:
            return f"alignments_format must be one of: {', '.join(cls.ALIGNMENT_FORMATS)}"
        if alignments_format == "sam" and not str(inputs.get("genome_assembly", "") or "").strip():
            return "genome_assembly is required when alignments_format is sam"
        transcript_selection = str(inputs.get("transcript_selection", "") or "")
        if transcript_selection and transcript_selection not in cls.TRANSCRIPT_SELECTION_OPTIONS:
            return f"transcript_selection must be one of: {', '.join(cls.TRANSCRIPT_SELECTION_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "fusions": ("TSV", {"description": "Arriba fusions.tsv table"}),
                "alignments": ("BAM", {"description": "STAR Aligned.out SAM or BAM file"}),
                "annotation": ("GTF", {"description": "Gene annotation in GTF format"}),
            },
            "optional": {
                "alignments_format": ("STRING", {"default": "bam", "options": cls.ALIGNMENT_FORMATS}),
                "alignments_index": ("BAI", {"default": "", "description": "BAM index for BAM inputs"}),
                "genome_assembly": ("FASTA", {"default": "", "description": "Genome FASTA required for SAM inputs"}),
                "protein_domains": ("GFF", {"default": "", "description": "Protein domain annotation in GFF3 format"}),
                "cytobands": ("TSV", {"default": "", "description": "Optional cytobands table"}),
                "sample_name": ("STRING", {"default": "", "advanced": True}),
                "transcript_selection": (
                    "STRING",
                    {"default": "provided", "options": cls.TRANSCRIPT_SELECTION_OPTIONS, "advanced": True},
                ),
                "min_confidence_for_circos_plot": (
                    "STRING",
                    {"default": "", "options": cls.MIN_CONFIDENCE_OPTIONS, "advanced": True},
                ),
                "squish_introns": ("STRING", {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True}),
                "show_intergenic_vicinity": ("STRING", {"default": "", "advanced": True}),
                "merge_domains_overlapping_by": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "print_exon_labels": ("STRING", {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True}),
                "coverage_range": ("STRING", {"default": "", "advanced": True}),
                "render_3d_effect": ("STRING", {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True}),
                "optimize_domain_colors": (
                    "STRING",
                    {"default": "", "options": cls.TRUE_FALSE_OPTIONS, "advanced": True},
                ),
                "color1": ("STRING", {"default": "", "advanced": True}),
                "color2": ("STRING", {"default": "", "advanced": True}),
                "pdf_width": ("FLOAT", {"default": "", "min": 1, "advanced": True}),
                "pdf_height": ("FLOAT", {"default": "", "min": 1, "advanced": True}),
                "font_family": ("STRING", {"default": "", "advanced": True}),
                "font_size": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "fixed_scale": ("INT", {"default": "", "min": 0, "advanced": True}),
                "plot_panels": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ArribaGetFiltersContract(ToolsIUCCommandContract):
    """Copy bundled Arriba reference filter files into workflow outputs."""

    LEGACY_NODE_ID = "arriba_get_filters"
    DISPLAY_NAME = "Arriba Get Filters"
    REQUIRED_CONDA_PACKAGES = ["arriba"]
    CATEGORY = "databases"
    DESCRIPTION = "Copy bundled Arriba blacklist, known-fusion, protein-domain, and cytoband reference files."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Arriba Get Filters",
        "arriba_get_filters",
        "blacklist",
        "known fusions",
        "protein domains",
        "cytobands",
        "download_references.sh",
    ]
    RETURN_TYPES = ("FILE", "FILE", "GFF", "TSV")
    RETURN_NAMES = ("blacklist", "known_fusions", "protein_domains", "cytobands")
    REQUIRED_EXECUTABLES = ["arriba", "find", "grep", "cp"]
    DOCUMENTATION_URL = "https://github.com/suhrig/arriba/wiki/04-Input-files"
    CITATION_DOIS = [ARRIBA_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ARRIBA_CITATION_DOI}"]
    CITATION_TEXT = ARRIBA_CITATION_TEXT
    VERSION = "2.5.1+galaxy0"
    SHELL = True

    REFERENCES = ["GRCh38", "GRCh37", "hg38", "hg19", "GRCm39", "GRCm38", "mm39", "mm10"]
    OUTPUT_FILES = {
        "blacklist": "blacklist.tsv.gz",
        "known_fusions": "known_fusions.tsv.gz",
        "protein_domains": "protein_domains.gff3",
        "cytobands": "cytobands.tsv",
    }

    @classmethod
    def _reference_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("arriba_reference_name", "GRCh38") or "GRCh38").split("+")[0].replace("viral", "")

    @classmethod
    def _path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        ref_name = cls._reference_name(inputs)
        commands = [
            "BASE_DIR=$(dirname $(dirname $(which arriba)))",
            "REF_SCRIPT=$(find $BASE_DIR -name download_references.sh)",
            "REF_DIR=$(dirname $REF_SCRIPT)",
            f"REF_NAME={shlex.quote(ref_name)}",
            "echo $REF_NAME",
        ]
        for pattern, filename in [
            ("blacklist_*", cls.OUTPUT_FILES["blacklist"]),
            ("known_fusions_*", cls.OUTPUT_FILES["known_fusions"]),
            ("protein_domains_*", cls.OUTPUT_FILES["protein_domains"]),
            ("cytobands_*", cls.OUTPUT_FILES["cytobands"]),
        ]:
            commands.append(f"cp $(find $REF_DIR -name '{pattern}' | grep -i $REF_NAME) {shlex.quote(cls._path(inputs, filename))}")
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / cls.OUTPUT_FILES["blacklist"],
            out / cls.OUTPUT_FILES["known_fusions"],
            out / cls.OUTPUT_FILES["protein_domains"],
            out / cls.OUTPUT_FILES["cytobands"],
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        ref_name = cls._reference_name(inputs)
        if ref_name not in cls.REFERENCES:
            return f"arriba_reference_name must be one of: {', '.join(cls.REFERENCES)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "arriba_reference_name": (
                    "STRING",
                    {
                        "default": "GRCh38",
                        "options": cls.REFERENCES,
                        "description": "Bundled Arriba reference file set to copy",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ArticGuppyplexContract(ToolsIUCCommandContract):
    """Filter and combine Nanopore FASTQ reads with ARTIC guppyplex."""

    LEGACY_NODE_ID = "artic_guppyplex"
    DISPLAY_NAME = "ARTIC guppyplex"
    REQUIRED_CONDA_PACKAGES = ["artic"]
    CATEGORY = "sequence"
    DESCRIPTION = "Filter Nanopore reads by read length and optionally quality with ARTIC guppyplex."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ARTIC guppyplex",
        "artic_guppyplex",
        "guppyplex",
        "Nanopore read length filter",
        "amplicon sequencing",
        "ARTIC amplicon scheme",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("output",)
    REQUIRED_EXECUTABLES = ["artic", "bash", "gzip"]
    DOCUMENTATION_URL = ARTIC_DOCUMENTATION_URL
    CITATION_DOIS = []
    CITATION_URLS = [ARTIC_CITATION_URL]
    CITATION_TEXT = ARTIC_CITATION_TEXT
    VERSION = "1.7.3+galaxy1"
    SHELL = True

    STRUCTURES = ["one_to_one", "one_to_many"]
    FASTQ_FORMATS = ["fastq", "fastq.gz", "fastqsanger", "fastqsanger.gz"]

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit_ext = str(inputs.get("input_ext", "") or "")
        if explicit_ext:
            return explicit_ext
        first_read = _as_list(inputs.get("reads"))[0] if _as_list(inputs.get("reads")) else ""
        suffixes = [suffix.lstrip(".") for suffix in Path(first_read).suffixes]
        if len(suffixes) >= 2 and suffixes[-1] == "gz":
            return f"{suffixes[-2]}.gz"
        return suffixes[-1] if suffixes else "fastq"

    @classmethod
    def _compressed(cls, inputs: dict[str, Any]) -> bool:
        return cls._input_ext(inputs) in {"fastq.gz", "fastqsanger.gz"}

    @classmethod
    def _output_filename(cls, inputs: dict[str, Any]) -> str:
        return "guppyplex_out.fastq.gz" if cls._compressed(inputs) else "guppyplex_out.fastq"

    @classmethod
    def _inputs_dir(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/inputs"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        reads = _as_list(inputs.get("reads"))
        input_ext = cls._input_ext(inputs)
        commands = [_shell_join(["mkdir", "-p", cls._inputs_dir(inputs)])]
        if str(inputs.get("structure", "one_to_one") or "one_to_one") == "one_to_one":
            if reads:
                commands.append(_shell_join(["ln", "-s", reads[0], f"{cls._inputs_dir(inputs)}/1.{input_ext}"]))
        else:
            for idx, read in enumerate(reads):
                commands.append(_shell_join(["ln", "-s", read, f"{cls._inputs_dir(inputs)}/{idx}.{input_ext}"]))

        cmd = [
            "artic",
            "guppyplex",
            "--min-length",
            str(inputs.get("min_length", 400)),
            "--max-length",
            str(inputs.get("max_length", 700)),
        ]
        min_quality = int(inputs.get("min_quality", 7))
        if min_quality == 0:
            cmd.append("--skip-quality-check")
        else:
            cmd.extend(["--quality", str(min_quality)])
        cmd.extend(["--directory", f"{cls._inputs_dir(inputs)}/", "--output", f"{_out(inputs)}/guppyplex_out.fastq"])
        commands.append(_shell_join(cmd))
        if cls._compressed(inputs):
            commands.append(_shell_join(["gzip", f"{_out(inputs)}/guppyplex_out.fastq"]))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_filename(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not _as_list(inputs.get("reads")):
            return "reads is required"
        structure = str(inputs.get("structure", "one_to_one") or "one_to_one")
        if structure not in cls.STRUCTURES:
            return f"structure must be one of: {', '.join(cls.STRUCTURES)}"
        input_ext = cls._input_ext(inputs)
        if input_ext not in cls.FASTQ_FORMATS:
            return f"input_ext must be one of: {', '.join(cls.FASTQ_FORMATS)}"
        try:
            min_length = int(inputs.get("min_length", 400))
            max_length = int(inputs.get("max_length", 700))
            min_quality = int(inputs.get("min_quality", 7))
        except (TypeError, ValueError):
            return "min_length, max_length, and min_quality must be integers"
        if min_length < 1:
            return "min_length must be greater than or equal to 1"
        if max_length < 1:
            return "max_length must be greater than or equal to 1"
        if min_quality < 0:
            return "min_quality must be greater than or equal to 0"
        if max_length < min_length:
            return "max_length must be greater than or equal to min_length"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "reads": ("FASTQ", {"description": "Nanopore FASTQ reads to filter"}),
            },
            "optional": {
                "structure": (
                    "STRING",
                    {"default": "one_to_one", "options": cls.STRUCTURES, "description": "One or multiple input datasets"},
                ),
                "input_ext": ("STRING", {"default": "fastq", "options": cls.FASTQ_FORMATS}),
                "max_length": (
                    "INT",
                    {"default": 700, "min": 1, "description": "Remove reads greater than this number of base pairs"},
                ),
                "min_length": (
                    "INT",
                    {"default": 400, "min": 1, "description": "Remove reads less than this number of base pairs"},
                ),
                "min_quality": (
                    "INT",
                    {"default": 7, "min": 0, "description": "Set to 0 to skip the average-quality check"},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _ArticMinionContract(ToolsIUCCommandContract):
    """Call variants and build consensus sequence outputs with ARTIC minion."""

    LEGACY_NODE_ID = "artic_minion"
    DISPLAY_NAME = "ARTIC minion"
    REQUIRED_CONDA_PACKAGES = ["artic"]
    CATEGORY = "variant"
    DESCRIPTION = "Build consensus sequences and call variants from amplicon-based Nanopore reads with ARTIC minion."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ARTIC minion",
        "artic_minion",
        "amplicon consensus",
        "Nanopore variants",
        "Clair3",
        "primertrimmed BAM",
    ]
    RETURN_TYPES = ("BAM", "TSV", "VCF_GZ", "VCF_GZ", "VCF_GZ", "FASTA", "TSV", "TXT")
    RETURN_NAMES = (
        "alignment_trimmed",
        "alignment_report",
        "variants_merged_vcf",
        "variants_fail_vcf",
        "variants_pass_vcf",
        "consensus_fasta",
        "coverage_mask",
        "analysis_log",
    )
    REQUIRED_EXECUTABLES = ["artic", "run_clair3.sh", "samtools", "bgzip", "sed", "tar"]
    DOCUMENTATION_URL = ARTIC_DOCUMENTATION_URL
    CITATION_DOIS = []
    CITATION_URLS = [ARTIC_CITATION_URL]
    CITATION_TEXT = ARTIC_CITATION_TEXT
    VERSION = "1.7.3+galaxy1"
    SHELL = True

    FETCH_OPTIONS = ["yes", "no"]
    MODEL_SOURCES = ["built-in", "datatable", "history"]
    BUILT_IN_MODELS = ["r941_prom_sup_g5014", "r941_prom_hac_g360+g422"]
    PRIMER_SCHEME_SOURCES = ["tool_data_table", "history"]
    REFERENCE_SOURCES = ["cached", "history"]

    @classmethod
    def _sample_name(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("sample_name", "sample") or "sample")

    @classmethod
    def _model_commands(cls, inputs: dict[str, Any]) -> list[str]:
        source = str(inputs.get("model_source", "built-in") or "built-in")
        if source == "history":
            model = str(inputs.get("model", "") or "")
            quoted_model = shlex.quote(model)
            return [
                f"OUTNAME=$(tar -tf {quoted_model} | head -1 | cut -f1 -d/)",
                f"tar -xf {quoted_model}",
                "mv $OUTNAME clair3_model",
            ]
        if source == "datatable":
            model = str(inputs.get("model", "") or "")
            return [_shell_join(["ln", "-s", model, "clair3_model"])]
        model = str(inputs.get("select_built_in", "r941_prom_sup_g5014") or "r941_prom_sup_g5014")
        return [f"ln -s $(dirname $(which run_clair3.sh))/models/{shlex.quote(model)} clair3_model"]

    @classmethod
    def _reference_commands(cls, inputs: dict[str, Any]) -> list[str]:
        if str(inputs.get("fetch", "yes") or "yes") != "no":
            return []
        return [
            _shell_join(["ln", "-s", str(inputs.get("bed", "") or ""), "primer.bed"]),
            _shell_join(["ln", "-s", str(inputs.get("reference", "") or ""), "reference.fasta"]),
            _shell_join(["samtools", "faidx", "reference.fasta"]),
        ]

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        commands = [*cls._model_commands(inputs), *cls._reference_commands(inputs)]
        cmd = [
            "artic",
            "minion",
            "--read-file",
            str(inputs.get("read_file", "") or ""),
            "--threads",
            "${GALAXY_SLOTS:-1}",
        ]
        if str(inputs.get("fetch", "yes") or "yes") == "no":
            cmd.extend(["--bed", "primer.bed", "--ref", "reference.fasta"])
        else:
            cmd.extend(
                [
                    "--scheme-name",
                    str(inputs.get("scheme_name", "") or ""),
                    "--scheme-version",
                    str(inputs.get("scheme_version", "") or ""),
                    "--scheme-length",
                    str(inputs.get("scheme_length", 400)),
                ]
            )
        cmd.extend(
            [
                "--model-dir",
                ".",
                "--model",
                "clair3_model",
                "--min-depth",
                str(inputs.get("min_depth", 20)),
                "--min-mapq",
                str(inputs.get("min_mapq", 20)),
                "--primer-match-threshold",
                str(inputs.get("primer_match_threshold", 35)),
            ]
        )
        if inputs.get("align_consensus", False):
            cmd.append("--align-consensus")
        if inputs.get("linearise_fasta", False):
            cmd.append("--linearise-fasta")
        if inputs.get("allow_mismatched_primers", False):
            cmd.append("--allow-mismatched-primers")
        normalise = int(inputs.get("normalise", 0))
        if normalise > 0:
            cmd.extend(["--normalise", str(normalise)])
        sample_name = cls._sample_name(inputs)
        quoted_sample_name = shlex.quote(sample_name)
        minion_command = _shell_join(cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}")
        commands.append(f"{minion_command} \"'{quoted_sample_name}'\"")
        commands.append(_shell_join(["bgzip", "-f", f"{sample_name}.fail.vcf"]))
        commands.append(
            f"sed -i \"1s/'{quoted_sample_name}'/{quoted_sample_name}/\" "
            f"{shlex.quote(f'{sample_name}.consensus.fasta')}"
        )
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        sample_name = cls._sample_name(inputs)
        return [
            out / f"{sample_name}.primertrimmed.rg.sorted.bam",
            out / f"{sample_name}.alignreport.txt",
            out / f"{sample_name}.merged.vcf.gz",
            out / f"{sample_name}.fail.vcf.gz",
            out / f"{sample_name}.pass.vcf.gz",
            out / f"{sample_name}.consensus.fasta",
            out / f"{sample_name}.coverage_mask.txt",
            out / f"{sample_name}.minion.log.txt",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("read_file"):
            return "read_file is required"
        fetch = str(inputs.get("fetch", "yes") or "yes")
        if fetch not in cls.FETCH_OPTIONS:
            return f"fetch must be one of: {', '.join(cls.FETCH_OPTIONS)}"
        if fetch == "yes":
            if not inputs.get("scheme_name"):
                return "scheme_name is required when fetch is yes"
            if not inputs.get("scheme_version"):
                return "scheme_version is required when fetch is yes"
        else:
            if not inputs.get("bed"):
                return "bed is required when fetch is no"
            if not inputs.get("reference"):
                return "reference is required when fetch is no"
        model_source = str(inputs.get("model_source", "built-in") or "built-in")
        if model_source not in cls.MODEL_SOURCES:
            return f"model_source must be one of: {', '.join(cls.MODEL_SOURCES)}"
        if (
            model_source == "datatable"
            and str(inputs.get("model_data_source", "") or "") == "rerio"
            and not inputs.get("ont_license_agree", False)
        ):
            return "ont_license_agree is required for Rerio models"
        try:
            normalise = int(inputs.get("normalise", 0))
        except (TypeError, ValueError):
            return "normalise must be an integer"
        if normalise < 0:
            return "normalise must be greater than or equal to 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "read_file": ("FASTQ", {"description": "Nanopore FASTQ reads for ARTIC minion"}),
            },
            "optional": {
                "sample_name": ("STRING", {"default": "sample", "description": "Sample name prefix for minion outputs"}),
                "fetch": (
                    "STRING",
                    {"default": "yes", "options": cls.FETCH_OPTIONS, "description": "Fetch a named ARTIC primer scheme"},
                ),
                "scheme_name": ("STRING", {"default": "", "description": "ARTIC scheme name when fetching primers"}),
                "scheme_version": ("STRING", {"default": "", "description": "ARTIC scheme version when fetching primers"}),
                "scheme_length": ("INT", {"default": 400, "min": 1, "description": "ARTIC scheme amplicon length"}),
                "primer_scheme_source_selector": (
                    "STRING",
                    {"default": "tool_data_table", "options": cls.PRIMER_SCHEME_SOURCES},
                ),
                "bed": ("BED", {"description": "Primer BED file when not fetching a scheme"}),
                "reference_source_selector": (
                    "STRING",
                    {"default": "cached", "options": cls.REFERENCE_SOURCES},
                ),
                "reference": ("FASTA", {"description": "Reference FASTA when not fetching a scheme"}),
                "model_source": (
                    "STRING",
                    {"default": "built-in", "options": cls.MODEL_SOURCES, "description": "Clair3 model source"},
                ),
                "select_built_in": (
                    "STRING",
                    {"default": "r941_prom_sup_g5014", "options": cls.BUILT_IN_MODELS},
                ),
                "model": ("FILE", {"description": "Clair3 model from tool data or history"}),
                "model_data_source": ("STRING", {"default": "", "advanced": True}),
                "ont_license_agree": ("BOOLEAN", {"default": False, "advanced": True}),
                "min_depth": ("INT", {"default": 20, "min": 0}),
                "min_mapq": ("INT", {"default": 20, "min": 0}),
                "primer_match_threshold": ("INT", {"default": 35, "min": 0}),
                "normalise": ("INT", {"default": 0, "min": 0}),
                "align_consensus": ("BOOLEAN", {"default": False}),
                "linearise_fasta": ("BOOLEAN", {"default": False}),
                "allow_mismatched_primers": ("BOOLEAN", {"default": False}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _BUSCOContract(ToolsIUCCommandContract):
    """Assess genome, transcriptome, or proteome completeness with BUSCO."""

    LEGACY_NODE_ID = "busco"
    DISPLAY_NAME = "BUSCO"
    REQUIRED_CONDA_PACKAGES = ["busco"]
    CATEGORY = "assembly"
    DESCRIPTION = "Assess assembly or annotation completeness using BUSCO lineage orthologs."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "busco", "completeness", "orthologs", "assembly qc", "annotation qc"]
    RETURN_TYPES = ("STATS_FILE", "TSV", "TSV", "IMAGE")
    RETURN_NAMES = ("short_summary", "full_table", "missing_buscos", "summary_image")
    REQUIRED_EXECUTABLES = ["busco"]
    DOCUMENTATION_URL = "https://busco.ezlab.org/"
    CITATION_DOIS = ["10.1093/bioinformatics/btv351"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btv351"]
    CITATION_TEXT = "BUSCO: assessing genome assembly and annotation completeness with single-copy orthologs."
    VERSION = "5.8.0"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        mode = str(inputs.get("mode", "genome"))
        mode_aliases = {
            "genome": "genome",
            "geno": "genome",
            "transcriptome": "transcriptome",
            "tran": "transcriptome",
            "proteins": "proteins",
            "prot": "proteins",
        }
        galaxy_mode = mode_aliases.get(mode, mode)
        cmd = [
            "busco",
            "--in",
            str(inputs.get("input", "")),
            "--mode",
            galaxy_mode,
            "--out",
            "busco_galaxy",
            "--out_path",
            _out(inputs),
            "--cpu",
            str(inputs.get("threads", 4)),
            "--evalue",
            str(inputs.get("evalue", 0.001)),
            "--limit",
            str(inputs.get("limit", 3)),
            "--contig_break",
            str(inputs.get("contig_break", 10)),
        ]
        if inputs.get("offline", True):
            cmd.append("--offline")
        _add_if_value(cmd, "--download_path", inputs.get("download_path"))

        lineage_mode = str(inputs.get("lineage_mode", "select_lineage"))
        if lineage_mode == "auto_detect":
            cmd.append(str(inputs.get("auto_lineage", "--auto-lineage")))
        else:
            _add_if_value(cmd, "--lineage_dataset", inputs.get("lineage_dataset"))

        predictor = str(inputs.get("gene_predictor", "miniprot"))
        if galaxy_mode == "genome" and predictor in {"miniprot", "augustus", "metaeuk"}:
            cmd.append(f"--{predictor}")
        _add_if_value(cmd, "--augustus_species", inputs.get("augustus_species"))
        if inputs.get("long"):
            cmd.append("--long")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "short_summary.txt",
            out / "full_table.tsv",
            out / "missing_buscos.tsv",
            out / "summary.png",
        ]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "Assembly, transcriptome, or protein FASTA to analyse"}),
                "mode": ("STRING", {"default": "genome", "options": ["genome", "transcriptome", "proteins"]}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128, "display": "slider"}),
            },
            "optional": {
                "lineage_mode": ("STRING", {"default": "select_lineage", "options": ["select_lineage", "auto_detect"]}),
                "lineage_dataset": ("STRING", {"default": "bacteria_odb10", "description": "BUSCO lineage dataset such as bacteria_odb10"}),
                "auto_lineage": ("STRING", {"default": "--auto-lineage", "options": ["--auto-lineage", "--auto-lineage-prok", "--auto-lineage-euk"]}),
                "gene_predictor": ("STRING", {"default": "miniprot", "options": ["miniprot", "augustus", "metaeuk"], "advanced": True}),
                "augustus_species": ("STRING", {"default": "", "advanced": True}),
                "download_path": ("DIRECTORY", {"description": "Cached BUSCO download directory", "advanced": True}),
                "offline": ("BOOLEAN", {"default": True, "advanced": True}),
                "evalue": ("FLOAT", {"default": 0.001, "min": 0, "max": 1, "advanced": True}),
                "limit": ("INT", {"default": 3, "min": 1, "advanced": True}),
                "contig_break": ("INT", {"default": 10, "min": 1, "advanced": True}),
                "long": ("BOOLEAN", {"default": False, "description": "Enable Augustus self-training optimization", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _HTSeqCountContract(ToolsIUCCommandContract):
    """Count reads overlapping genomic features with HTSeq-count."""

    LEGACY_NODE_ID = "htseq_count"
    DISPLAY_NAME = "HTSeq-count"
    REQUIRED_CONDA_PACKAGES = ["htseq", "samtools"]
    CATEGORY = "rna_seq"
    DESCRIPTION = "Count aligned reads in SAM/BAM files that overlap GFF/GTF features."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "htseq-count", "htseq", "gene counts", "rna-seq counts"]
    RETURN_TYPES = ("COUNTS",)
    RETURN_NAMES = ("counts",)
    REQUIRED_EXECUTABLES = ["htseq-count", "samtools"]
    DOCUMENTATION_URL = "https://htseq.readthedocs.io/en/latest/htseqcount.html"
    CITATION_DOIS = ["10.1093/bioinformatics/btu638"]
    CITATION_URLS = ["https://doi.org/10.1093/bioinformatics/btu638"]
    CITATION_TEXT = "HTSeq: a Python framework to work with high-throughput sequencing data."
    VERSION = "2.1.2"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        samfile = str(inputs.get("samfile", ""))
        if inputs.get("sort_bam"):
            samfile = f"{_out(inputs)}/name_sorted.bam"
            cmd = ["samtools", "sort", "-n", "-o", samfile, str(inputs.get("samfile", "")), "&&"]
        else:
            cmd = []
        cmd.extend([
            "htseq-count",
            "--format=bam" if str(inputs.get("samfile", "")).lower().endswith(".bam") else "--format=sam",
            f"--mode={inputs.get('mode', 'union')}",
            f"--stranded={inputs.get('stranded', 'yes')}",
            f"--minaqual={inputs.get('minaqual', 0)}",
            f"--type={inputs.get('featuretype', 'exon')}",
            f"--idattr={inputs.get('idattr', 'gene_id')}",
            f"--nonunique={inputs.get('nonunique', 'none')}",
            f"--secondary-alignments={inputs.get('secondary_alignments', 'score')}",
            f"--supplementary-alignments={inputs.get('supplementary_alignments', 'score')}",
            f"--order={inputs.get('order', 'pos')}",
            samfile,
            str(inputs.get("gfffile", "")),
        ])
        _add_shell_redirect(cmd, f"{_out(inputs)}/counts.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "counts.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "samfile": ("BAM", {"description": "Aligned SAM/BAM file"}),
                "gfffile": ("GFF_GTF", {"description": "GFF/GTF feature annotation"}),
            },
            "optional": {
                "mode": ("STRING", {"default": "union", "options": ["union", "intersection-strict", "intersection-nonempty"]}),
                "stranded": ("STRING", {"default": "yes", "options": ["yes", "no", "reverse"]}),
                "minaqual": ("INT", {"default": 0, "min": 0}),
                "featuretype": ("STRING", {"default": "exon"}),
                "idattr": ("STRING", {"default": "gene_id"}),
                "nonunique": ("STRING", {"default": "none", "options": ["none", "all", "fraction", "random"]}),
                "secondary_alignments": ("STRING", {"default": "score", "options": ["score", "ignore"], "advanced": True}),
                "supplementary_alignments": ("STRING", {"default": "score", "options": ["score", "ignore"], "advanced": True}),
                "order": ("STRING", {"default": "pos", "options": ["pos", "name"], "advanced": True}),
                "sort_bam": ("BOOLEAN", {"default": False, "description": "Name-sort BAM with samtools before counting", "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }


class _RoaryContract(ToolsIUCCommandContract):
    """Calculate prokaryotic pan-genomes and core gene alignments from GFF3 annotations."""

    LEGACY_NODE_ID = "roary"
    DISPLAY_NAME = "Roary"
    REQUIRED_CONDA_PACKAGES = ["roary"]
    CATEGORY = "pangenomics"
    DESCRIPTION = (
        "Quickly generate prokaryotic pan-genome gene clusters and core gene alignments from GFF3 annotations."
    )
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Roary",
        "roary",
        "pan genome",
        "pangenome",
        "core gene alignment",
        "gene presence absence",
        "Prokka GFF3",
    ]
    RETURN_TYPES = (
        "TSV",
        "FASTA",
        "CSV",
        "FASTA",
        "FILE",
        "FILE",
        "FILE",
        "TSV",
        "TXT",
        "TXT",
        "FILE",
        "FILE",
        "TSV",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "TXT",
        "FASTA",
    )
    RETURN_NAMES = (
        "summary_statistics",
        "core_gene_alignment",
        "gene_presence_absence",
        "accessory_binary_genes",
        "accessory_binary_genes_newick",
        "accessory_graph",
        "accessory_header_embl",
        "accessory_table",
        "blast_identity_frequency",
        "clustered_proteins",
        "core_accessory_graph",
        "core_accessory_embl",
        "core_accessory_table",
        "gene_presence_absence_rtab",
        "number_of_conserved_genes",
        "number_of_genes_in_pan_genome",
        "number_of_new_genes",
        "number_of_unique_genes",
        "pan_genome_reference",
    )
    REQUIRED_EXECUTABLES = ["roary"]
    DOCUMENTATION_URL = f"{DOI_URL}{ROARY_CITATION_DOI}"
    CITATION_DOIS = [ROARY_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{ROARY_CITATION_DOI}"]
    CITATION_TEXT = ROARY_CITATION_TEXT
    VERSION = "3.13.0+galaxy3"
    SHELL = True

    GFF_INPUT_OPTIONS = ["individual", "collection"]
    OUTPUT_OPTIONS = [
        "abg_nw",
        "abg_fa",
        "accgraph",
        "acchead_embl",
        "acctab",
        "blastfreq",
        "clust",
        "coreaccgraph",
        "coreaccembl",
        "coreacctab",
        "genepa_rtab",
        "numcons_rtab",
        "numpangene_rtab",
        "numnew_rtab",
        "numuniq_rtab",
        "pangenomeref",
    ]
    OUTPUT_FILE_ORDER = [
        "abg_fa",
        "abg_nw",
        "accgraph",
        "acchead_embl",
        "acctab",
        "blastfreq",
        "clust",
        "coreaccgraph",
        "coreaccembl",
        "coreacctab",
        "genepa_rtab",
        "numcons_rtab",
        "numpangene_rtab",
        "numnew_rtab",
        "numuniq_rtab",
        "pangenomeref",
    ]
    TRANS_TAB_OPTIONS = [1, 4, 11]
    OPTIONAL_OUTPUT_PATHS = {
        "abg_fa": "accessory_binary_genes.fa",
        "abg_nw": "accessory_binary_genes.fa.newick",
        "accgraph": "accessory_graph.dot",
        "acchead_embl": "accessory.header.embl",
        "acctab": "accessory.tab",
        "blastfreq": "blast_identity_frequency.Rtab",
        "clust": "clustered_proteins",
        "coreaccgraph": "core_accessory_graph.dot",
        "coreaccembl": "core_accessory.header.embl",
        "coreacctab": "core_accessory.tab",
        "genepa_rtab": "gene_presence_absence.Rtab",
        "numcons_rtab": "number_of_conserved_genes.Rtab",
        "numpangene_rtab": "number_of_genes_in_pan_genome.Rtab",
        "numnew_rtab": "number_of_new_genes.Rtab",
        "numuniq_rtab": "number_of_unique_genes.Rtab",
        "pangenomeref": "pan_genome_reference.fa",
    }

    @staticmethod
    def _staged_gff_name(path: str) -> str:
        stem = Path(path).stem or "input"
        sanitized = sub(r"[^\w_-]", "_", stem)
        return f"{sanitized}.gff"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        staged_names: list[str] = []
        commands: list[str] = []
        for gff in _as_list(inputs.get("gffs")):
            staged_name = cls._staged_gff_name(gff)
            commands.append(_shell_join(["cp", gff, staged_name]))
            staged_names.append(staged_name)

        roary_cmd = [
            "roary",
            "-f",
            f"{_out(inputs)}/out",
            "-p",
            "${GALAXY_SLOTS:-1}",
            "-e",
            "-z",
            "-n",
            "-i",
            str(inputs.get("percent_ident", 95)),
            "-cd",
            str(inputs.get("core_diff", 99.0)),
            "-g",
            str(inputs.get("maxclust", 50000)),
        ]
        if inputs.get("split_para"):
            roary_cmd.append("-s")
        roary_cmd.extend([
            "-t",
            str(inputs.get("trans_tab", 11)),
            "-iv",
            str(inputs.get("mcl", 1.5)),
            *staged_names,
        ])
        commands.append(_shell_join(roary_cmd).replace("'${GALAXY_SLOTS:-1}'", "${GALAXY_SLOTS:-1}"))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outputs = [
            out / "summary_statistics.txt",
            out / "core_gene_alignment.aln",
            out / "gene_presence_absence.csv",
        ]
        requested_outputs = _as_list(inputs.get("outputs"))
        for option in cls.OUTPUT_FILE_ORDER:
            if option in requested_outputs:
                outputs.append(out / cls.OPTIONAL_OUTPUT_PATHS[option])
        return outputs

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if len(_as_list(inputs.get("gffs"))) < 2:
            return "at least two gffs are required"
        gff_input_selector = str(inputs.get("gff_input_selector", "individual"))
        if gff_input_selector not in cls.GFF_INPUT_OPTIONS:
            return f"gff_input_selector must be one of: {', '.join(cls.GFF_INPUT_OPTIONS)}"
        unsupported_outputs = [value for value in _as_list(inputs.get("outputs")) if value not in cls.OUTPUT_OPTIONS]
        if unsupported_outputs:
            return f"outputs contains unsupported values: {', '.join(unsupported_outputs)}"
        percent_ident = int(inputs.get("percent_ident", 95))
        if percent_ident < 1 or percent_ident > 100:
            return "percent_ident must be between 1 and 100"
        core_diff = float(inputs.get("core_diff", 99.0))
        if core_diff < 0 or core_diff > 100:
            return "core_diff must be between 0 and 100"
        maxclust = int(inputs.get("maxclust", 50000))
        if maxclust < 1:
            return "maxclust must be >= 1"
        trans_tab = int(inputs.get("trans_tab", 11))
        if trans_tab not in cls.TRANS_TAB_OPTIONS:
            return "trans_tab must be one of: 1, 4, 11"
        mcl = float(inputs.get("mcl", 1.5))
        if mcl <= 0:
            return "mcl must be > 0"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "gffs": (
                    "GFF",
                    {
                        "multiple": True,
                        "min_items": 2,
                        "description": "Two or more Prokka-style GFF3 annotation files for Roary",
                    },
                ),
            },
            "optional": {
                "gff_input_selector": (
                    "STRING",
                    {"default": "individual", "options": cls.GFF_INPUT_OPTIONS},
                ),
                "percent_ident": (
                    "INT",
                    {"default": 95, "min": 1, "max": 100, "description": "Minimum blastp percent identity"},
                ),
                "core_diff": (
                    "FLOAT",
                    {
                        "default": 99.0,
                        "min": 0,
                        "max": 100,
                        "description": "Percentage of isolates required for a gene to be core",
                    },
                ),
                "outputs": (
                    "STRING",
                    {
                        "default": [],
                        "multiple": True,
                        "options": cls.OUTPUT_OPTIONS,
                        "description": "Additional Roary output files to collect",
                    },
                ),
                "maxclust": ("INT", {"default": 50000, "min": 1, "advanced": True}),
                "split_para": (
                    "BOOLEAN",
                    {"default": False, "description": "Do not split paralogs", "advanced": True},
                ),
                "trans_tab": (
                    "INT",
                    {"default": 11, "options": cls.TRANS_TAB_OPTIONS, "advanced": True},
                ),
                "mcl": ("FLOAT", {"default": 1.5, "min": 0, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitStatsContract(ToolsIUCCommandContract):
    """Compute FASTA/Q summary statistics with SeqKit."""

    LEGACY_NODE_ID = "seqkit_stats"
    DISPLAY_NAME = "SeqKit Stats"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "qc"
    DESCRIPTION = "Compute sequence counts, length summaries, N50, and FASTQ quality statistics."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "seqkit", "stats", "fasta statistics", "fastq statistics", "n50"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("stats",)
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#stats"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["seqkit", "stats", str(inputs.get("input", ""))]
        if inputs.get("all"):
            cmd.append("--all")
        if inputs.get("basename"):
            cmd.append("--basename")
        if inputs.get("skip_err"):
            cmd.append("--skip-err")
        if inputs.get("tabular", True):
            cmd.append("--tabular")
        _add_shell_redirect(cmd, f"{_out(inputs)}/stats.tsv")
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "stats.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FASTQ_LIST", {"description": "FASTA or FASTQ file"})},
            "optional": {
                "all": ("BOOLEAN", {"default": False, "description": "Output all statistics"}),
                "basename": ("BOOLEAN", {"default": False, "description": "Report input basename only"}),
                "skip_err": ("BOOLEAN", {"default": False, "description": "Skip errors and show warnings"}),
                "tabular": ("BOOLEAN", {"default": True, "description": "Output tabular format"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKCompNode(CommandNode):
    """Report nucleotide composition for FASTA/Q records with seqtk comp."""

    LEGACY_NODE_ID = "seqtk_comp"
    DISPLAY_NAME = "SeqTK Composition"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "gawk"]
    CATEGORY = "sequence"
    DESCRIPTION = "Report per-record nucleotide composition for FASTA or FASTQ data with seqtk comp."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk comp",
        "SeqTK comp",
        "nucleotide composition",
        "FASTA composition",
        "FASTQ composition",
        "base composition",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("composition",)
    REQUIRED_EXECUTABLES = ["seqtk", "awk"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    HEADER = r"#chr\tlength\t#A\t#C\t#G\t#T\t#2\t#3\t#4\t#CpG\t#tv\t#ts\t#CpG-ts"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/composition.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "comp"]
        _add_if_value(cmd, "-r", inputs.get("in_bed"))
        cmd.append(str(inputs.get("in_file", "")))
        return (
            f"{_shell_join(cmd)} | "
            f"awk 'BEGIN{{print \"{cls.HEADER}\"}}1' "
            f"> {shlex.quote(cls._out_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "composition.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "in_bed": ("BED", {"default": "", "description": "Restrict composition to regions from this BED file"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKCutNNode(CommandNode):
    """Split FASTA/Q records at long N tracts with seqtk cutN."""

    LEGACY_NODE_ID = "seqtk_cutN"
    DISPLAY_NAME = "SeqTK CutN"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Split FASTA or FASTQ records at long N tracts with seqtk cutN."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk cutN",
        "SeqTK cutN",
        "seqtk split at N",
        "split at N",
        "long N tracts",
        "assembly gaps",
        "gaps BED",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ", "BED")
    RETURN_NAMES = ("split_sequences", "split_reads", "gaps_bed")
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("g"):
            return "gaps.bed"
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            ext = "fasta"
        elif ext in {"fq", "fastqsanger"}:
            ext = "fastq"
        elif ext in {"fa.gz", "fna.gz"}:
            ext = "fasta.gz"
        elif ext in {"fq.gz", "fastqsanger.gz"}:
            ext = "fastq.gz"
        return f"cutN.{ext}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "seqtk",
            "cutN",
            "-n",
            str(inputs.get("n", 1000)),
            "-p",
            str(inputs.get("p", 10)),
        ]
        if inputs.get("g"):
            cmd.append("-g")
        cmd.append(str(inputs.get("in_file", "")))
        if not inputs.get("g") and cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "n": ("INT", {"default": 1000, "min": 1, "description": "Minimum size of N tract"}),
                "p": ("INT", {"default": 10, "min": 0, "description": "Penalty for a non-N base"}),
                "g": ("BOOLEAN", {"default": False, "description": "Print gaps only as BED instead of split sequence"}),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "Input/output sequence format used to mirror Galaxy format_source",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKDropSENode(CommandNode):
    """Remove unpaired records from interleaved paired-end FASTA/Q with seqtk dropse."""

    LEGACY_NODE_ID = "seqtk_dropse"
    DISPLAY_NAME = "SeqTK DropSE"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Remove unpaired records from interleaved paired-end FASTA or FASTQ data with seqtk dropse."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk dropse",
        "SeqTK dropse",
        "drop single-end",
        "remove unpaired reads",
        "interleaved paired-end",
        "paired reads only",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ")
    RETURN_NAMES = ("paired_sequences", "paired_reads")
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        return SeqTKCutNNode._input_ext(inputs)

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            ext = "fasta"
        elif ext in {"fq", "fastqsanger"}:
            ext = "fastq"
        elif ext in {"fa.gz", "fna.gz"}:
            ext = "fasta.gz"
        elif ext in {"fq.gz", "fastqsanger.gz"}:
            ext = "fastq.gz"
        return f"paired.{ext}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "dropse", str(inputs.get("in_file", ""))]
        if cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Interleaved paired-end FASTA/Q file"}),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "Input/output sequence format used to mirror Galaxy format_source",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKFqchkNode(CommandNode):
    """Report FASTQ base composition and quality summaries with seqtk fqchk."""

    LEGACY_NODE_ID = "seqtk_fqchk"
    DISPLAY_NAME = "SeqTK FASTQ Check"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "gawk"]
    CATEGORY = "qc"
    DESCRIPTION = "Report base-by-base FASTQ composition and quality summaries with seqtk fqchk."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk fqchk",
        "SeqTK fqchk",
        "FASTQ QC",
        "base quality summary",
        "quality distribution",
        "base composition",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("quality_information",)
    REQUIRED_EXECUTABLES = ["seqtk", "awk"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/quality_information.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "fqchk", "-q", str(inputs.get("q", 20)), str(inputs.get("in_file", ""))]
        return (
            f"{_shell_join(cmd)} | "
            "awk '{if(NR<4){print \"#\"$0}else{print $0}}' "
            f"> {shlex.quote(cls._out_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "quality_information.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ", {"description": "Input FASTQ file, optionally gzip-compressed"}),
            },
            "optional": {
                "q": (
                    "INT",
                    {
                        "default": 20,
                        "min": 0,
                        "description": "Quality threshold; use 0 to report all quality values",
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKHetyNode(CommandNode):
    """Report regional heterozygosity with seqtk hety."""

    LEGACY_NODE_ID = "seqtk_hety"
    DISPLAY_NAME = "SeqTK Heterozygosity"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "gawk"]
    CATEGORY = "sequence"
    DESCRIPTION = "Report regional heterozygosity across FASTA or FASTQ data with seqtk hety."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk hety",
        "SeqTK hety",
        "regional heterozygosity",
        "heterozygous regions",
        "masked lowercase",
        "FASTA heterozygosity",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("heterozygous_regions",)
    REQUIRED_EXECUTABLES = ["seqtk", "awk"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    HEADER = r"#chr\tstart\tend\tA\tB\tnum_het"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/heterozygous_regions.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "seqtk",
            "hety",
            "-w",
            str(inputs.get("w", 50000)),
            "-t",
            str(inputs.get("t", 5)),
        ]
        if inputs.get("m"):
            cmd.append("-m")
        cmd.append(str(inputs.get("in_file", "")))
        return (
            f"{_shell_join(cmd)} | "
            f"awk 'BEGIN{{print \"{cls.HEADER}\"}}1' "
            f"> {shlex.quote(cls._out_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "heterozygous_regions.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "w": ("INT", {"default": 50000, "min": 1, "description": "Window size"}),
                "t": ("INT", {"default": 5, "min": 1, "description": "Number of start positions in a window"}),
                "m": ("BOOLEAN", {"default": False, "description": "Treat lowercase bases as masked"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKListHetNode(CommandNode):
    """List heterozygous ambiguity-base positions with seqtk listhet."""

    LEGACY_NODE_ID = "seqtk_listhet"
    DISPLAY_NAME = "SeqTK List Heterozygous Bases"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "gawk"]
    CATEGORY = "sequence"
    DESCRIPTION = "List positions of heterozygous IUPAC ambiguity bases in FASTA or FASTQ data."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk listhet",
        "SeqTK listhet",
        "heterozygous bases",
        "heterozygous positions",
        "IUPAC ambiguity bases",
        "ambiguous bases",
    ]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("heterozygous_bases",)
    REQUIRED_EXECUTABLES = ["seqtk", "awk"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    HEADER = r"#chr\tposition\tbase"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/heterozygous_bases.tsv"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "listhet", str(inputs.get("in_file", ""))]
        return (
            f"{_shell_join(cmd)} | "
            f"awk 'BEGIN{{print \"{cls.HEADER}\"}}1' "
            f"> {shlex.quote(cls._out_path(inputs))}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "heterozygous_bases.tsv"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKMergeFANode(CommandNode):
    """Merge two FASTA/Q files into FASTA with seqtk mergefa."""

    LEGACY_NODE_ID = "seqtk_mergefa"
    DISPLAY_NAME = "SeqTK Merge FASTA"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Merge two FASTA or FASTQ files into FASTA using IUPAC ambiguity codes."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk mergefa",
        "SeqTK mergefa",
        "merge FASTA",
        "merge FASTQ",
        "IUPAC ambiguity codes",
        "random allele",
        "suppress hets",
    ]
    RETURN_TYPES = ("FASTA",)
    RETURN_NAMES = ("merged_fasta",)
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy1"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_fa1", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if cls._input_ext(inputs).endswith(".gz"):
            return "merged.fasta.gz"
        return "merged.fasta"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "mergefa", "-q", str(inputs.get("q", 0))]
        for key, flag in (("i", "-i"), ("m", "-m"), ("r", "-r"), ("h", "-h")):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend([str(inputs.get("in_fa1", "")), str(inputs.get("in_fa2", ""))])
        if cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_fa1": ("FASTQ_LIST", {"description": "First input FASTA/Q file"}),
                "in_fa2": ("FASTQ_LIST", {"description": "Second input FASTA/Q file"}),
            },
            "optional": {
                "q": ("INT", {"default": 0, "min": 0, "description": "Quality threshold for FASTQ input"}),
                "i": ("BOOLEAN", {"default": False, "description": "Take the intersection of records"}),
                "m": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Pick the least ambiguous base, masking conflicts and uncertainties",
                    },
                ),
                "r": ("BOOLEAN", {"default": False, "description": "Pick a random allele from heterozygous bases"}),
                "h": ("BOOLEAN", {"default": False, "description": "Suppress heterozygous bases in the input"}),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "First input format used to mirror Galaxy dynamic output metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKMergePENode(CommandNode):
    """Interleave paired FASTA/Q files with seqtk mergepe."""

    LEGACY_NODE_ID = "seqtk_mergepe"
    DISPLAY_NAME = "SeqTK Merge Paired-End"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Interleave two unpaired FASTA or FASTQ files into a paired-end FASTA/Q file."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk mergepe",
        "SeqTK mergepe",
        "interleaved paired-end",
        "paired-end interleave",
        "merge paired reads",
        "paired FASTQ",
    ]
    # Single interleaved output (PLAN_OUTPUTS emits one file); its concrete
    # format follows the input (FASTA or FASTQ), so we expose one FASTQ port.
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("interleaved_pairs",)
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_fq1", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fastq"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            ext = "fasta"
        elif ext in {"fq", "fastqsanger"}:
            ext = "fastq"
        elif ext in {"fa.gz", "fna.gz"}:
            ext = "fasta.gz"
        elif ext in {"fq.gz", "fastqsanger.gz"}:
            ext = "fastq.gz"
        return f"interleaved.{ext}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "mergepe", str(inputs.get("in_fq1", "")), str(inputs.get("in_fq2", ""))]
        if cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_fq1": ("FASTQ_LIST", {"description": "First unpaired FASTA/Q file"}),
                "in_fq2": ("FASTQ_LIST", {"description": "Second unpaired FASTA/Q file"}),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "First input format used to mirror Galaxy format_source metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKMutFANode(CommandNode):
    """Apply point mutations to FASTA/Q records with seqtk mutfa."""

    LEGACY_NODE_ID = "seqtk_mutfa"
    DISPLAY_NAME = "SeqTK Mutate FASTA"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Apply point mutations from a tabular SNP file to FASTA or FASTQ sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk mutfa",
        "SeqTK mutfa",
        "point mutations",
        "SNP mutations",
        "mutate FASTA",
        "mutate FASTQ",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ")
    RETURN_NAMES = ("mutated_sequences", "mutated_reads")
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            ext = "fasta"
        elif ext in {"fq", "fastqsanger"}:
            ext = "fastq"
        elif ext in {"fa.gz", "fna.gz"}:
            ext = "fasta.gz"
        elif ext in {"fq.gz", "fastqsanger.gz"}:
            ext = "fastq.gz"
        return f"mutated.{ext}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "mutfa", str(inputs.get("in_file", "")), str(inputs.get("in_snp", ""))]
        if cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
                "in_snp": (
                    "TSV",
                    {
                        "description": (
                            "SNP table with chromosome, 1-based position, placeholder, and replacement base columns"
                        ),
                    },
                ),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "Input/output sequence format used to mirror Galaxy format_source metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKRandBaseNode(CommandNode):
    """Randomly resolve ambiguous bases with seqtk randbase."""

    LEGACY_NODE_ID = "seqtk_randbase"
    DISPLAY_NAME = "SeqTK Random Base"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Randomly resolve ambiguous IUPAC bases in FASTA or FASTQ sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk randbase",
        "SeqTK randbase",
        "ambiguous bases",
        "IUPAC ambiguity",
        "random base",
        "resolve heterozygous bases",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ")
    RETURN_NAMES = ("unambiguous_sequences", "unambiguous_reads")
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            ext = "fasta"
        elif ext in {"fq", "fastqsanger"}:
            ext = "fastq"
        elif ext in {"fa.gz", "fna.gz"}:
            ext = "fasta.gz"
        elif ext in {"fq.gz", "fastqsanger.gz"}:
            ext = "fastq.gz"
        return f"unambiguous.{ext}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "randbase", str(inputs.get("in_file", ""))]
        if cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "Input/output sequence format used to mirror Galaxy format_source metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKSampleNode(CommandNode):
    """Randomly subsample FASTA/Q records with seqtk sample."""

    LEGACY_NODE_ID = "seqtk_sample"
    DISPLAY_NAME = "SeqTK Sample"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Randomly subsample FASTA or FASTQ sequences with a reproducible seed."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk sample",
        "SeqTK sample",
        "subsample reads",
        "random subsample",
        "FASTQ subsampling",
        "RNG seed",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ")
    RETURN_NAMES = ("subsampled_sequences", "subsampled_reads")
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            ext = "fasta"
        elif ext in {"fq", "fastqsanger"}:
            ext = "fastq"
        elif ext in {"fa.gz", "fna.gz"}:
            ext = "fasta.gz"
        elif ext in {"fq.gz", "fastqsanger.gz"}:
            ext = "fastq.gz"
        return f"subsampled.{ext}"

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "seqtk",
            "sample",
            "-s",
            str(inputs.get("s", 4)),
        ]
        if not cls._bool_value(inputs.get("single_pass_mode", False)):
            cmd.append("-2")
        cmd.extend([str(inputs.get("in_file", "")), str(inputs.get("subsample_size", 100))])
        if cls._input_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
                "subsample_size": (
                    "FLOAT",
                    {
                        "default": 100,
                        "description": "Subsample size as an integer read count or decimal fraction",
                    },
                ),
            },
            "optional": {
                "s": ("INT", {"default": 4, "description": "Random number generator seed"}),
                "single_pass_mode": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Enable one-pass mode; default two-pass mode emits -2 for lower memory use",
                        "advanced": True,
                    },
                ),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "Input/output sequence format used to mirror Galaxy format_source metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKSeqNode(CommandNode):
    """Transform FASTA/Q records with seqtk seq."""

    LEGACY_NODE_ID = "seqtk_seq"
    DISPLAY_NAME = "SeqTK Seq"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Transform FASTA or FASTQ sequences with seqtk seq."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk seq",
        "SeqTK seq",
        "reverse complement",
        "force FASTA",
        "quality masking",
        "mask regions",
        "drop ambiguous bases",
        "sample fraction",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ")
    RETURN_NAMES = ("transformed_sequences", "transformed_reads")
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy1"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    @classmethod
    def _normalized_output_ext(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if cls._bool_value(inputs.get("A", False)):
            return "fasta.gz" if ext in {"fasta.gz", "fastq.gz"} else "fasta"
        if ext in {"fa", "fna"}:
            return "fasta"
        if ext in {"fq", "fastqsanger", "fastqillumina"}:
            return "fastq"
        if ext in {"fa.gz", "fna.gz"}:
            return "fasta.gz"
        if ext in {"fq.gz", "fastqsanger.gz", "fastqillumina.gz"}:
            return "fastq.gz"
        return ext or "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return f"transformed.{cls._normalized_output_ext(inputs)}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "seqtk",
            "seq",
            "-q",
            str(inputs.get("q", 0)),
            "-X",
            str(inputs.get("X", 255)),
        ]
        _add_if_value(cmd, "-n", inputs.get("n"))
        cmd.extend(
            [
                "-l",
                str(inputs.get("l", 0)),
                "-Q",
                str(inputs.get("Q", 33)),
                "-s",
                str(inputs.get("s", 11)),
                "-f",
                str(inputs.get("f", 1)),
            ]
        )
        _add_if_value(cmd, "-M", inputs.get("M"))
        cmd.extend(["-L", str(inputs.get("L", 0))])
        if cls._bool_value(inputs.get("c", False)):
            cmd.append("-c")
        direction = str(inputs.get("direction", "forward") or "forward")
        if direction != "forward":
            cmd.append(direction)
        for key, flag in (("A", "-A"), ("C", "-C"), ("N", "-N"), ("x1", "-1"), ("x2", "-2")):
            if cls._bool_value(inputs.get(key, False)):
                cmd.append(flag)
        if cls._input_ext(inputs) == "fastqillumina" or cls._bool_value(inputs.get("fastqillumina", False)):
            cmd.append("-V")
        cmd.append(str(inputs.get("in_file", "")))
        if cls._normalized_output_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "q": ("INT", {"default": 0, "description": "Mask bases with quality lower than this value"}),
                "X": ("INT", {"default": 255, "description": "Mask bases with quality higher than this value"}),
                "n": (
                    "STRING",
                    {
                        "default": "",
                        "description": "Convert masked bases to this character; blank leaves lowercase masking",
                    },
                ),
                "l": ("INT", {"default": 0, "description": "Number of residues per line; 0 keeps seqtk default"}),
                "Q": ("INT", {"default": 33, "description": "ASCII quality offset used for quality comparisons"}),
                "s": ("INT", {"default": 11, "description": "Random seed used with sample fraction"}),
                "f": ("FLOAT", {"default": 1, "description": "Sample fraction of sequences"}),
                "M": ("FILE", {"default": "", "description": "BED or name-list file of regions to mask"}),
                "L": ("INT", {"default": 0, "description": "Drop sequences shorter than this length"}),
                "c": ("BOOLEAN", {"default": False, "description": "Mask complement regions when a mask file is supplied"}),
                "direction": (
                    "STRING",
                    {
                        "default": "forward",
                        "options": ["forward", "-r", "-R"],
                        "description": "Output forward, reverse complement, or both directions",
                    },
                ),
                "A": ("BOOLEAN", {"default": False, "description": "Force FASTA output and discard qualities"}),
                "C": ("BOOLEAN", {"default": False, "description": "Drop comments from header lines"}),
                "N": ("BOOLEAN", {"default": False, "description": "Drop sequences containing ambiguous bases"}),
                "x1": ("BOOLEAN", {"default": False, "description": "Output only 2n-1 reads"}),
                "x2": ("BOOLEAN", {"default": False, "description": "Output only 2n reads"}),
                "fastqillumina": (
                    "BOOLEAN",
                    {
                        "default": False,
                        "description": "Apply the Galaxy fastqillumina quality-shift flag (-V)",
                        "advanced": True,
                    },
                ),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz", "fastqillumina"],
                        "description": "Input/output sequence format used to mirror Galaxy dynamic output metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKSubseqNode(CommandNode):
    """Extract selected FASTA/Q records with seqtk subseq."""

    LEGACY_NODE_ID = "seqtk_subseq"
    DISPLAY_NAME = "SeqTK Subsequence"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "gawk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Extract selected FASTA or FASTQ records by BED regions or sequence IDs."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk subseq",
        "SeqTK subseq",
        "extract subsequences",
        "BED regions",
        "sequence ID list",
        "FASTA IDs",
        "selected sequences",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ", "TSV")
    RETURN_NAMES = ("selected_sequences", "selected_reads", "selected_table")
    REQUIRED_EXECUTABLES = ["seqtk", "awk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fasta"

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "-t"}
        return bool(value)

    @classmethod
    def _output_ext(cls, inputs: dict[str, Any]) -> str:
        if cls._bool_value(inputs.get("t", False)):
            return "tsv"
        ext = cls._input_ext(inputs)
        if ext in {"fa", "fna"}:
            return "fasta"
        if ext in {"fq", "fastqsanger"}:
            return "fastq"
        if ext in {"fa.gz", "fna.gz"}:
            return "fasta.gz"
        if ext in {"fq.gz", "fastqsanger.gz"}:
            return "fastq.gz"
        return ext or "fasta"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return f"selected.{cls._output_ext(inputs)}"

    @classmethod
    def _source_path(cls, inputs: dict[str, Any]) -> str:
        source_type = str(inputs.get("source_type", "bed") or "bed")
        if source_type == "bed":
            return str(inputs.get("in_bed", ""))
        return str(inputs.get("name_list", ""))

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = ["seqtk", "subseq"]
        if cls._bool_value(inputs.get("t", False)):
            cmd.append("-t")
        cmd.extend(["-l", str(inputs.get("l", 0)), str(inputs.get("in_file", "")), cls._source_path(inputs)])
        command = _shell_join(cmd)
        if cls._bool_value(inputs.get("t", False)):
            return f"{command} | awk 'BEGIN{{print \"chr\\tunknown\\tseq\"}}1' > {shlex.quote(cls._out_path(inputs))}"
        if cls._output_ext(inputs).endswith(".gz"):
            return (
                f"{command} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{command} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base = super().VALIDATE_INPUTS(inputs)
        if base is not True:
            return base
        source_type = str(inputs.get("source_type", "bed") or "bed")
        if source_type not in {"bed", "name"}:
            return f"Unsupported source_type: {source_type}"
        if source_type == "bed" and not str(inputs.get("in_bed", "")).strip():
            return "in_bed is required when source_type is 'bed'"
        if source_type == "name" and not str(inputs.get("name_list", "")).strip():
            return "name_list is required when source_type is 'name'"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "source_type": (
                    "STRING",
                    {
                        "default": "bed",
                        "options": ["bed", "name"],
                        "description": "Select sequences by BED regions or by a newline-delimited ID list",
                    },
                ),
                "in_bed": ("BED", {"default": "", "description": "BED intervals to extract when source_type is bed"}),
                "name_list": (
                    "TXT",
                    {"default": "", "description": "Newline-delimited FASTA/Q IDs to extract when source_type is name"},
                ),
                "t": ("BOOLEAN", {"default": False, "description": "Emit tab-delimited output with a Galaxy header"}),
                "l": ("INT", {"default": 0, "description": "Sequence line length"}),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": ["fasta", "fastq", "fasta.gz", "fastq.gz"],
                        "description": "Input/output sequence format used to mirror Galaxy format_source metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKTeloNode(CommandNode):
    """Find telomeric repeats with seqtk telo."""

    LEGACY_NODE_ID = "seqtk_telo"
    DISPLAY_NAME = "SeqTK Telomere"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "sequence"
    DESCRIPTION = "Find telomeric repeat regions in FASTA or FASTQ sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk telo",
        "SeqTK telo",
        "telomere",
        "telomere repeat",
        "vertebrate repeat",
        "CCCTAA",
        "telomeric regions",
    ]
    RETURN_TYPES = ("BED",)
    RETURN_NAMES = ("telomeres",)
    REQUIRED_EXECUTABLES = ["seqtk"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @staticmethod
    def _bool_value(value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on", "-p"}
        return bool(value)

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/telomeres.bed"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        cmd = [
            "seqtk",
            "telo",
            "-m",
            str(inputs.get("m", "CCCTAA")),
            "-p",
            str(inputs.get("p", 1)),
            "-d",
            str(inputs.get("d", 2000)),
            "-s",
            str(inputs.get("s", 300)),
        ]
        if cls._bool_value(inputs.get("P", False)):
            cmd.append("-P")
        cmd.append(str(inputs.get("in_file", "")))
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / "telomeres.bed"]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTA/Q file, optionally gzip-compressed"}),
            },
            "optional": {
                "m": ("STRING", {"default": "CCCTAA", "description": "Telomere repeat motif to search for"}),
                "p": ("INT", {"default": 1, "description": "Penalty for a non-repeat"}),
                "d": ("INT", {"default": 2000, "description": "Maximum score drop"}),
                "s": ("INT", {"default": 300, "description": "Minimum telomere score"}),
                "P": ("BOOLEAN", {"default": False, "description": "Print scoring information"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _LegacySeqTKTrimFQNode(CommandNode):
    """Trim FASTQ reads with seqtk trimfq."""

    LEGACY_NODE_ID = "seqtk_trimfq"
    DISPLAY_NAME = "SeqTK Trim FASTQ"
    REQUIRED_CONDA_PACKAGES = ["seqtk", "pigz"]
    CATEGORY = "trimming"
    DESCRIPTION = "Trim FASTQ reads by Phred quality or fixed end positions."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqtk",
        "seqtk trimfq",
        "SeqTK trimfq",
        "FASTQ trimming",
        "Phred trimming",
        "quality trimming",
        "trim reads",
        "fixed position trim",
    ]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("trimmed_reads",)
    REQUIRED_EXECUTABLES = ["seqtk", "pigz"]
    DOCUMENTATION_URL = SEQTK_CITATION_URL
    CITATION_DOIS: list[str] = []
    CITATION_URLS = [SEQTK_CITATION_URL]
    CITATION_TEXT = SEQTK_CITATION_TEXT
    VERSION = "1.5+galaxy0"
    SHELL = True

    @classmethod
    def _input_ext(cls, inputs: dict[str, Any]) -> str:
        explicit = str(inputs.get("input_ext", "") or "").strip().lstrip(".")
        if explicit:
            return explicit
        suffixes = Path(str(inputs.get("in_file", ""))).suffixes
        if len(suffixes) >= 2 and suffixes[-1] == ".gz":
            return f"{suffixes[-2].lstrip('.')}.gz"
        if suffixes:
            return suffixes[-1].lstrip(".")
        return "fastq"

    @classmethod
    def _output_ext(cls, inputs: dict[str, Any]) -> str:
        ext = cls._input_ext(inputs)
        if ext in {"fq", "fastqsanger"}:
            return "fastq"
        if ext in {"fq.gz", "fastqsanger.gz"}:
            return "fastq.gz"
        return ext or "fastq"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return f"trimmed.{cls._output_ext(inputs)}"

    @classmethod
    def _out_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/{cls._output_name(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        mode = str(inputs.get("mode_select", "quality") or "quality")
        cmd = ["seqtk", "trimfq"]
        if mode == "position":
            cmd.extend(["-b", str(inputs.get("b", 0)), "-e", str(inputs.get("e", 0))])
        else:
            cmd.extend(["-q", str(inputs.get("q", 0.05)), "-l", str(inputs.get("l", 30))])
        cmd.append(str(inputs.get("in_file", "")))
        if cls._output_ext(inputs).endswith(".gz"):
            return (
                f"{_shell_join(cmd)} | "
                f"pigz -p ${{GALAXY_SLOTS:-1}} --no-name --no-time "
                f"> {shlex.quote(cls._out_path(inputs))}"
            )
        return f"{_shell_join(cmd)} > {shlex.quote(cls._out_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        base = super().VALIDATE_INPUTS(inputs)
        if base is not True:
            return base
        mode = str(inputs.get("mode_select", "quality") or "quality")
        if mode not in {"quality", "position"}:
            return f"Unsupported trim mode: {mode}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "in_file": ("FASTQ_LIST", {"description": "Input FASTQ file, optionally gzip-compressed"}),
            },
            "optional": {
                "mode_select": (
                    "STRING",
                    {
                        "default": "quality",
                        "options": ["quality", "position"],
                        "description": "Trim by quality thresholds or fixed end positions",
                    },
                ),
                "q": ("FLOAT", {"default": 0.05, "description": "Error rate threshold for quality trimming"}),
                "l": ("INT", {"default": 30, "description": "Maximally trim down to this read length"}),
                "b": ("INT", {"default": 0, "description": "Trim this many bases from the left end"}),
                "e": ("INT", {"default": 0, "description": "Trim this many bases from the right end"}),
                "input_ext": (
                    "STRING",
                    {
                        "default": "fastq",
                        "options": ["fastq", "fastq.gz", "fastqsanger", "fastqsanger.gz"],
                        "description": "Input/output FASTQ format used to mirror Galaxy format_source metadata",
                        "advanced": True,
                    },
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitGrepContract(ToolsIUCCommandContract):
    """Search FASTA/Q records by ID, name, or sequence with SeqKit grep."""

    LEGACY_NODE_ID = "seqkit_grep"
    DISPLAY_NAME = "SeqKit Grep"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Filter FASTA or FASTQ records by ID, full name, sequence motif, or a file of patterns using SeqKit grep."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "seqkit", "grep", "seqkit grep", "FASTA grep", "FASTQ grep", "motif search", "sequence filter"]
    RETURN_TYPES = ("FASTQ", "FASTA", "STATS_FILE")
    RETURN_NAMES = ("fastq_output", "fasta_output", "count")
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#grep"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        if inputs.get("count"):
            return "count.txt"
        ext = str(inputs.get("output_ext", "fasta.gz")).strip().lstrip(".") or "fasta.gz"
        return f"grep.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = ["seqkit", "grep", "--threads", str(inputs.get("threads", 4))]
        pattern_mode = str(inputs.get("pattern_mode", "expression"))
        if pattern_mode == "file":
            cmd.extend(["--pattern-file", str(inputs.get("pattern_file", ""))])
        else:
            cmd.extend(["--pattern", str(inputs.get("pattern", ""))])
            if inputs.get("use_regexp"):
                cmd.append("--use-regexp")
        for key, flag in (
            ("allow_duplicated_patterns", "--allow-duplicated-patterns"),
            ("by_name", "--by-name"),
            ("by_seq", "--by-seq"),
            ("circular", "--circular"),
            ("count", "--count"),
            ("degenerate", "--degenerate"),
            ("delete_matched", "--delete-matched"),
            ("ignore_case", "--ignore-case"),
            ("invert_match", "--invert-match"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        if inputs.get("by_seq") and not inputs.get("degenerate"):
            cmd.extend(["--max-mismatch", str(inputs.get("max_mismatch", 0))])
        if inputs.get("only_positive_strand"):
            cmd.append("--only-positive-strand")
        if inputs.get("region"):
            cmd.extend(["--region", str(inputs.get("region"))])
        cmd.extend([str(inputs.get("input", "")), ">", f"{_out(inputs)}/{cls._output_name(inputs)}"])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ_LIST", {"description": "Input FASTA/FASTQ file"}),
                "pattern_mode": ("STRING", {"default": "expression", "options": ["expression", "file"], "description": "Pattern source"}),
            },
            "optional": {
                "pattern": ("STRING", {"default": "", "description": "Pattern or motif sequence"}),
                "pattern_file": ("FILE", {"description": "Text file with one pattern per line"}),
                "use_regexp": ("BOOLEAN", {"default": False, "description": "Interpret expression pattern as a regular expression"}),
                "allow_duplicated_patterns": ("BOOLEAN", {"default": False, "advanced": True}),
                "by_name": ("BOOLEAN", {"default": False, "description": "Match against full sequence name/header"}),
                "by_seq": ("BOOLEAN", {"default": False, "description": "Search sequence content"}),
                "circular": ("BOOLEAN", {"default": False, "description": "Treat sequences as circular", "advanced": True}),
                "count": ("BOOLEAN", {"default": False, "description": "Print only the count of matching records"}),
                "degenerate": ("BOOLEAN", {"default": False, "description": "Pattern contains degenerate bases"}),
                "delete_matched": ("BOOLEAN", {"default": False, "advanced": True}),
                "ignore_case": ("BOOLEAN", {"default": False, "description": "Ignore case"}),
                "invert_match": ("BOOLEAN", {"default": False, "description": "Select non-matching records"}),
                "max_mismatch": ("INT", {"default": 0, "min": 0, "description": "Allowed mismatches for sequence search"}),
                "only_positive_strand": ("BOOLEAN", {"default": False, "description": "Search only the positive strand"}),
                "region": ("STRING", {"default": "", "description": "Sequence region such as 1:30, :100, or -12:-1"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "output_ext": ("STRING", {"default": "fasta.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"], "description": "Sequence output extension"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitHeadContract(ToolsIUCCommandContract):
    """Return the first N FASTA/Q records with SeqKit head."""

    LEGACY_NODE_ID = "seqkit_head"
    DISPLAY_NAME = "SeqKit Head"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Return the first N FASTA or FASTQ records with SeqKit head."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "seqkit", "head", "seqkit head", "first records", "FASTA head", "FASTQ head"]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("head_output",)
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#head"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", inputs.get("output_ext", "fastq.gz"))).strip().lstrip(".") or "fastq.gz"
        return f"input.{ext}"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("output_ext", "fastq.gz")).strip().lstrip(".") or "fastq.gz"
        return f"head.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        output_path = f"{_out(inputs)}/{cls._output_name(inputs)}"
        return " ".join(
            [
                "ln",
                "-sf",
                shlex.quote(str(inputs.get("input", ""))),
                shlex.quote(input_name),
                "&&",
                "seqkit",
                "head",
                shlex.quote(input_name),
                "--number",
                shlex.quote(str(inputs.get("number", 10))),
                "-o",
                shlex.quote(output_path),
                "--threads",
                shlex.quote(str(inputs.get("threads", 4))),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ_LIST", {"description": "Input FASTA or FASTQ file"}),
                "number": ("INT", {"default": 10, "min": 1, "description": "Number of FASTA/Q records to output"}),
            },
            "optional": {
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "input_ext": ("STRING", {"default": "fastq.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"], "advanced": True}),
                "output_ext": ("STRING", {"default": "fastq.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitFx2tabContract(ToolsIUCCommandContract):
    """Convert FASTA/Q records to tabular columns with SeqKit fx2tab."""

    LEGACY_NODE_ID = "seqkit_fx2tab"
    DISPLAY_NAME = "SeqKit fx2tab"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Convert FASTA or FASTQ records to tabular columns with SeqKit fx2tab."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "seqkit", "fx2tab", "FASTA to tabular", "FASTQ to TSV", "sequence table", "GC content"]
    RETURN_TYPES = ("TSV",)
    RETURN_NAMES = ("tabular",)
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#fx2tab"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fastqsanger.gz")).strip().lstrip(".") or "fastqsanger.gz"
        return f"input.{ext}"

    @classmethod
    def _output_name(cls) -> str:
        return "fx2tab.tsv"

    @classmethod
    def _joined_bases(cls, value: Any) -> str:
        return "".join(_as_list(value)).replace(",", "")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        cmd = ["seqkit", "fx2tab", input_name]
        if inputs.get("alphabet"):
            cmd.append("--alphabet")
        if inputs.get("avg_qual"):
            cmd.append("--avg-qual")
        base_percentages = cls._joined_bases(inputs.get("base_percentages", inputs.get("B")))
        if base_percentages:
            cmd.extend(["-B", base_percentages])
        base_counts = cls._joined_bases(inputs.get("base_counts", inputs.get("C")))
        if base_counts:
            cmd.extend(["-C", base_counts])
        for key, flag in (
            ("gc", "--gc"),
            ("gc_skew", "--gc-skew"),
            ("header_line", "--header-line"),
            ("length", "--length"),
            ("name", "--name"),
            ("no_qual", "--no-qual"),
            ("only_id", "--only-id"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        if str(inputs.get("qual_ascii_base", "")) != "":
            cmd.extend(["--qual-ascii-base", str(inputs.get("qual_ascii_base"))])
        if inputs.get("seq_hash"):
            cmd.append("--seq-hash")
        cmd.extend([">", f"{_out(inputs)}/{cls._output_name()}"])
        return f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_name)} && " + " ".join(
            shlex.quote(part) if part not in {">"} else part for part in cmd
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name()]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FASTQ_LIST", {"description": "Input FASTA or FASTQ file"})},
            "optional": {
                "input_ext": ("STRING", {"default": "fastqsanger.gz", "options": ["fasta", "fasta.gz", "fastqsanger", "fastqsanger.gz"], "advanced": True}),
                "alphabet": ("BOOLEAN", {"default": False, "description": "Output alphabet letters"}),
                "avg_qual": ("BOOLEAN", {"default": False, "description": "Output average quality"}),
                "base_percentages": ("STRING", {"default": "", "description": "Bases for percentage columns, e.g. A,T", "advanced": True}),
                "base_counts": ("STRING", {"default": "", "description": "Bases for count columns, e.g. A,N", "advanced": True}),
                "gc": ("BOOLEAN", {"default": False, "description": "Output GC content"}),
                "gc_skew": ("BOOLEAN", {"default": False, "description": "Output GC skew"}),
                "header_line": ("BOOLEAN", {"default": False, "description": "Output a header line"}),
                "length": ("BOOLEAN", {"default": False, "description": "Output sequence length"}),
                "name": ("BOOLEAN", {"default": False, "description": "Output names instead of sequences and qualities"}),
                "no_qual": ("BOOLEAN", {"default": False, "description": "Suppress quality column"}),
                "only_id": ("BOOLEAN", {"default": False, "description": "Output sequence ID instead of full header"}),
                "qual_ascii_base": ("INT", {"default": 33, "min": 0, "advanced": True}),
                "seq_hash": ("BOOLEAN", {"default": False, "description": "Output md5 hash of sequence"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitSortContract(ToolsIUCCommandContract):
    """Sort FASTA/Q records with SeqKit sort."""

    LEGACY_NODE_ID = "seqkit_sort"
    DISPLAY_NAME = "SeqKit Sort"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Sort FASTA or FASTQ records by sequence ID, name, sequence, non-gap bases, or length with SeqKit."
    SEARCH_ALIASES = [BIONODULO_BUILTIN_ALIAS, "seqkit", "sort", "SeqKit sort", "sort FASTA", "sort FASTQ", "sort by length", "sort by sequence"]
    RETURN_TYPES = ("FASTQ",)
    RETURN_NAMES = ("sorted_sequences",)
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#sort"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", inputs.get("output_ext", "fastq.gz"))).strip().lstrip(".") or "fastq.gz"
        return f"input.{ext}"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("output_ext", "fastq.gz")).strip().lstrip(".") or "fastq.gz"
        return f"sorted.{ext}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        output_path = f"{_out(inputs)}/{cls._output_name(inputs)}"
        cmd = ["seqkit", "sort", input_name]
        if inputs.get("reverse"):
            cmd.append("--reverse")
        sort_by = str(inputs.get("sort_by", ""))
        if sort_by:
            cmd.append(sort_by)
        cmd.extend(["-o", output_path, "--threads", str(inputs.get("threads", 4))])
        return f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_name)} && " + " ".join(
            shlex.quote(part) for part in cmd
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FASTQ_LIST", {"description": "Input FASTA or FASTQ file"})},
            "optional": {
                "sort_by": (
                    "STRING",
                    {
                        "default": "",
                        "options": ["", "--by-bases", "--by-length", "--by-name", "--by-seq"],
                        "description": "Sort by sequence ID, non-gap bases, length, full name, or sequence",
                    },
                ),
                "reverse": ("BOOLEAN", {"default": False, "description": "Reverse the sorted result"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "input_ext": ("STRING", {"default": "fastq.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"], "advanced": True}),
                "output_ext": ("STRING", {"default": "fastq.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitLocateContract(ToolsIUCCommandContract):
    """Locate FASTA subsequences or motifs with SeqKit locate."""

    LEGACY_NODE_ID = "seqkit_locate"
    DISPLAY_NAME = "SeqKit Locate"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Locate FASTA subsequences or motifs with optional mismatches and BED, GTF, or tabular output using SeqKit."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqkit",
        "locate",
        "SeqKit locate",
        "motif search",
        "subsequence search",
        "mismatch",
        "BED motifs",
        "GTF motifs",
    ]
    RETURN_TYPES = ("TSV", "BED", "GFF_GTF")
    RETURN_NAMES = ("tabular", "bed", "gtf")
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#locate"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("input_ext", "fasta.gz")).strip().lstrip(".") or "fasta.gz"
        return f"input.{ext}"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        output_mode = str(inputs.get("output_mode", ""))
        return {"--bed": "locate.bed", "--gtf": "locate.gtf"}.get(output_mode, "locate.tsv")

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_name = cls._input_name(inputs)
        cmd = ["seqkit", "locate", "--threads", str(inputs.get("threads", 4))]
        if str(inputs.get("pattern_mode", "expression")) == "file":
            cmd.extend(["--pattern-file", str(inputs.get("pattern_file", ""))])
        else:
            cmd.extend(["--pattern", str(inputs.get("pattern", ""))])
            if inputs.get("use_regexp"):
                cmd.append("--use-regexp")
        output_mode = str(inputs.get("output_mode", ""))
        if output_mode:
            cmd.append(output_mode)
        for key, flag in (
            ("circular", "--circular"),
            ("degenerate", "--degenerate"),
            ("hide_matched", "--hide-matched"),
            ("ignore_case", "--ignore-case"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        if not inputs.get("degenerate"):
            cmd.extend(["--max-mismatch", str(inputs.get("max_mismatch", 0))])
            if inputs.get("use_fmi"):
                cmd.append("--use-fmi")
        for key, flag in (
            ("non_greedy", "--non-greedy"),
            ("only_positive_strand", "--only-positive-strand"),
            ("id_ncbi", "--id-ncbi"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(["--seq-type", str(inputs.get("seq_type", "auto")), input_name, ">", f"{_out(inputs)}/{cls._output_name(inputs)}"])
        return f"ln -sf {shlex.quote(str(inputs.get('input', '')))} {shlex.quote(input_name)} && " + " ".join(
            shlex.quote(part) if part != ">" else part for part in cmd
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTQ_LIST", {"description": "Input FASTA file"}),
                "pattern_mode": ("STRING", {"default": "expression", "options": ["expression", "file"], "description": "Pattern source"}),
            },
            "optional": {
                "pattern": ("STRING", {"default": "", "description": "Pattern or motif sequence"}),
                "pattern_file": ("FILE", {"description": "FASTA file with motif sequences"}),
                "use_regexp": ("BOOLEAN", {"default": False, "description": "Interpret expression pattern as a regular expression"}),
                "seq_type": ("STRING", {"default": "auto", "options": ["auto", "dna", "rna", "protein"], "description": "Sequence type"}),
                "output_mode": ("STRING", {"default": "", "options": ["", "--gtf", "--bed"], "description": "Output format"}),
                "circular": ("BOOLEAN", {"default": False, "description": "Treat sequences as circular", "advanced": True}),
                "degenerate": ("BOOLEAN", {"default": False, "description": "Pattern contains degenerate bases"}),
                "hide_matched": ("BOOLEAN", {"default": False, "description": "Hide matched sequence column"}),
                "ignore_case": ("BOOLEAN", {"default": False, "description": "Ignore case"}),
                "max_mismatch": ("INT", {"default": 0, "min": 0, "description": "Allowed mismatches"}),
                "use_fmi": ("BOOLEAN", {"default": False, "description": "Use FM-index when degenerate matching is disabled", "advanced": True}),
                "non_greedy": ("BOOLEAN", {"default": False, "description": "Use non-greedy matching", "advanced": True}),
                "only_positive_strand": ("BOOLEAN", {"default": False, "description": "Search only the positive strand"}),
                "id_ncbi": ("BOOLEAN", {"default": False, "description": "Parse NCBI-style FASTA identifiers", "advanced": True}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "input_ext": ("STRING", {"default": "fasta.gz", "options": ["fasta.gz", "fasta"], "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitTranslateContract(ToolsIUCCommandContract):
    """Translate nucleotide FASTA/Q records to protein sequences with SeqKit."""

    LEGACY_NODE_ID = "seqkit_translate"
    DISPLAY_NAME = "SeqKit Translate"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Translate DNA or RNA FASTA/FASTQ records to protein sequences with frame, codon table, and unknown-codon handling."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqkit",
        "translate",
        "SeqKit translate",
        "DNA to protein",
        "RNA to protein",
        "codon table",
        "six frame translation",
    ]
    RETURN_TYPES = ("FASTA", "FASTQ")
    RETURN_NAMES = ("translated_fasta", "translated_fastq")
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#translate"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        ext = str(inputs.get("output_ext", "fasta.gz")).strip().lstrip(".") or "fasta.gz"
        return f"translated.{ext}"

    @classmethod
    def _frames(cls, value: Any) -> str:
        frames = _as_list(value)
        if not frames:
            return "1"
        return ",".join(frame.replace(",", "") for frame in frames if frame.replace(",", ""))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "seqkit",
            "translate",
            str(inputs.get("input", "")),
            "-o",
            f"{_out(inputs)}/{cls._output_name(inputs)}",
        ]
        unknown_action = str(inputs.get("unknown_action", inputs.get("selector", "trimming")))
        if unknown_action == "translate":
            if inputs.get("allow_unknown_codon"):
                cmd.append("--allow-unknown-codon")
        elif inputs.get("trim"):
            cmd.append("--trim")
        for key, flag in (
            ("append_frame", "--append-frame"),
            ("clean", "--clean"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(["-f", cls._frames(inputs.get("frame", "1"))])
        if inputs.get("init_codon_as_M"):
            cmd.append("--init-codon-as-M")
        transl_table = str(inputs.get("transl_table", "1"))
        if transl_table:
            cmd.extend(["-T", transl_table])
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / cls._output_name(inputs)]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {"input": ("FASTQ_LIST", {"description": "Input FASTA or FASTQ nucleotide records"})},
            "optional": {
                "frame": (
                    "STRING",
                    {
                        "default": "1",
                        "options": ["1", "2", "3", "-1", "-2", "-3", "6"],
                        "description": "Frame or comma-separated frames to translate",
                    },
                ),
                "append_frame": ("BOOLEAN", {"default": False, "description": "Append frame information to sequence IDs"}),
                "transl_table": (
                    "STRING",
                    {
                        "default": "1",
                        "options": [
                            "1",
                            "2",
                            "3",
                            "4",
                            "5",
                            "6",
                            "9",
                            "10",
                            "11",
                            "12",
                            "13",
                            "14",
                            "16",
                            "21",
                            "22",
                            "23",
                            "24",
                            "25",
                            "26",
                            "27",
                            "28",
                            "29",
                            "30",
                            "31",
                        ],
                        "description": "NCBI genetic code table",
                    },
                ),
                "clean": ("BOOLEAN", {"default": False, "description": "Change STOP codons from * to X"}),
                "unknown_action": (
                    "STRING",
                    {
                        "default": "trimming",
                        "options": ["trimming", "translate"],
                        "description": "Trim terminal unknowns/stops or translate unknown codons to X",
                    },
                ),
                "trim": ("BOOLEAN", {"default": False, "description": "Remove X and * characters from the right end"}),
                "allow_unknown_codon": ("BOOLEAN", {"default": False, "description": "Translate unknown codons to X"}),
                "init_codon_as_M": ("BOOLEAN", {"default": False, "description": "Translate initial codon as M"}),
                "output_ext": ("STRING", {"default": "fasta.gz", "options": ["fasta.gz", "fasta", "fastq.gz", "fastq"]}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _SeqKitSplit2Contract(ToolsIUCCommandContract):
    """Split FASTA/Q records into files with SeqKit split2."""

    LEGACY_NODE_ID = "seqkit_split2"
    DISPLAY_NAME = "SeqKit Split2"
    REQUIRED_CONDA_PACKAGES = ["seqkit"]
    CATEGORY = "sequence"
    DESCRIPTION = "Split single-end or paired-end FASTA/FASTQ records into multiple files by part count, sequence count, or sequence length."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "seqkit",
        "split2",
        "SeqKit split2",
        "split FASTQ",
        "split FASTA",
        "paired split",
        "split by length",
        "split by parts",
    ]
    RETURN_TYPES = ("DIRECTORY", "DIRECTORY")
    RETURN_NAMES = ("split_files", "paired_split_files")
    REQUIRED_EXECUTABLES = ["seqkit"]
    DOCUMENTATION_URL = "https://bioinf.shenwei.me/seqkit/usage/#split2"
    CITATION_DOIS = ["10.1371/journal.pone.0163962"]
    CITATION_URLS = ["https://doi.org/10.1371/journal.pone.0163962"]
    CITATION_TEXT = "SeqKit: a cross-platform and ultrafast toolkit for FASTA/Q file manipulation."
    VERSION = "2.13.0"
    SHELL = True

    @classmethod
    def _input_name(cls, inputs: dict[str, Any], index: int | None = None) -> str:
        key = "input_1_ext" if index in {None, 1} else "input_2_ext"
        default = "fastqsanger.gz" if index == 2 else "fasta.gz"
        ext = str(inputs.get(key, default)).strip().lstrip(".") or default
        prefix = "input" if index is None else f"input_{index}"
        return f"{prefix}.{ext}"

    @classmethod
    def _is_paired(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get("input_type", inputs.get("type", "single"))) == "paired_collection"

    @classmethod
    def _output_name(cls, inputs: dict[str, Any]) -> str:
        return "paired_split_files" if cls._is_paired(inputs) else "split_files"

    @classmethod
    def _add_split_selector(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        split_selector = str(inputs.get("split_selector", "by_part"))
        if split_selector == "by_size":
            cmd.extend(["-s", str(inputs.get("by_size", ""))])
            if cls._is_paired(inputs):
                cmd.extend(["--by-size-prefix", "string", "seqkit_split2_R{read}_"])
        elif split_selector == "by_length":
            cmd.extend(["-l", str(inputs.get("by_length", ""))])
        else:
            cmd.extend(["-p", str(inputs.get("by_part", ""))])
            if cls._is_paired(inputs):
                cmd.extend(["--by-part-prefix", "seqkit_split2_R{read}_"])

    @classmethod
    def _paired_rename_command(cls, out_dir: str) -> str:
        quoted_out = shlex.quote(out_dir)
        return (
            f"(find {quoted_out}/ -type f -name 'seqkit_split2_*.*' | "
            "while read -r file; do mv \"$file\" \"$(echo \"$file\" | "
            "sed -E 's/(seqkit_split2)_(R1|R2)_([0-9]+)(\\..+)/\\1_\\3_\\2\\4/' | "
            "sed -E 's/_R1/_forward/; s/_R2/_reverse/')\"; done)"
        )

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out_dir = f"{_out(inputs)}/{cls._output_name(inputs)}"
        parts = ["mkdir", "-p", out_dir]
        if cls._is_paired(inputs):
            input_1_name = cls._input_name(inputs, 1)
            input_2_name = cls._input_name(inputs, 2)
            cmd = ["seqkit", "split2", "-1", input_1_name, "-2", input_2_name]
            cls._add_split_selector(cmd, inputs)
            cmd.extend(["-o", "seqkit_split2", "-O", out_dir, "-j", str(inputs.get("threads", 4))])
            commands = [
                " ".join(shlex.quote(part) for part in parts),
                f"ln -sf {shlex.quote(str(inputs.get('input_1', '')))} {shlex.quote(input_1_name)}",
                f"ln -sf {shlex.quote(str(inputs.get('input_2', '')))} {shlex.quote(input_2_name)}",
                " ".join(shlex.quote(part) for part in cmd),
                cls._paired_rename_command(out_dir),
            ]
        else:
            input_name = cls._input_name(inputs)
            cmd = ["seqkit", "split2", input_name]
            cls._add_split_selector(cmd, inputs)
            cmd.extend(["-o", "seqkit_split2", "-O", out_dir, "-j", str(inputs.get("threads", 4))])
            commands = [
                " ".join(shlex.quote(part) for part in parts),
                f"ln -sf {shlex.quote(str(inputs.get('input_1', inputs.get('input', ''))))} {shlex.quote(input_name)}",
                " ".join(shlex.quote(part) for part in cmd),
            ]
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID / cls._output_name(inputs)
        out.mkdir(parents=True, exist_ok=True)
        return [out]

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input_type": (
                    "STRING",
                    {
                        "default": "single",
                        "options": ["single", "paired_collection"],
                        "description": "Single-end or paired-end reads",
                    },
                ),
            },
            "optional": {
                "input_1": ("FASTQ_LIST", {"description": "Single-end input or paired-end forward reads"}),
                "input_2": ("FASTQ_LIST", {"description": "Paired-end reverse reads"}),
                "split_selector": (
                    "STRING",
                    {
                        "default": "by_part",
                        "options": ["by_part", "by_size", "by_length"],
                        "description": "Split by number of parts, sequences per part, or sequence length",
                    },
                ),
                "by_part": ("INT", {"default": 2, "min": 1, "description": "Number of output parts"}),
                "by_size": ("INT", {"default": 1000, "min": 1, "description": "Sequences per output part"}),
                "by_length": ("STRING", {"default": "50K", "description": "Chunk size with optional K/M/G suffix"}),
                "threads": ("INT", {"default": 4, "min": 1, "max": 128}),
                "input_1_ext": ("STRING", {"default": "fasta.gz", "options": ["fasta", "fasta.gz", "fastqsanger", "fastqsanger.gz"], "advanced": True}),
                "input_2_ext": ("STRING", {"default": "fastqsanger.gz", "options": ["fasta", "fasta.gz", "fastqsanger", "fastqsanger.gz"], "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class _AMRFinderPlusContract(ToolsIUCCommandContract):
    """Find AMR genes, point mutations, and plus genes with NCBI AMRFinderPlus."""

    LEGACY_NODE_ID = "amrfinderplus"
    DISPLAY_NAME = "AMRFinderPlus"
    REQUIRED_CONDA_PACKAGES = ["ncbi-amrfinderplus"]
    CATEGORY = "annotation"
    DESCRIPTION = "Find acquired antimicrobial resistance genes, point mutations, stress response, biocide, and virulence genes in nucleotide and/or protein sequences."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "amrfinder",
        "amrfinderplus",
        "NCBI AMRFinderPlus",
        "antimicrobial resistance",
        "AMR genes",
        "point mutations",
        "virulence genes",
    ]
    RETURN_TYPES = ("TSV", "TSV", "FASTA", "FASTA", "FASTA")
    RETURN_NAMES = (
        "amrfinderplus_report",
        "mutation_all_report",
        "protein_output",
        "nucleotide_output",
        "nucleotide_flank5_output",
    )
    REQUIRED_EXECUTABLES = ["amrfinder"]
    DOCUMENTATION_URL = "https://github.com/ncbi/amr/wiki"
    CITATION_DOIS = ["10.1038/s41598-021-91456-0"]
    CITATION_URLS = ["https://doi.org/10.1038/s41598-021-91456-0"]
    CITATION_TEXT = "AMRFinderPlus and the Reference Gene Catalog facilitate examination of the genomic links among antimicrobial resistance, stress response, and virulence."
    VERSION = "4.2.7"
    SHELL = True

    @classmethod
    def _report_path(cls, inputs: dict[str, Any], filename: str) -> str:
        return f"{_out(inputs)}/{filename}"

    @classmethod
    def _has_organism(cls, inputs: dict[str, Any]) -> bool:
        return str(inputs.get("organism_select", "")) == "add_organism" or bool(inputs.get("organism"))

    @classmethod
    def _flank5_size(cls, inputs: dict[str, Any]) -> int:
        try:
            return int(inputs.get("nucleotide_flank5_size", 0) or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _add_nucleotide_inputs(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cmd.extend(["--nucleotide", str(inputs.get("nucleotide_input", ""))])
        if cls._flank5_size(inputs) > 0:
            cmd.extend([
                "--nucleotide_flank5_size",
                str(cls._flank5_size(inputs)),
                "--nucleotide_flank5_output",
                cls._report_path(inputs, "amrfinderplus_flanking_sequence_output.fasta"),
            ])
        cmd.extend(["--nucleotide_output", cls._report_path(inputs, "amrfinderplus_nucleotide_output.fasta")])

    @classmethod
    def _add_protein_inputs(cls, cmd: list[str], inputs: dict[str, Any], *, require_annotation: bool = False) -> None:
        cmd.extend(["--protein", str(inputs.get("protein_input", ""))])
        gff = inputs.get("gff_annotation")
        if require_annotation or gff:
            cmd.extend(["--gff", str(gff or "")])
        annotation_format = inputs.get("annotation_format")
        if require_annotation or annotation_format:
            cmd.extend(["--annotation_format", str(annotation_format or "genbank")])
        cmd.extend(["--protein_output", cls._report_path(inputs, "amrfinderplus_protein_output.fasta")])

    @classmethod
    def _add_version_columns_command(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        database = str(inputs.get("database", ""))
        database_name = str(inputs.get("database_name", Path(database).name or "amrfinderplus_database"))
        report_path = cls._report_path(inputs, "amrfinderplus_report.tsv")
        mutation_path = cls._report_path(inputs, "mutation_all_report.tsv")
        script = (
            "from pathlib import Path\n"
            f"tool_version = '{cls.VERSION}'\n"
            f"database = Path('{database}')\n"
            f"database_version = (database / 'version.txt').read_text().strip() if (database / 'version.txt').is_file() else '{database_name}'\n"
            f"for report in [Path('{report_path}'), Path('{mutation_path}')]:\n"
            "    if not report.is_file() or report.stat().st_size == 0:\n"
            "        continue\n"
            "    lines = report.read_text().splitlines()\n"
            "    if not lines:\n"
            "        continue\n"
            "    updated = [lines[0] + '\\tDatabase version\\tTool version']\n"
            "    updated.extend(line + '\\t' + database_version + '\\t' + tool_version for line in lines[1:])\n"
            "    report.write_text('\\n'.join(updated) + '\\n')\n"
        )
        cmd.extend([
            "&&",
            "python",
            "-c",
            script,
        ])

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> list[str]:
        cmd = [
            "amrfinder",
            "--threads",
            str(inputs.get("threads", 1)),
            "--database",
            str(inputs.get("database", "")),
        ]
        input_select = str(inputs.get("input_select", "nucleotide"))
        if input_select == "protein":
            cls._add_protein_inputs(cmd, inputs)
        elif input_select == "nucl_prot":
            cmd.extend(["--nucleotide", str(inputs.get("nucleotide_input", ""))])
            if cls._flank5_size(inputs) > 0:
                cmd.extend([
                    "--nucleotide_flank5_size",
                    str(cls._flank5_size(inputs)),
                    "--nucleotide_flank5_output",
                    cls._report_path(inputs, "amrfinderplus_flanking_sequence_output.fasta"),
                ])
            cmd.extend([
                "--protein",
                str(inputs.get("protein_input", "")),
                "--gff",
                str(inputs.get("gff_annotation", "")),
                "--annotation_format",
                str(inputs.get("annotation_format", "genbank")),
                "--nucleotide_output",
                cls._report_path(inputs, "amrfinderplus_nucleotide_output.fasta"),
                "--protein_output",
                cls._report_path(inputs, "amrfinderplus_protein_output.fasta"),
            ])
        else:
            cls._add_nucleotide_inputs(cmd, inputs)

        if cls._has_organism(inputs):
            cmd.extend(["--organism", str(inputs.get("organism", ""))])
            if inputs.get("mutation_all"):
                cmd.extend(["--mutation_all", cls._report_path(inputs, "mutation_all_report.tsv")])
            if inputs.get("plus") and inputs.get("report_common"):
                cmd.append("--report_common")

        cmd.extend(["--ident_min", str(inputs.get("ident_min", -1))])
        cmd.extend(["--coverage_min", str(inputs.get("coverage_min", 0.5))])
        _add_if_value(cmd, "--translation_table", inputs.get("translation_table"))
        _add_if_value(cmd, "--name", inputs.get("name"))
        for key, flag in (
            ("plus", "--plus"),
            ("report_all_equal", "--report_all_equal"),
            ("print_node", "--print_node"),
        ):
            if inputs.get(key):
                cmd.append(flag)
        cmd.extend(["--output", cls._report_path(inputs, "amrfinderplus_report.tsv")])
        if inputs.get("add_version_columns"):
            cls._add_version_columns_command(cmd, inputs)
        return cmd

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        input_select = str(inputs.get("input_select", "nucleotide"))
        outputs = [_amrfinderplus_out(output_dir, "amrfinderplus_report.tsv")]
        if cls._has_organism(inputs) and inputs.get("mutation_all"):
            outputs.append(_amrfinderplus_out(output_dir, "mutation_all_report.tsv"))
        if input_select in {"protein", "nucl_prot"}:
            outputs.append(_amrfinderplus_out(output_dir, "amrfinderplus_protein_output.fasta"))
        if input_select in {"nucleotide", "nucl_prot"}:
            outputs.append(_amrfinderplus_out(output_dir, "amrfinderplus_nucleotide_output.fasta"))
        if input_select in {"nucleotide", "nucl_prot"} and cls._flank5_size(inputs) > 0:
            outputs.append(_amrfinderplus_out(output_dir, "amrfinderplus_flanking_sequence_output.fasta"))
        return outputs

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "database": ("DIRECTORY", {"description": "AMRFinderPlus database directory, matching Galaxy's amrfinderplus versioned database"}),
                "input_select": ("STRING", {"default": "nucleotide", "options": ["nucleotide", "protein", "nucl_prot"], "description": "Analyze nucleotide, protein, or paired nucleotide and protein files"}),
            },
            "optional": {
                "nucleotide_input": ("FASTA", {"default": "", "description": "Input nucleotide sequence file"}),
                "protein_input": ("FASTA", {"default": "", "description": "Input protein sequence file"}),
                "gff_annotation": ("GFF", {"default": "", "description": "GFF3 annotation file for protein locations"}),
                "annotation_format": ("STRING", {"default": "genbank", "options": AMRFINDERPLUS_ANNOTATION_FORMATS, "description": "Annotation format such as bakta, prokka, rast, or genbank"}),
                "nucleotide_flank5_size": ("INT", {"default": 0, "min": 0, "description": "5' flanking sequence size added to nucleotide matches"}),
                "organism_select": ("STRING", {"default": "", "options": ["", "add_organism"], "description": "Enable organism-specific point mutation screening"}),
                "organism": ("STRING", {"default": "", "options": AMRFINDERPLUS_ORGANISMS, "description": "Taxonomic group for point mutation screening"}),
                "mutation_all": ("BOOLEAN", {"default": False, "description": "Report genotypes at all screened point mutation locations"}),
                "report_common": ("BOOLEAN", {"default": False, "description": "Report proteins common to the taxonomy group when plus and organism options are enabled"}),
                "ident_min": ("FLOAT", {"default": -1, "min": -1, "max": 1, "description": "Minimum amino acid identity; -1 uses curated thresholds"}),
                "coverage_min": ("FLOAT", {"default": 0.5, "min": 0, "max": 1, "description": "Minimum coverage of the reference protein"}),
                "translation_table": ("STRING", {"default": "11", "options": AMRFINDERPLUS_TRANSLATION_TABLES, "description": "NCBI genetic code for translated BLAST"}),
                "plus": ("BOOLEAN", {"default": False, "description": "Include stress response, biocide, virulence, and other plus genes"}),
                "report_all_equal": ("BOOLEAN", {"default": False, "description": "Report all equally scoring BLAST and HMM matches"}),
                "print_node": ("BOOLEAN", {"default": False, "description": "Print hierarchy node or family"}),
                "name": ("STRING", {"default": "", "description": "Value to add as the report's first-column sample name"}),
                "add_version_columns": ("BOOLEAN", {"default": False, "description": "Append database and tool version columns to tabular reports"}),
                "database_name": ("STRING", {"default": "", "description": "Fallback database label when database/version.txt is unavailable", "advanced": True}),
                "threads": ("INT", {"default": 1, "min": 1, "max": 128, "display": "slider"}),
            },
            "hidden": {"output": ("STRING", {})},
        }


def __getattr__(name: str) -> Any:
    """Preserve the legacy featureCounts import after moving live ownership."""

    if name == "FeatureCountsNode":
        from bionodulo.nodes.builtin.rna_seq_family.featurecounts import FeatureCountsNode

        return FeatureCountsNode
    raise AttributeError(name)


# Preserve historical imports while live ownership resides in focused modules.
from bionodulo.nodes.builtin.seqtk_family.comp import SeqTKCompNode
from bionodulo.nodes.builtin.seqtk_family.cutn import SeqTKCutNNode
from bionodulo.nodes.builtin.seqtk_family.dropse import SeqTKDropSENode
from bionodulo.nodes.builtin.seqtk_family.fqchk import SeqTKFqchkNode
from bionodulo.nodes.builtin.seqtk_family.hety import SeqTKHetyNode
from bionodulo.nodes.builtin.seqtk_family.listhet import SeqTKListHetNode
from bionodulo.nodes.builtin.seqtk_family.mergefa import SeqTKMergeFANode
from bionodulo.nodes.builtin.seqtk_family.mergepe import SeqTKMergePENode
from bionodulo.nodes.builtin.seqtk_family.mutfa import SeqTKMutFANode
from bionodulo.nodes.builtin.seqtk_family.randbase import SeqTKRandBaseNode
from bionodulo.nodes.builtin.seqtk_family.sample import SeqTKSampleNode
from bionodulo.nodes.builtin.seqtk_family.seq import SeqTKSeqNode
from bionodulo.nodes.builtin.seqtk_family.subseq import SeqTKSubseqNode
from bionodulo.nodes.builtin.seqtk_family.telo import SeqTKTeloNode
from bionodulo.nodes.builtin.seqtk_family.trimfq import SeqTKTrimFQNode
