"""Classic alignment and phylogeny wrapper contracts."""
# ruff: noqa: F403,F405
from __future__ import annotations

from bionodulo.nodes.builtin._wrapped_tool_utils import *

from bionodulo.nodes.builtin.wrapped_phylogeny_assembly_family.evidence import pin_contract

class ClustalWNode(CommandNode):
    """Align DNA or protein FASTA sequences with ClustalW."""

    LEGACY_NODE_ID = "clustalw"
    DISPLAY_NAME = "ClustalW"
    REQUIRED_CONDA_PACKAGES = ["clustalw"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Align DNA or protein FASTA sequences with ClustalW and emit the alignment plus guide tree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "ClustalW",
        "clustalw2",
        "clustal",
        "multiple sequence alignment",
        "DNA alignment",
        "protein alignment",
        "guide tree",
    ]
    RETURN_TYPES = ("ALIGNMENT", "PHYLOGENY_TREE")
    RETURN_NAMES = ("alignment", "guide_tree")
    REQUIRED_EXECUTABLES = ["clustalw2"]
    DOCUMENTATION_URL = "http://www.clustal.org/clustal2/"
    CITATION_DOIS = [CLUSTALW_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{CLUSTALW_CITATION_DOI}"]
    CITATION_TEXT = CLUSTALW_CITATION_TEXT
    VERSION = "2.1+galaxy1"
    SHELL = True

    OUTPUT_EXTENSIONS = {
        "clustal": "aln",
        "phylip": "phy",
        "fasta": "fasta",
    }

    @classmethod
    def _alignment_output(cls, inputs: dict[str, Any]) -> str:
        outform = str(inputs.get("outform", "clustal") or "clustal").lower()
        ext = cls.OUTPUT_EXTENSIONS.get(outform, "aln")
        return f"{_out(inputs)}/alignment.{ext}"

    @classmethod
    def _append_value_option(cls, cmd: list[str], flag: str, value: Any) -> None:
        if value is not None and str(value) != "":
            cmd.append(f"{flag}={value}")

    @classmethod
    def _append_multiple_alignment_options(cls, cmd: list[str], inputs: dict[str, Any]) -> None:
        cls._append_value_option(cmd, "-GAPOPEN", inputs.get("gapopen"))
        cls._append_value_option(cmd, "-GAPEXT", inputs.get("gapext"))
        if inputs.get("endgaps"):
            cmd.append("-ENDGAPS")
        cls._append_value_option(cmd, "-GAPDIST", inputs.get("gapdist"))
        if inputs.get("nopgap"):
            cmd.append("-NOPGAP")
        if inputs.get("nohgap"):
            cmd.append("-NOHGAP")
        cls._append_value_option(cmd, "-MAXDIV", inputs.get("maxdiv"))
        if inputs.get("negative"):
            cmd.append("-NEGATIVE")
        cls._append_value_option(cmd, "-TRANSWEIGHT", inputs.get("transweight"))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        sequence_type = str(inputs.get("sequence_type", "DNA") or "DNA").upper()
        outform = str(inputs.get("outform", "clustal") or "clustal").lower()
        clustal_output = {"clustal": "CLUSTAL", "phylip": "PHYLIP", "fasta": "FASTA"}.get(outform, "CLUSTAL")
        input_fasta = str(inputs.get("input", ""))
        cmd = [
            "clustalw2",
            "-INFILE=input.fasta",
            f"-OUTFILE={cls._alignment_output(inputs)}",
            f"-OUTORDER={inputs.get('out_order', 'ALIGNED')}",
            f"-TYPE={sequence_type}",
            f"-OUTPUT={clustal_output}",
        ]
        if outform == "clustal" and inputs.get("out_seqnos"):
            cmd.append("-SEQNOS=ON")
        if str(inputs.get("range_mode", "complete")) == "part":
            cmd.append(f"-RANGE={inputs.get('seq_range_start', 1)},{inputs.get('seq_range_end', 99999)}")

        algorithm = str(inputs.get("algorithm", "slow") or "slow").lower()
        if sequence_type == "PROTEIN":
            if algorithm == "fast":
                cmd.append("-QUICKTREE")
                for flag, key in (
                    ("-KTUPLE", "ktuple"),
                    ("-TOPDIAGS", "topdiags"),
                    ("-WINDOW", "window"),
                    ("-PAIRGAP", "pairgap"),
                    ("-SCORE", "score"),
                ):
                    cls._append_value_option(cmd, flag, inputs.get(key))
            else:
                cls._append_value_option(cmd, "-PWMATRIX", inputs.get("pwmatrix", "GONNET"))
                cls._append_value_option(cmd, "-PWGAPOPEN", inputs.get("pwgapopen"))
                cls._append_value_option(cmd, "-PWGAPEXT", inputs.get("pwgapext"))
            cls._append_value_option(cmd, "-MATRIX", inputs.get("matrix", "GONNET"))
        else:
            if algorithm == "fast":
                cmd.append("-QUICKTREE")
                for flag, key in (
                    ("-KTUPLE", "ktuple"),
                    ("-TOPDIAGS", "topdiags"),
                    ("-WINDOW", "window"),
                    ("-PAIRGAP", "pairgap"),
                    ("-SCORE", "score"),
                ):
                    cls._append_value_option(cmd, flag, inputs.get(key))
            else:
                cls._append_value_option(cmd, "-PWDNAMATRIX", inputs.get("pwdnamatrix", "IUB"))
                cls._append_value_option(cmd, "-PWGAPOPEN", inputs.get("pwgapopen"))
                cls._append_value_option(cmd, "-PWGAPEXT", inputs.get("pwgapext"))
            cls._append_value_option(cmd, "-DNAMATRIX", inputs.get("dn_matrix", "IUB"))
        cls._append_multiple_alignment_options(cmd, inputs)
        cls._append_value_option(cmd, "-OUTPUTTREE", inputs.get("outputtree", "PHYLIP"))
        if inputs.get("kimura"):
            cmd.append("-KIMURA")
        if inputs.get("tossgaps"):
            cmd.append("-TOSSGAPS")
        return (
            f"ln -sf {shlex.quote(input_fasta)} input.fasta && "
            f"{' '.join(shlex.quote(part) for part in cmd)} && "
            f"cp input.dnd {shlex.quote(f'{_out(inputs)}/guide_tree.dnd')}"
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        outform = str(inputs.get("outform", "clustal") or "clustal").lower()
        ext = cls.OUTPUT_EXTENSIONS.get(outform, "aln")
        return [out / f"alignment.{ext}", out / "guide_tree.dnd"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input"):
            return "input FASTA is required"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": ("FASTA", {"description": "FASTA sequences to align"}),
                "sequence_type": (
                    "STRING",
                    {"default": "DNA", "options": ["DNA", "PROTEIN"], "description": "DNA/RNA or protein sequences"},
                ),
                "outform": (
                    "STRING",
                    {"default": "clustal", "options": ["clustal", "phylip", "fasta"], "description": "Alignment output format"},
                ),
            },
            "optional": {
                "out_order": (
                    "STRING",
                    {"default": "ALIGNED", "options": ["ALIGNED", "INPUT"], "description": "Output aligned or input order"},
                ),
                "out_seqnos": ("BOOLEAN", {"default": False, "description": "Show residue numbers in Clustal output"}),
                "range_mode": (
                    "STRING",
                    {"default": "complete", "options": ["complete", "part"], "description": "Output complete alignment or a range"},
                ),
                "seq_range_start": ("INT", {"default": 1, "min": 1, "advanced": True}),
                "seq_range_end": ("INT", {"default": 99999, "min": 1, "advanced": True}),
                "algorithm": (
                    "STRING",
                    {"default": "slow", "options": ["slow", "fast"], "description": "Guide-tree algorithm"},
                ),
                "pwdnamatrix": ("STRING", {"default": "IUB", "options": ["IUB", "CLUSTALW"], "advanced": True}),
                "dn_matrix": ("STRING", {"default": "IUB", "options": ["IUB", "CLUSTALW"], "advanced": True}),
                "pwmatrix": ("STRING", {"default": "GONNET", "options": ["BLOSUM", "PAM", "GONNET", "ID"], "advanced": True}),
                "matrix": ("STRING", {"default": "GONNET", "options": ["BLOSUM", "PAM", "GONNET", "ID"], "advanced": True}),
                "pwgapopen": ("INT", {"default": "", "min": 0, "advanced": True}),
                "pwgapext": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "ktuple": ("INT", {"default": "", "min": 0, "advanced": True}),
                "topdiags": ("INT", {"default": "", "min": 0, "advanced": True}),
                "window": ("INT", {"default": "", "min": 0, "advanced": True}),
                "pairgap": ("INT", {"default": "", "min": 0, "advanced": True}),
                "score": ("STRING", {"default": "PERCENT", "options": ["PERCENT", "ABSOLUTE"], "advanced": True}),
                "gapopen": ("INT", {"default": "", "min": 0, "advanced": True}),
                "gapext": ("FLOAT", {"default": "", "min": 0, "advanced": True}),
                "endgaps": ("BOOLEAN", {"default": False, "advanced": True}),
                "gapdist": ("INT", {"default": "", "min": 0, "advanced": True}),
                "nopgap": ("BOOLEAN", {"default": False, "advanced": True}),
                "nohgap": ("BOOLEAN", {"default": False, "advanced": True}),
                "maxdiv": ("INT", {"default": "", "min": 0, "max": 100, "advanced": True}),
                "negative": ("BOOLEAN", {"default": False, "advanced": True}),
                "transweight": ("FLOAT", {"default": "", "min": 0, "max": 1, "advanced": True}),
                "outputtree": (
                    "STRING",
                    {"default": "PHYLIP", "options": ["PHYLIP", "DIST", "NJ", "NEXUS"], "advanced": True},
                ),
                "kimura": ("BOOLEAN", {"default": False, "advanced": True}),
                "tossgaps": ("BOOLEAN", {"default": False, "advanced": True}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class QuicktreeNode(CommandNode):
    """Build phylogenetic trees or distance matrices with Quicktree."""

    LEGACY_NODE_ID = "quicktree"
    DISPLAY_NAME = "Quicktree"
    REQUIRED_CONDA_PACKAGES = ["quicktree", "hmmer"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Construct phylogenetic trees or distance matrices from alignments with Quicktree."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "Quicktree",
        "quicktree",
        "neighbor joining",
        "distance matrix",
        "UPGMA",
        "Kimura",
        "bootstrap",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("output_file",)
    REQUIRED_EXECUTABLES = ["quicktree", "esl-reformat"]
    DOCUMENTATION_URL = "https://github.com/khowe/quicktree"
    CITATION_DOIS = [QUICKTREE_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{QUICKTREE_CITATION_DOI}"]
    CITATION_TEXT = QUICKTREE_CITATION_TEXT
    VERSION = "2.5+galaxy1"
    SHELL = True

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return ".dist" if str(inputs.get("output_type", "tree_out")) == "dist_out" else ".nwk"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/output_file{cls._output_suffix(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_format = str(inputs.get("format", "align"))
        input_file = str(inputs.get("input_file", ""))
        if input_format == "dist":
            stage = f"ln -s {shlex.quote(input_file)} input.quicktree"
            in_mode = "m"
        else:
            stage = f"esl-reformat -o input.quicktree stockholm {shlex.quote(input_file)}"
            in_mode = "a"
        out_mode = "m" if str(inputs.get("output_type", "tree_out")) == "dist_out" else "t"
        cmd = ["quicktree", "-in", in_mode, "-out", out_mode]
        if inputs.get("upgma"):
            cmd.append("-upgma")
        if inputs.get("kimura"):
            cmd.append("-kimura")
        if inputs.get("boot") not in (None, ""):
            cmd.extend(["-boot", str(inputs.get("boot"))])
        cmd.append("input.quicktree")
        return f"{stage} && {_shell_join(cmd)} > {shlex.quote(cls._output_path(inputs))}"

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"output_file{cls._output_suffix(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not inputs.get("input_file"):
            return "input alignment or distance matrix is required"
        if inputs.get("boot") not in (None, ""):
            try:
                boot = int(inputs.get("boot"))
            except (TypeError, ValueError):
                return "boot must be an integer"
            if boot < 0:
                return "boot must be >= 0"
        base_validation = super().VALIDATE_INPUTS(inputs)
        if base_validation is not True:
            return base_validation
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "format": (
                    "STRING",
                    {"default": "align", "options": ["align", "dist"], "description": "Input alignment or distance matrix"},
                ),
                "input_file": ("ALIGNMENT", {"description": "Alignment or PHYLIP-format distance matrix"}),
                "output_type": (
                    "STRING",
                    {"default": "tree_out", "options": ["tree_out", "dist_out"], "description": "Newick tree or distance matrix output"},
                ),
            },
            "optional": {
                "upgma": ("BOOLEAN", {"default": False, "description": "Use UPGMA instead of neighbor joining"}),
                "kimura": ("BOOLEAN", {"default": False, "description": "Apply Kimura translation to pairwise distances"}),
                "boot": ("INT", {"default": "", "min": 0, "description": "Bootstrap iterations"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class RapidNJNode(CommandNode):
    """Build neighbour-joining trees or distance matrices with RapidNJ."""

    LEGACY_NODE_ID = "rapidnj"
    DISPLAY_NAME = "RapidNJ"
    REQUIRED_CONDA_PACKAGES = ["rapidnj"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Construct neighbour-joining phylogenetic trees or distance matrices rapidly with RapidNJ."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "RapidNJ",
        "rapidnj",
        "neighbor joining",
        "neighbour joining",
        "distance matrix",
        "Kimura",
        "Jukes-Cantor",
        "bootstrap",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE",)
    RETURN_NAMES = ("distances",)
    REQUIRED_EXECUTABLES = ["rapidnj"]
    DOCUMENTATION_URL = "https://birc.au.dk/software/rapidnj"
    CITATION_DOIS = [RAPIDNJ_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{RAPIDNJ_CITATION_DOI}"]
    CITATION_TEXT = RAPIDNJ_CITATION_TEXT
    VERSION = "2.3.2"
    SHELL = True

    INPUT_FORMAT_OPTIONS = ["fasta", "stockholm", "phylip"]
    INPUT_FORMAT_FLAGS = {
        "fasta": ("fa", "fa"),
        "stockholm": ("sth", "sth"),
        "phylip": ("pd", "pd"),
    }
    OUTPUT_FORMAT_OPTIONS = ["t", "m"]
    EVOLUTION_MODEL_OPTIONS = ["kim", "jc"]
    ALIGNMENT_TYPE_OPTIONS = ["p", "d"]

    @classmethod
    def _input_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("input_format", "fasta") or "fasta")

    @classmethod
    def _output_format(cls, inputs: dict[str, Any]) -> str:
        return str(inputs.get("output_format", "t") or "t")

    @classmethod
    def _output_suffix(cls, inputs: dict[str, Any]) -> str:
        return ".tsv" if cls._output_format(inputs) == "m" else ".nhx"

    @classmethod
    def _staged_input(cls, inputs: dict[str, Any]) -> str:
        input_format = cls._input_format(inputs)
        _rapidnj_format, suffix = cls.INPUT_FORMAT_FLAGS.get(input_format, cls.INPUT_FORMAT_FLAGS["fasta"])
        return f"{_out(inputs)}/input.{suffix}"

    @classmethod
    def _output_path(cls, inputs: dict[str, Any]) -> str:
        return f"{_out(inputs)}/distances{cls._output_suffix(inputs)}"

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        out = _out(inputs)
        input_format = cls._input_format(inputs)
        rapidnj_format, _suffix = cls.INPUT_FORMAT_FLAGS.get(input_format, cls.INPUT_FORMAT_FLAGS["fasta"])
        staged_input = cls._staged_input(inputs)
        cmd = [
            "rapidnj",
            staged_input,
            "--input-format",
            rapidnj_format,
            "--output-format",
            cls._output_format(inputs),
            "--evolution-model",
            str(inputs.get("evolution_model", "kim") or "kim"),
            "--cores",
            str(inputs.get("threads", 1) or 1),
        ]
        if inputs.get("bootstrap") not in (None, ""):
            cmd.extend(["--bootstrap", str(inputs.get("bootstrap"))])
        cmd.extend(["--alignment-type", str(inputs.get("alignment_type", "p") or "p")])
        if inputs.get("no_negative_length"):
            cmd.append("--no-negative-length")
        cmd.extend([">", cls._output_path(inputs)])
        return " && ".join(
            [
                f"mkdir -p {shlex.quote(out)}",
                _shell_join(["ln", "-s", str(inputs.get("alignments", "")), staged_input]),
                _shell_join(cmd),
            ]
        )

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [out / f"distances{cls._output_suffix(inputs)}"]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("alignments", "")).strip():
            return "alignments is required"
        input_format = cls._input_format(inputs)
        if input_format not in cls.INPUT_FORMAT_OPTIONS:
            return f"input_format must be one of: {', '.join(cls.INPUT_FORMAT_OPTIONS)}"
        output_format = cls._output_format(inputs)
        if output_format not in cls.OUTPUT_FORMAT_OPTIONS:
            return f"output_format must be one of: {', '.join(cls.OUTPUT_FORMAT_OPTIONS)}"
        evolution_model = str(inputs.get("evolution_model", "kim") or "kim")
        if evolution_model not in cls.EVOLUTION_MODEL_OPTIONS:
            return f"evolution_model must be one of: {', '.join(cls.EVOLUTION_MODEL_OPTIONS)}"
        alignment_type = str(inputs.get("alignment_type", "p") or "p")
        if alignment_type not in cls.ALIGNMENT_TYPE_OPTIONS:
            return f"alignment_type must be one of: {', '.join(cls.ALIGNMENT_TYPE_OPTIONS)}"
        if inputs.get("bootstrap") not in (None, ""):
            try:
                bootstrap = int(inputs.get("bootstrap"))
            except (TypeError, ValueError):
                return "bootstrap must be an integer"
            if bootstrap < 0:
                return "bootstrap must be >= 0"
        try:
            threads = int(inputs.get("threads", 1) or 1)
        except (TypeError, ValueError):
            return "threads must be an integer"
        if threads < 1:
            return "threads must be >= 1"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "alignments": ("ALIGNMENT", {"description": "FASTA, Stockholm, or PHYLIP alignment/distance input"}),
            },
            "optional": {
                "input_format": (
                    "STRING",
                    {
                        "default": "fasta",
                        "options": cls.INPUT_FORMAT_OPTIONS,
                        "description": "Input format: FASTA, Stockholm, or PHYLIP distance/alignment",
                    },
                ),
                "output_format": (
                    "STRING",
                    {
                        "default": "t",
                        "options": cls.OUTPUT_FORMAT_OPTIONS,
                        "description": "Output a Newick/NHX tree or distance matrix",
                    },
                ),
                "evolution_model": (
                    "STRING",
                    {"default": "kim", "options": cls.EVOLUTION_MODEL_OPTIONS, "description": "Sequence evolution model"},
                ),
                "bootstrap": ("INT", {"default": "", "min": 0, "description": "Bootstrap samples"}),
                "alignment_type": (
                    "STRING",
                    {"default": "p", "options": cls.ALIGNMENT_TYPE_OPTIONS, "description": "Protein or DNA alignment"},
                ),
                "no_negative_length": (
                    "BOOLEAN",
                    {"default": False, "description": "Adjust negative branch lengths"},
                ),
                "threads": ("INT", {"default": 1, "min": 1, "description": "Number of CPU cores"}),
            },
            "hidden": {"output": ("STRING", {})},
        }

class PhyMLNode(CommandNode):
    """Infer maximum-likelihood phylogenies with PhyML."""

    LEGACY_NODE_ID = "phyml"
    DISPLAY_NAME = "PhyML"
    REQUIRED_CONDA_PACKAGES = ["phyml"]
    CATEGORY = "phylogeny"
    DESCRIPTION = "Infer maximum-likelihood phylogenies from PHYLIP alignments with PhyML."
    SEARCH_ALIASES = [
        BIONODULO_BUILTIN_ALIAS,
        "PhyML",
        "phyml",
        "maximum likelihood",
        "phylogeny",
        "PHYLIP",
        "bootstrap",
        "aLRT",
        "SH-like branch support",
    ]
    RETURN_TYPES = ("PHYLOGENY_TREE", "TXT", "TXT")
    RETURN_NAMES = ("output_tree", "output_stats", "output_stdout")
    REQUIRED_EXECUTABLES = ["phyml"]
    DOCUMENTATION_URL = f"{DOI_URL}{PHYML_CITATION_DOI}"
    CITATION_DOIS = [PHYML_CITATION_DOI]
    CITATION_URLS = [f"{DOI_URL}{PHYML_CITATION_DOI}"]
    CITATION_TEXT = PHYML_CITATION_TEXT
    VERSION = "3.3.20220408+galaxy0"
    SHELL = True

    PHYLIP_FORMAT_OPTIONS = ["", "--sequential"]
    TYPE_OPTIONS = ["nt", "aa"]
    NT_MODEL_OPTIONS = ["HKY85", "JC69", "K80", "F81", "F84", "TN93", "GTR"]
    AA_MODEL_OPTIONS = [
        "LG",
        "WAG",
        "JTT",
        "MtREV",
        "Dayhoff",
        "DCMut",
        "RtREV",
        "CpREV",
        "VT",
        "Blosum62",
        "MtMam",
        "MtArt",
        "HIVw",
        "HIVb",
    ]
    EQUI_FREQ_OPTIONS = ["m", "e"]
    MOVE_OPTIONS = ["NNI", "SPR", "BEST"]
    OPTIMISATION_OPTIONS = ["tlr", "tl", "l", "r", "n"]
    BRANCH_SUPPORT_OPTIONS = ["0", "1", "-1", "-2", "-4", "-5"]

    @staticmethod
    def _staged_name(path: str) -> str:
        return sub(r"[^\s\w\-]", "_", Path(path).name or "input")

    @classmethod
    def _model(cls, inputs: dict[str, Any]) -> str:
        if str(inputs.get("type_of_seq", "nt")) == "aa":
            return str(inputs.get("aa_model", "LG"))
        return str(inputs.get("nt_model", inputs.get("model", "HKY85")))

    @classmethod
    def render_command(cls, inputs: dict[str, Any]) -> str:
        input_file = str(inputs.get("input", ""))
        staged_input = cls._staged_name(input_file)
        commands = [_shell_join(["ln", "-sf", input_file, staged_input])]
        user_tree = str(inputs.get("userInputTree", "") or "")
        staged_tree = ""
        if user_tree:
            staged_tree = cls._staged_name(user_tree)
            commands.append(_shell_join(["ln", "-sf", user_tree, staged_tree]))

        branch_support = str(inputs.get("branchSupport", "-4"))
        bootstrap = str(inputs.get("replicate", 100)) if branch_support == "1" else branch_support
        cmd = [
            "phyml",
            "--input",
            staged_input,
        ]
        phylip_format = str(inputs.get("phylip_format", ""))
        if phylip_format:
            cmd.append(phylip_format)
        type_of_seq = str(inputs.get("type_of_seq", "nt"))
        cmd.extend([
            "--datatype",
            type_of_seq,
            "--multiple",
            str(inputs.get("nb_data_set", 1)),
            "--bootstrap",
            bootstrap,
            "--model",
            cls._model(inputs),
        ])
        if type_of_seq == "nt":
            cmd.extend(["-t", str(inputs.get("tstv", "e"))])
        cmd.extend([
            "-f",
            str(inputs.get("equi_freq", "m")),
            "--pinv",
            str(inputs.get("prop_invar", "e")),
            "--nclasses",
            str(inputs.get("nbSubstCat", 4)),
        ])
        if str(inputs.get("nbSubstCat", 4)) != "1":
            cmd.extend(["--alpha", str(inputs.get("gamma", "e"))])
        cmd.extend([
            "--search",
            str(inputs.get("move", "NNI")),
            "-o",
            str(inputs.get("optimisationTopology", "tlr")),
        ])
        if staged_tree:
            cmd.extend(["--inputtree", staged_tree])
        if str(inputs.get("numStartSeed", 0)) != "0":
            cmd.extend(["--r_seed", str(inputs.get("numStartSeed"))])
        cmd.extend(["--no_memory_check", "|", "tee", f"{_out(inputs)}/output_stdout.txt"])
        commands.append(_shell_join(cmd))
        return " && ".join(commands)

    @classmethod
    def PLAN_OUTPUTS(cls, inputs: dict[str, Any], output_dir: str | Path) -> list[Path]:
        out = Path(output_dir) / cls.NODE_ID
        out.mkdir(parents=True, exist_ok=True)
        return [
            out / "output_tree.nwk",
            out / "output_stats.txt",
            out / "output_stdout.txt",
        ]

    @classmethod
    def VALIDATE_INPUTS(cls, inputs: dict[str, Any]) -> bool | str:
        if not str(inputs.get("input", "")).strip():
            return "input alignment is required"
        phylip_format = str(inputs.get("phylip_format", ""))
        if phylip_format not in cls.PHYLIP_FORMAT_OPTIONS:
            return f"phylip_format must be one of: {', '.join(cls.PHYLIP_FORMAT_OPTIONS)}"
        type_of_seq = str(inputs.get("type_of_seq", "nt"))
        if type_of_seq not in cls.TYPE_OPTIONS:
            return f"type_of_seq must be one of: {', '.join(cls.TYPE_OPTIONS)}"
        if type_of_seq == "nt":
            nt_model = str(inputs.get("nt_model", inputs.get("model", "HKY85")))
            if nt_model not in cls.NT_MODEL_OPTIONS:
                return f"nt_model must be one of: {', '.join(cls.NT_MODEL_OPTIONS)}"
        else:
            aa_model = str(inputs.get("aa_model", "LG"))
            if aa_model not in cls.AA_MODEL_OPTIONS:
                return f"aa_model must be one of: {', '.join(cls.AA_MODEL_OPTIONS)}"
        if int(inputs.get("nb_data_set", 1)) < 1:
            return "nb_data_set must be >= 1"
        if int(inputs.get("nbSubstCat", 4)) < 1:
            return "nbSubstCat must be >= 1"
        branch_support = str(inputs.get("branchSupport", "-4"))
        if branch_support not in cls.BRANCH_SUPPORT_OPTIONS:
            return f"branchSupport must be one of: {', '.join(cls.BRANCH_SUPPORT_OPTIONS)}"
        if branch_support == "1" and int(inputs.get("replicate", 100)) < 1:
            return "replicate must be >= 1 when branchSupport is 1"
        move = str(inputs.get("move", "NNI"))
        if move not in cls.MOVE_OPTIONS:
            return f"move must be one of: {', '.join(cls.MOVE_OPTIONS)}"
        optimisation = str(inputs.get("optimisationTopology", "tlr"))
        if optimisation not in cls.OPTIMISATION_OPTIONS:
            return f"optimisationTopology must be one of: {', '.join(cls.OPTIMISATION_OPTIONS)}"
        equi_freq = str(inputs.get("equi_freq", "m"))
        if equi_freq not in cls.EQUI_FREQ_OPTIONS:
            return f"equi_freq must be one of: {', '.join(cls.EQUI_FREQ_OPTIONS)}"
        return True

    @classmethod
    def INPUT_TYPES(cls) -> dict[str, dict[str, Any]]:
        return {
            "required": {
                "input": (
                    "FILE",
                    {"description": "PHYLIP alignment file for PhyML"},
                ),
            },
            "optional": {
                "phylip_format": (
                    "STRING",
                    {"default": "", "options": cls.PHYLIP_FORMAT_OPTIONS, "description": "Interleaved or sequential PHYLIP"},
                ),
                "nb_data_set": ("INT", {"default": 1, "min": 1, "description": "Number of datasets"}),
                "type_of_seq": (
                    "STRING",
                    {"default": "nt", "options": cls.TYPE_OPTIONS, "description": "Nucleotide or amino-acid alignment"},
                ),
                "tstv": (
                    "STRING",
                    {"default": "e", "description": "Transition/transversion ratio or e to estimate", "advanced": True},
                ),
                "nt_model": (
                    "STRING",
                    {"default": "HKY85", "options": cls.NT_MODEL_OPTIONS, "description": "Nucleotide substitution model"},
                ),
                "aa_model": (
                    "STRING",
                    {"default": "LG", "options": cls.AA_MODEL_OPTIONS, "description": "Amino-acid evolution model"},
                ),
                "prop_invar": (
                    "STRING",
                    {"default": "e", "description": "Invariant-site proportion or e to estimate"},
                ),
                "equi_freq": (
                    "STRING",
                    {"default": "m", "options": cls.EQUI_FREQ_OPTIONS, "description": "Equilibrium frequencies"},
                ),
                "nbSubstCat": (
                    "INT",
                    {"default": 4, "min": 1, "description": "Discrete gamma model category count"},
                ),
                "gamma": (
                    "STRING",
                    {"default": "e", "description": "Gamma model alpha parameter or e to estimate"},
                ),
                "move": (
                    "STRING",
                    {"default": "NNI", "options": cls.MOVE_OPTIONS, "description": "Tree topology search"},
                ),
                "optimisationTopology": (
                    "STRING",
                    {"default": "tlr", "options": cls.OPTIMISATION_OPTIONS, "description": "Optimized parameters"},
                ),
                "branchSupport": (
                    "STRING",
                    {
                        "default": "-4",
                        "options": cls.BRANCH_SUPPORT_OPTIONS,
                        "description": "Bootstrap or approximate branch support test",
                    },
                ),
                "replicate": (
                    "INT",
                    {"default": 100, "min": 1, "description": "Bootstrap replicate count when branchSupport is 1"},
                ),
                "numStartSeed": (
                    "INT",
                    {"default": 0, "description": "Random seed; 0 asks PhyML to choose a seed"},
                ),
                "userInputTree": (
                    "PHYLOGENY_TREE",
                    {"default": "", "description": "Optional Newick/NHX starting tree", "advanced": True},
                ),
            },
            "hidden": {"output": ("STRING", {})},
        }

pin_contract(ClustalWNode)
pin_contract(QuicktreeNode)
pin_contract(RapidNJNode)
pin_contract(PhyMLNode)

__all__ = ["ClustalWNode","QuicktreeNode","RapidNJNode","PhyMLNode"]
